"""Tasks of the correction phase in AMC: importing the reviewed scans, annotating the corrected copies."""

import os
import pathlib
import shutil

from celery import shared_task
from celery_progress.backend import logger
from django.conf import settings

from examc_app.exceptions.amc import AmcAnnotateError
from examc_app.models import Exam, PageMarkers
from examc_app.services.exam.paths import get_exam_marked_scans_dir, get_exam_scans_dir
from examc_app.services.jobs import update_job_progress
from examc_app.utils.amc_functions import (
    amc_annotate,
    amc_automatic_data_capture_subprocess,
    get_amc_project_path,
)
from examc_app.utils.marker_rendering import (
    iter_render_grading_only_marked_scans,
    render_key,
    render_marked_scan,
)
from examc_app.utils.review_functions import iter_review_scan_files


def _set_amc_import_progress(task, lines, status="running"):
    task.update_state(
        state="PROGRESS",
        meta={
            "status": status,
            "output": "".join(lines[-500:]),
            "line_count": len(lines),
        },
    )


def _append_amc_import_line(task, lines, line):
    lines.append(line if line.endswith("\n") else line + "\n")
    _set_amc_import_progress(task, lines)
    logger.info("AMC import task progress: %s", line.strip())


def _render_review_marked_scans(task, exam, selected_filenames=None):
    lines = []
    rendered_keys = set()
    is_selected_import = selected_filenames is not None
    selected_filenames = set(selected_filenames or [])

    if is_selected_import:
        _append_amc_import_line(
            task,
            lines,
            f"Generating marked scans from review annotations for {len(selected_filenames)} selected page(s) ...",
        )
        page_markers_list = [
            page_markers
            for page_markers in PageMarkers.objects.filter(exam=exam).exclude(markers__isnull=True).exclude(markers="")
            if pathlib.Path(page_markers.filename).name in selected_filenames
        ]
        total = len(page_markers_list)
    else:
        _append_amc_import_line(task, lines, "Generating marked scans from review annotations ...")
        marked_scans_root = get_exam_marked_scans_dir(exam)
        if marked_scans_root.exists():
            shutil.rmtree(marked_scans_root)

        page_markers_qs = PageMarkers.objects.filter(exam=exam).exclude(markers__isnull=True).exclude(markers="")
        total = page_markers_qs.count()
        page_markers_list = page_markers_qs.iterator()

    for index, page_markers in enumerate(page_markers_list, start=1):
        render_marked_scan(page_markers)
        rendered_keys.add(render_key(page_markers.pages_group_id, page_markers.copie_no, page_markers.page_no))
        _append_amc_import_line(
            task,
            lines,
            f"{index}/{total} - Generated marked scan copy {page_markers.copie_no} page {page_markers.page_no}",
        )

    grading_count = 0
    for page_markers, output_path in iter_render_grading_only_marked_scans(
        exam,
        rendered_keys=rendered_keys,
        selected_filenames=selected_filenames if is_selected_import else None,
    ):
        grading_count += 1
        _append_amc_import_line(
            task,
            lines,
            (
                "Generated grading scheme marked scan "
                f"copy {page_markers.copie_no} page {page_markers.page_no}: {output_path.name}"
            ),
        )

    _append_amc_import_line(task, lines, f"Marked scan generation completed ({total + grading_count} file(s)).")
    return lines


def _write_review_import_file_list(exam, scans_list=None):
    amc_proj_path = get_amc_project_path(exam, False)
    file_list_path = amc_proj_path + "/list-file"
    if os.path.exists(file_list_path):
        os.remove(file_list_path)

    if scans_list is None:
        scans_dir = get_exam_scans_dir(exam)
        scans_list = [str(path) for path in iter_review_scan_files(scans_dir)]

    count = 0
    marked_count = 0
    with open(file_list_path, "w") as f:
        for scan in scans_list:
            scan_path = pathlib.Path(scan)
            marked_scan = pathlib.Path(
                str(scan_path).replace(str(settings.SCANS_ROOT), str(settings.MARKED_SCANS_ROOT))
            )
            marked_scan = marked_scan.with_name(f"marked_{marked_scan.stem}.png")
            if marked_scan.exists():
                f.write(str(marked_scan) + "\n")
                marked_count += 1
            else:
                f.write(str(scan) + "\n")
            count += 1

    return file_list_path, count, marked_count


@shared_task(bind=True, name="examc_app.tasks.amc_import_from_review_task")
def amc_import_from_review_task(self, exam_pk: int, scans_list=None):
    lines = []
    try:
        exam = Exam.objects.get(pk=exam_pk)
        selected_filenames = None
        if scans_list is not None:
            selected_filenames = {pathlib.Path(scan).name for scan in scans_list}

        _append_amc_import_line(self, lines, f"Starting AMC import from review for exam {exam.pk} ...")
        lines.extend(_render_review_marked_scans(self, exam, selected_filenames=selected_filenames))

        file_list_path, file_count, marked_count = _write_review_import_file_list(exam, scans_list=scans_list)
        _append_amc_import_line(
            self,
            lines,
            f"AMC file list written ({file_count} file(s), {marked_count} marked scan(s)).",
        )

        for line in amc_automatic_data_capture_subprocess(None, exam, None, True, file_list_path=file_list_path):
            _append_amc_import_line(self, lines, line)

        _append_amc_import_line(self, lines, "AMC import from review completed.")
        return {
            "status": "done",
            "output": "".join(lines[-500:]),
            "line_count": len(lines),
        }

    except Exception as exception:
        logger.exception("AMC import from review failed exam=%s", exam_pk)
        _append_amc_import_line(self, lines, f"AMC import from review failed: {type(exception).__name__}: {exception}")
        update_job_progress(
            self,
            error=f"AMC import from review failed: {exception}",
            error_type=type(exception).__name__,
            output="".join(lines[-500:]),
            line_count=len(lines)
        )


@shared_task(bind=True, name="examc_app.tasks.amc_annotate_task")
def amc_annotate_task(
    self,
    exam_pk: int,
    single_file: bool,
    add_grading_scheme_report: bool,
    # Defaults: tasks queued before this change (during a deploy) still run
    include_grading_scheme_description: bool = False,
    include_student_comments: bool = False,
):
    last_progress = {"progress": ""}

    def progress_callback(done=None, total=None, message=""):
        if message:
            progress = message
        elif total:
            progress = f"{done}/{total} files generated"
        else:
            progress = "Processing annotated PDFs..."
        last_progress["progress"] = progress
        logger.info(
            "AMC annotate task progress exam=%s progress=%s done=%s total=%s",
            exam_pk, progress, done, total,
        )
        update_job_progress(self, progress=progress, done=done, total=total, message=message)

    exam = Exam.objects.get(pk=exam_pk)
    logger.info(
        "AMC annotate task started exam=%s single_file=%s grading_scheme=%s description=%s comments=%s",
        exam_pk, single_file, add_grading_scheme_report,
        include_grading_scheme_description, include_student_comments,
    )

    progress_callback(message="Starting AMC annotation...")
    try:
        result = amc_annotate(
            exam,
            single_file,
            add_grading_scheme_report,
            include_grading_scheme_description=include_grading_scheme_description,
            include_student_comments=include_student_comments,
            progress_callback=progress_callback,
        )
    except Exception:
        logger.exception("AMC annotate task failed exam=%s", exam_pk)
        raise

    # AMC reports some failures as an "ERR:" result rather than an exception: make it a failed job
    if isinstance(result, str) and result.startswith("ERR:"):
        logger.error("AMC annotate task completed with AMC error exam=%s result=%s", exam_pk, result)
        raise AmcAnnotateError(result.removeprefix("ERR:").strip() or "AMC couldn't generate the corrected exams.")

    logger.info("AMC annotate task completed exam=%s", exam_pk)
    return {"output": result, "progress": last_progress["progress"]}
