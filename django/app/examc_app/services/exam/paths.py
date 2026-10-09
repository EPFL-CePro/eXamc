"""
Where the files of an exam live.

Every storage root (scans, marked scans, AMC projects, catalogs) uses the same layout:
`<ROOT>/<year>/<semester>/<code>_<YYYYMMDD>`.
"""
import logging
import shutil
from pathlib import Path

from django.conf import settings

from examc_app.exceptions.exam import (
    ExamDateMissingError,
    ExamFolderConflictError,
    ExamFolderNameInvalidError,
)
from examc_app.models import Exam

logger = logging.getLogger(__name__)

EXAM_FOLDER_ROOT_SETTINGS = (
    "SCANS_ROOT",
    "MARKED_SCANS_ROOT",
    "AMC_PROJECTS_ROOT",
    "CATALOG_ROOT",
)


def _check_folder_name(value: str, exam: Exam) -> str:
    name = str(value).strip() if value is not None else ""
    if not name or name in (".", "..") or "/" in name or "\\" in name or "\0" in name:
        raise ExamFolderNameInvalidError(
            f"Cannot use {value!r} as a folder name (exam pk={exam.pk})", context={"exam": exam}
        )
    return name


def get_exam_subdir(exam: Exam) -> str:
    """
    '<year>/<semester>/<code>_<YYYYMMDD>', the folder of an exam under every storage root.
    :raise ExamDateMissingError: if the exam has no date
    :raise ExamFolderNameInvalidError: if the year, semester or code can't be a folder name
    """
    if not exam.date:
        raise ExamDateMissingError(f"Exam pk={exam.pk} has no date", context={"exam": exam})

    year = _check_folder_name(exam.year.code, exam)
    semester = _check_folder_name(str(exam.semester.code), exam)
    code = _check_folder_name(exam.code, exam)
    return f"{year}/{semester}/{code}_{exam.date:%Y%m%d}"


def get_exam_scans_dir(exam: Exam) -> Path:
    return Path(settings.SCANS_ROOT) / get_exam_subdir(exam)


def get_exam_marked_scans_dir(exam: Exam) -> Path:
    return Path(settings.MARKED_SCANS_ROOT) / get_exam_subdir(exam)


def get_exam_amc_project_dir(exam: Exam) -> Path:
    return Path(settings.AMC_PROJECTS_ROOT) / get_exam_subdir(exam)


def get_exam_catalog_dir(exam: Exam) -> Path:
    return Path(settings.CATALOG_ROOT) / get_exam_subdir(exam)


def get_exam_amc_project_url(exam: Exam) -> str:
    return f"{settings.AMC_PROJECTS_URL}{get_exam_subdir(exam)}"


def rename_exam_folders(old_subdir: str, new_subdir: str) -> list[Path]:
    """
    Move the folders of an exam from one subdir to another, in every storage root where it exists.

    :return: the new paths of the folders that were moved
    :raise ExamFolderConflictError: if a destination already exists
    """
    if old_subdir == new_subdir:
        return []

    moves = []
    for setting_name in EXAM_FOLDER_ROOT_SETTINGS:
        root = Path(getattr(settings, setting_name))
        source = root / old_subdir
        destination = root / new_subdir
        if not source.is_dir():
            continue
        if destination.exists():
            raise ExamFolderConflictError(f"Cannot move {source} to {destination}: it already exists")
        moves.append((source, destination))

    moved = []
    for source, destination in moves:
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(source), str(destination))
        logger.info("Moved exam folder %s to %s", source, destination)
        moved.append(destination)
    return moved
