import logging
from typing import Final, TypedDict

from celery.result import AsyncResult
from django.http import HttpRequest
from django.utils import timezone

logger = logging.getLogger(__name__)

AMC_JOB_TTL_SECONDS: Final = 24 * 3600
AMC_JOB_MAX_TRACKED: Final = 200

AMC_JOB_MANAGER_CELERY_STATES = ("PENDING", "RECEIVED", "STARTED", "PROGRESS", "RETRY")

class AmcJob(TypedDict):
    exam_pk: int
    created_at: int

# Jobs stored by job_id.
AmcJobs = dict[str, AmcJob]


class AmcJobsManager:
    """
    Tracks the AMC Celery jobs started from a session, to check that a job belongs to it.
    """

    def __init__(self, request: HttpRequest, session_key: str, status_url_name: str):
        self.request = request
        self.session_key = session_key
        self.status_url_name = status_url_name

    @staticmethod
    def prune(raw_jobs: object) -> AmcJobs:
        """
        Keep only the valid and recent jobs, the newest ones if there are too many.
        :param raw_jobs: Jobs read from the session, not trusted.
        :return: Valid jobs, with job_id as their key.
        """
        if not isinstance(raw_jobs, dict):
            return {}

        min_ts = int(timezone.now().timestamp()) - AMC_JOB_TTL_SECONDS
        pruned: AmcJobs = {}

        for job_id, meta in raw_jobs.items():
            if not isinstance(meta, dict):
                continue
            try:
                created_at = int(meta.get("created_at", 0))
                exam_pk = int(meta.get("exam_pk", 0))
            except (TypeError, ValueError):
                continue
            if created_at < min_ts or exam_pk <= 0:
                continue

            pruned[str(job_id)] = AmcJob(exam_pk=exam_pk, created_at=created_at)

        if len(pruned) > AMC_JOB_MAX_TRACKED:
            newest = sorted(pruned.items(), key=lambda item: item[1]["created_at"], reverse=True)
            pruned = dict(newest[:AMC_JOB_MAX_TRACKED])

        return pruned

    def get_jobs(self) -> AmcJobs:
        """
        Get the valid jobs of the session, and save them back if pruning removed some.
        :return: Valid jobs, with job_id as their key.
        """
        raw = self.request.session.get(self.session_key, {})
        jobs = self.prune(raw)
        if jobs != raw:
            self.request.session[self.session_key] = jobs
        return jobs

    def track(self, exam_pk: int, job_id: str) -> None:
        """Remember a job started by this session."""
        jobs = self.get_jobs()
        jobs[job_id] = AmcJob(exam_pk=exam_pk, created_at=int(timezone.now().timestamp()))
        self.request.session[self.session_key] = self.prune(jobs)  # enforces the max count

    def is_owned(self, exam_pk: int, job_id: str) -> bool:
        """True if this session started the job, for this exam."""
        meta = self.get_jobs().get(job_id)
        return meta is not None and meta["exam_pk"] == exam_pk

    def get_running_job_id(self, exam_pk: int) -> str | None:
        """Id of a job of this exam still running in Celery, if any."""
        for job_id, meta in self.get_jobs().items():
            logger.info(f"Exam {exam_pk} job {job_id} state: {AsyncResult(job_id).state}")
            if meta["exam_pk"] == exam_pk and AsyncResult(job_id).state in AMC_JOB_MANAGER_CELERY_STATES:
                return job_id
        return None
