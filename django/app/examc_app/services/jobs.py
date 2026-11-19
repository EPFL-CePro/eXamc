import logging
import time
from typing import Protocol

from celery import Task
from celery.exceptions import Ignore
from celery.result import AsyncResult

logger = logging.getLogger(__name__)


# The state of a job reporting its progress, and how long it may stay silent before it's considered dead
JOB_PROGRESS_STATE = "PROGRESS"
JOB_STALE_AFTER_SECONDS = 5 * 60


class ProgressCallback(Protocol):
    """Reports the progress of a long AMC operation."""

    def __call__(self, done: int | None = None, total: int | None = None, message: str = "") -> None: ...


def update_job_progress(
        task: Task,
        *,
        error: str | None = None,
        error_type: str = "RuntimeError",
        **meta
) -> None:
    """
    Reports a running job's progress, or, with `error`, ends it as failed.

    Progress gets a timestamp, which lets fail_if_stale tell a dead job (its worker was restarted)
    from a slow one. With `error`, the job is marked as failed with that message for the user
    (the status views show it) and the type `error_type`, and Ignore is raised, so Celery keeps
    that state: call it as the task's last statement, typically in its `except` block.
    """
    if error is not None:
        task.update_state(state="FAILURE", meta={**meta, "exc_type": error_type, "exc_message": error})
        raise Ignore()
    task.update_state(state=JOB_PROGRESS_STATE, meta={**meta, "updated_at": time.time()})


def fail_if_stale(job_id: str) -> bool:
    """
    Marks a job that stopped reporting progress as failed, so it no longer counts as running.

    :return: True if it was stale.
    """
    result = AsyncResult(job_id)
    if result.state != JOB_PROGRESS_STATE or not isinstance(result.info, dict):
        return False
    updated_at = result.info.get("updated_at")
    if updated_at is None or time.time() - updated_at < JOB_STALE_AFTER_SECONDS:
        return False
    result.backend.store_result(job_id, RuntimeError("The job was interrupted. Please start it again."), "FAILURE")
    return True