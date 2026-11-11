import json
import logging
import pathlib
import shutil
import zipfile
from collections.abc import Callable, Iterator
from functools import wraps
from typing import Any, Final

import celery
from celery.result import AsyncResult
from django.conf import settings
from django.core.files.storage import FileSystemStorage
from django.core.files.uploadedfile import UploadedFile
from django.http import (
    FileResponse,
    Http404,
    HttpRequest,
    HttpResponse,
    HttpResponseBadRequest,
    HttpResponseNotFound,
    JsonResponse,
    StreamingHttpResponse,
)
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_POST

from examc_app.decorators import exam_permission_required
from examc_app.exceptions.amc import AmcDbManagerError, AmcProjectPathNotFoundError
from examc_app.forms.amc import AnnotateForm
from examc_app.models import Exam, PagesGroup, UnrecognizedReviewScan
from examc_app.services.amc.data_capture.manual import get_amc_data_capture_manual_data
from examc_app.services.amc_jobs import AmcJobsManager
from examc_app.services.import_data.upload import get_upload_scan_pending_context
from examc_app.signing import make_token_for
from examc_app.tasks import (
    amc_annotate_task,
    amc_import_from_review_task,
    import_csv_data,
)
from examc_app.utils.amc.path import resolve_amc_path
from examc_app.utils.amc_db_queries.association import AmcAssociationDbManager
from examc_app.utils.amc_db_queries.capture import AmcCaptureDbManager
from examc_app.utils.amc_functions import (
    add_unrecognized_page_to_project,
    amc_automatic_association,
    amc_automatic_data_capture_subprocess,
    amc_generate_results,
    amc_layout_detection,
    amc_mark_subprocess,
    amc_send_annotated_papers,
    amc_update_documents,
    amc_update_options_xml_by_key,
    check_students_csv_file,
    create_amc_project_dir_from_zip,
    create_annotated_zip,
    get_amc_catalog_pdf_path,
    get_amc_exam_pdf_path,
    get_amc_layout_detection_info,
    get_amc_manual_association_data,
    get_amc_marks_positions_data,
    get_amc_mean,
    get_amc_option_by_key,
    get_amc_project_path,
    get_amc_results_file_path,
    get_amc_send_annotated_papers_data,
    get_amc_update_document_info,
    get_annotated_papers_generated_at,
    get_automatic_association_code,
    get_automatic_data_capture_summary,
    get_project_dir_info,
    get_questions_scoring_details_list,
    get_students_csv_headers,
    update_amc_mark_zone_data,
)
from examc_app.utils.global_functions import user_allowed
from examc_app.utils.review_functions import create_students_from_amc, get_scans_list
from examc_app.utils.review_upload_state import clear_pending_amc_import
from examc_app.utils.view_context_helpers import ViewContext

logger = logging.getLogger(__name__)

# Background jobs, tracked in the user's session per exam
AMC_ANNOTATE_JOBS_SESSION_KEY: Final = "amc_annotate_jobs"
AMC_IMPORT_JOBS_SESSION_KEY: Final = "amc_import_jobs"
AMC_ANNOTATE_STATUS_URL_NAME: Final = "amc_annotate_status"
AMC_IMPORT_STATUS_URL_NAME: Final = "amc_import_from_review_status"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _annotate_jobs(request: HttpRequest) -> AmcJobsManager:
    return AmcJobsManager(
        request=request,
        session_key=AMC_ANNOTATE_JOBS_SESSION_KEY,
        status_url_name=AMC_ANNOTATE_STATUS_URL_NAME,
    )


def _import_jobs(request: HttpRequest) -> AmcJobsManager:
    return AmcJobsManager(
        request=request,
        session_key=AMC_IMPORT_JOBS_SESSION_KEY,
        status_url_name=AMC_IMPORT_STATUS_URL_NAME,
    )


def get_running_annotate_status_url(request: HttpRequest, exam_pk: int) -> str | None:
    """Status URL of the annotation job running for this exam in this session, if any."""
    jobs = _annotate_jobs(request)
    job_id = jobs.get_running_job_id(exam_pk)
    return jobs.status_url(exam_pk, job_id) if job_id else None


def get_amc_lock_reason(request: HttpRequest, exam_pk: int) -> str | None:
    """
    Why the exam's AMC project can't be changed right now, or None if it can: scans being imported
    (from the import page or the data capture tab), or corrected exams being generated.
    """
    if get_upload_scan_pending_context(request, exam_pk)["upload_task_active"]:
        return "Scans are being imported for this exam"
    if _import_jobs(request).get_running_job_id(exam_pk):
        return "Scans are being imported for this exam"
    if get_running_annotate_status_url(request, exam_pk):
        return "Corrected exams are being generated for this exam"
    return None


def refuse_while_amc_locked(view: Callable[..., HttpResponse]) -> Callable[..., HttpResponse]:
    """Answers 409 while a job uses the exam's AMC project (see get_amc_lock_reason): changes would alter it."""
    @wraps(view)
    def wrapper(request: HttpRequest, exam_pk: int, *args: Any, **kwargs: Any) -> HttpResponse:
        reason = get_amc_lock_reason(request, exam_pk)
        if reason:
            return JsonResponse({"error": f"{reason}. Try again once it's done."}, status=409)
        return view(request, exam_pk, *args, **kwargs)
    return wrapper


def _scan_token(file_path: pathlib.Path, project_path: str) -> str | None:
    """
    Signed token serving a scan, or None if it isn't in a folder scans may be served from.
    Project scans (extra pages included) get a token relative to AMC_PROJECTS_ROOT.
    """
    # (folder the scan must be in, folder its token's path is relative to)
    allowed = [
        (pathlib.Path(settings.MARKED_SCANS_ROOT), pathlib.Path(settings.MARKED_SCANS_ROOT)),
        (pathlib.Path(settings.SCANS_ROOT), pathlib.Path(settings.SCANS_ROOT)),
        (pathlib.Path(project_path, "scans"), pathlib.Path(settings.AMC_PROJECTS_ROOT)),
    ]
    root = next(
        (token_root.resolve() for folder, token_root in allowed if file_path.is_relative_to(folder.resolve())),
        None,
    )
    if root is None:
        return None
    return make_token_for(file_path.relative_to(root).as_posix(), str(root))


def _resolve_amc_project_file(amc_project_path: str, relative_path: str) -> pathlib.Path:
    project_root = pathlib.Path(amc_project_path).resolve()
    candidate = (project_root / relative_path).resolve()
    if not candidate.is_relative_to(project_root):
        raise Http404("Invalid AMC project filepath")
    return candidate


def _resolve_students_list_path(exam: Exam, amc_project_path: str) -> pathlib.Path:
    students_list_raw = get_amc_option_by_key(exam, "listeetudiants").replace("%PROJET", amc_project_path)
    students_list_path = pathlib.Path(students_list_raw).resolve()
    if not students_list_path.is_relative_to(pathlib.Path(amc_project_path).resolve()):
        raise Http404("Invalid students list filepath")
    return students_list_path


def _streaming_text_response(iterator: Iterator[str]) -> StreamingHttpResponse:
    response = StreamingHttpResponse(iterator, content_type="text/plain; charset=utf-8")
    response["Cache-Control"] = "no-cache"
    response["X-Accel-Buffering"] = "no"
    return response


def _logged_stream(iterator: Iterator[str], operation: str, exam_pk: int, user: Any = None) -> Iterator[str]:
    user_pk = getattr(user, "pk", None)
    logger.info("AMC stream started operation=%s exam=%s user=%s", operation, exam_pk, user_pk)
    try:
        yield from iterator
    except GeneratorExit:
        logger.warning("AMC stream client disconnected operation=%s exam=%s user=%s", operation, exam_pk, user_pk)
        raise
    except (BrokenPipeError, ConnectionResetError):
        logger.warning(
            "AMC stream connection interrupted operation=%s exam=%s user=%s",
            operation, exam_pk, user_pk, exc_info=True,
        )
        raise
    except Exception:
        logger.exception("AMC stream failed operation=%s exam=%s user=%s", operation, exam_pk, user_pk)
        raise
    else:
        logger.info("AMC stream completed operation=%s exam=%s user=%s", operation, exam_pk, user_pk)


def _job_status_response(job_id: str, running: Callable[[Any], dict], done: Callable[[Any], dict]) -> JsonResponse:
    """
    Status of a background job. Always 200: the request worked, whatever happened to the job
    (`status` is "running", "done" or "error").
    """
    res = AsyncResult(job_id)

    if not res.ready():
        # PENDING, RECEIVED, STARTED, RETRY, or the custom PROGRESS state with its progress info
        meta = res.info if res.state == "PROGRESS" and isinstance(res.info, dict) else {}
        return JsonResponse({"status": "running", "state": res.state, **running(meta)})

    if res.state != celery.states.SUCCESS:
        # FAILURE or REVOKED: res.result is the user-facing exception
        return JsonResponse({
            "status": "error",
            "state": res.state,
            "error": str(res.result) or "The job was cancelled.",
        })

    return JsonResponse({"status": "done", "state": res.state, **done(res.result)})


# ---------------------------------------------------------------------------
# AMC page
# ---------------------------------------------------------------------------

@exam_permission_required(["manage"])
def amc_view(request: HttpRequest, exam_pk: int, task_id: str | None = None) -> HttpResponse:
    exam = get_object_or_404(Exam, pk=exam_pk)
    view_context = ViewContext(nav_url="amc_view")

    if not user_allowed(exam, request.user.id):
        return render(request, "amc/amc.html", view_context.as_dict())

    view_context.set_exam(exam.pk)
    view_context.set_task_id(task_id)
    view_context.set_user_allowed(True)

    try:
        amc_project_path = get_amc_project_path(exam)
    except AmcProjectPathNotFoundError:
        return render(request, "amc/amc.html", view_context.as_dict())  # the page offers to upload one

    with AmcCaptureDbManager(amc_data_path=f"{amc_project_path}/data/") as amc_capture_db_manager:
        project_dir_dict, project_dir_files_list = get_project_dir_info(exam)[:2]

        number_of_copies, missing_pages, nb_unrecognized_pages, overwritten_pages = (
            get_automatic_data_capture_summary(exam)
        )
        nb_incomplete_copies = len(missing_pages)

        data_capture_manual = get_amc_data_capture_manual_data(exam)
        data_pages: list = []
        exam_nb_pages = 1.0
        if data_capture_manual is not None:
            data_pages = data_capture_manual.get("pages") or []
            # No pages yet (e.g. layout not detected): keep the default of 1 page.
            exam_nb_pages = max((float(page["page"]) for page in data_pages), default=exam_nb_pages)
            view_context.update(
                data_questions=data_capture_manual.get("questions") or [],
                data_copies=data_capture_manual.get("copies") or [],
            )

        annotated_papers_generated_at = get_annotated_papers_generated_at(exam)

        view_context.update(
            # Project
            number_of_copies_param=get_amc_option_by_key(exam, "nombre_copies"),
            catalog_pdf_path=get_amc_catalog_pdf_path(exam),
            update_documents_msg=get_amc_update_document_info(exam),
            layout_detection_msg=get_amc_layout_detection_info(exam),
            project_dir_dict=project_dir_dict,
            project_dir_files_list=project_dir_files_list,
            # Data capture
            data_pages=data_pages,
            data_capture_missing=not data_pages,
            copy_count=number_of_copies,
            nb_complete_copies=number_of_copies - nb_incomplete_copies,
            nb_incomplete_copies=nb_incomplete_copies,
            missing_pages=missing_pages,
            nb_unrecognized_pages=nb_unrecognized_pages,
            overwritten_pages=overwritten_pages,
            scans_list_json=get_scans_list(exam),
            exam_nb_pages=range(1, int(exam_nb_pages) + 1),
            # Marking
            students_list=get_amc_option_by_key(exam, "listeetudiants").replace("%PROJET/", ""),
            students_list_headers=get_students_csv_headers(exam),
            auto_assoc_pk=get_amc_option_by_key(exam, "liste_key"),
            auto_assoc_code=get_automatic_association_code(exam),
            mean=get_amc_mean(exam),
            questions_scoring_details=get_questions_scoring_details_list(exam),
            count_missing_assoc=amc_capture_db_manager.get_count_missing_associations(),
            has_grading_schemes=PagesGroup.objects.filter(exam=exam, use_grading_scheme=True).exists(),
            # Reports
            has_results=get_amc_results_file_path(exam),
            annotated_papers_available=annotated_papers_generated_at is not None,
            annotated_papers_generated_at=annotated_papers_generated_at,
            # While a job uses the project, the page is locked (<fieldset data-amc-lock>) with this reason;
            # during the corrected exams generation, the reports tab also follows the job
            amc_lock_reason=get_amc_lock_reason(request, exam.pk),
            annotate_job_status_url=get_running_annotate_status_url(request, exam.pk),
        )

    return render(request, "amc/amc.html", view_context.as_dict())


# ---------------------------------------------------------------------------
# Project
# ---------------------------------------------------------------------------

@exam_permission_required(["manage"])
@require_POST
@refuse_while_amc_locked
def upload_amc_project(request: HttpRequest, exam_pk: int) -> JsonResponse:
    """
    Replaces the exam's AMC project by the uploaded .zip of its directory.

    :return: ``message`` and ``amc_url`` (the AMC page) once imported, or an error status with ``error``.
    """
    exam = get_object_or_404(Exam, pk=exam_pk)

    zip_file = request.FILES.get("amc_project_zip_file")
    if zip_file is None:
        return JsonResponse({"error": "No .zip file was provided."}, status=400)
    if not zipfile.is_zipfile(zip_file):
        return JsonResponse({"error": "This file isn't a valid .zip archive."}, status=400)
    zip_file.seek(0)

    try:
        create_amc_project_dir_from_zip(exam, zip_file)
        create_students_from_amc(exam)
    except Exception:
        # The details stay in the logs: they can contain paths and other server details.
        logger.exception("AMC project import failed for exam %s", exam.pk)
        return JsonResponse(
            {"error": "The AMC project couldn't be imported. Check the .zip file and try again."},
            status=500,
        )

    return JsonResponse({
        "message": "The AMC project was imported.",
        "amc_url": reverse("amc_view", kwargs={"exam_pk": exam.pk}),
    })


@exam_permission_required(["manage"])
@require_POST
@refuse_while_amc_locked
def call_amc_update_documents(request: HttpRequest, exam_pk: int) -> HttpResponse:
    exam = get_object_or_404(Exam, pk=exam_pk)
    return HttpResponse(amc_update_documents(exam, request.POST["nb_copies"], False))


@exam_permission_required(["manage"])
@require_POST
@refuse_while_amc_locked
def call_amc_layout_detection(request: HttpRequest, exam_pk: int) -> HttpResponse:
    exam = get_object_or_404(Exam, pk=exam_pk)
    result = amc_layout_detection(exam)
    if "ERR:" not in result:
        result = get_amc_layout_detection_info(exam)
    return HttpResponse(result)


@exam_permission_required(["manage"])
@require_POST
def edit_amc_file(request: HttpRequest, exam_pk: int) -> HttpResponse:
    """A project file's content; for the students list, its path in the project and its content."""
    exam = get_object_or_404(Exam, pk=exam_pk)
    amc_project_path = get_amc_project_path(exam)

    if request.POST["filepath"] == "students_list":
        filepath = _resolve_students_list_path(exam, amc_project_path)
        content = filepath.read_text(encoding="utf-8")
        return JsonResponse([str(filepath.relative_to(pathlib.Path(amc_project_path).resolve())), content], safe=False)

    filepath = _resolve_amc_project_file(amc_project_path, request.POST["filepath"])
    return HttpResponse(filepath.read_text(encoding="utf-8"))


@exam_permission_required(["manage"])
@require_POST
@refuse_while_amc_locked
def save_amc_edited_file(request: HttpRequest, exam_pk: int) -> HttpResponse:
    """Saves an edited project file; the students list is checked first, and left as is if invalid."""
    exam = get_object_or_404(Exam, pk=exam_pk)
    amc_project_path = get_amc_project_path(exam)
    data = request.POST["data"]
    filepath = _resolve_amc_project_file(amc_project_path, request.POST["filepath"])

    if "is_students_list" not in request.POST:
        filepath.write_text(data, encoding="utf-8")
        return HttpResponse("ok")

    tmp_filepath = pathlib.Path(amc_project_path, "_tmp_students.csv")
    shutil.copyfile(filepath, tmp_filepath)
    tmp_filepath.write_text(data, encoding="utf-8")
    check = check_students_csv_file(str(tmp_filepath))
    if check != "ok":
        tmp_filepath.unlink(missing_ok=True)
        return HttpResponse(f"{check} -- file not updated !")

    tmp_filepath.replace(filepath)  # atomic overwrite
    return HttpResponse(check)


@exam_permission_required(["manage"])
def open_amc_exam_pdf(request: HttpRequest, exam_pk: int) -> FileResponse:
    exam = get_object_or_404(Exam, pk=exam_pk)
    try:
        return FileResponse(open(get_amc_exam_pdf_path(exam), "rb"), content_type="application/pdf")
    except FileNotFoundError:
        raise Http404("Exam PDF not found")


@exam_permission_required(["manage"])
def open_amc_catalog_pdf(request: HttpRequest, exam_pk: int) -> FileResponse:
    exam = get_object_or_404(Exam, pk=exam_pk)
    try:
        return FileResponse(open(get_amc_catalog_pdf_path(exam), "rb"), content_type="application/pdf")
    except FileNotFoundError:
        raise Http404("Catalog PDF not found")


@exam_permission_required(["manage"])
@require_POST
def view_amc_log_file(request: HttpRequest, exam_pk: int) -> HttpResponse:
    exam = get_object_or_404(Exam, pk=exam_pk)
    log_path = pathlib.Path(get_amc_project_path(exam), "amc-compiled.log")
    try:
        return HttpResponse(log_path.read_text(encoding="latin-1"))
    except FileNotFoundError:
        raise Http404("No AMC log yet")


# ---------------------------------------------------------------------------
# Data capture
# ---------------------------------------------------------------------------

@exam_permission_required(["manage"])
@require_POST
def get_amc_marks_positions(request: HttpRequest, exam_pk: int) -> JsonResponse:
    exam = get_object_or_404(Exam, pk=exam_pk)
    data = get_amc_marks_positions_data(exam, request.POST["copy"], request.POST["page"])
    return JsonResponse(data, safe=False)


@exam_permission_required(["manage"])
@require_POST
@refuse_while_amc_locked
def update_amc_mark_zone(request: HttpRequest, exam_pk: int) -> HttpResponse:
    exam = get_object_or_404(Exam, pk=exam_pk)
    update_amc_mark_zone_data(exam, request.POST["zoneid"], request.POST["copy"], request.POST["page"])
    return HttpResponse("")


@exam_permission_required(["manage"])
@require_POST
def get_amc_scan_url(request: HttpRequest, exam_pk: int) -> HttpResponse:
    exam = get_object_or_404(Exam, pk=exam_pk)
    copy_nr = request.POST.get("copy", "")
    page_nr = request.POST.get("page", "")
    if not copy_nr or not page_nr:
        return HttpResponseBadRequest("Missing copy or page")

    try:
        project_path = get_amc_project_path(exam)
    except AmcProjectPathNotFoundError:
        return HttpResponseNotFound("No AMC project")

    if "." in page_nr:  # extra page
        c = copy_nr.zfill(4)
        scan_path = pathlib.Path(project_path, "scans", "extra", c, f"copy_{c}_{page_nr}.jpg").resolve()
    else:
        with AmcCaptureDbManager(amc_data_path=f"{project_path}/data/") as amc_capture_db_manager:
            raw_scan_path = amc_capture_db_manager.select_amc_scan_path(copy_nr, page_nr)
        if not raw_scan_path:
            return HttpResponseNotFound("No scan for this page")
        scan_path = resolve_amc_path(raw_scan_path, project_path)

    token = _scan_token(scan_path, project_path)
    if token is None or not scan_path.is_file():
        logger.warning("Scan not servable: copy=%s page=%s path=%s", copy_nr, page_nr, scan_path)
        return HttpResponseNotFound("Scan file not found")
    return HttpResponse(token)


@exam_permission_required(["manage"])
@require_POST
def get_unrecognized_pages(request: HttpRequest, exam_pk: int) -> JsonResponse:
    """Scans AMC couldn't match to a copy/page, each with a signed URL (None if it can't be served)."""
    exam = get_object_or_404(Exam, pk=exam_pk)
    try:
        project_path = get_amc_project_path(exam)
    except AmcProjectPathNotFoundError:
        return JsonResponse(None, safe=False)

    with AmcCaptureDbManager(amc_data_path=f"{project_path}/data/") as amc_capture_db_manager:
        unrecognized_pages = amc_capture_db_manager.select_unrecognized_pages()

    for page in unrecognized_pages:
        # Resolves %PROJET, and the old %HOME/html/eXamc location, to real folders
        file_path = resolve_amc_path(page["filepath"], project_path)
        page["filepath"] = _scan_token(file_path, project_path)
        if page["filepath"] is None:
            logger.error("Unrecognized page outside the allowed folders: %s", file_path)

    return JsonResponse(unrecognized_pages, safe=False)


@exam_permission_required(["manage"])
@require_POST
@refuse_while_amc_locked
def add_unrecognized_page(request: HttpRequest, exam_pk: int) -> HttpResponse:
    exam = get_object_or_404(Exam, pk=exam_pk)
    add_unrecognized_page_to_project(
        exam,
        request.POST["copy"],
        request.POST["unrec_page"],
        True,  # extra page
        request.POST["unrecognized-img-src"],
    )
    return HttpResponse(True)


@exam_permission_required(["manage"])
@require_POST
@refuse_while_amc_locked
def call_amc_automatic_data_capture(request: HttpRequest, exam_pk: int, from_review: bool = False) -> StreamingHttpResponse:
    exam = get_object_or_404(Exam, pk=exam_pk)
    zip_file = request.FILES["amc_scans_zip_file"]
    return _streaming_text_response(_logged_stream(
        amc_automatic_data_capture_subprocess(request, exam, zip_file, from_review, file_list_path=None),
        "automatic_data_capture_upload",
        exam.pk,
        request.user,
    ))


@exam_permission_required(["manage"])
@require_POST
def import_scans_from_review(request: HttpRequest, exam_pk: int) -> JsonResponse:
    """Starts importing all the review scans, or returns the import already running for this exam."""
    exam = get_object_or_404(Exam, pk=exam_pk)
    logger.info("AMC import all review scans requested exam=%s user=%s", exam.pk, getattr(request.user, "pk", None))

    # A running import is returned below; corrected exams being generated block a new one
    if get_running_annotate_status_url(request, exam.pk):
        return JsonResponse(
            {"error": "Corrected exams are being generated for this exam. Try again once it's done."}, status=409,
        )

    unresolved_count = UnrecognizedReviewScan.objects.filter(exam=exam, resolved=False).count()
    if unresolved_count:
        return JsonResponse({
            "status": "blocked",
            "error": f"Assign or delete all unrecognized scans before AMC import starts ({unresolved_count} remaining).",
            "unresolved_count": unresolved_count,
        }, status=409)

    import_jobs = _import_jobs(request)
    job_id = import_jobs.get_running_job_id(exam.pk)
    existing = job_id is not None
    if job_id is None:
        job_id = amc_import_from_review_task.delay(exam.pk).id
        import_jobs.track(exam.pk, job_id)

    clear_pending_amc_import(request, exam.pk)
    return import_jobs.job_response(exam.pk, job_id, existing)


@exam_permission_required(["manage"])
@require_POST
def import_scans_from_review_pages(request: HttpRequest, exam_pk: int) -> JsonResponse:
    """Starts importing the selected review scans, or returns the import already running for this exam."""
    exam = get_object_or_404(Exam, pk=exam_pk)
    scans_list = request.POST.getlist("pages_list[]")
    logger.info(
        "AMC import selected review scans requested exam=%s user=%s selected_count=%s",
        exam.pk, getattr(request.user, "pk", None), len(scans_list),
    )

    import_jobs = _import_jobs(request)
    # A second click, or another tab, follows the running import instead of starting another one
    running_job_id = import_jobs.get_running_job_id(exam.pk)
    if running_job_id:
        return import_jobs.job_response(exam.pk, running_job_id, existing=True)
    if get_running_annotate_status_url(request, exam.pk):
        return JsonResponse(
            {"error": "Corrected exams are being generated for this exam. Try again once it's done."}, status=409,
        )

    job = amc_import_from_review_task.delay(exam.pk, scans_list)
    import_jobs.track(exam.pk, job.id)
    return import_jobs.job_response(exam.pk, job.id)


@exam_permission_required(["manage"])
@require_GET
def amc_import_from_review_status(request: HttpRequest, exam_pk: int, job_id: str) -> JsonResponse:
    if not _import_jobs(request).is_owned(exam_pk, job_id):
        return JsonResponse({"status": "forbidden", "error": "Unknown or unauthorized job id."}, status=403)

    def output(info: Any) -> dict:
        info = info if isinstance(info, dict) else {}
        return {"output": info.get("output", ""), "line_count": info.get("line_count", 0)}

    return _job_status_response(job_id, running=output, done=output)


# ---------------------------------------------------------------------------
# Marking
# ---------------------------------------------------------------------------

@exam_permission_required(["manage"])
@require_POST
@refuse_while_amc_locked
def call_amc_mark(request: HttpRequest, exam_pk: int) -> StreamingHttpResponse:
    exam = get_object_or_404(Exam, pk=exam_pk)
    update_scoring_strategy = request.POST["update_scoring_strategy"] == "true"
    return _streaming_text_response(_logged_stream(
        amc_mark_subprocess(exam, update_scoring_strategy),
        "mark",
        exam.pk,
        request.user,
    ))


@exam_permission_required(["manage"])
@require_POST
@refuse_while_amc_locked
def call_amc_automatic_association(request: HttpRequest, exam_pk: int) -> JsonResponse:
    exam = get_object_or_404(Exam, pk=exam_pk)
    result = amc_automatic_association(exam, request.POST["assoc_primary_key"])
    if "ERR:" in result:
        return JsonResponse({"ok": False, "error": result})
    return JsonResponse({"ok": True, "redirect": reverse("amc_view", kwargs={"exam_pk": exam.pk})})


@exam_permission_required(["manage"])
@require_POST
def amc_manual_association_data(request: HttpRequest, exam_pk: int) -> JsonResponse:
    exam = get_object_or_404(Exam, pk=exam_pk)
    return JsonResponse(get_amc_manual_association_data(exam), safe=False)


@exam_permission_required(["manage"])
@require_POST
@refuse_while_amc_locked
def amc_set_manual_association(request: HttpRequest, exam_pk: int) -> JsonResponse:
    """Manually associate a student with an answer sheet, or remove the sheet's student.

    POST parameters:
        copy_nr:    the sheet number (AMC's `student` column, shown as "Copy Nr.")
        copy:       the copy number, 0 unless sheets were photocopied (optional, default 0)
        student_id: the student code from the students list, or "0" ("Select...") to remove the student

    The student is first unlinked from any other sheet, as in AMC.
    Returns {"ok": true}, or {"ok": false, "error": "..."} with an error status.
    """
    exam = get_object_or_404(Exam, pk=exam_pk)

    try:
        sheet = int(request.POST["copy_nr"])
        copy = int(request.POST.get("copy", 0))
    except (KeyError, ValueError):
        return JsonResponse({"ok": False, "error": "Invalid sheet number."}, status=400)
    if sheet < 0 or copy < 0:
        return JsonResponse({"ok": False, "error": "Invalid sheet number."}, status=400)

    code = request.POST.get("student_id", "").strip()  # kept as text: codes can have leading zeros

    no_data = JsonResponse(
        {"ok": False, "error": "No association data for this exam yet. Run the automatic association or the marking first."},
        status=404,
    )
    try:
        amc_data_path = pathlib.Path(get_amc_project_path(exam), "data")
    except AmcProjectPathNotFoundError:
        return no_data
    if not (amc_data_path / "association.sqlite").is_file():
        return no_data

    with AmcAssociationDbManager(amc_data_path=str(amc_data_path)) as amc_association_db_manager:
        try:
            if code in ("", "0"):  # "0": the "Select..." choice
                amc_association_db_manager.unlink(sheet, copy)
                logger.info("%s removed the student of sheet %s/%s (exam %s)", request.user, sheet, copy, exam.pk)
            else:
                previous = amc_association_db_manager.associate_manually(code, sheet, copy)
                logger.info(
                    "%s associated student %s with sheet %s/%s (exam %s), previously on %s",
                    request.user, code, sheet, copy, exam.pk, previous or "no sheet",
                )
        except AmcDbManagerError:
            logger.exception("Manual association failed for sheet %s/%s, student %r (exam %s)", sheet, copy, code, exam.pk)
            return JsonResponse({"ok": False, "error": "The association could not be saved."}, status=500)

    return JsonResponse({"ok": True})


@exam_permission_required(["manage"])
@require_POST
@refuse_while_amc_locked
def amc_update_students_file(request: HttpRequest, exam_pk: int) -> HttpResponse:
    exam = get_object_or_404(Exam, pk=exam_pk)

    students_list_csv: UploadedFile | None = request.FILES.get("students-list-csv")
    if students_list_csv is None or not students_list_csv.name:
        return HttpResponseBadRequest("No students file uploaded")

    project_path = pathlib.Path(get_amc_project_path(exam))
    file_name = pathlib.Path(students_list_csv.name).name  # drop any client-supplied path parts
    storage = FileSystemStorage(location=project_path)

    # Saved to a temporary file for checking; save() returns the name actually used
    tmp_path = project_path / storage.save("_tmp_students.csv", students_list_csv)

    check = check_students_csv_file(str(tmp_path))
    if check != "ok":
        tmp_path.unlink(missing_ok=True)
        return HttpResponse(check)

    tmp_path.replace(project_path / file_name)  # atomic overwrite
    amc_update_options_xml_by_key(exam, "listeetudiants", f"%PROJET/{file_name}")
    return HttpResponse("ok")


# ---------------------------------------------------------------------------
# Reports
# ---------------------------------------------------------------------------

@exam_permission_required(["manage"])
@require_POST
@refuse_while_amc_locked
def call_amc_generate_results(request: HttpRequest, exam_pk: int) -> JsonResponse:
    """
    Generates the results with AMC, then imports them in the background.

    :return: ``redirect``, the AMC page following the import, or an error status with ``error``.
    """
    exam = get_object_or_404(Exam, pk=exam_pk)
    result = amc_generate_results(exam)
    if "ERR:" in result:
        logger.error("AMC results generation failed for exam %s: %s", exam.pk, result)
        return JsonResponse({"error": result}, status=500)

    results_csv_path = f"{get_amc_project_path(exam)}/exports/{exam.code}_amc_raw.csv"
    task = import_csv_data.delay(results_csv_path, exam.pk)

    url = reverse("amc_view", kwargs={"exam_pk": exam.pk})
    return JsonResponse({"redirect": f"{url}?task_id={task.id}#results-tab"})

@exam_permission_required(["manage"])
@require_POST
def call_amc_annotate(request: HttpRequest, exam_pk: int) -> JsonResponse:
    """Starts generating the corrected exams, or returns the job already running for this exam."""
    exam = get_object_or_404(Exam, pk=exam_pk)

    form = AnnotateForm(request.POST)
    form.is_valid()  # optional booleans only: always valid
    options = form.cleaned_data
    add_grading_scheme_report = options["add_grading_scheme_report"]
    task_options = {
        "single_file": options["single_file"],
        "add_grading_scheme_report": add_grading_scheme_report,
        # Details of the grading scheme report: only meaningful with it
        "include_grading_scheme_description": add_grading_scheme_report and options["include_grading_scheme_description"],
        "include_student_comments": add_grading_scheme_report and options["include_student_comments"],
    }
    logger.info(
        "AMC annotate requested exam=%s user=%s options=%s",
        exam.pk, getattr(request.user, "pk", None), task_options,
    )

    annotate_jobs = _annotate_jobs(request)
    # A second click, or another tab, follows the running job instead of starting another one
    running_job_id = annotate_jobs.get_running_job_id(exam.pk)
    if running_job_id:
        return annotate_jobs.job_response(exam.pk, running_job_id, existing=True)
    # Nothing else may run on the project meanwhile (e.g. a scans import)
    reason = get_amc_lock_reason(request, exam.pk)
    if reason:
        return JsonResponse({"error": f"{reason}. Try again once it's done."}, status=409)

    job = amc_annotate_task.delay(exam_pk=exam.pk, **task_options)
    annotate_jobs.track(exam.pk, job.id)
    return annotate_jobs.job_response(exam.pk, job.id)


@exam_permission_required(["manage"])
@require_GET
def amc_annotate_status(request: HttpRequest, exam_pk: int, job_id: str) -> JsonResponse:
    if not _annotate_jobs(request).is_owned(exam_pk, job_id):
        return JsonResponse({"status": "forbidden", "error": "Unknown or unauthorized job id."}, status=403)

    def running(meta: dict) -> dict:
        return {"progress": meta.get("progress", ""), "done": meta.get("done"), "total": meta.get("total")}

    def done(result: Any) -> dict:
        result = result if isinstance(result, dict) else {"output": result}
        return {"result": result.get("output", ""), "progress": result.get("progress", "")}

    return _job_status_response(job_id, running=running, done=done)


@exam_permission_required(["manage"])
@require_GET
@refuse_while_amc_locked
def download_annotated_pdf(request: HttpRequest, exam_pk: int) -> FileResponse:
    exam = get_object_or_404(Exam, pk=exam_pk)
    zip_file_path = create_annotated_zip(exam)
    if not zip_file_path:
        raise Http404("The corrected exams' ZIP file couldn't be created")
    return FileResponse(open(zip_file_path, "rb"), as_attachment=True)


@exam_permission_required(["manage"])
@require_POST
def amc_send_annotated_papers_data(request: HttpRequest, exam_pk: int) -> JsonResponse:
    exam = get_object_or_404(Exam, pk=exam_pk)
    return JsonResponse({
        "email_subject": get_amc_option_by_key(exam, "email_subject"),
        "email_text": get_amc_option_by_key(exam, "email_text"),
        "data": get_amc_send_annotated_papers_data(exam),
    })


@exam_permission_required(["manage"])
@require_POST
@refuse_while_amc_locked
def call_amc_send_annotated_papers(request: HttpRequest, exam_pk: int) -> JsonResponse:
    exam = get_object_or_404(Exam, pk=exam_pk)
    result = amc_send_annotated_papers(
        exam,
        json.loads(request.POST["selected-students"]),
        request.POST["email-subject"],
        request.POST["email-body"],
        request.POST["email-column"],
    )
    return JsonResponse(result, safe=False)
