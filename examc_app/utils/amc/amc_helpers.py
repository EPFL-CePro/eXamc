"""
AMC helper utilities.

This module contains small shared helpers used by the AMC integration layer.
Its responsibilities are intentionally narrow:

- build AMC project paths from an ``Exam``
- expose the canonical AMC question and answer identifiers used by Django
- centralize common file path helpers for compiled artifacts
- provide a few safety/convenience helpers for filesystem operations

Important:
    The identifier helpers in this module are part of the contract between
    Django-side data and the generated LaTeX/AMC output. If the LaTeX naming
    convention changes, these helpers must be updated at the same time.
"""

import os
from pathlib import Path
from typing import Optional

from examc import settings
from examc_app.models import Exam, PrepQuestion, PrepQuestionAnswer


def get_amc_project_path(exam, even_if_not_exist):
    """
    Return the persistent AMC project folder for an exam.

    The path is derived from the configured AMC root and the exam academic
    context (year, semester, code, date). This folder is used as the long-lived
    project workspace that stores the latest generated LaTeX sources and the
    latest promoted AMC artifacts.

    Args:
        exam: Exam instance.
        even_if_not_exist: When ``True``, return the computed path even if the
            directory does not exist yet. When ``False``, return ``None`` if the
            directory is missing.

    Returns:
        str | None: The AMC project path, or ``None`` when the directory is
        required to exist but is missing.
    """
    amc_project_path = str(settings.AMC_PROJECTS_ROOT) + "/" + str(exam.year.code) + "/" + str(exam.semester.code) + "/" + exam.code + "_" + exam.date.strftime("%Y%m%d")

    print('****************** amc_project_path : ' + amc_project_path)
    if os.path.isdir(amc_project_path):
        return amc_project_path
    elif even_if_not_exist:
        return amc_project_path
    else:
        return None

# ---------------------------------------------------------------------------
# AMC ID HELPERS (SINGLE SOURCE OF TRUTH)
# ---------------------------------------------------------------------------

def get_amc_question_id(question: PrepQuestion) -> str:
    """
    Build the canonical AMC question identifier for a preparation question.

    This identifier must stay aligned with LaTeX generation because it is later
    used to map compiled AMC artifacts back onto Django snapshot rows.

    Example:
        SECTION-1-SCQ-3
    """
    return (
        f"SECTION-{question.prep_section.position}-"
        f"{question.question_type.code}-{question.position}"
    )



def get_amc_answer_code(
    question: PrepQuestion,
    answer: PrepQuestionAnswer,
) -> str:
    """
    Build the canonical Django-side answer identifier for an answer choice.

    AMC itself mainly relies on numeric answer order, but Django keeps this
    additional stable identifier so layout/scoring data can be mapped back to
    the frozen build snapshot in a readable way.

    Example:
        SECTION-1-SCQ-3-A2
    """
    return f"{get_amc_question_id(question)}-A{answer.position}"


# ---------------------------------------------------------------------------
# BUILD / PATH HELPERS
# ---------------------------------------------------------------------------

def get_exam_build_base_path(exam: Exam, base_dir: str) -> Path:
    """
    Return the root folder that stores all build versions for an exam.

    Example:
        /data/amc/exams/{exam.code}/
    """
    return Path(base_dir) / f"{exam.code}"



def get_exam_build_path(exam: Exam, version: int, base_dir: str) -> Path:
    """
    Return the folder for one specific exam build version.

    Example:
        /data/amc/exams/MATH101/build_1/
    """
    return get_exam_build_base_path(exam, base_dir) / f"build_{version}"



def get_exam_latex_main_file(build_path: Path) -> Path:
    """
    Return the main LaTeX file for an AMC build/project folder.
    """
    return build_path / "exam.tex"



def get_exam_pdf_path(build_path: Path) -> Path:
    """
    Return the canonical compiled PDF path inside an AMC build/project folder.
    """
    return build_path / "amc-compiled.pdf"



def get_amc_log_path(build_path: Path) -> Path:
    """
    Return the canonical AMC log path inside an AMC build/project folder.
    """
    return build_path / "amc-compiled.amc"



def get_xy_path(build_path: Path) -> Path:
    """
    Return the canonical AMC layout XY path inside an AMC build/project folder.
    """
    return build_path / "calage.xy"


# ---------------------------------------------------------------------------
# SAFETY HELPERS
# ---------------------------------------------------------------------------

def ensure_directory(path: Path) -> None:
    """
    Create a directory and its parents if they do not already exist.
    """
    path.mkdir(parents=True, exist_ok=True)



def safe_str(value: Optional[str]) -> str:
    """
    Return an empty string instead of ``None``.

    This is mainly useful when serializing values, building debug output, or
    composing paths/log messages that should not contain ``None``.
    """
    return value or ""
