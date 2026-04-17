"""
AMC exam build pipeline.

This module is the orchestration layer for converting the current Django exam
preparation state into persistent AMC artifacts and a frozen ``ExamBuild``
snapshot.

Main responsibilities:
- compute a stable hash of the preparation source content
- create immutable build snapshot rows for questions and answers
- compile AMC artifacts in an isolated temporary workspace
- promote successful outputs back into the persistent project folder
- keep SUBJECT artifacts as the canonical source for layout/scoring extraction
- trigger subject-only layout page population and XY extraction

Important invariants:
- subject compilation is canonical for database-related paths and extraction
- catalog compilation is only a convenience artifact and must not drive DB state
- temporary workspace files should not be stored on the build after promotion
- frozen snapshot data must reflect the exact question/answer state at build time
"""

import inspect
import shutil
import subprocess
import tempfile
from hashlib import sha256
from pathlib import Path

from django.db import transaction
from django.db.models import Max
from django.utils import timezone

from examc import settings
from examc_app.models import (
    Exam,
    ExamBuild,
    ExamBuildAnswer,
    ExamBuildQuestion,
)
from examc_app.utils.amc.amc_helpers import (
    get_amc_answer_code,
    get_amc_question_id,
    get_exam_latex_main_file,
)
from examc_app.utils.amc.amc_helpers import get_amc_project_path
from examc_app.utils.amc.amc_layout_functions import extract_layout_from_xy, get_subject_copy_and_page_counts_from_xy, \
    populate_subject_layout_pages, get_pdf_page_metrics, LayoutExtractionError
from examc_app.utils.preparation_latex_functions import update_exam_latex


# ---------------------------------------------------------------------------
# Snapshot helpers
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
                    f"question_canceled:{int(question.canceled)}",
                    f"question_new_page:{int(question.new_page)}",
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
                        f"answer_fix_position:{int(answer.fix_position)}",
                    ]
                )

    payload = "\n".join(chunks)
    return sha256(payload.encode("utf-8")).hexdigest()


@transaction.atomic
def create_exam_build_snapshot(
    exam: Exam,
    user=None,
    *,
    lock_build: bool = False,
    latex_engine: str = "pdflatex",
    project_path: str = "",
    latex_main_path: str = "",
) -> ExamBuild:
    """
    Create a frozen ``ExamBuild`` snapshot from the current preparation state.

    The snapshot duplicates the question/answer information needed later for
    layout extraction, scan mapping, and scoring, so future edits to the exam do
    not retroactively change an older build.

    Returns:
        ExamBuild: Newly created build in ``draft`` status.
    """
    version = get_next_exam_build_version(exam)
    source_hash = compute_exam_source_hash(exam)
    locked_at = timezone.now() if lock_build else None

    build = ExamBuild.objects.create(
        exam=exam,
        version=version,
        status="draft",
        is_locked=lock_build,
        locked_at=locked_at,
        requested_by=user,
        source_hash=source_hash,
        latex_engine=latex_engine,
        project_path=project_path or "",
        latex_main_path=latex_main_path or "",
    )

    sections = exam.prepSections.order_by("position", "pk").prefetch_related(
        "prepQuestions__prepAnswers",
        "prepQuestions__question_type",
    )
    global_index = 1
    for section in sections:
        for question in section.prepQuestions.order_by("position", "pk"):
            question_type_code = question.question_type.code if question.question_type else ""
            rendered_id = get_amc_question_id(question)

            build_question = ExamBuildQuestion.objects.create(
                build=build,
                prep_question=question,
                rendered_id=rendered_id,
                amc_question_number=global_index,
                rendered_code=rendered_id,
                rendered_position=question.position,
                section_position=section.position,
                question_type_code=question_type_code,
                prep_question_id_snapshot=question.pk,
                title_snapshot=question.title or "",
                text_snapshot=question.question_text or "",
                max_points_snapshot=question.max_points or 0,
                point_increment_snapshot=question.point_increment or "",
                random_answers_snapshot=question.random_answers,
                new_page_snapshot=question.new_page,
                canceled_snapshot=question.canceled,
            )
            global_index += 1

            for answer in question.prepAnswers.order_by("position", "pk"):
                if not answer.box_type:
                    ExamBuildAnswer.objects.create(
                        build_question=build_question,
                        prep_answer=answer,
                        rendered_answer_number=answer.position,
                        rendered_position=answer.position,
                        rendered_code=get_amc_answer_code(question, answer),
                        prep_answer_id_snapshot=answer.pk,
                        title_snapshot=answer.title or "",
                        answer_text_snapshot=answer.answer_text or "",
                        is_correct_snapshot=answer.is_correct,
                        box_type_snapshot=answer.box_type or "",
                        box_height_mm_snapshot=answer.box_height_mm,
                        fix_position_snapshot=answer.fix_position,
                    )

    return build


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
    - use ``calage.xy`` if it already exists
    - otherwise copy ``amc-compiled.xy`` to ``calage.xy``

    Returns:
        Path | None: Normalized ``calage.xy`` path when available.
    """
    calage_xy = workspace_path / "calage.xy"
    compiled_xy = workspace_path / "amc-compiled.xy"

    if calage_xy.exists():
        return calage_xy

    if compiled_xy.exists():
        shutil.copy2(compiled_xy, calage_xy)
        return calage_xy

    return None



def compile_exam_in_workspace(
    workspace_path: Path,
    *,
    timeout: int = 60,
    latex_engine: str = "pdflatex",
    mode: str = "subject",
) -> dict:
    """
    Compile an exam in a temporary workspace.

    Supported modes:
    - ``subject``: uses ``students.csv`` and produces canonical layout artifacts
    - ``catalog``: uses ``student_prev.csv`` and produces a one-copy catalog PDF

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
        result = subprocess.run(
            cmd,
            cwd=str(workspace_path),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return {
            "ok": False,
            "error": "Compilation timeout",
            "status": 500,
            "build_log": "",
        }
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

    if result.returncode != 0 or not pdf_path.exists():
        error_message = result.stdout or result.stderr or build_log or "LaTeX compilation failed"
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

def export_exam_named_artifacts(project_path: Path, exam: Exam) -> dict:
    """
    Create AMC-style user-facing filenames alongside internal compiled files.

    This is mainly a convenience export layer for files such as
    ``{prefix}-sujet.pdf`` and ``{prefix}-calage.xy``.
    """
    prefix = _safe_exam_prefix(exam)

    exported = {
        "subject_pdf": "",
        "calage_xy": "",
    }

    compiled_pdf = project_path / "amc-compiled.pdf"
    calage_xy = project_path / "calage.xy"

    subject_pdf = project_path / f"{prefix}-sujet.pdf"
    exam_calage_xy = project_path / f"{prefix}-calage.xy"

    if compiled_pdf.exists():
        shutil.copy2(compiled_pdf, subject_pdf)
        exported["subject_pdf"] = str(subject_pdf)

    if calage_xy.exists():
        shutil.copy2(calage_xy, exam_calage_xy)
        exported["calage_xy"] = str(exam_calage_xy)

    return exported

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
    Replace the persistent AMC project folder with the latest successful outputs.

    The result is one current AMC-compatible project folder per exam containing
    the latest sources and promoted subject/catalog artifacts.

    Returns:
        dict: Paths to the promoted project and key artifacts.
    """
    project_path = Path(persistent_project_path)
    project_path.mkdir(parents=True, exist_ok=True)

    prefix = _safe_exam_prefix(exam)

    managed_names = set(PERSISTENT_AMC_FILES)
    managed_names.update(
        {
            f"{prefix}-sujet.pdf",
            f"{prefix}-catalog.pdf",
            f"{prefix}-calage.xy",
        }
    )

    for name in managed_names:
        target = project_path / name
        if target.exists():
            if target.is_dir():
                shutil.rmtree(target)
            else:
                target.unlink()

    for name in PERSISTENT_AMC_FILES:
        source = workspace_path / name
        if source.exists():
            shutil.copy2(source, project_path / name)

    subject_pdf = workspace_path / f"{prefix}-sujet.pdf"
    catalog_pdf = workspace_path / f"{prefix}-catalog.pdf"
    exam_calage_xy = workspace_path / f"{prefix}-calage.xy"

    if subject_pdf.exists():
        shutil.copy2(subject_pdf, project_path / subject_pdf.name)

    if catalog_pdf.exists():
        shutil.copy2(catalog_pdf, project_path / catalog_pdf.name)

    if exam_calage_xy.exists():
        shutil.copy2(exam_calage_xy, project_path / exam_calage_xy.name)

    return {
        "project_path": str(project_path),
        "compiled_pdf_path": str(project_path / "amc-compiled.pdf") if (project_path / "amc-compiled.pdf").exists() else "",
        "amc_log_path": str(project_path / "subject.amc") if (project_path / "subject.amc").exists() else "",
        "xy_path": str(project_path / f"{prefix}-calage.xy") if (project_path / f"{prefix}-calage.xy").exists() else "",
        "subject_pdf_path": str(project_path / f"{prefix}-sujet.pdf") if (project_path / f"{prefix}-sujet.pdf").exists() else "",
        "catalog_pdf_path": str(project_path / f"{prefix}-catalog.pdf") if (project_path / f"{prefix}-catalog.pdf").exists() else "",
        "exam_calage_xy_path": str(project_path / f"{prefix}-calage.xy") if (project_path / f"{prefix}-calage.xy").exists() else "",
        "subject_log_path": str(project_path / "subject.log") if (project_path / "subject.log").exists() else "",
        "subject_amc_path": str(project_path / "subject.amc") if (project_path / "subject.amc").exists() else "",
        "catalog_log_path": str(project_path / "catalog.log") if (project_path / "catalog.log").exists() else "",
        "catalog_amc_path": str(project_path / "catalog.amc") if (project_path / "catalog.amc").exists() else "",
    }


# ---------------------------------------------------------------------------
# Main entrypoint
# ---------------------------------------------------------------------------

def build_final_exam(
    exam: Exam,
    user=None,
    *,
    timeout: int = 60,
    latex_engine: str = "pdflatex",
) -> ExamBuild:
    """
    Run the full final build pipeline for one exam.

    Flow:
    1. Regenerate current LaTeX into the persistent AMC project folder.
    2. Create a frozen ``ExamBuild`` snapshot.
    3. Copy the persistent project into a temporary workspace.
    4. Compile subject mode using ``students.csv``.
    5. Compile catalog mode using ``student_prev.csv``.
    6. Promote successful outputs back to the persistent project folder.
    7. Bind canonical build paths to the promoted SUBJECT artifacts only.

    Returns:
        ExamBuild: Build in ``ready`` or ``error`` state.
    """
    persistent_project_path = get_amc_project_path(exam, False)
    exam_prefix = exam.code or f"exam-{exam.pk}"

    update_exam_latex(exam)

    build = create_exam_build_snapshot(
        exam=exam,
        user=user,
        lock_build=True,
        latex_engine=latex_engine,
        project_path=persistent_project_path,
        latex_main_path=str(Path(persistent_project_path) / "exam.tex"),
    )

    try:
        mark_exam_build_building(build)
        Path(settings.AMC_TMP_ROOT).mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=settings.AMC_TMP_ROOT,prefix=f"amc_exam_{exam.pk}_") as tmp_dir:
            workspace_path = Path(tmp_dir)

            copy_project_to_workspace(persistent_project_path, workspace_path)

            # SUBJECT BUILD
            # students.csv -> canonical build for DB/layout extraction
            subject_result = compile_exam_in_workspace(
                workspace_path,
                timeout=timeout,
                latex_engine=latex_engine,
                mode="subject",
            )

            if not subject_result["ok"]:
                mark_exam_build_error(
                    build,
                    error_message=subject_result["error"],
                    build_log=subject_result.get("build_log", ""),
                )
                return build

            subject_pdf = workspace_path / "amc-compiled.pdf"
            subject_named_pdf = workspace_path / f"{exam_prefix}-sujet.pdf"
            if subject_pdf.exists():
                shutil.copy2(subject_pdf, subject_named_pdf)

            subject_xy = workspace_path / "calage.xy"
            subject_named_xy = workspace_path / f"{exam_prefix}-calage.xy"
            if subject_xy.exists():
                shutil.copy2(subject_xy, subject_named_xy)

            subject_build_log = subject_result.get("build_log", "")
            subject_amc_log_path = (
                subject_result.get("renamed_amc_path", "")
                or subject_result.get("amc_log_path", "")
            )
            subject_xy_path = (
                str(subject_named_xy)
                if subject_named_xy.exists()
                else subject_result.get("xy_path", "")
            )

            # CATALOG BUILD
            # student_prev.csv -> exported convenience artifact only
            catalog_result = compile_exam_in_workspace(
                workspace_path,
                timeout=timeout,
                latex_engine=latex_engine,
                mode="catalog",
            )

            if not catalog_result["ok"]:
                mark_exam_build_error(
                    build,
                    error_message=catalog_result["error"],
                    build_log=catalog_result.get("build_log", "") or subject_build_log,
                )
                return build

            catalog_pdf = workspace_path / "amc-compiled.pdf"
            catalog_named_pdf = workspace_path / f"{exam_prefix}-catalog.pdf"
            if catalog_pdf.exists():
                shutil.copy2(catalog_pdf, catalog_named_pdf)

            # PROMOTE TO PERSISTENT PROJECT FOLDER
            promoted = promote_workspace_to_project(
                workspace_path=workspace_path,
                persistent_project_path=persistent_project_path,
                exam=exam,
            )

            # SUBJECT is canonical for DB-related paths.
            final_subject_pdf_path = (
                promoted.get("subject_pdf_path", "")
                or str(subject_named_pdf)
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

            mark_exam_build_ready(
                build,
                compiled_pdf_path=final_subject_pdf_path,
                amc_log_path=final_subject_amc_path,
                xy_path=final_subject_xy_path,
                build_log=subject_build_log,
                lock_build=True,
            )

            # Keep build pointing to the persistent folder, not the temp workspace.
            build.project_path = promoted["project_path"]
            build.latex_main_path = str(Path(promoted["project_path"]) / "exam.tex")
            build.save(update_fields=["project_path", "latex_main_path", "updated_at"])

            return build

    except Exception as exc:
        mark_exam_build_error(build, str(exc))
        return build



def generate_final_exam_files(exam, user, job_id, timeout=30):
    """
    Build the final exam and extract the canonical subject layout into the DB.

    This is the high-level pipeline used by the application when it needs both
    the generated files and the normalized layout rows.

    Flow:
    - build/promote subject and catalog artifacts
    - resolve canonical subject PDF and XY files
    - derive subject copy/page counts from the subject XY file
    - populate ``LayoutPage`` rows using subject page metrics
    - extract subject-only layout objects onto those pages

    Returns:
        dict: Success or error payload with artifact paths and extraction counts.
    """
    build = build_final_exam(
        exam,
        user=user,
        timeout=timeout,
    )

    if build.status != "ready":
        return {
            "ok": False,
            "error": build.error_message or "Final exam build failed.",
            "job_id": job_id,
            "build_id": build.pk if build else None,
        }

    try:
        project_path = Path(build.project_path) if build.project_path else None
        exam_prefix = exam.code or f"exam-{exam.pk}"

        subject_pdf_path = ""
        catalog_pdf_path = ""
        subject_xy_path = build.xy_path or ""

        if project_path and project_path.exists():
            subject_pdf = project_path / f"{exam_prefix}-sujet.pdf"
            catalog_pdf = project_path / f"{exam_prefix}-catalog.pdf"
            subject_xy = project_path / f"{exam_prefix}-calage.xy"

            if subject_pdf.exists():
                subject_pdf_path = str(subject_pdf)
            elif build.compiled_pdf_path:
                subject_pdf_path = build.compiled_pdf_path

            if catalog_pdf.exists():
                catalog_pdf_path = str(catalog_pdf)

            if subject_xy.exists():
                subject_xy_path = str(subject_xy)

        if not subject_xy_path:
            raise Exception("Subject XY path is missing; cannot extract subject layout.")

        # SUBJECT ONLY: determine copy/page structure from subject XY.
        counts = get_subject_copy_and_page_counts_from_xy(subject_xy_path)
        pdf_metrics = get_pdf_page_metrics(subject_pdf_path, dpi=300.0)

        if pdf_metrics["page_count"] != counts["total_pages"]:
            raise LayoutExtractionError(
                f"PDF/XY page mismatch: PDF={pdf_metrics['page_count']} XY={counts['total_pages']}"
            )

        page_result = populate_subject_layout_pages(
            build,
            total_copies=counts["total_copies"],
            pages_per_copy=counts["pages_per_copy"],
            dpi=pdf_metrics["dpi"],
            width=pdf_metrics["width"],
            height=pdf_metrics["height"],
        )

        # SUBJECT ONLY: attach boxes/zones/digits to existing pages.
        layout_result = extract_layout_from_xy(
            build,
            xy_path=subject_xy_path,
            clear_existing=True,
        )

        return {
            "ok": True,
            "job_id": job_id,
            "build_id": build.pk,
            "pdf_path": subject_pdf_path or build.compiled_pdf_path or "",
            "subject_pdf_path": subject_pdf_path or "",
            "catalog_pdf_path": catalog_pdf_path or "",
            "amc_log_path": build.amc_log_path or "",
            "xy_path": subject_xy_path,
            "exam_calage_xy_path": subject_xy_path,
            "page_result": page_result,
            "layout_result": layout_result,
        }

    except Exception as e:
        return {
            "ok": False,
            "error": f"Layout extraction failed: {str(e)}",
            "job_id": job_id,
            "build_id": build.pk,
            "pdf_path": build.compiled_pdf_path or "",
            "subject_pdf_path": build.compiled_pdf_path or "",
            "catalog_pdf_path": "",
            "amc_log_path": build.amc_log_path or "",
            "xy_path": build.xy_path or "",
        }
