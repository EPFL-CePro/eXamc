import datetime
import json
import logging
import os
import pathlib
import shutil
from typing import Any, Final

import celery
from celery.result import AsyncResult
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
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_POST

from examc import settings
from examc_app.decorators import exam_permission_required
from examc_app.exceptions.amc import (
    AmcDbManagerError,
    AmcProjectPathNotFoundError,
)
from examc_app.models import Exam, PageMarkers, PagesGroup, UnrecognizedReviewScan
from examc_app.services.amc.data_capture.manual import get_amc_data_capture_manual_data
from examc_app.services.amc_jobs import AmcJobsManager
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
    amc_annotate,
    amc_automatic_association,
    amc_automatic_datacapture_subprocess,
    amc_generate_results,
    amc_layout_detection,
    amc_mark_subprocess,
    amc_send_annotated_papers,
    amc_update_documents,
    amc_update_options_xml_by_key,
    check_annotated_papers_available,
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
    get_automatic_association_code,
    get_automatic_data_capture_summary,
    get_copy_page_zooms,
    get_project_dir_info,
    get_questions_scoring_details_list,
    get_students_csv_headers,
    update_amc_mark_zone_data,
)
from examc_app.utils.global_functions import user_allowed
from examc_app.utils.marker_rendering import (
    get_exam_marked_scans_dir,
    iter_render_grading_only_marked_scans,
    render_key,
    render_marked_scan,
)
from examc_app.utils.review_functions import (
    create_students_from_amc,
    get_scans_list,
    iter_review_copy_dirs,
    iter_review_scan_files,
)
from examc_app.utils.review_upload_state import clear_pending_amc_import

AMC_ANNOTATE_JOBS_SESSION_KEY: Final = "amc_annotate_jobs"
AMC_IMPORT_JOBS_SESSION_KEY: Final = "amc_import_jobs"

logger = logging.getLogger(__name__)


def streaming_text_response(iterator):
    response = StreamingHttpResponse(iterator, content_type="text/plain; charset=utf-8")
    response["Cache-Control"] = "no-cache"
    response["X-Accel-Buffering"] = "no"
    return response


def logged_stream(iterator, operation, exam_pk: int, user=None):
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
            operation,
            exam_pk,
            user_pk,
            exc_info=True,
        )
        raise
    except Exception:
        logger.exception("AMC stream failed operation=%s exam=%s user=%s", operation, exam_pk, user_pk)
        raise
    else:
        logger.info("AMC stream completed operation=%s exam=%s user=%s", operation, exam_pk, user_pk)


def _job_response(status_url_name: str, exam_pk: int, job_id: str, existing: bool = False) -> JsonResponse:
    """202 response pointing the frontend to the job's status URL."""
    return JsonResponse({
        "job_id": job_id,
        "status_url": reverse(status_url_name, args=[exam_pk, job_id]),
        "existing": existing,
    }, status=202)


@exam_permission_required(['manage'])
def upload_amc_project(request: HttpRequest, exam_pk: int):
    exam = Exam.objects.get(pk=exam_pk)

    exam_selected = exam.get_overall_exam_or_default()

    if request.method == 'POST':
        if 'amc_project_zip_file' not in request.FILES:
            message = "No zip file provided."
            return render(
                request,
                'amc/upload_amc_project.html',
                {
                    'exam': exam,
                    'message': message,
                    "nav_url": "upload_amc_project"
                }
            )

        zip_file = request.FILES['amc_project_zip_file']

        message = create_amc_project_dir_from_zip(exam, zip_file)

        create_students_from_amc(exam)

        return render(
            request,
            'amc/upload_amc_project.html',
            {
                'exam': exam,
                'exam_selected': exam_selected,
                'nav_url': "upload_amc_project",
                'message': message
            }
        )

    return render(
        request,
        'amc/upload_amc_project.html',
        {
            'exam': exam,
            'exam_selected': exam_selected,
            'nav_url': "upload_amc_project"
        }
    )


@exam_permission_required(['manage'])
def amc_view(request: HttpRequest, exam_pk: int, curr_tab: str | None = None, task_id: str | None = None):
    exam = Exam.objects.get(pk=exam_pk)

    amc_project_path = get_amc_project_path(exam, False)

    context = {}

    if user_allowed(exam, request.user.id):
        if amc_project_path:
            # capture db mgt
            with AmcCaptureDbManager(amc_data_path=f"{amc_project_path}/data/") as amc_capture_db_manager:
                # get amc options and infos
                amc_option_nb_copies = get_amc_option_by_key(exam, 'nombre_copies')
                amc_update_documents_msg = get_amc_update_document_info(exam)
                amc_layout_detection_msg = get_amc_layout_detection_info(exam)
                #amc_exam_pdf_path = get_amc_exam_pdf_path(exam)
                amc_catalog_pdf_path = get_amc_catalog_pdf_path(exam)

                # get project dir list
                project_dir_info = get_project_dir_info(exam)
                project_dir_dict = project_dir_info[0]
                project_dir_files_list = project_dir_info[1]

                # get data
                data_capture_manual = get_amc_data_capture_manual_data(exam)
                amc_data_capture_summary = get_automatic_data_capture_summary(exam)
                number_of_copies = amc_data_capture_summary[0]
                number_of_incomplete_copies = len(amc_data_capture_summary[1])
                missing_pages = amc_data_capture_summary[1]
                if number_of_incomplete_copies > 0:
                    data_capture_message = "Data capture from " + str(
                        number_of_copies - number_of_incomplete_copies) + " complete and " + str(
                        number_of_incomplete_copies) + " incomplete papers"
                else:
                    data_capture_message = "Data capture from " + str(number_of_copies) + " complete papers"
                nb_unrecognized_pages = amc_data_capture_summary[2]

                overwritten_pages = amc_data_capture_summary[3]

                students_list = get_amc_option_by_key(exam, "listeetudiants").replace("%PROJET/", '')

                has_results = get_amc_results_file_path(exam)

                scans_list = get_scans_list(exam)
                scans_list_json_string = json.dumps(scans_list)

                has_grading_schemes = PagesGroup.objects.filter(exam=exam, use_grading_scheme=True).exists()

                exam_nb_pages = 1
                if data_capture_manual is not None:
                    exam_nb_pages = 0
                    if data_capture_manual["pages"]:
                        exam_nb_pages = max(data_capture_manual["pages"], key=lambda x: float(x['page']))['page']
                    context['data_pages'] = data_capture_manual["pages"]
                    context['data_questions'] = data_capture_manual["questions"]
                    context['data_copies'] = data_capture_manual["copies"]

                context['number_of_copies_param'] = amc_option_nb_copies
                context['copy_count'] = number_of_copies
                context['catalog_pdf_path'] = amc_catalog_pdf_path
                context['update_documents_msg'] = amc_update_documents_msg
                context['layout_detection_msg'] = amc_layout_detection_msg
                context['project_dir_dict'] = project_dir_dict
                context['project_dir_files_list'] = project_dir_files_list
                context['data_capture_message'] = data_capture_message
                context['missing_pages'] = missing_pages
                context['nb_unrecognized_pages'] = nb_unrecognized_pages
                context['overwritten_pages'] = overwritten_pages
                context['students_list'] = students_list
                context['students_list_headers'] = get_students_csv_headers(exam)
                context['auto_assoc_pk'] = get_amc_option_by_key(exam, 'liste_key')
                context['auto_assoc_code'] = get_automatic_association_code(exam)
                context['mean'] = get_amc_mean(exam)
                context['questions_scoring_details'] = get_questions_scoring_details_list(exam)
                context['count_missing_assoc'] = amc_capture_db_manager.get_count_missing_associations()
                context['annotated_papers_available'] = check_annotated_papers_available(exam)
                context['has_results'] = has_results
                context['has_grading_schemes'] = has_grading_schemes
                context['task_id'] = task_id
                context['curr_tab'] = curr_tab
                context['scans_list_json'] = json.loads(scans_list_json_string)
                context['exam_nb_pages'] = range(1, int(float(exam_nb_pages)) + 1, 1)

        context['exam_selected'] = exam

        exam = exam.get_overall_exam_or_default()

        context['exam'] = exam
        context['user_allowed'] = True
        context['nav_url'] = 'amc_view'

    else:
        context['user_allowed'] = False

    return render(request, 'amc/amc.html', context)


@exam_permission_required(['manage'])
def amc_data_capture_manual(request: HttpRequest, exam_pk: int):
    exam = Exam.objects.get(pk=exam_pk)

    context: dict[str, Any] = {'nav_url': 'amc_data_capture_manual'}

    if user_allowed(exam, request.user.id):
        context['exam_selected'] = exam

        exam = exam.get_overall_exam_or_default()

        context['exam'] = exam
        context['user_allowed'] = True
    else:
        context['user_allowed'] = False

    return render(
        request,
        'amc/amc_data_capture_manual.html',
        context
    )


@exam_permission_required(['manage'])
@require_POST
def get_amc_marks_positions(request: HttpRequest, exam_pk: int):
    exam = Exam.objects.get(pk=exam_pk)
    copy = request.POST['copy']
    page = request.POST['page']

    data_positions = get_amc_marks_positions_data(exam, copy, page)

    return HttpResponse(json.dumps(data_positions))


@require_POST
@exam_permission_required(['manage'])
def get_unrecognized_pages(request: HttpRequest, exam_pk: int):
    exam = Exam.objects.get(pk=exam_pk)
    amc_project_path = get_amc_project_path(exam, False)
    unrecognized_pages = None
    if amc_project_path:
        amc_data_path = f"{amc_project_path}/data/"

        with AmcCaptureDbManager(amc_data_path=amc_data_path) as amc_capture_db_manager:
            unrecognized_pages = amc_capture_db_manager.select_unrecognized_pages()

            for unrecognized_page in unrecognized_pages:
                file_path = unrecognized_page['filepath']
                if '%HOME' in file_path:
                    print("******************* " + str(pathlib.Path.home()) + " **************************")

                    app_home_path = str(settings.BASE_DIR).replace(str(pathlib.Path.home()), '%HOME')
                    file_path = file_path.replace(app_home_path + '/', '')
                    print("******************* " + file_path + " **************************")

                    # change old file path (www/html/...) to new (srv/examc/private_media/...) from amc db
                    file_path = file_path.replace('%HOME/html/eXamc', str(settings.PRIVATE_MEDIA_ROOT))

                file_root = str(settings.SCANS_ROOT)
                if file_path.startswith(str(settings.MARKED_SCANS_ROOT)):
                    file_root = str(settings.MARKED_SCANS_ROOT)
                file_path = make_token_for(os.path.relpath(file_path, file_root), file_root)

                unrecognized_page['filepath'] = file_path

    return HttpResponse(json.dumps(unrecognized_pages))


@exam_permission_required(['manage'])
@require_POST
def update_amc_mark_zone(request: HttpRequest, exam_pk: int):
    exam = Exam.objects.get(pk=exam_pk)
    zoneid = request.POST['zoneid']
    copy = request.POST['copy']
    page = request.POST['page']

    update_amc_mark_zone_data(exam, zoneid, copy, page)

    return HttpResponse('')


def _resolve_amc_project_file(amc_project_path: str, relative_path: str) -> pathlib.Path:
    project_root = pathlib.Path(amc_project_path).resolve()
    candidate = (project_root / relative_path).resolve()
    try:
        candidate.relative_to(project_root)
    except ValueError as exc:
        raise Http404("Invalid AMC project filepath") from exc
    return candidate


def _resolve_students_list_path(exam, amc_project_path: str) -> pathlib.Path:
    students_list_raw = get_amc_option_by_key(exam, 'listeetudiants').replace("%PROJET", amc_project_path)
    students_list_path = pathlib.Path(students_list_raw).resolve()
    project_root = pathlib.Path(amc_project_path).resolve()
    try:
        students_list_path.relative_to(project_root)
    except ValueError as exc:
        raise Http404("Invalid students list filepath") from exc
    return students_list_path


@exam_permission_required(['manage'])
@require_POST
def edit_amc_file(request: HttpRequest, exam_pk: int):
    exam = Exam.objects.get(pk=exam_pk)
    amc_project_path = get_amc_project_path(exam, False)

    if not amc_project_path:
        raise Http404("AMC project path not found")

    if request.POST['filepath'] == 'students_list':
        filepath = _resolve_students_list_path(exam, amc_project_path)

        with open(filepath, 'r') as f:
            file_contents = f.read()
            f.close()
            return HttpResponse(json.dumps([os.path.relpath(str(filepath), amc_project_path), file_contents]))
    else:
        filepath = _resolve_amc_project_file(amc_project_path, request.POST['filepath'])

        with open(filepath, 'r', encoding='utf-8') as f:
            file_contents = f.read()
            f.close()
            return HttpResponse(file_contents)


@exam_permission_required(['manage'])
@require_POST
def save_amc_edited_file(request: HttpRequest, exam_pk: int):
    data = request.POST['data']
    exam = Exam.objects.get(pk=exam_pk)
    amc_project_path = get_amc_project_path(exam, False)

    if not amc_project_path:
        raise Http404("AMC project path not found")

    filepath = _resolve_amc_project_file(amc_project_path, request.POST['filepath'])
    if 'is_students_list' in request.POST:
        tmp_filepath = get_amc_project_path(exam, False) + '/_tmp_students.csv'
        shutil.copyfile(filepath, tmp_filepath)
        with open(tmp_filepath, 'r+', encoding="utf-8") as f:
            f.truncate(0)
            f.write(data)
            f.close()
        check = check_students_csv_file(tmp_filepath)
        if check == 'ok':
            os.rename(tmp_filepath, filepath)
        else:
            os.remove(tmp_filepath)
            check += " -- file not updated !"
        return HttpResponse(check)
    else:
        filepath = _resolve_amc_project_file(amc_project_path, request.POST['filepath'])
        with open(filepath, 'r+', encoding="utf-8") as f:
            f.truncate(0)
            f.write(data)
            f.close()
        return HttpResponse('ok')


@exam_permission_required(['manage'])
@require_POST
def call_amc_update_documents(request: HttpRequest, exam_pk: int):
    exam = Exam.objects.get(pk=exam_pk)
    nb_copies = request.POST['nb_copies']

    result = amc_update_documents(exam, nb_copies, False)

    return HttpResponse(result)


@exam_permission_required(['manage'])
@require_POST
def call_amc_layout_detection(request: HttpRequest, exam_pk: int):
    exam = Exam.objects.get(pk=exam_pk)
    result = amc_layout_detection(exam)
    if not 'ERR:' in result:
        result = get_amc_layout_detection_info(exam)
    return HttpResponse(result)


@require_POST
@exam_permission_required(['manage'])
def call_amc_automatic_data_capture(request: HttpRequest, exam_pk: int, from_review=False):
    exam = Exam.objects.get(pk=exam_pk)
    zip_file = request.FILES['amc_scans_zip_file']

    return streaming_text_response(
        logged_stream(
            amc_automatic_datacapture_subprocess(request, exam, zip_file, from_review, file_list_path=None),
            "automatic_data_capture_upload",
            exam.pk,
            request.user,
        )
    )


@exam_permission_required(['manage'])
@require_POST
def import_scans_from_review_pages(request: HttpRequest, exam_pk: int) -> JsonResponse:
    exam = get_object_or_404(Exam, pk=exam_pk)
    scans_list = request.POST.getlist('pages_list[]')
    logger.info(
        "AMC import selected review scans requested exam=%s user=%s selected_count=%s",
        exam.pk,
        getattr(request.user, "pk", None),
        len(scans_list),
    )

    status_url_name = "amc_import_from_review_status"

    import_jobs = AmcJobsManager(
        request=request,
        session_key=AMC_ANNOTATE_JOBS_SESSION_KEY,
        status_url_name=status_url_name
    )

    def job_response(job_id: str, existing: bool = False) -> JsonResponse:
        return JsonResponse({
            "job_id": job_id,
            "status_url": reverse(status_url_name, args=[exam.pk, job_id]),
            "existing": existing,
        }, status=202)

    running_job_id = import_jobs.get_running_job_id(exam.pk)

    if running_job_id:
        return job_response(running_job_id, existing=True)

    job = amc_import_from_review_task.delay(exam.pk, scans_list)
    import_jobs.track(exam.pk, job.id)
    return job_response(job.id)


def stream_import_scans_from_review_pages(request: HttpRequest, exam, scans_list):
    selected_filenames = {pathlib.Path(scan).name for scan in scans_list}
    rendered_keys = set()

    if selected_filenames:
        logger.info(
            "AMC selected review import marked scan generation started exam=%s selected_count=%s",
            exam.pk,
            len(selected_filenames),
        )
        yield "Generating marked scans from review annotations ...\n"
        selected_page_markers = [
            page_markers
            for page_markers in PageMarkers.objects.filter(exam=exam).exclude(markers__isnull=True).exclude(markers="")
            if pathlib.Path(page_markers.filename).name in selected_filenames
        ]
        total = len(selected_page_markers)
        logger.info(
            "AMC selected review import user marker pages found exam=%s marker_count=%s",
            exam.pk,
            total,
        )
        for index, page_markers in enumerate(selected_page_markers, start=1):
            render_marked_scan(page_markers)
            rendered_keys.add(render_key(page_markers.pages_group_id, page_markers.copie_no, page_markers.page_no))
            yield (
                f"{index}/{total} - Generated marked scan "
                f"copy {page_markers.copie_no} page {page_markers.page_no}\n"
            )

        grading_count = 0
        for page_markers, output_path in iter_render_grading_only_marked_scans(
                exam,
                rendered_keys=rendered_keys,
                selected_filenames=selected_filenames,
        ):
            grading_count += 1
            yield (
                f"Generated grading scheme marked scan "
                f"copy {page_markers.copie_no} page {page_markers.page_no}: {output_path.name}\n"
            )
        yield f"Marked scan generation completed ({total + grading_count} file(s)).\n"
        logger.info(
            "AMC selected review import marked scan generation completed exam=%s user_marker_count=%s grading_only_count=%s",
            exam.pk,
            total,
            grading_count,
        )

    amc_proj_path = get_amc_project_path(exam, False)
    file_list_path = amc_proj_path + "/list-file"
    if os.path.exists(file_list_path):
        os.remove(file_list_path)

    with open(file_list_path, "w") as f:
        file_list_count = 0
        for scan in scans_list:
            scan_path = pathlib.Path(scan)
            marked_scan = pathlib.Path(
                str(scan_path).replace(str(settings.SCANS_ROOT), str(settings.MARKED_SCANS_ROOT))
            )
            marked_scan = marked_scan.with_name(f"marked_{marked_scan.stem}.png")
            if marked_scan.exists():
                f.write(str(marked_scan) + "\n")
            else:
                f.write(scan + "\n")
            file_list_count += 1

    logger.info(
        "AMC selected review import file list written exam=%s path=%s count=%s",
        exam.pk,
        file_list_path,
        file_list_count,
    )

    yield from amc_automatic_datacapture_subprocess(request, exam, None, True, file_list_path=file_list_path)


@exam_permission_required(['manage'])
@require_POST
def import_scans_from_review(request: HttpRequest, exam_pk: int) -> JsonResponse:
    exam = get_object_or_404(Exam, pk=exam_pk)
    logger.info(
        "AMC import all review scans requested exam=%s user=%s",
        exam.pk,
        getattr(request.user, "pk", None),
    )

    unresolved_count = UnrecognizedReviewScan.objects.filter(exam=exam, resolved=False).count()
    if unresolved_count:
        return JsonResponse({
            "status": "blocked",
            "error": f"Assign or delete all unrecognized scans before AMC import starts ({unresolved_count} remaining).",
            "unresolved_count": unresolved_count,
        }, status=409)

    status_url_name = "amc_import_from_review_status"

    import_jobs = AmcJobsManager(
        request=request,
        session_key=AMC_IMPORT_JOBS_SESSION_KEY,
        status_url_name=status_url_name
    )

    job_id = import_jobs.get_running_job_id(exam.pk)
    existing = job_id is not None
    if job_id is None:
        job_id = amc_import_from_review_task.delay(exam.pk).id
        import_jobs.track(exam.pk, job_id)

    clear_pending_amc_import(request, exam.pk)
    return _job_response(status_url_name, exam.pk, job_id, existing)


@require_GET
@exam_permission_required(['manage'])
def amc_import_from_review_status(request: HttpRequest, exam_pk: int, job_id: str) -> JsonResponse:
    amc_job_manager = AmcJobsManager(
        request=request,
        session_key=AMC_IMPORT_JOBS_SESSION_KEY,
        status_url_name="amc_import_from_review_status"
    )

    if not amc_job_manager.is_owned(exam_pk, job_id):
        return JsonResponse({"status": "forbidden", "error": "Unknown or unauthorized job id."}, status=403)

    res = AsyncResult(job_id)

    if not res.ready():
        # PENDING, RECEIVED, STARTED, RETRY, or the custom PROGRESS state with output so far
        meta = res.info if res.state == "PROGRESS" and isinstance(res.info, dict) else {}
        return JsonResponse({
            "status": "running",
            "state": res.state,
            "output": meta.get("output", ""),
            "line_count": meta.get("line_count", 0),
        })

    if res.state != celery.states.SUCCESS:
        # FAILURE or REVOKED: res.result is the user_facing_exception
        return JsonResponse({
            "status": "error",
            "state": res.state,
            "error": str(res.result) or "The import was cancelled.",
            "output": "",
            "line_count": 0,
        }, status=500)

    result = res.result
    if not isinstance(result, dict): result = {}

    return JsonResponse({
        "status": "done",
        "state": res.state,
        "output": result.get("output", ""),
        "line_count": result.get("line_count", 0),
    })

def stream_import_scans_from_review(request: HttpRequest, exam):
    amc_proj_path = get_amc_project_path(exam, False)
    file_list_path = amc_proj_path + "/list-file"

    if os.path.exists(file_list_path):
        os.remove(file_list_path)

    scans_dir = str(settings.SCANS_ROOT) + "/" + str(exam.year.code) + "/" + str(
        exam.semester.code) + "/" + exam.code + "_" + exam.date.strftime("%Y%m%d")
    logger.info("AMC full review import scans_dir exam=%s path=%s", exam.pk, scans_dir)
    marked_dir = str(settings.MARKED_SCANS_ROOT) + "/" + str(exam.year.code) + "/" + str(
        exam.semester.code) + "/" + exam.code + "_" + exam.date.strftime("%Y%m%d")

    yield "Generating marked scans from review annotations ...\n"
    logger.info("AMC full review import marked scan generation started exam=%s", exam.pk)
    marked_scans_root = get_exam_marked_scans_dir(exam)
    if marked_scans_root.exists():
        logger.info("AMC full review import removing previous marked scan directory exam=%s path=%s", exam.pk,
                    marked_scans_root)
        shutil.rmtree(marked_scans_root)

    page_markers_qs = PageMarkers.objects.filter(exam=exam).exclude(markers__isnull=True).exclude(markers="")
    total = page_markers_qs.count()
    logger.info("AMC full review import user marker pages found exam=%s marker_count=%s", exam.pk, total)
    rendered_keys = set()
    for index, page_markers in enumerate(page_markers_qs.iterator(), start=1):
        render_marked_scan(page_markers)
        rendered_keys.add(render_key(page_markers.pages_group_id, page_markers.copie_no, page_markers.page_no))
        yield (
            f"{index}/{total} - Generated marked scan "
            f"copy {page_markers.copie_no} page {page_markers.page_no}\n"
        )

    grading_count = 0
    for page_markers, output_path in iter_render_grading_only_marked_scans(exam, rendered_keys=rendered_keys):
        grading_count += 1
        yield (
            f"Generated grading scheme marked scan "
            f"copy {page_markers.copie_no} page {page_markers.page_no}: {output_path.name}\n"
        )
    yield f"Marked scan generation completed ({total + grading_count} file(s)).\n"
    logger.info(
        "AMC full review import marked scan generation completed exam=%s user_marker_count=%s grading_only_count=%s",
        exam.pk,
        total,
        grading_count,
    )

    export_subdir = 'marked_' + str(exam.year.code) + "_" + str(
        exam.semester.code) + "_" + exam.code + "_" + datetime.datetime.now().strftime('%Y%m%d%H%M%S%f')[:-5]
    export_subdir = export_subdir.replace(" ", "_")
    export_tmp_dir = (str(settings.EXPORT_TMP_ROOT) + "/" + export_subdir)

    if not os.path.exists(export_tmp_dir):
        os.makedirs(export_tmp_dir, exist_ok=True)

    # list files from normal copy scan dirs
    for dir_entry in iter_review_copy_dirs(scans_dir):
        dir = dir_entry.name

        copy_export_subdir = export_tmp_dir + "/" + dir

        if not os.path.exists(copy_export_subdir):
            os.mkdir(copy_export_subdir)

        for filename in sorted(os.listdir(scans_dir + "/" + dir)):
            # check if a marked file exist, if yes copy it, or copy original scans

            scan_filename = pathlib.Path(filename)
            marked_file_path = pathlib.Path(marked_dir) / dir / f"marked_{scan_filename.stem}.png"
            if os.path.exists(marked_file_path):
                shutil.copyfile(marked_file_path, copy_export_subdir + "/" + marked_file_path.name)
            else:
                shutil.copyfile(scans_dir + "/" + dir + "/" + filename, copy_export_subdir + "/" + filename)

    with open(file_list_path, "w") as tmp_file_list:
        files = [str(path) for path in iter_review_scan_files(scans_dir)]
        file_list_count = 0
        marked_file_count = 0
        for file in files:
            file_path = pathlib.Path(file)
            marked_file_path = pathlib.Path(marked_dir) / file_path.parent.name / f"marked_{file_path.stem}.png"
            if os.path.exists(marked_file_path):
                tmp_file_list.write(str(marked_file_path) + "\n")
                marked_file_count += 1
            else:
                tmp_file_list.write(file + "\n")
            file_list_count += 1

        tmp_file_list.close()
        logger.info(
            "AMC full review import file list written exam=%s path=%s count=%s marked_count=%s",
            exam.pk,
            file_list_path,
            file_list_count,
            marked_file_count,
        )

        yield from amc_automatic_datacapture_subprocess(request, exam, None, True, file_list_path=file_list_path)


@exam_permission_required(['manage'])
def open_amc_exam_pdf(request: HttpRequest, exam_pk: int):
    exam = Exam.objects.get(pk=exam_pk)
    file_path = get_amc_exam_pdf_path(exam)
    try:
        return FileResponse(open(file_path, 'rb'), content_type='application/pdf')
    except FileNotFoundError:
        raise Http404('not found')


@exam_permission_required(['manage'])
def open_amc_catalog_pdf(request: HttpRequest, exam_pk: int):
    exam = Exam.objects.get(pk=exam_pk)
    file_path = get_amc_catalog_pdf_path(exam)
    try:
        return FileResponse(open(file_path, 'rb'), content_type='application/pdf')
    except FileNotFoundError:
        raise Http404('not found')


@exam_permission_required(['manage'])
@require_POST
def view_amc_log_file(request: HttpRequest, exam_pk: int):
    exam = Exam.objects.get(pk=exam_pk)
    amc_log_file_path = get_amc_project_path(exam, False) + "/amc-compiled.log"

    with open(amc_log_file_path, 'r', encoding='latin-1') as f:
        file_contents = f.read()
        f.close()
        return HttpResponse(file_contents)


@exam_permission_required(['manage'])
@require_POST
def get_amc_zooms(request: HttpRequest, exam_pk: int):
    exam = Exam.objects.get(pk=exam_pk)
    copy = request.POST['copy']
    page = request.POST['page']

    zooms_data = get_copy_page_zooms(exam, copy, page)

    return HttpResponse(json.dumps(zooms_data))


@exam_permission_required(['manage'])
@require_POST
def add_unrecognized_page(request: HttpRequest, exam_pk: int):
    exam = Exam.objects.get(pk=exam_pk)
    page = request.POST['unrec_page']
    copy = request.POST['copy']
    extra = True  #request.POST['extra']
    img_filename = request.POST['unrecognized-img-src']  #.split('/')[-1]
    add_unrecognized_page_to_project(exam, copy, page, extra, img_filename)

    return HttpResponse(True)


@exam_permission_required(['manage'])
@require_POST
def call_amc_mark(request: HttpRequest, exam_pk: int):
    exam = Exam.objects.get(pk=exam_pk)
    update_scoring_strategy = request.POST['update_scoring_strategy']

    return streaming_text_response(amc_mark_subprocess(request, exam, update_scoring_strategy))


# result = amc_mark(exam,update_scoring_strategy)


@exam_permission_required(['manage'])
@require_POST
def call_amc_automatic_association(request: HttpRequest, exam_pk: int):
    exam = Exam.objects.get(pk=exam_pk)
    assoc_primary_key = request.POST['assoc_primary_key']

    result = amc_automatic_association(exam, assoc_primary_key)

    if not 'ERR:' in result:
        url = reverse('amc_view', kwargs={'exam_pk': exam.pk})
        return JsonResponse({'ok': True, 'redirect': url})
    else:
        return JsonResponse({'error': result})


@exam_permission_required(['manage'])
@require_POST
def amc_update_students_file(request: HttpRequest, exam_pk: int) -> HttpResponse:
    exam: Exam = get_object_or_404(Exam, pk=exam_pk)

    students_list_csv: UploadedFile | None = request.FILES.get('students-list-csv')
    if students_list_csv is None or not students_list_csv.name:
        return HttpResponseBadRequest('No students file uploaded')

    try:
        amc_project_dir: str = get_amc_project_path(exam, False)
    except AmcProjectPathNotFoundError:
        return HttpResponse('ok')  # same as the original; consider returning an error instead

    project_path = pathlib.Path(amc_project_dir)
    file_name: str = pathlib.Path(students_list_csv.name).name  # drop any client-supplied path parts
    storage = FileSystemStorage(location=project_path)

    # Save to a temp file for checking.
    # storage.save() returns the name actually used, which differs if the file already exists.
    tmp_name: str = storage.save('_tmp_students.csv', students_list_csv)
    tmp_path: pathlib.Path = project_path / tmp_name

    check: str = check_students_csv_file(str(tmp_path))
    if check != 'ok':
        tmp_path.unlink(missing_ok=True)
        return HttpResponse(check)

    tmp_path.replace(project_path / file_name)  # atomic overwrite
    amc_update_options_xml_by_key(exam, 'listeetudiants', f'%PROJET/{file_name}')
    return HttpResponse('ok')


@exam_permission_required(['manage'])
@require_POST
def old_call_amc_annotate(request: HttpRequest, exam_pk: int):
    exam = Exam.objects.get(pk=exam_pk)
    single_file = request.POST['single_file']
    add_grading_scheme_report = request.POST['add_grading_scheme_report']
    if single_file == '1':
        single_file = True
    else:
        single_file = False

    result = amc_annotate(exam, single_file, add_grading_scheme_report)

    return HttpResponse(result)


@require_POST
@exam_permission_required(['manage'])
def call_amc_annotate(request: HttpRequest, exam_pk: int) -> JsonResponse:
    exam = get_object_or_404(Exam, pk=exam_pk)

    single_file = request.POST.get("single_file") == "1"
    add_grading_scheme_report = request.POST.get("add_grading_scheme_report") in ("true", "True", "1")

    amc_job_manager = AmcJobsManager(
        request=request,
        session_key=AMC_ANNOTATE_JOBS_SESSION_KEY,
        status_url_name="amc_annotate_status",
    )
    job = amc_annotate_task.delay(exam.pk, single_file, add_grading_scheme_report)
    amc_job_manager.track(exam.pk, job.id)

    return _job_response(amc_job_manager.status_url_name, exam.pk, job.id)




@require_GET
@exam_permission_required(['manage'])
def amc_annotate_status(request: HttpRequest, exam_pk: int, job_id: str) -> JsonResponse:
    amc_job_manager = AmcJobsManager(
        request=request,
        session_key=AMC_ANNOTATE_JOBS_SESSION_KEY,
        status_url_name="amc_annotate_status",
    )
    if not amc_job_manager.is_owned(exam_pk, job_id):
        return JsonResponse({"status": "forbidden", "error": "Unknown or unauthorized job id."}, status=403)

    res = AsyncResult(job_id)

    if not res.ready():
        # PENDING, RECEIVED, STARTED, RETRY, or the custom PROGRESS state with its progress info
        raw_info = res.info
        meta: dict[str, Any] = raw_info if res.state == "PROGRESS" and isinstance(raw_info, dict) else {}
        return JsonResponse({
            "status": "running",
            "state": res.state,
            "progress": meta.get("progress", ""),
            "done": meta.get("done"),
            "total": meta.get("total"),
        })

    if res.state != celery.states.SUCCESS:
        # FAILURE or REVOKED: res.result is the user_facing_exception
        return JsonResponse({
            "status": "error",
            "state": res.state,
            "error": str(res.result) or "The annotation was cancelled.",
            "progress": "",
        }, status=500)

    raw_result = res.result
    result: dict[str, Any] = raw_result if isinstance(raw_result, dict) else {"output": raw_result}
    return JsonResponse({
        "status": "done",
        "state": res.state,
        "result": result.get("output", ""),
        "progress": result.get("progress", ""),
    })


@exam_permission_required(['manage'])
def download_annotated_pdf(request: HttpRequest, exam_pk: int):
    exam = Exam.objects.get(pk=exam_pk)
    zip_file_path = create_annotated_zip(exam)

    if zip_file_path:
        return FileResponse(open(zip_file_path, 'rb'))
    else:
        return HttpResponse('ZIP file not created !')


@exam_permission_required(['manage'])
@require_POST
def call_amc_generate_results(request: HttpRequest, exam_pk: int):
    exam = Exam.objects.get(pk=exam_pk)
    result = amc_generate_results(exam)

    if not 'ERR:' in result:
        project_path = get_amc_project_path(exam, False)
        results_csv_path = project_path + "/exports/" + exam.code + "_amc_raw.csv"

        task = import_csv_data.delay(results_csv_path, exam.pk)
        task_id = task.task_id

        url = reverse('amc_view_tab', kwargs={'exam_pk': exam.pk, 'curr_tab': 'results-tab'})
        return redirect(f"{url}?task_id={task_id}")
    else:
        return HttpResponse(result)


@exam_permission_required(['manage'])
@require_POST
def amc_manual_association_data(request: HttpRequest, exam_pk: int):
    exam = Exam.objects.get(pk=exam_pk)
    data = get_amc_manual_association_data(exam)

    return HttpResponse(json.dumps(data))


@require_POST
@exam_permission_required(['manage'])
def amc_set_manual_association(request: HttpRequest, exam_pk: int) -> JsonResponse:
    """Manually associate a student with an answer sheet, or remove the sheet's student.

    :param request: the HTTP request
    :param exam_pk: the exam's primary key

    POST parameters:
        copy_nr:    the sheet number (AMC's `student` column, shown as "Copy Nr.")
        copy:       the copy number, 0 unless sheets were photocopied (optional, default 0)
        student_id: the student code from the students list, or "0" ("Select...") to remove the student

    The student is first unlinked from any other sheet, as in AMC.
    Returns {"ok": true} or {"ok": false, "error": "..."}.
    """
    exam = get_object_or_404(Exam, pk=exam_pk)

    try:
        sheet = int(request.POST["copy_nr"])
        copy = int(request.POST.get("copy", 0))
    except (KeyError, ValueError):
        return JsonResponse({"error": "Invalid sheet number."}, status=400)
    if sheet < 0 or copy < 0:
        return JsonResponse({"error": "Invalid sheet number."}, status=400)

    code = request.POST.get("student_id", "").strip()  # kept as text: codes can have leading zeros

    amc_project_path = get_amc_project_path(exam, even_if_not_exist=False)
    if not amc_project_path:
        return JsonResponse(
            {"error": "No association data for this exam yet. Run the automatic association or the marking first."},
            status=404)

    amc_data_path = os.path.join(amc_project_path, "data")
    if not os.path.isfile(os.path.join(amc_data_path, "association.sqlite")):
        return JsonResponse(
            {"error": "No association data for this exam yet. Run the automatic association or the marking first."},
            status=404)

    with AmcAssociationDbManager(amc_data_path=amc_data_path) as amc_association_db_manager:
        try:
            no_student_choice = "0"
            if code in ("", no_student_choice):
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
            return JsonResponse({"error": "The association could not be saved."})

        return JsonResponse({"ok": True})


@require_POST
@exam_permission_required(['manage'])
def amc_send_annotated_papers_data(request: HttpRequest, exam_pk: int):
    exam = Exam.objects.get(pk=exam_pk)
    data = get_amc_send_annotated_papers_data(exam)
    email_subject = get_amc_option_by_key(exam, 'email_subject')
    email_text = get_amc_option_by_key(exam, 'email_text')
    # amc_update_options_xml_by_key()

    values = {"email_subject": email_subject, "email_text": email_text, "data": data}
    return HttpResponse(json.dumps(values))


@require_POST
@exam_permission_required(['manage'])
def call_amc_send_annotated_papers(request: HttpRequest, exam_pk: int):
    exam = Exam.objects.get(pk=exam_pk)
    selected_students = json.loads(request.POST['selected-students'])
    email_subject = request.POST['email-subject']
    email_body = request.POST['email-body']
    email_column = request.POST['email-column']

    result = amc_send_annotated_papers(exam, selected_students, email_subject, email_body, email_column)
    return HttpResponse(json.dumps(result))


@require_POST
@exam_permission_required(['manage'])
def get_amc_scan_url(request: HttpRequest, exam_pk: int):
    exam = Exam.objects.get(pk=exam_pk)
    copy_nr = request.POST['copy']
    page_nr = request.POST['page']
    project_path = get_amc_project_path(exam, False)

    if not project_path:
        return HttpResponseNotFound('No AMC project')

    if '.' in page_nr:  # extra page
        c = copy_nr.zfill(4)
        scan_path = pathlib.Path(project_path, 'scans', 'extra', c, f'copy_{c}_{page_nr}.jpg').resolve()
    else:
        with AmcCaptureDbManager(amc_data_path=f'{project_path}/data/') as amc_capture_db_manager:
            raw_scan_path = amc_capture_db_manager.select_amc_scan_path(copy_nr, page_nr)

        if not raw_scan_path:
            return HttpResponseNotFound('No scan for this page')

        scan_path = resolve_amc_path(raw_scan_path, project_path)

    roots = [pathlib.Path(settings.MARKED_SCANS_ROOT), pathlib.Path(settings.SCANS_ROOT), pathlib.Path(project_path, 'scans', 'extra')]
    root = next((r.resolve() for r in roots if scan_path.is_relative_to(r.resolve())), None)

    if root is None or not scan_path.is_file():
        logger.warning('Scan not found: copy=%s page=%s path=%s', copy_nr, page_nr, scan_path)
        return HttpResponseNotFound('Scan file not found')

    return HttpResponse(make_token_for(str(scan_path.relative_to(root)), str(root)))
