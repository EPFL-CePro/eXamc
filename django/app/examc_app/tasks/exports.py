"""Tasks that export the marked copies of an exam."""

import os
import pathlib
import shutil
import uuid
import zipfile
from datetime import datetime

from celery import chord, group, shared_task
from celery.exceptions import Ignore
from celery_progress.backend import ProgressRecorder, logger
from django.conf import settings
from django.db import connection
from fpdf import FPDF
from PIL import UnidentifiedImageError

from examc_app.models import (
    Exam,
    PagesGroupComment,
)
from examc_app.services.exam.paths import get_exam_marked_scans_dir, get_exam_scans_dir
from examc_app.services.jobs import update_job_progress
from examc_app.utils.marker_rendering import regenerate_marked_scans_for_exam
from examc_app.utils.review_functions import (
    generate_comments_pdf_pages,
    iter_review_copy_dirs,
    scan_as_jpeg,
    zipdir,
)

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png"}


def _zip_export(export_tmp_dir: pathlib.Path) -> None:
    """Zips the export folder next to it, then removes the folder."""
    zip_path = export_tmp_dir.parent / f"{export_tmp_dir.name}.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
        zipdir(export_tmp_dir, zipf)
    shutil.rmtree(export_tmp_dir)


@shared_task(bind=True, name="examc_app.tasks.generate_marked_copy_pdf")
def generate_marked_copy_pdf(self, exam_pk: int, files_path: str, subdir: str, with_comments: bool) -> list[str]:
    """
    Builds one copy's marked PDF from the images in ``files_path/subdir``; returns the scans it couldn't read.

    The arguments are plain values (a pk, a path as a string) because they go through the broker as JSON.
    """
    progress_recorder = ProgressRecorder(self)
    exam = Exam.objects.get(pk=exam_pk)

    unreadable: list[str] = []

    subdir_path = os.path.join(files_path, subdir)
    images_paths: list[str] = sorted(os.listdir(subdir_path))

    # one step per page, and one more for the final PDF
    total_steps_count = len(images_paths) + 1

    def update_progress(count: int):
        progress_recorder.set_progress(
            count,
            total_steps_count,
            description=f"Generating marked copy PDF for copy {subdir}...",
        )

    try:
        update_progress(0)

        pdf = FPDF(orientation='P', unit='mm', format='A4')
        pdf.set_auto_page_break(False)
        pdf.set_margins(0, 0, 0)

        for i, image_path in enumerate(images_paths):
            if pathlib.Path(image_path).suffix.lower() not in IMAGE_EXTENSIONS:
                update_progress(i + 1)
                logger.warning("Skipping unreadable scan %s of copy %s (exam %s)", image_path, subdir, exam.pk)
                continue

            pdf.add_page()

            try:
                scan = scan_as_jpeg(os.path.join(subdir_path, image_path))
            except (OSError, UnidentifiedImageError):
                logger.exception("Unreadable scan %s of copy %s (exam %s)", image_path, subdir, exam.pk)
                unreadable.append(f"copy {subdir}: {image_path}")
                # A visible page instead of a silently missing one
                pdf.set_font("Helvetica", "B", 16)
                pdf.set_xy(20, 120)
                pdf.multi_cell(0, 10, f"Scan {image_path} could not be read.\nPlease contact the exam organisers.")
                update_progress(i + 1)
                continue

            update_progress(i + 1)
            pdf.image(scan, w=pdf.epw)

        if with_comments:
            pages_comments = PagesGroupComment.objects.filter(pages_group__exam=exam, copy_no=subdir).order_by(
                'copy_no', 'pages_group__group_name', 'parent_id')
            if pages_comments:
                pdf.add_page()
            pdf.set_font("Helvetica", "", 8)
            pdf.set_auto_page_break(True)
            generate_comments_pdf_pages(exam, None, subdir, pdf)

        pdf.output(name=f"{files_path}/copy_{subdir}.pdf")

        return unreadable
    finally:
        update_progress(total_steps_count)

        # each thread gets its own database connection: don't leave it open
        connection.close()


@shared_task(bind=True, name="examc_app.tasks.finish_marked_files_zip")
def finish_marked_files_zip(self, unreadable_per_copy: list[list[str]], export_tmp_dir: str, export_subdir: str) -> str:
    """
    Runs once every copy's PDF is built (the callback of the chord in generate_marked_files_zip): removes the image
    folders and zips the PDFs. Its result is the one of generate_marked_files_zip, which it replaced.

    :param unreadable_per_copy: What each generate_marked_copy_pdf returned, in the order of the copies.
    """
    try:
        progress_recorder = ProgressRecorder(self)
        progress_recorder.set_progress(0, 1, description="Zipping the marked copies...")

        unreadable = [scan for copy_unreadable in unreadable_per_copy for scan in copy_unreadable or []]
        if unreadable:
            logger.warning(
                "Export %s: %s unreadable scan(s): %s", export_subdir, len(unreadable), ", ".join(unreadable)
            )

        export_dir = pathlib.Path(export_tmp_dir)

        # remove subfolders with img: the PDFs are built
        for entry in export_dir.iterdir():
            if entry.is_dir():
                shutil.rmtree(entry)

        _zip_export(export_dir)

        progress_recorder.set_progress(1, 1, description="Done!")
        return export_subdir + ".zip"

    except Exception as exception:
        logger.exception("Export failed")
        update_job_progress(
            self,
            error=f"Error during export: {exception}",
            error_type=type(exception).__name__,
        )


@shared_task(bind=True, name="examc_app.tasks.generate_marked_files_zip")
def generate_marked_files_zip(self, exam_pk: int, export_type, with_comments: bool):
    try:
        exam = Exam.objects.get(pk=exam_pk)
        scans_dir = str(get_exam_scans_dir(exam))
        marked_dir = str(get_exam_marked_scans_dir(exam))
        task_token = str(self.request.id or uuid.uuid4()).replace("-", "")
        export_subdir = (
            f"marked_{exam.year.code}_{exam.semester.code}_{exam.code}_{datetime.now().strftime("%Y%m%d%H%M%S%f")}_{task_token[:12]}"
        )

        export_subdir = export_subdir.replace(" ", "_")
        export_tmp_dir = pathlib.Path(f"{settings.EXPORT_TMP_ROOT}/{export_subdir}")

        progress_recorder = ProgressRecorder(self)

        if not os.path.exists(export_tmp_dir):
            os.mkdir(export_tmp_dir)

        regenerate_marked_scans_for_exam(
            exam,
            progress_callback=lambda index, total: progress_recorder.set_progress(
                index, total, description=f"{index}/{total} - Rendering marked scans..."
            ),
        )

        # list files from normal copy scan dirs
        copy_dirs: list[str] = []
        for dir_entry in iter_review_copy_dirs(scans_dir):
            d = dir_entry.name
            copy_dirs.append(d)

            copy_export_subdir = f"{export_tmp_dir}/{d}"

            if not os.path.exists(copy_export_subdir):
                os.mkdir(copy_export_subdir)

            for filename in sorted(os.listdir(f"{scans_dir}/{d}")):
                if pathlib.Path(filename).suffix.lower() not in IMAGE_EXTENSIONS:
                    continue

                # check if a marked file exist, if yes copy it, or copy original scans

                scan_filename = pathlib.Path(filename)
                marked_file_path = pathlib.Path(
                    f"{marked_dir}/{d}/marked_{scan_filename.stem}.png"
                )

                if os.path.exists(marked_file_path):
                    shutil.copyfile(
                        marked_file_path,
                        f"{copy_export_subdir}/{scan_filename.with_suffix('.png').name}",
                    )
                else:
                    shutil.copyfile(
                        f"{scans_dir}/{d}/{filename}",
                        f"{copy_export_subdir}/{filename}",
                    )

        if int(export_type) > 1 and copy_dirs:
            progress_recorder.set_progress(
                0, len(copy_dirs), description=f"Generating the PDFs of {len(copy_dirs)} copies..."
            )

            # One task per copy, run in parallel by the workers; once they have all finished, the callback removes
            # the image folders and zips the PDFs
            generate_marked_pdfs_task_group = group(
                generate_marked_copy_pdf.s(exam.pk, str(export_tmp_dir), copy_dir, with_comments)
                for copy_dir in copy_dirs
            )
            pdfs_then_zip = chord(
                generate_marked_pdfs_task_group,
                finish_marked_files_zip.s(str(export_tmp_dir), export_subdir),
            )

            # This task ends here and the chord takes over: the callback runs under this task's id, so what polls
            # this task gets the zip's name (or the error) from it. Waiting for the group here instead (.get())
            # would hold a worker slot and can deadlock the pool.
            raise self.replace(pdfs_then_zip)

        _zip_export(export_tmp_dir)

        return export_subdir + ".zip"

    except Ignore:
        # How self.replace() hands over to the chord: not a failure
        raise
    except Exception as exception:
        logger.exception("Export failed")
        update_job_progress(
            self,
            error=f"Error during export: {exception}",
            error_type=type(exception).__name__,
        )