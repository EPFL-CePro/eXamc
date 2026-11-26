"""Tasks of the preparation phase: preview compilation, scoring updates and the final exam build in AMC."""

import pathlib
import uuid

from celery import shared_task
from celery_progress.backend import ProgressRecorder, logger
from django.utils import timezone

from examc_app.models import Exam, ExamAMCJob
from examc_app.utils.amc.amc_build_functions import (
    AmcStepError,
    BuildCancelled,
    build_final_exam,
    mark_exam_build_error,
    register_exam_in_amc,
    update_scoring_in_amc,
)
from examc_app.utils.amc.amc_layout_functions import (
    LayoutExtractionError,
    get_pdf_page_metrics,
    get_subject_copy_and_page_counts_from_xy,
)
from examc_app.utils.preparation_functions import compile_exam_preview
from examc_app.utils.preparation_latex_functions import update_exam_scoring_latex


@shared_task(bind=True, name="examc_app.tasks.compile_exam_preview_task")
def compile_exam_preview_task(self, job_id):
    job = ExamAMCJob.objects.get(pk=job_id)
    # Read by the error handling below, whatever fails first
    result = None

    try:
        job.status = "running"
        job.error_message = ""
        job.pdf_path = ""
        job.save(update_fields=["status", "error_message", "pdf_path", "updated_at"])

        result = compile_exam_preview(job.exam, job_id=job.pk)

        if result["ok"]:
            job.status = "success"
            job.pdf_path = str(result["pdf_path"])
        else:
            job.status = "error"
            job.error_message = result["error"]

    except Exception:
        error_ref = f"AMC-{uuid.uuid4().hex[:8].upper()}"

        logger.error(
            "Exam generation returned error | error_ref=%s | job_id=%s | exam_id=%s | result=%s",
            error_ref,
            job_id,
            getattr(job, "exam_id", None),
            result,
        )

        job.status = "error"
        job.error_message = f"An error occurred while generating the exam. Reference: {error_ref}"
        job.result_json = {
            "ok": False,
            "error": "An error occurred while generating the exam.",
            "error_ref": error_ref,
            "debug": result,
        }

    job.save(update_fields=["status", "pdf_path", "error_message", "updated_at"])
    logger.info("Exam preview finished | job_id=%s | status=%s", job_id, job.status)


@shared_task(bind=True, name="examc_app.tasks.update_amc_scoring_task")
def update_amc_scoring_task(self, job_id):
    """
    Updates the scoring strategy of AMC for an exam whose final files were generated, after its scoring formulas
    changed: rewrites the scoring part of the LaTeX files of the project, then AMC extracts the strategy again.
    The state is read by the page with the job (see views.preparation.scoring.scoring_update_status).
    """
    job = ExamAMCJob.objects.select_related("exam").get(pk=job_id)

    try:
        job.status = "running"
        job.error_message = ""
        job.result_json = {}
        job.save(update_fields=["status", "error_message", "result_json", "updated_at"])

        update_exam_scoring_latex(job.exam)
        warnings = update_scoring_in_amc(job.exam)

        job.status = "success"
        job.result_json = {"warnings": warnings}
    except AmcStepError as exc:
        job.status = "error"
        job.error_message = str(exc)
    except Exception:
        error_ref = f"AMC-{uuid.uuid4().hex[:8].upper()}"
        logger.exception("Scoring update failed | error_ref=%s | job_id=%s | exam_id=%s", error_ref, job_id, job.exam_id)
        job.status = "error"
        job.error_message = f"An error occurred while updating the scoring in AMC. Reference: {error_ref}"

    job.save(update_fields=["status", "error_message", "result_json", "updated_at"])
    logger.info("Scoring update finished | job_id=%s | status=%s", job_id, job.status)


@shared_task(bind=True, name="examc_app.tasks.generate_final_exam_files_task")
def generate_final_exam_files_task(self, job_id):
    progress_recorder = ProgressRecorder(self)

    job = ExamAMCJob.objects.select_related("exam", "requested_by").get(pk=job_id)
    exam = job.exam

    def set_progress(current, description):
        progress_recorder.set_progress(current, 100, description=description)

    def make_amc_progress_callback(progress_recorder):
        def _callback(*, percent, message):
            progress_recorder.set_progress(percent, 100, description=message)
        return _callback

    build = None

    try:
        job.status = "running"
        job.error_message = ""
        job.result_json = {}
        job.pdf_path = ""
        job.exam_build_id = None
        job.save(update_fields=[
            "status",
            "error_message",
            "result_json",
            "pdf_path",
            "exam_build_id",
            "updated_at",
        ])

        set_progress(0, "Waiting for worker...")
        set_progress(5, "Preparing final exam build...")

        progress_callback = make_amc_progress_callback(progress_recorder)

        def cancel_requested():
            return ExamAMCJob.objects.filter(pk=job.pk, cancel_requested=True).exists()

        def raise_if_cancelled():
            # build_final_exam checks it itself while it runs; this is for the steps after it
            if cancel_requested():
                raise BuildCancelled("The generation was cancelled.")

        build = build_final_exam(
            exam,
            user=job.requested_by,
            timeout=60,
            progress_callback=progress_callback,
            should_cancel=cancel_requested,
        )

        if build.status != "ready":
            job.status = "error"
            job.error_message = build.error_message or "Final exam build failed."
            job.exam_build_id = build.pk if build else None
            job.save(update_fields=[
                "status",
                "error_message",
                "exam_build_id",
                "updated_at",
            ])
            raise Exception(job.error_message)

        raise_if_cancelled()
        set_progress(86, "Resolving generated artifacts...")

        project_path = pathlib.Path(build.project_path) if build.project_path else None
        exam_prefix = exam.code or f"exam-{exam.pk}"

        subject_pdf_path = ""
        catalog_pdf_path = ""
        subject_xy_path = build.xy_path or ""

        if project_path and project_path.exists():
            subject_pdf = project_path / f"{exam_prefix}-sujet.pdf"
            catalog_pdf = project_path / f"{exam_prefix}-catalog.pdf"
            subject_xy = project_path / f"{exam_prefix}-calage.xy"

            if subject_pdf.exists():
                subject_pdf_path = str(subject_pdf)
            elif build.compiled_pdf_path:
                subject_pdf_path = build.compiled_pdf_path

            if catalog_pdf.exists():
                catalog_pdf_path = str(catalog_pdf)

            if subject_xy.exists():
                subject_xy_path = str(subject_xy)

        if not subject_xy_path:
            raise LayoutExtractionError("Subject XY path is missing; cannot extract subject layout.")

        set_progress(88, "Reading subject XY structure...")
        counts = get_subject_copy_and_page_counts_from_xy(subject_xy_path)

        # The copies padded after a second compilation (see build_final_exam)
        warnings = list(getattr(build, "build_warnings", []))

        # Only a booklet needs a multiple of 4: the final build pads the copies with blank pages up to it
        if exam.print_format == Exam.PRINT_FORMAT_BOOKLET and counts["pages_per_copy"] % 4 != 0:
            warnings.append(
                f"This exam has {counts['pages_per_copy']} pages per copy. "
                f"For booklet printing, the total number of pages per copy should be a multiple of 4."
            )

        set_progress(90, "Reading subject PDF metrics...")
        pdf_metrics = get_pdf_page_metrics(subject_pdf_path, dpi=300.0)

        if pdf_metrics["page_count"] != counts["total_pages"]:
            raise LayoutExtractionError(
                f"PDF/XY page mismatch: PDF={pdf_metrics['page_count']} XY={counts['total_pages']}"
            )

        raise_if_cancelled()
        # AMC reads the layout of the subject and its scoring strategy itself: its databases (data/layout.sqlite and
        # data/scoring.sqlite of the project) are the reference of the scans and the marks
        warnings += register_exam_in_amc(
            exam,
            subject_xy_path,
            expected_pages=counts["total_pages"],
            should_cancel=cancel_requested,
            progress_callback=progress_callback,
        )

        # Last chance to stop: the exam is finalized below
        raise_if_cancelled()

        result = {
            "ok": True,
            "job_id": job.pk,
            "build_id": build.pk,
            "pdf_path": subject_pdf_path or build.compiled_pdf_path or "",
            "subject_pdf_path": subject_pdf_path or "",
            "catalog_pdf_path": catalog_pdf_path or "",
            "amc_log_path": build.amc_log_path or "",
            "xy_path": subject_xy_path,
            "exam_calage_xy_path": subject_xy_path,
            "warnings": warnings,
            "summary": {
                "copies": counts["total_copies"],
                "pages_per_copy": counts["pages_per_copy"],
                "pages": counts["total_pages"],
            },
        }

        exam.is_finalized = True
        exam.finalized_at = timezone.now()
        exam.finalized_build = build
        exam.save(update_fields=["is_finalized", "finalized_at", "finalized_build"])

        job.status = "success"
        job.exam_build_id = build.pk
        job.pdf_path = subject_pdf_path or build.compiled_pdf_path or ""
        job.result_json = result
        job.error_message = ""
        job.save(update_fields=[
            "status",
            "exam_build_id",
            "pdf_path",
            "result_json",
            "error_message",
            "updated_at",
        ])

        set_progress(100, "Final build complete.")
        return result

    except BuildCancelled as exc:
        job.status = "cancelled"
        job.error_message = str(exc)
        job.save(update_fields=["status", "error_message", "updated_at"])
        # Cancelled after the build (build_final_exam marks its own build): the build is dropped
        if build is not None:
            mark_exam_build_error(build, str(exc))
        raise
    except (AmcStepError, LayoutExtractionError) as exc:
        # After the build (build_final_exam marks its own failures): the build is not usable, the user sees why
        job.status = "error"
        job.error_message = str(exc)
        job.save(update_fields=["status", "error_message", "updated_at"])
        if build is not None:
            mark_exam_build_error(build, str(exc))
        raise
    except Exception as exc:
        job.status = "error"
        job.error_message = str(exc)
        job.save(update_fields=["status", "error_message", "updated_at"])
        raise
