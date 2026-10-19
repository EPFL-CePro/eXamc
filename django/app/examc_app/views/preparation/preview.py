"""PDF preview of the exam: start, status and file."""

from pathlib import Path

from django.http import FileResponse, Http404, JsonResponse
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.views.decorators.http import require_POST

from examc_app.decorators import exam_permission_required
from examc_app.models import Exam, ExamAMCJob
from examc_app.tasks import compile_exam_preview_task
from examc_app.utils.preparation_functions import delete_exam_preview_job_files


@exam_permission_required(["manage"])
def exam_preview_pdf_file(request, exam_pk, job_pk):
    job = get_object_or_404(
        ExamAMCJob,
        pk=job_pk,
        exam_id=exam_pk,
        requested_by=request.user,
    )

    if job.status != "success" or not job.pdf_path:
        raise Http404("Preview PDF not ready")

    pdf_path = Path(job.pdf_path)
    if not pdf_path.exists():
        raise Http404("Preview PDF file missing")

    return FileResponse(open(pdf_path, "rb"), content_type="application/pdf")


@exam_permission_required(["manage"])
@require_POST
def exam_preview_start(request, exam_pk):
    exam = get_object_or_404(Exam, pk=exam_pk)

    active_jobs = ExamAMCJob.objects.filter(
        exam=exam,
        requested_by=request.user,
        job_type="exam_preview",
        status__in=["pending", "running"],
    )

    for active_job in active_jobs:
        active_job.status = "error"
        active_job.error_message = "Replaced by a new preview request."
        active_job.save(update_fields=["status", "error_message", "updated_at"])

    old_jobs = ExamAMCJob.objects.filter(
        exam=exam,
        job_type="exam_preview",
        requested_by=request.user,
    )

    for old_job in old_jobs:
        delete_exam_preview_job_files(old_job)

    old_jobs.delete()

    job = ExamAMCJob.objects.create(
        exam=exam,
        requested_by=request.user,
        job_type="exam_preview",
        status="pending",
        pdf_path="",
        error_message="",
    )

    async_result = compile_exam_preview_task.apply_async(
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
def exam_preview_status(request, exam_pk, job_pk):
    exam = get_object_or_404(Exam, pk=exam_pk)
    job = get_object_or_404(
        ExamAMCJob,
        pk=job_pk,
        exam=exam,
        requested_by=request.user,
    )

    data = {
        "status": job.status,
    }

    if job.status == "success":
        data["pdf_url"] = reverse(
            "exam_preview_pdf_file",
            kwargs={"exam_pk": exam.pk, "job_pk": job.pk},
        )
    elif job.status == "error":
        data["error"] = job.error_message

    return JsonResponse(data)
