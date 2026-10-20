"""
AMC exam build pipeline.

This module is the orchestration layer for converting the current Django exam
preparation state into persistent AMC artifacts, recorded by an ``ExamBuild``.

Main responsibilities:
- compute a stable hash of the preparation source content
- create the ``ExamBuild`` of a generation
- compile AMC artifacts in an isolated temporary workspace
- promote successful outputs back into the persistent project folder
- keep SUBJECT artifacts as the canonical output of the build
- have AMC read the layout and the scoring strategy of the subject (register_exam_in_amc)

Important invariants:
- subject compilation is canonical for the paths of the build
- catalog compilation is only a convenience artifact
- temporary workspace files should not be stored on the build after promotion
"""

import contextvars
import math
import re
import shutil
import subprocess
import tempfile
import threading
import time
from hashlib import sha256
from pathlib import Path

from django.conf import settings
from django.db import connection, transaction
from django.db.models import Max
from django.utils import timezone

from examc_app.exceptions.amc import AmcDbManagerError
from examc_app.models import (
    Exam,
    ExamBuild,
)
from examc_app.services.student.prep_amc_csv import StudentsCsvError, write_students_csv
from examc_app.utils.amc.amc_helpers import (
    get_amc_answer_code,
    get_amc_question_id,
    get_exam_latex_main_file,
)
from examc_app.utils.amc.amc_layout_functions import get_pages_by_copy_from_xy
from examc_app.utils.amc_db_queries.layout import AmcLayoutDbManager
from examc_app.utils.amc_functions import get_amc_project_path
from examc_app.utils.preparation_latex_functions import update_exam_latex

# ---------------------------------------------------------------------------
# Build helpers
# ---------------------------------------------------------------------------

def get_next_exam_build_version(exam: Exam) -> int:
    """
    Return the next monotonically increasing build version number for an exam.
    """
    max_version = exam.builds.aggregate(max_version=Max("version"))["max_version"] or 0
    return max_version + 1



def compute_exam_source_hash(exam: Exam) -> str:
    """
    Compute a deterministic hash of the exam preparation content.

    The hash is based on the main exam metadata plus the ordered tree of
    sections, questions, and answers. It can be used to detect whether two
    builds were produced from identical source content.

    Returns:
        str: SHA-256 hex digest.
    """
    chunks = [
        f"exam:{exam.pk}",
        f"exam_code:{exam.code}",
        f"exam_name:{exam.name}",
        f"exam_date:{exam.date.isoformat() if exam.date else ''}",
        f"exam_duration:{exam.duration or ''}",
        f"first_page:{getattr(exam, 'first_page_text', '') or ''}",
    ]

    sections = exam.prepSections.order_by("position", "pk").prefetch_related(
        "prepQuestions__prepAnswers",
        "prepQuestions__question_type",
    )

    for section in sections:
        chunks.extend(
            [
                f"section_pk:{section.pk}",
                f"section_position:{section.position}",
                f"section_title:{section.title or ''}",
                f"section_text:{section.section_text or ''}",
                f"section_random_questions:{int(section.random_questions)}",
                f"section_start_on_new_page:{int(section.start_on_new_page)}",
            ]
        )

        for question in section.prepQuestions.order_by("position", "pk"):
            question_type_code = question.question_type.code if question.question_type else ""

            chunks.extend(
                [
                    f"question_pk:{question.pk}",
                    f"question_id:{get_amc_question_id(question)}",
                    f"question_type:{question_type_code}",
                    f"question_position:{question.position}",
                    f"question_title:{question.title or ''}",
                    f"question_text:{question.question_text or ''}",
                    f"question_random_answers:{int(question.random_answers)}",
                    f"question_max_points:{question.max_points}",
                    f"question_point_increment:{question.point_increment or ''}",
                ]
            )

            for answer in question.prepAnswers.order_by("position", "pk"):
                chunks.extend(
                    [
                        f"answer_pk:{answer.pk}",
                        f"answer_code:{get_amc_answer_code(question, answer)}",
                        f"answer_position:{answer.position}",
                        f"answer_title:{answer.title or ''}",
                        f"answer_text:{answer.answer_text or ''}",
                        f"answer_is_correct:{int(answer.is_correct)}",
                        f"answer_box_type:{answer.box_type or ''}",
                        f"answer_box_height_mm:{answer.box_height_mm if answer.box_height_mm is not None else ''}",
                    ]
                )

    # The students list (students.csv): one copy per student
    for student in exam.prepStudents.order_by("copy_no", "pk"):
        chunks.append(
            f"student:{student.copy_no}|{student.sciper}|{student.last_name}|{student.first_name}|"
            f"{student.email or ''}|{student.section or ''}|{student.room or ''}|{student.seat}"
        )

    payload = "\n".join(chunks)
    return sha256(payload.encode("utf-8")).hexdigest()


@transaction.atomic
def create_exam_build(
    exam: Exam,
    user=None,
    *,
    lock_build: bool = False,
    latex_engine: str = "pdflatex",
    project_path: str = "",
    latex_main_path: str = "",
) -> ExamBuild:
    """
    Create the ``ExamBuild`` of a generation, with the hash of the preparation content it starts from.

    Returns:
        ExamBuild: Newly created build in ``draft`` status.
    """
    return ExamBuild.objects.create(
        exam=exam,
        version=get_next_exam_build_version(exam),
        status="draft",
        is_locked=lock_build,
        locked_at=timezone.now() if lock_build else None,
        requested_by=user,
        source_hash=compute_exam_source_hash(exam),
        latex_engine=latex_engine,
        project_path=project_path or "",
        latex_main_path=latex_main_path or "",
    )


@transaction.atomic
def mark_exam_build_building(build: ExamBuild) -> ExamBuild:
    """
    Mark a build as currently compiling.
    """
    build.status = "building"
    build.save(update_fields=["status", "updated_at"])
    return build


@transaction.atomic
def mark_exam_build_ready(
    build: ExamBuild,
    *,
    compiled_pdf_path: str = "",
    amc_log_path: str = "",
    xy_path: str = "",
    build_log: str = "",
    lock_build: bool = False,
) -> ExamBuild:
    """
    Mark a build as ready and persist the canonical artifact paths.

    Only subject artifacts should be stored as canonical DB-facing paths.
    """
    build.status = "ready"

    if compiled_pdf_path:
        build.compiled_pdf_path = compiled_pdf_path
    if amc_log_path:
        build.amc_log_path = amc_log_path
    if xy_path:
        build.xy_path = xy_path
    if build_log:
        build.build_log = build_log

    if lock_build:
        if not build.is_locked:
            build.is_locked = True
            build.locked_at = timezone.now()

    build.save(
        update_fields=[
            "status",
            "compiled_pdf_path",
            "amc_log_path",
            "xy_path",
            "build_log",
            "is_locked",
            "locked_at",
            "updated_at",
        ]
    )
    return build


@transaction.atomic
def mark_exam_build_error(build: ExamBuild, error_message: str, build_log: str = "") -> ExamBuild:
    """
    Mark a build as failed and persist the error details.
    """
    build.status = "error"
    build.error_message = error_message or ""
    if build_log:
        build.build_log = build_log

    build.save(
        update_fields=[
            "status",
            "error_message",
            "build_log",
            "updated_at",
        ]
    )
    return build


# ---------------------------------------------------------------------------
# Compile helpers
# ---------------------------------------------------------------------------

def write_amc_config_file(
    workspace_path: Path,
    *,
    sujet_externe: bool = False,
    catalog_externe: bool = False,
    student_file: str = "student_prev.csv",
) -> Path:
    """
    Write the AMC configuration include used for one compilation mode.

    Args:
        workspace_path: Temporary compilation workspace.
        sujet_externe: Whether subject mode should be enabled.
        catalog_externe: Whether catalog mode should be enabled.
        student_file: Student CSV file to expose to the LaTeX build.

    Returns:
        Path: Created config file path.
    """
    config_path = workspace_path / "amc-compiled-config.tex"

    lines = [
        r"\def\NoWatermarkExterne{1}",
        r"\def\NoHyperRef{1}",
        rf"\def\AMCStudentFile{{{student_file}}}",
    ]

    if sujet_externe:
        lines.append(r"\def\SujetExterne{1}")

    if catalog_externe:
        lines.append(r"\def\CatalogExterne{1}")

    config_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return config_path


IGNORED_BUILD_FILES = {
    "amc-compiled.pdf",
    "amc-compiled.amc",
    "amc-compiled.log",
    "amc-compiled.aux",
    "amc-compiled.xy",
    "calage.xy",
    "amc-compiled-config.tex",
    "subject.log",
    "subject.amc",
    "catalog.log",
    "catalog.amc",
}


def copy_project_to_workspace(source_project_path: str, workspace_path: Path) -> None:
    """
    Copy the persistent AMC project into a temporary workspace.

    Generated artifacts listed in ``IGNORED_BUILD_FILES`` are skipped so the
    workspace always recompiles from the current sources instead of inheriting
    stale outputs.
    """
    source_path = Path(source_project_path)
    if not source_path.exists():
        raise FileNotFoundError(f"AMC project path does not exist: {source_path}")

    for item in source_path.iterdir():
        if item.name in IGNORED_BUILD_FILES:
            continue

        destination = workspace_path / item.name
        if item.is_dir():
            shutil.copytree(item, destination)
        else:
            shutil.copy2(item, destination)



def _read_log_file_if_exists(log_path: Path) -> str:
    """
    Read a log file if present, returning an empty string otherwise.
    """
    if not log_path.exists():
        return ""
    try:
        return log_path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ""



def _ensure_xy_output(workspace_path: Path) -> Path | None:
    """
    Normalize the expected XY output file name.

    Preference order:
    - copy ``amc-compiled.xy`` (written by the compilation just done) to ``calage.xy``
    - otherwise use ``calage.xy`` if it already exists

    The ``calage.xy`` of an earlier compilation of the same build must not be kept: its pages would not be those
    of the PDF ("PDF/XY page mismatch").

    Returns:
        Path | None: Normalized ``calage.xy`` path when available.
    """
    calage_xy = workspace_path / "calage.xy"
    compiled_xy = workspace_path / "amc-compiled.xy"

    if compiled_xy.exists():
        shutil.copy2(compiled_xy, calage_xy)
        return calage_xy

    if calage_xy.exists():
        return calage_xy

    return None



# pdflatex prints "[<page number>" on its output when it ships a page out ("[2021/..." of the package
# dates excluded). AMC numbers the pages of each copy from 1: the markers are counted, not read.
PAGE_SHIPOUT_RE = re.compile(r"\[(\d+)(?=[\s\]{<]|$)")


class BuildCancelled(Exception):
    """The user asked to stop the final generation."""


# Set by build_final_exam: returns True when the user asked to stop the generation. Checked between the steps
# (_report_progress) and, while LaTeX compiles, every CANCEL_POLL_SECONDS (the compilation is then killed).
_should_cancel = contextvars.ContextVar("examc_should_cancel", default=None)
CANCEL_POLL_SECONDS = 1.0


def _raise_if_cancelled():
    should_cancel = _should_cancel.get()
    if should_cancel and should_cancel():
        raise BuildCancelled("The generation was cancelled.")


def _run_latex(cmd: list[str], cwd: Path, timeout: int, on_page=None) -> tuple[int | None, str]:
    """
    Runs a LaTeX command, reading its output while it compiles: `on_page(pages)` is called with the number of
    pages shipped out so far. Returns (return code, output), the return code being None after `timeout` seconds
    (the process is then killed). Raises BuildCancelled (process killed) when the user asked to stop.
    """
    process = subprocess.Popen(
        cmd,
        cwd=str(cwd),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        errors="replace",
    )
    timed_out = threading.Event()

    def kill():
        timed_out.set()
        process.kill()

    timer = threading.Timer(timeout, kill)
    timer.start()
    should_cancel = _should_cancel.get()
    cancelled = threading.Event()
    finished = threading.Event()

    def watch_cancel():
        try:
            while not finished.wait(CANCEL_POLL_SECONDS):
                if should_cancel():
                    cancelled.set()
                    process.kill()
                    return
        finally:
            # should_cancel reads the database: the connection of this thread is not left open
            connection.close()

    watcher = threading.Thread(target=watch_cancel, daemon=True) if should_cancel else None
    if watcher:
        watcher.start()
    output = []
    pages = 0
    try:
        for line in process.stdout:
            output.append(line)
            shipped = len(PAGE_SHIPOUT_RE.findall(line))
            if shipped and on_page:
                pages += shipped
                on_page(pages)
        process.wait()
    finally:
        finished.set()
        timer.cancel()
        if process.poll() is None:
            process.kill()
    if cancelled.is_set():
        raise BuildCancelled("The generation was cancelled.")
    return (None if timed_out.is_set() else process.returncode), "".join(output)


# The qrcode package computes each QR code in TeX (~0.15 s each, one per page of each copy) and saves it in the
# .aux file, where the next compilation reads it back. The QR codes are keyed by their text ("...,<ID>,<page>"):
# when the students or the pages change, the missing ones are computed and the others are no longer written.
QR_CACHE_LINE_PREFIXES = ("\\ifx\\qr@savematrix", "\\qr@savematrix{")


def read_qr_cache(aux_path: Path) -> list[str]:
    """The QR code lines of a LaTeX .aux file (and the line defining their macro), nothing else of it."""
    try:
        lines = aux_path.read_text(encoding="latin-1").splitlines()
    except OSError:
        return []
    return [line for line in lines if line.startswith(QR_CACHE_LINE_PREFIXES)]


def seed_qr_cache(workspace_path: Path, qr_cache: list[str]) -> None:
    """Writes the .aux of the next compilation with only the QR codes of `qr_cache`."""
    if qr_cache:
        (workspace_path / "amc-compiled.aux").write_text("\\relax\n" + "\n".join(qr_cache) + "\n",
                                                         encoding="latin-1")


def compile_exam_in_workspace(
    workspace_path: Path,
    *,
    timeout: int = 60,
    latex_engine: str = "pdflatex",
    mode: str = "subject",
    on_page=None,
) -> dict:
    """
    Compile an exam in a temporary workspace.

    Supported modes:
    - ``subject``: uses ``students.csv`` and produces canonical layout artifacts
    - ``catalog``: uses ``student_prev.csv`` and produces a one-copy catalog PDF

    ``on_page(pages)`` is called while compiling with the number of pages produced so far.

    Returns:
        dict: Success flag, paths, logs, and error/status details.
    """
    main_tex = get_exam_latex_main_file(workspace_path)
    if not main_tex.exists():
        return {
            "ok": False,
            "error": f"Main LaTeX file not found: {main_tex}",
            "status": 400,
            "build_log": "",
        }

    if mode == "subject":
        write_amc_config_file(
            workspace_path,
            sujet_externe=True,
            catalog_externe=False,
            student_file="students.csv",
        )
    elif mode == "catalog":
        write_amc_config_file(
            workspace_path,
            sujet_externe=False,
            catalog_externe=True,
            student_file="student_prev.csv",
        )
    else:
        return {
            "ok": False,
            "error": f"Unknown compile mode: {mode}",
            "status": 400,
            "build_log": "",
        }

    cmd = [
        latex_engine,
        "--jobname=amc-compiled",
        "-interaction=nonstopmode",
        "-halt-on-error",
        main_tex.name,
    ]

    try:
        returncode, output = _run_latex(cmd, workspace_path, timeout, on_page)
    except FileNotFoundError:
        return {
            "ok": False,
            "error": f"LaTeX engine not found: {latex_engine}",
            "status": 500,
            "build_log": "",
        }

    pdf_path = workspace_path / "amc-compiled.pdf"
    amc_log_path = workspace_path / "amc-compiled.amc"
    tex_log_path = workspace_path / "amc-compiled.log"
    xy_path = _ensure_xy_output(workspace_path)

    build_log = _read_log_file_if_exists(tex_log_path)

    if returncode is None:
        return {
            "ok": False,
            "error": f"Compilation timeout ({timeout} s)",
            "status": 500,
            "build_log": build_log,
        }

    if returncode != 0 or not pdf_path.exists():
        error_message = output or build_log or "LaTeX compilation failed"
        return {
            "ok": False,
            "error": error_message,
            "status": 400,
            "build_log": build_log,
        }

    renamed_log_path = workspace_path / f"{mode}.log"
    renamed_amc_path = workspace_path / f"{mode}.amc"

    if tex_log_path.exists():
        shutil.copy2(tex_log_path, renamed_log_path)

    if amc_log_path.exists():
        shutil.copy2(amc_log_path, renamed_amc_path)

    return {
        "ok": True,
        "status": 200,
        "build_log": build_log,
        "pdf_path": str(pdf_path),
        "amc_log_path": str(amc_log_path) if amc_log_path.exists() else "",
        "xy_path": str(xy_path) if xy_path else "",
        "renamed_log_path": str(renamed_log_path) if renamed_log_path.exists() else "",
        "renamed_amc_path": str(renamed_amc_path) if renamed_amc_path.exists() else "",
    }


# ---------------------------------------------------------------------------
# Persistent project promotion
# ---------------------------------------------------------------------------


PERSISTENT_AMC_FILES = [
    "exam.tex",
    "first_page.tex",
    "packages.tex",
    "commands.tex",
    "global_scoring.tex",
    "amc-compiled.pdf",
    "amc-compiled.amc",
    "amc-compiled.log",
    "amc-compiled.aux",
    "amc-compiled-config.tex",
    "amc-compiled.xy",
    "calage.xy",
    "subject.log",
    "subject.amc",
    "catalog.log",
    "catalog.amc",
]


def _safe_exam_prefix(exam: Exam) -> str:
    """
    Return a filesystem-safe exam prefix, falling back to ``exam-{pk}``.
    """
    return exam.code or f"exam-{exam.pk}"



def promote_workspace_to_project(
    workspace_path: Path,
    persistent_project_path: str,
    exam: Exam,
) -> dict:
    """
    Promote the successful temporary AMC workspace back into the persistent
    per-exam AMC project folder.

    Design intent
    -------------
    The persistent AMC project folder must always end in the canonical
    SUBJECT state after a successful final build.

    This helper is therefore used only after the full final pipeline has run,
    with the following expected compile order:

    1. CATALOG
    2. SUBJECT (final canonical state, unless some copies are longer)
    3. SUBJECT again when some copies are longer (final canonical state)

    Because SUBJECT is compiled last, the workspace already contains the
    final AMC config/data/log state that later features depend on.
    This helper copies that state back into the persistent project folder.

    Canonical rules
    ---------------
    - SUBJECT is canonical and drives downstream processing.
    - CATALOG is kept only as a side artifact PDF/log pair.
    - Returned canonical paths must point to SUBJECT artifacts only.
    - The generic AMC files in ``PERSISTENT_AMC_FILES`` are copied from the
      final workspace state, which must therefore be the final SUBJECT state.

    Args:
        workspace_path:
            Temporary AMC workspace containing the successful final build.
        persistent_project_path:
            Persistent per-exam AMC project directory to replace/update.
        exam:
            Exam instance used to derive the artifact prefix.

    Returns:
        dict:
            Promoted project paths and artifact paths. Canonical output fields
            such as ``compiled_pdf_path``, ``amc_log_path``, and ``xy_path``
            always point to SUBJECT artifacts.
    """
    project_path = Path(persistent_project_path)
    project_path.mkdir(parents=True, exist_ok=True)

    prefix = _safe_exam_prefix(exam)

    # Files explicitly managed by this promotion step.
    #
    # PERSISTENT_AMC_FILES contains the generic AMC project files that must
    # reflect the final workspace state. Since SUBJECT is compiled last in the
    # final build pipeline, these generic files are expected to represent the
    # final SUBJECT configuration.
    managed_names = set(PERSISTENT_AMC_FILES)
    managed_names.update(
        {
            f"{prefix}-sujet.pdf",
            f"{prefix}-catalog.pdf",
            f"{prefix}-calage.xy",
        }
    )

    # Remove previous managed files so promotion behaves like a clean replace
    # for all artifacts owned by the final build process.
    for name in managed_names:
        target = project_path / name
        if target.exists():
            if target.is_dir():
                shutil.rmtree(target)
            else:
                target.unlink()

    # Copy the generic AMC project state first.
    #
    # Important: this relies on the workspace already being in final SUBJECT
    # state when this function is called.
    for name in PERSISTENT_AMC_FILES:
        source = workspace_path / name
        if source.exists():
            shutil.copy2(source, project_path / name)

    # Copy named promoted artifacts explicitly.
    subject_pdf = workspace_path / f"{prefix}-sujet.pdf"
    catalog_pdf = workspace_path / f"{prefix}-catalog.pdf"
    subject_xy = workspace_path / f"{prefix}-calage.xy"

    if subject_pdf.exists():
        shutil.copy2(subject_pdf, project_path / subject_pdf.name)

    if catalog_pdf.exists():
        shutil.copy2(catalog_pdf, project_path / catalog_pdf.name)

    if subject_xy.exists():
        shutil.copy2(subject_xy, project_path / subject_xy.name)

    # Canonical return values MUST point to subject artifacts only.
    final_subject_pdf_path = project_path / f"{prefix}-sujet.pdf"
    final_catalog_pdf_path = project_path / f"{prefix}-catalog.pdf"
    final_subject_xy_path = project_path / f"{prefix}-calage.xy"
    final_subject_amc_path = project_path / "subject.amc"
    final_subject_log_path = project_path / "subject.log"
    final_catalog_amc_path = project_path / "catalog.amc"
    final_catalog_log_path = project_path / "catalog.log"

    return {
        "project_path": str(project_path),

        # Canonical outputs: always SUBJECT
        "compiled_pdf_path": str(final_subject_pdf_path) if final_subject_pdf_path.exists() else "",
        "amc_log_path": str(final_subject_amc_path) if final_subject_amc_path.exists() else "",
        "xy_path": str(final_subject_xy_path) if final_subject_xy_path.exists() else "",

        # Explicit named artifacts
        "subject_pdf_path": str(final_subject_pdf_path) if final_subject_pdf_path.exists() else "",
        "catalog_pdf_path": str(final_catalog_pdf_path) if final_catalog_pdf_path.exists() else "",
        "exam_calage_xy_path": str(final_subject_xy_path) if final_subject_xy_path.exists() else "",

        # Subject logs/config
        "subject_log_path": str(final_subject_log_path) if final_subject_log_path.exists() else "",
        "subject_amc_path": str(final_subject_amc_path) if final_subject_amc_path.exists() else "",

        # Catalog logs/config
        "catalog_log_path": str(final_catalog_log_path) if final_catalog_log_path.exists() else "",
        "catalog_amc_path": str(final_catalog_amc_path) if final_catalog_amc_path.exists() else "",
    }

# ---------------------------------------------------------------------------
# AMC databases (layout.sqlite, scoring.sqlite)
# ---------------------------------------------------------------------------


class AmcStepError(Exception):
    """An AMC command of the final generation failed: the message is shown to the user."""


# The lines AMC prints for the problems of the exam (questions, LaTeX...) and the warnings
AMC_MESSAGE_RE = re.compile(r"^(ERR|WARN):\s*(.*)$", re.MULTILINE)
AMC_OUTPUT_TAIL = 1500
AMC_LAYOUT_TIMEOUT = 600


def _run_amc_step(command: list[str], cwd: Path, timeout: int, label: str) -> list[str]:
    """
    Runs one AMC command: returns its warnings, raises AmcStepError with its errors when it failed, and
    BuildCancelled when the user asked to stop.
    """
    returncode, output = _run_latex(command, cwd, timeout)
    messages = AMC_MESSAGE_RE.findall(output)
    errors = [text for kind, text in messages if kind == "ERR"]
    warnings = [text for kind, text in messages if kind == "WARN"]

    if returncode is None:
        raise AmcStepError(f"AMC: {label} timed out after {timeout} s.")
    if returncode != 0 or errors:
        details = " ".join(errors) or output.strip()[-AMC_OUTPUT_TAIL:] or f"exit code {returncode}"
        raise AmcStepError(f"AMC: {label} failed. {details}")
    return warnings


def _copy_amc_sources(project_path: Path, destination: Path) -> None:
    """
    Copies what AMC needs to read the exam (the LaTeX sources, the students list, the options and the media), and
    not the generated documents: AMC compiles in the folder of the source, and its compilation must not replace the
    SUBJECT state kept in the project (amc-compiled.*, amc-compiled-config.tex).
    """
    for item in project_path.iterdir():
        if item.is_dir():
            if item.name == "media":
                shutil.copytree(item, destination / item.name)
        elif item.name not in IGNORED_BUILD_FILES and item.suffix not in (".pdf", ".xy"):
            shutil.copy2(item, destination / item.name)


def _extract_scoring_in_amc(exam: Exam, project_path: Path, data_path: Path, expected_pages: int, timeout: int) -> list[str]:
    """
    ``prepare --mode b``: AMC compiles the sources once more and extracts the scoring strategy of every copy in
    ``data/scoring.sqlite``. It reads the layout, so ``data/layout.sqlite`` must exist. It runs in a copy of the sources
    (AMC compiles in the folder of the source): the project keeps its SUBJECT state.
    """
    Path(settings.AMC_TMP_ROOT).mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=settings.AMC_TMP_ROOT, prefix=f"amc_scoring_{exam.pk}_") as tmp_dir:
        sources_path = Path(tmp_dir)
        _copy_amc_sources(project_path, sources_path)
        # The QR codes of the subject compiled by the final generation: computing them in TeX takes ~0.15 s per page
        seed_qr_cache(sources_path, read_qr_cache(project_path / "amc-compiled.aux"))
        return _run_amc_step(
            [
                "auto-multiple-choice", "prepare",
                "--mode", "b",
                "--data", f"{data_path}/",
                "--with", "pdflatex",
                "--filter", "latex",
                "--prefix", f"{sources_path}/",
                str(sources_path / "exam.tex"),
            ],
            sources_path, _compile_timeout(timeout, expected_pages), "the extraction of the scoring strategy")


def update_scoring_in_amc(exam: Exam, *, timeout: int = 60, should_cancel=None, progress_callback=None) -> list[str]:
    """
    Extracts again the scoring strategy of an exam whose final files were generated, after its scoring formulas changed
    (the LaTeX files of the project must have been rewritten, see update_exam_scoring_latex). The scoring does not
    change the layout: only ``data/scoring.sqlite`` is rewritten.

    Returns the warnings of AMC. Raises AmcStepError when the layout of the exam is not in the project (the final
    generation did not register it in AMC) or when AMC fails.
    """
    project_path = Path(get_amc_project_path(exam, False))
    data_path = project_path / "data"
    try:
        with AmcLayoutDbManager(amc_data_path=f"{data_path}/") as layout_db:
            pages = layout_db.select_count_layout_pages()
    except AmcDbManagerError:
        pages = 0
    if not pages:
        raise AmcStepError("AMC: the layout of this exam is not in its project: unlock the editing and generate the "
                           "final files again before changing the scoring.")

    token = _should_cancel.set(should_cancel)
    try:
        _report_progress(progress_callback, 10, "Extracting the scoring strategy with AMC...")
        return _extract_scoring_in_amc(exam, project_path, data_path, pages, timeout)
    finally:
        _should_cancel.reset(token)


def register_exam_in_amc(
    exam: Exam,
    xy_path: str,
    *,
    expected_pages: int,
    timeout: int = 60,
    should_cancel=None,
    progress_callback=None,
) -> list[str]:
    """
    Feeds the databases of the AMC project with the exam just generated, as AMC does itself, so that the scans and the
    marks are processed by AMC:

    1. the layout (``meptex`` reads the SUBJECT XY file: ``data/layout.sqlite``),
    2. the scoring strategy (``prepare --mode b`` compiles the sources once more: ``data/scoring.sqlite``). It reads
       the layout, so it comes second, and runs in a copy of the sources: the project keeps its SUBJECT state.

    Returns the warnings of AMC. Raises AmcStepError when AMC fails or does not find the pages of the PDF (its
    message is shown to the user), and BuildCancelled when the user asked to stop.
    """
    project_path = Path(get_amc_project_path(exam, False))
    data_path = project_path / "data"
    data_path.mkdir(exist_ok=True)

    token = _should_cancel.set(should_cancel)
    try:
        _report_progress(progress_callback, 92, "Detecting the layout with AMC...")
        warnings = _run_amc_step(
            ["auto-multiple-choice", "meptex", "--src", str(xy_path), "--data", f"{data_path}/"],
            project_path, AMC_LAYOUT_TIMEOUT, "the layout detection")

        with AmcLayoutDbManager(amc_data_path=f"{data_path}/") as layout_db:
            detected_pages = layout_db.select_count_layout_pages()
        if detected_pages != expected_pages:
            raise AmcStepError(
                f"AMC: the layout detection found {detected_pages} pages, but the subject has {expected_pages}.")

        _report_progress(progress_callback, 94, "Extracting the scoring strategy with AMC...")
        warnings += _extract_scoring_in_amc(exam, project_path, data_path, expected_pages, timeout)
    finally:
        _should_cancel.reset(token)

    return warnings


# --------------------------------------------------------------------------
# Progress helper
# --------------------------------------------------------------------------
def _report_progress(progress_callback, percent, message):
    _raise_if_cancelled()
    if progress_callback:
        progress_callback(percent=percent, message=message)


# Seconds allowed to a compilation: ~0.3 s per page is measured (QR codes not cached), 1 s per page is allowed
LATEX_BASE_TIMEOUT = 120
LATEX_SECONDS_PER_PAGE = 1


def _compile_timeout(timeout: int, expected_pages: int) -> int:
    return max(timeout, LATEX_BASE_TIMEOUT + LATEX_SECONDS_PER_PAGE * expected_pages)


def _page_progress(
        progress_callback, start: int, end: int, label: str, copies: int, pages_per_copy: int, min_interval: float = 2.0
):
    """
    on_page callback of compile_exam_in_workspace: reports "<label>: copy X / N" with a percent from `start` to
    `end`, at most every `min_interval` seconds. `pages_per_copy` may be an estimate (before the first subject
    compilation): the percent then stops just before `end`.
    """
    expected_pages = max(1, copies * pages_per_copy)
    last_report = [0.0]

    def on_page(pages):
        now = time.monotonic()
        if now - last_report[0] < min_interval:
            return
        last_report[0] = now
        done = min(1.0, pages / expected_pages)
        copy = min(copies, math.ceil(pages / max(1, pages_per_copy)))
        _report_progress(progress_callback, start + int((end - 1 - start) * done), f"{label}: copy {copy} / {copies}")

    return on_page

# ---------------------------------------------------------------------------
# Main entrypoint
# ---------------------------------------------------------------------------
# IMPORTANT:
# Final generation intentionally compiles CATALOG first and SUBJECT last.
# SUBJECT must remain the canonical retained AMC project state because
# later features (layout extraction, scan processing, downstream data usage)
# depend on subject files/config remaining in place after the build.
# Written in the LaTeX log for each copy by \\examcPadPages (exam_template.tex): the pages of its content
COPY_PAGES_RE = re.compile(r"^EXAMC-COPY-PAGES=(\d+)", re.MULTILINE)


def read_copy_pages_from_log(log: str) -> list[int]:
    """The pages of the content of each copy (before the blank pages), in the order of the copies."""
    return [int(pages) for pages in COPY_PAGES_RE.findall(log or "")]


def round_pages_per_copy(pages: int, booklet: bool) -> int:
    """The pages of a copy: a multiple of 4 for a booklet (A3 folded), see \\examcPadPages."""
    return math.ceil(pages / 4) * 4 if booklet else pages


def exam_has_shuffling(exam: Exam) -> bool:
    """True when the questions or the answers of some copies are in random order (their length then varies)."""
    return (exam.prepSections.filter(random_questions=True).exists()
            or exam.prepSections.filter(prepQuestions__random_answers=True).exists())


def longer_copies_warning(copy_pages: list[int], estimated: int, final: int, shuffled: bool,
                          booklet: bool, max_listed: int = 10) -> str:
    """Why all the copies were padded to `final` pages instead of `estimated` (the pages of the catalog copy).
    `copy_pages` are the pages of the content of each copy (see read_copy_pages_from_log)."""
    longer = [copy for copy, pages in enumerate(copy_pages, start=1) if pages > estimated]
    listed = ", ".join(str(copy) for copy in longer[:max_listed])
    if len(longer) > max_listed:
        listed += f" and {len(longer) - max_listed} others"
    reason = ("the questions or the answers are in random order, so the length of the copies varies"
              if shuffled else "their content is longer than the one of the catalog copy")
    pages_text = f"{final} pages" + (" (a multiple of 4 for the booklet)" if booklet else "")
    return (
        f"{len(longer)} {'copy has' if len(longer) == 1 else 'copies have'} more than {estimated} pages "
        f"(copy {listed}) because {reason}. All the copies were padded with blank pages to {pages_text}, "
        f"which needed a second compilation of the subject."
    )


def build_final_exam(
    exam: Exam,
    user=None,
    *,
    timeout: int = 60,
    latex_engine: str = "pdflatex",
    progress_callback=None,
    should_cancel=None,
) -> ExamBuild:
    """
    Build the final AMC project for one exam.

    `should_cancel()` returns True when the user asked to stop: BuildCancelled is raised (the build is then marked
    as failed, and the compilation running is killed).

    This pipeline intentionally compiles the two AMC modes in the following order:

    1. Generate LaTeX once without a known ``pages_per_copy`` value.
    2. Create and lock an ``ExamBuild``.
    3. Copy the persistent AMC project into a temporary workspace.
    3b. Write the students list ``students.csv`` (PrepStudent) into the persistent project.
    4. Compile CATALOG first using ``student_prev.csv`` (one anonymous copy).
       - This produces only the catalog PDF side artifact.
       - It must never become the canonical build state.
       - Its number of pages estimates ``pages_per_copy`` (multiple of 4 for a booklet).
    5. Regenerate LaTeX with the estimated ``pages_per_copy`` and compile SUBJECT using ``students.csv``: the
       copies are padded to this number of pages, and their first page shows it.
    6. Read the subject XY file: when no copy is longer than the estimate (the usual case), this compilation is
       the canonical build output. Otherwise (shuffled questions or answers...), LaTeX is regenerated with the
       real ``pages_per_copy`` and SUBJECT is compiled again, and a warning tells it (``build.build_warnings``).
    7. Promote successful workspace artifacts back to the persistent project.
    8. Bind canonical ``ExamBuild`` paths to SUBJECT artifacts only.

    Important invariants:
    - SUBJECT is always the canonical final build state.
    - CATALOG is kept only as a side artifact: ``{prefix}-catalog.pdf``.
    - Layout extraction and downstream processing must always use SUBJECT XY.
    - The persistent AMC project folder must end in SUBJECT state, because
      later features rely on the retained subject config/data files.

    Returns:
        ExamBuild:
            A build in ``ready`` state when the final subject build succeeds,
            otherwise a build in ``error`` state.
    """

    token = _should_cancel.set(should_cancel)
    try:
        return _build_final_exam(exam, user, timeout, latex_engine, progress_callback)
    finally:
        _should_cancel.reset(token)


def _build_final_exam(exam, user, timeout, latex_engine, progress_callback) -> ExamBuild:
    _report_progress(progress_callback, 6, "Preparing AMC workspace...")

    persistent_project_path = get_amc_project_path(exam, False)
    exam_prefix = exam.code or f"exam-{exam.pk}"

    # ------------------------------------------------------------------
    # INITIAL LATEX GENERATION (without final pages_per_copy yet)
    # ------------------------------------------------------------------
    _report_progress(progress_callback, 7, "Generating LaTeX sources...")
    update_exam_latex(exam, pages_per_copy=None)
    _report_progress(progress_callback, 8, "LaTeX sources generated.")

    build = create_exam_build(
        exam=exam,
        user=user,
        lock_build=True,
        latex_engine=latex_engine,
        project_path=persistent_project_path,
        latex_main_path=str(Path(persistent_project_path) / "exam.tex"),
    )
    # Shown to the user at the end of the generation (not saved)
    build.build_warnings = []

    try:
        mark_exam_build_building(build)

        # The students list of the prep module, read by AMC: one copy per student
        _report_progress(progress_callback, 9, "Writing the students list...")
        try:
            write_students_csv(exam, persistent_project_path)
        except StudentsCsvError as error:
            mark_exam_build_error(build, error_message=" ".join(error.errors))
            return build

        Path(settings.AMC_TMP_ROOT).mkdir(parents=True, exist_ok=True)

        with tempfile.TemporaryDirectory(
            dir=settings.AMC_TMP_ROOT,
            prefix=f"amc_exam_{exam.pk}_",
        ) as tmp_dir:
            workspace_path = Path(tmp_dir)

            copy_project_to_workspace(persistent_project_path, workspace_path)

            # QR codes of the previous build (see read_qr_cache), given to each first compilation
            qr_cache = read_qr_cache(Path(persistent_project_path) / "amc-compiled.aux")
            copies = exam.prepStudents.count() or 1

            subject_build_log = ""
            subject_amc_log_path = ""
            subject_xy_path = ""

            # ==========================================================
            # STEP 1 - CATALOG BUILD FIRST
            # ==========================================================
            #
            # Goal:
            # - produce {prefix}-catalog.pdf
            # - do NOT let catalog become canonical project/build state
            #
            # Why first?
            # - we want the final retained state in the workspace/project
            #   to be the SUBJECT state, because later features depend on it.
            # ==========================================================
            _report_progress(progress_callback, 10, "Compiling catalog PDF...")

            # One anonymous copy (no student_prev.csv): its pages estimate the pages per copy
            catalog_pages = [0]
            seed_qr_cache(workspace_path, qr_cache)
            catalog_result = compile_exam_in_workspace(
                workspace_path,
                timeout=_compile_timeout(timeout, 50),
                latex_engine=latex_engine,
                mode="catalog",
                on_page=lambda pages: catalog_pages.__setitem__(0, pages),
            )

            if not catalog_result["ok"]:
                mark_exam_build_error(
                    build,
                    error_message=catalog_result["error"],
                    build_log=catalog_result.get("build_log", ""),
                )
                return build

            catalog_pdf = workspace_path / "amc-compiled.pdf"
            catalog_named_pdf = workspace_path / f"{exam_prefix}-catalog.pdf"
            if catalog_pdf.exists():
                shutil.copy2(catalog_pdf, catalog_named_pdf)

            _report_progress(progress_callback, 12, "Catalog PDF compiled.")
            booklet = exam.print_format == Exam.PRINT_FORMAT_BOOKLET
            # The pages of the content of the catalog copy (pages shipped out with an older exam_template.tex)
            catalog_copy_pages = read_copy_pages_from_log(catalog_result.get("build_log", "")) or catalog_pages
            estimated_pages_per_copy = round_pages_per_copy(max(1, catalog_copy_pages[0]), booklet)

            def refresh_latex(pages_per_copy):
                # The copies are padded up to `pages_per_copy` (\\examcPadPages), shown on their first page
                update_exam_latex(exam, pages_per_copy=pages_per_copy)
                for src in Path(persistent_project_path).glob("*.tex"):
                    shutil.copy2(src, workspace_path / src.name)

            def compile_subject(pages_per_copy, start, end, label):
                """Compiles the subject; returns (build log, AMC log path, XY path), or None when it failed (the
                build is then marked as failed)."""
                _report_progress(progress_callback, start, label + "...")
                result = compile_exam_in_workspace(
                    workspace_path,
                    timeout=_compile_timeout(timeout, copies * pages_per_copy * 2),
                    latex_engine=latex_engine,
                    mode="subject",
                    on_page=_page_progress(progress_callback, start, end, label, copies, pages_per_copy),
                )
                if not result["ok"]:
                    mark_exam_build_error(
                        build,
                        error_message=result["error"],
                        build_log=result.get("build_log", "") or subject_build_log,
                    )
                    return None

                subject_pdf = workspace_path / "amc-compiled.pdf"
                if subject_pdf.exists():
                    shutil.copy2(subject_pdf, workspace_path / f"{exam_prefix}-sujet.pdf")
                subject_xy = workspace_path / "calage.xy"
                subject_named_xy = workspace_path / f"{exam_prefix}-calage.xy"
                if subject_xy.exists():
                    shutil.copy2(subject_xy, subject_named_xy)

                xy_path = str(subject_named_xy) if subject_named_xy.exists() else result.get("xy_path", "")
                if not xy_path:
                    mark_exam_build_error(
                        build,
                        error_message="Subject XY path is missing after subject compilation.",
                        build_log=result.get("build_log", ""),
                    )
                    return None
                return (
                    result.get("build_log", ""),
                    result.get("renamed_amc_path", "") or result.get("amc_log_path", ""),
                    xy_path,
                )

            # ==========================================================
            # STEP 2 - SUBJECT BUILD, PADDED TO THE ESTIMATED PAGES
            # ==========================================================
            #
            # Usually the canonical final state: the copies have the pages of the catalog copy. Only when some
            # copies are longer is the subject compiled again (STEP 3).
            # ==========================================================
            refresh_latex(estimated_pages_per_copy)
            # The catalog compilation rewrote the .aux with its single copy
            seed_qr_cache(workspace_path, qr_cache)
            compiled = compile_subject(estimated_pages_per_copy, 12, 80, "Compiling subject PDF")
            if compiled is None:
                return build
            subject_build_log, subject_amc_log_path, subject_xy_path = compiled

            _report_progress(progress_callback, 80, "Reading subject page structure...")
            # The pages of the content of each copy, before the blank pages (with an older exam_template.tex:
            # the pages of each copy in the XY file)
            copy_pages = (read_copy_pages_from_log(subject_build_log)
                          or [pages for _, pages in sorted(get_pages_by_copy_from_xy(subject_xy_path).items())])
            pages_per_copy = round_pages_per_copy(max(copy_pages, default=1), booklet)

            # ==========================================================
            # STEP 3 - PAGES PER COPY DIFFERENT FROM THE ESTIMATE
            # ==========================================================
            #
            # Some copies are longer than the catalog copy (shuffled questions or answers...): all the copies are
            # padded to the longest one, which the user is told. Or all are shorter (the catalog shows the keys
            # of the questions): the copies would have useless blank pages.
            # ==========================================================
            if pages_per_copy != estimated_pages_per_copy:
                if pages_per_copy > estimated_pages_per_copy:
                    build.build_warnings.append(longer_copies_warning(
                        copy_pages, estimated_pages_per_copy, pages_per_copy, exam_has_shuffling(exam), booklet))
                refresh_latex(pages_per_copy)
                # The .aux of the first compilation holds all the QR codes of this build
                compiled = compile_subject(
                    pages_per_copy, 81, 84, f"Compiling subject PDF again with {pages_per_copy} pages per copy")
                if compiled is None:
                    return build
                subject_build_log, subject_amc_log_path, subject_xy_path = compiled

            _report_progress(progress_callback, 84, "Final subject PDF compiled.")

            # ==========================================================
            # STEP 5 - PROMOTE WORKSPACE TO PERSISTENT PROJECT
            # ==========================================================
            #
            # Because SUBJECT was compiled last, the promoted project state
            # naturally stays in the final subject configuration.
            #
            # CATALOG is still kept as a side artifact PDF, but must never be
            # bound as the canonical build output.
            # ==========================================================
            _report_progress(progress_callback, 85, "Saving generated artifacts...")

            promoted = promote_workspace_to_project(
                workspace_path=workspace_path,
                persistent_project_path=persistent_project_path,
                exam=exam,
            )

            final_subject_pdf_path = (
                promoted.get("subject_pdf_path", "")
                or str(workspace_path / f"{exam_prefix}-sujet.pdf")
                or promoted.get("compiled_pdf_path", "")
            )
            final_subject_amc_path = (
                promoted.get("subject_amc_path", "")
                or subject_amc_log_path
            )
            final_subject_xy_path = (
                promoted.get("exam_calage_xy_path", "")
                or subject_xy_path
            )

            # Canonical ExamBuild paths MUST point to subject artifacts only.
            mark_exam_build_ready(
                build,
                compiled_pdf_path=final_subject_pdf_path,
                amc_log_path=final_subject_amc_path,
                xy_path=final_subject_xy_path,
                build_log=subject_build_log,
                lock_build=True,
            )

            build.project_path = promoted["project_path"]
            build.latex_main_path = str(Path(promoted["project_path"]) / "exam.tex")
            build.save(update_fields=["project_path", "latex_main_path", "updated_at"])

            return build

    except BuildCancelled as exc:
        mark_exam_build_error(build, str(exc))
        raise
    except Exception as exc:
        mark_exam_build_error(build, str(exc))
        return build