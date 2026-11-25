"""Tasks that export the marked copies of an exam."""

import os
import pathlib
import shutil
import uuid
import zipfile
from datetime import datetime

from celery import shared_task
from celery_progress.backend import ProgressRecorder, logger
from django.conf import settings

from examc_app.models import Exam
from examc_app.services.exam.paths import get_exam_marked_scans_dir, get_exam_scans_dir
from examc_app.services.jobs import update_job_progress
from examc_app.utils.marker_rendering import regenerate_marked_scans_for_exam
from examc_app.utils.review_functions import (
    generate_marked_pdfs,
    iter_review_copy_dirs,
    zipdir,
)

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png"}


@shared_task(bind=True)
def generate_marked_files_zip(self, exam_pk: int, export_type, with_comments: bool):
    try:
        exam = Exam.objects.get(pk=exam_pk)
        scans_dir = str(get_exam_scans_dir(exam))
        marked_dir = str(get_exam_marked_scans_dir(exam))
        task_token = str(self.request.id or uuid.uuid4()).replace("-", "")
        export_subdir = (
            "marked_"
            + str(exam.year.code)
            + "_"
            + str(exam.semester.code)
            + "_"
            + exam.code
            + "_"
            + datetime.now().strftime("%Y%m%d%H%M%S%f")
            + "_"
            + task_token[:12]
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
        for dir_entry in iter_review_copy_dirs(scans_dir):
            d = dir_entry.name

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

        if int(export_type) > 1:
            generate_marked_pdfs(
                exam=exam,
                files_path=export_tmp_dir,
                progress_recorder=progress_recorder,
                with_comments=with_comments,
            )

            # remove subfolders with img
            for root, dirs, files in os.walk(export_tmp_dir):
                for name in dirs:
                    shutil.rmtree(os.path.join(root, name))

        # zip folder
        zip_path = export_tmp_dir.parent / f"{export_tmp_dir.name}.zip"
        zipf = zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED)
        zipdir(export_tmp_dir, zipf)
        zipf.close()

        # remove tmp folder not zipped
        shutil.rmtree(export_tmp_dir)

        return export_subdir + ".zip"

    except Exception as exception:
        logger.exception("Export failed")
        update_job_progress(
            self,
            error=f"Error during export: {exception}",
            error_type=type(exception).__name__,
        )