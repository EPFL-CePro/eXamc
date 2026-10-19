"""Final generation of the exam files: start and cancel."""

from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.views.decorators.http import require_POST

from examc_app.decorators import exam_permission_required
from examc_app.models import Exam, ExamAMCJob
from examc_app.services.preparation.exam_checks import check_exam_content
from examc_app.services.student.prep_amc_csv import students_csv_problems
from examc_app.tasks import generate_final_exam_files_task
from examc_app.utils.preparation_functions import get_active_final_build_job


@exam_permission_required(["manage"])
@require_POST
def generate_final_exam_files_start(request, exam_pk):
    exam = get_object_or_404(Exam, pk=exam_pk)

    # Two generations at once would write in the same AMC project: the page follows the running one instead
    active_job = get_active_final_build_job(exam)
    if active_job:
        return JsonResponse({
            "error": f"A final generation of this exam is already running (started by {active_job.requested_by} "
                     f"at {timezone.localtime(active_job.created_at):%H:%M}).",
            "job_id": active_job.pk,
            "task_id": active_job.celery_task_id,
        }, status=409)

    # The errors prevent the generation; the warnings are listed for the user, who starts again with
    # confirm_warnings=1 (the students list is written to the AMC project by build_final_exam)
    checks = check_exam_content(exam)
    errors = checks.errors + students_csv_problems(exam)
    if errors:
        return JsonResponse({"error": " ".join(errors), "errors": errors, "warnings": checks.warnings}, status=400)
    if checks.warnings and request.POST.get("confirm_warnings") != "1":
        return JsonResponse({"warnings": checks.warnings})

    old_jobs = ExamAMCJob.objects.filter(
        exam=exam,
        requested_by=request.user,
    )
    old_jobs.delete()

    job = ExamAMCJob.objects.create(
        exam=exam,
        requested_by=request.user,
        job_type="final_build",
        status="pending",
        pdf_path="",
        error_message="",
    )

    async_result = generate_final_exam_files_task.apply_async(
        args=[job.pk],
        queue="celery",
        routing_key="celery",
    )

    job.celery_task_id = async_result.id
    job.save(update_fields=["celery_task_id", "updated_at"])

    return JsonResponse({
        "job_id": job.pk,
        "task_id": async_result.id,
        "status": job.status,
        "reused": False,
    })


@exam_permission_required(["manage"])
@require_POST
def cancel_final_exam_files(request, exam_pk):
    """Asks the running final generation to stop: the task stops at its next check, within a few seconds (see
    BuildCancelled). The exam is editable again once it has stopped."""
    exam = get_object_or_404(Exam, pk=exam_pk)
    job = get_active_final_build_job(exam)
    if job is None:
        return JsonResponse({"error": "No final generation is running for this exam."}, status=404)

    job.cancel_requested = True
    job.save(update_fields=["cancel_requested", "updated_at"])

    if job.status == "pending":
        # Not started yet (waiting for a worker): it must never start
        if job.celery_task_id:
            from examc.celery import app as celery_app
            celery_app.control.revoke(job.celery_task_id)
        job.status = "cancelled"
        job.error_message = "The generation was cancelled."
        job.save(update_fields=["status", "error_message", "updated_at"])

    return JsonResponse({"cancelling": True, "job_id": job.pk, "status": job.status})
