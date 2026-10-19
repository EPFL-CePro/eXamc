import shutil
import subprocess
import tempfile
from datetime import timedelta
from decimal import Decimal
from pathlib import Path

from django.db.models import Max
from django.http import HttpResponseForbidden
from django.utils import timezone

from django.conf import settings
from examc_app.forms.preparation import (
    PrepQuestionAnswerForm,
    PrepQuestionForm,
    PrepSectionForm,
)
from examc_app.models import (
    Exam,
    ExamAMCJob,
    PrepQuestion,
    PrepQuestionAnswer,
    PrepScoringFormula,
    PrepSection,
)
from examc_app.services.student.prep_amc_csv import STUDENTS_CSV_NAME
from examc_app.utils.amc_functions import ensure_amc_project
from examc_app.utils.preparation_latex_functions import (
    update_exam_latex,
)


# -------------------------
# Query / context helpers
# -------------------------
def get_sections(exam):
    return list(exam.prepSections.all().order_by("position", "pk"))


def get_questions(section):
    return list(section.prepQuestions.all().order_by("position", "pk"))


def get_answers(question):
    if question.question_type.code == 'OPEN':
        return list(question.prepAnswers.filter(box_type__isnull=False).order_by("position","pk"))
    else:
        return list(question.prepAnswers.all().order_by("position", "pk"))

def build_sections_list_context(exam):
    sections = get_sections(exam)

    section_items = [
        {
            "section": section,
            "section_form": build_section_form(section),
            "questions": get_questions(section),
        }
        for section in sections
    ]

    return {
        "sections": sections,
        "section_items": section_items,
    }

# -------------------------
# Form helpers
# -------------------------
def build_section_form(section, *, data=None):
    return PrepSectionForm(
        data=data,
        instance=section,
        prefix=f"section-{section.pk}",
    )

def build_question_form(question, *, data=None):
    return PrepQuestionForm(
        data=data,
        instance=question,
        prefix=f"question-{question.pk}",
    )

def build_answer_form(answer, *, data=None):
    return PrepQuestionAnswerForm(
        data=data,
        instance=answer,
        prefix=f"answer-{answer.pk}",
    )

# -------------------------
# Ordering helpers
# -------------------------

def renumber_sections(exam):
    sections = get_sections(exam)
    for index, section in enumerate(sections, start=1):
        if section.position != index:
            section.position = index
            section.save(update_fields=["position"])
    return get_sections(exam)

def renumber_questions(section):
    questions = get_questions(section)
    for index, question in enumerate(questions, start=1):
        if question.position != index:
            question.position = index
            question.save(update_fields=["position"])
    return get_questions(section)

def renumber_answers(question):
    answers = get_answers(question)
    for index, answer in enumerate(answers, start=1):
        if answer.position != index:
            answer.position = index
            answer.save(update_fields=["position"])
    return get_answers(question)

# -------------------------
# Creation / mutation helpers
# -------------------------

# A final generation not finished after this time is considered interrupted (worker stopped...): far above the
# compilation timeouts of build_final_exam for a big exam
FINAL_BUILD_MAX_DURATION = timedelta(hours=4)


def get_active_final_build_job(exam):
    """
    The final generation of the exam still running, whoever started it, or None. A job whose Celery task ended
    without updating it (worker killed...) or older than FINAL_BUILD_MAX_DURATION is marked as failed.
    """
    from celery.result import AsyncResult

    job = (ExamAMCJob.objects
           .filter(exam=exam, job_type="final_build", status__in=["pending", "running"])
           .order_by("-created_at")
           .first())
    if job is None:
        return None

    interrupted = job.created_at < timezone.now() - FINAL_BUILD_MAX_DURATION
    if not interrupted and job.celery_task_id:
        interrupted = AsyncResult(job.celery_task_id).state in ("FAILURE", "REVOKED")
    if interrupted:
        job.status = "error"
        job.error_message = job.error_message or "The final generation was interrupted."
        job.save(update_fields=["status", "error_message", "updated_at"])
        return None
    return job


def exam_lock_reason(exam):
    """Why the exam (content and students) cannot be modified: finalized, or a final generation is running."""
    if exam.is_finalized:
        return "This exam is finalized. Unlock editing before making changes."
    if get_active_final_build_job(exam):
        return "The final generation of this exam is running. Wait for its end, or cancel it, before making changes."
    return None


def is_exam_locked(exam) -> bool:
    return exam_lock_reason(exam) is not None


def ensure_exam_not_finalized(exam):
    """A 403 response when the exam cannot be modified (see exam_lock_reason), else None."""
    reason = exam_lock_reason(exam)
    if reason:
        return HttpResponseForbidden(reason)
    return None

def create_prep_section(exam: Exam, title="New section", section_text=""):
    next_position = (
        exam.prepSections.aggregate(max_pos=Max("position"))["max_pos"] or 0
    ) + 1

    section = PrepSection.objects.create(
        exam=exam,
        title=title,
        section_text=section_text,
        position=next_position,
    )

    return section

def create_prep_question(section, question_type, title="New question", nb_answers=0):
    next_position = (
        section.prepQuestions.aggregate(max_pos=Max("position"))["max_pos"] or 0
    ) + 1

    question = PrepQuestion.objects.create(
        prep_section=section,
        question_type=question_type,
        title=title,
        question_text="",
        position=next_position,
    )

    _create_default_answers_for_question(question,question_type,nb_answers)

    return question


def create_prep_answer(question, title="New answer", answer_text="", is_correct=False):
    next_position = (
        question.prepAnswers.aggregate(max_pos=Max("position"))["max_pos"] or 0
    ) + 1
    box_type = None
    if question.question_type.code == 'OPEN':
        box_type = 'grid'

    answer = PrepQuestionAnswer.objects.create(
        prep_question=question,
        title=title,
        answer_text=answer_text,
        is_correct=is_correct,
        position=next_position,
        box_type=box_type
    )

    return answer

def _create_default_answers_for_question(question, question_type, nb_answers=0):
    code = question_type.code

    if code in {"SCQ", "MCQ"}:
        _create_scq_mcq_answers(question, nb_answers)
    elif code == "TF":
        _create_tf_answers(question)

def _create_scq_mcq_answers(question, nb_answers):
    for i in range(nb_answers):
        PrepQuestionAnswer.objects.create(
            prep_question=question,
            title=f"Answer {i + 1}",
            answer_text="",
            is_correct=False,
            position=i + 1,
        )

def update_open_answers(question : PrepQuestion):

    question.prepAnswers.filter(box_type__isnull=True).delete()
    max_points = Decimal(str(question.max_points))
    increment = Decimal(str(question.point_increment))

    if increment <= 0:
        raise ValueError("increment must be > 0")
    if max_points < 0:
        raise ValueError("max_points must be >= 0")
    if max_points % increment != 0:
        raise ValueError("max_points must be divisible by increment")

    steps = int(max_points / increment)

    for i in range(steps + 1):
        value = i * increment

        PrepQuestionAnswer.objects.create(
            prep_question=question,
            title=f"{value:g} point{'s' if value != 1 else ''}",
            answer_text="",
            is_correct=(i == steps),
            position=i + 1,
        )


def _create_tf_answers(question):
    PrepQuestionAnswer.objects.create(
        prep_question=question,
        title="TRUE",
        answer_text="TRUE",
        is_correct=False,
        position=1,
    )
    PrepQuestionAnswer.objects.create(
        prep_question=question,
        title="FALSE",
        answer_text="FALSE",
        is_correct=False,
        position=2,
    )

# -------------------------
# Preview / LaTeX
# -------------------------
def delete_exam_preview_job_files(job):
    if not job.pdf_path:
        return

    pdf_path = Path(job.pdf_path)

    if pdf_path.exists():
        preview_dir = pdf_path.parent
        if preview_dir.exists():
            shutil.rmtree(preview_dir, ignore_errors=True)


def get_exam_preview_job_dir(exam: Exam, job_id):
    preview_dir = Path(settings.PRIVATE_MEDIA_ROOT) / "exam_previews" / str(exam.pk) / str(job_id)
    preview_dir.mkdir(parents=True, exist_ok=True)
    return preview_dir


def compile_exam_preview(exam: Exam, job_id, timeout: int = 30):
    amc_project_path = Path(ensure_amc_project(exam))
    root_latex_file_path = amc_project_path / "exam.tex"

    # exam.tex is generated by the preparation module: an exam whose content was never saved doesn't have it yet
    if not root_latex_file_path.exists():
        update_exam_latex(exam)

    if not root_latex_file_path.exists():
        return {
            "ok": False,
            "error": "File exam.tex not found",
            "status": 400,
        }

    try:
        with tempfile.TemporaryDirectory(prefix=f"exam_preview_{exam.pk}_{job_id}_") as tmp_dir:
            tmp_path = Path(tmp_dir)

            for item in amc_project_path.iterdir():
                # Without students list, the preview is a single anonymous copy (see exam_template.tex)
                if item.name == STUDENTS_CSV_NAME:
                    continue
                src = item
                dst = tmp_path / item.name

                if item.is_dir():
                    shutil.copytree(src, dst)
                else:
                    shutil.copy2(src, dst)

            output_pdf_path = tmp_path / "exam.pdf"
            output_log_path = tmp_path / "exam.log"

            result = subprocess.run(
                [
                    "pdflatex",
                    "-interaction=nonstopmode",
                    "-halt-on-error",
                    root_latex_file_path.name,
                ],
                check=False, cwd=str(tmp_path),
                capture_output=True,
                text=True,
                timeout=timeout,
            )

            if result.returncode != 0 or not output_pdf_path.exists():
                error_message = result.stdout or result.stderr or "LaTeX compilation failed"

                if output_log_path.exists():
                    try:
                        error_message = output_log_path.read_text(
                            encoding="utf-8",
                            errors="replace",
                        )
                    except Exception:
                        pass

                return {
                    "ok": False,
                    "error": error_message,
                    "status": 400,
                }

            final_dir = get_exam_preview_job_dir(exam, job_id)
            final_pdf_path = final_dir / "exam_preview.pdf"

            # Clean existing file if exists
            if final_pdf_path.exists():
                final_pdf_path.unlink()

            shutil.copy2(output_pdf_path, final_pdf_path)

            return {
                "ok": True,
                "pdf_path": final_pdf_path,
                "status": 200,
            }

    except subprocess.TimeoutExpired:
        return {
            "ok": False,
            "error": "Compilation timeout",
            "status": 500,
        }
    except FileNotFoundError:
        return {
            "ok": False,
            "error": "pdflatex not found",
            "status": 500,
        }



# -------------------------
# Scoring formulas
# -------------------------

# The levels of the scoring formulas, shown next to the Scoring buttons (see get_applied_scorings)
SCORING_LEVEL_EXAM = "Global"
SCORING_LEVEL_SECTION = "Section"
SCORING_LEVEL_QUESTION = "Question"
SCORING_LEVEL_ANSWER = "Answer"


NO_FORMULA_TEXT = "AMC default"


def scoring_info_text(info) -> str:
    """The text next to a Scoring button: 'Section : "b=2,m=-1"', or the default of AMC when no level has a formula."""
    if not info:
        return ""
    if not info["formula"]:
        return NO_FORMULA_TEXT
    return f'{info["level"]} : "{info["formula"]}"'


SCORING_BADGE_CUSTOM = "Custom"


def scoring_badge_text(codes) -> str:
    """The text on the Scoring button of a level: the question types it has formulas for ("MCQ, SCQ"), or "Custom"
    for the formulas without question type (questions and answers). Empty when the level has no formula."""
    if not codes:
        return ""
    typed = sorted(code for code in codes if code)
    return ", ".join(typed) if typed else SCORING_BADGE_CUSTOM


def scoring_badges(defined: dict[str, dict[int, set]]) -> dict[str, dict[str, str]]:
    """The texts of the Scoring buttons that have one: {level kind: {id: text}}, for the page to update them."""
    return {
        kind: {str(pk): text for pk, codes in levels.items() if (text := scoring_badge_text(codes))}
        for kind, levels in defined.items()
    }


def get_applied_scorings(exam) -> dict[str, dict]:
    """
    The scoring formula applied to each choice question and answer of the exam, with its level:
    {"questions": {question id: info}, "answers": {answer id: info}}, info being {"level": ..., "formula": ...}
    (None for an open question, scored by its corrector boxes, and its answers).
    "defined" is what each level has formulas for, to show on its Scoring button: {"exam" (id 0), "section",
    "question", "answer": {id: set of question type codes, None for a formula without question type}}.

    A question has the formula of the most specific level that has one for it: the question, its section (formula of
    its question type), the exam (formula of its question type). Otherwise AMC applies its own default: formula "".
    An answer has its own formula, otherwise the one of its question.
    This is what question_scoring_tex and the answer rendering write in the LaTeX sources.
    One query for the formulas, one for the questions and one for the answers.
    """
    exam_formulas, section_formulas, question_formulas, answer_formulas = {}, {}, {}, {}
    defined = {"exam": {0: set()}, "section": {}, "question": {}, "answer": {}}
    for formula in PrepScoringFormula.objects.filter(exam=exam).select_related("question_type").order_by("pk"):
        code = formula.question_type.code if formula.question_type else None
        if formula.prep_answer_id:
            answer_formulas.setdefault(formula.prep_answer_id, formula.formula)
            defined["answer"].setdefault(formula.prep_answer_id, set()).add(code)
        elif formula.prep_question_id:
            question_formulas.setdefault(formula.prep_question_id, formula.formula)
            defined["question"].setdefault(formula.prep_question_id, set()).add(code)
        elif formula.prep_section_id:
            defined["section"].setdefault(formula.prep_section_id, set()).add(code)
            if code:
                section_formulas.setdefault((formula.prep_section_id, code), formula.formula)
        else:
            defined["exam"][0].add(code)
            if code:
                exam_formulas.setdefault(code, formula.formula)

    questions = {}
    for question in PrepQuestion.objects.filter(prep_section__exam=exam).select_related("question_type"):
        code = question.question_type.code
        if code == "OPEN":
            questions[question.pk] = None
        elif question.pk in question_formulas:
            questions[question.pk] = {"level": SCORING_LEVEL_QUESTION, "formula": question_formulas[question.pk]}
        elif (question.prep_section_id, code) in section_formulas:
            questions[question.pk] = {"level": SCORING_LEVEL_SECTION,
                                      "formula": section_formulas[(question.prep_section_id, code)]}
        elif code in exam_formulas:
            questions[question.pk] = {"level": SCORING_LEVEL_EXAM, "formula": exam_formulas[code]}
        else:
            questions[question.pk] = {"level": "", "formula": ""}

    answers = {}
    for answer_id, question_id in PrepQuestionAnswer.objects.filter(
            prep_question__prep_section__exam=exam).values_list("pk", "prep_question_id"):
        if questions.get(question_id) is None:
            answers[answer_id] = None
        elif answer_id in answer_formulas:
            answers[answer_id] = {"level": SCORING_LEVEL_ANSWER, "formula": answer_formulas[answer_id]}
        else:
            answers[answer_id] = questions[question_id]

    return {"questions": questions, "answers": answers, "defined": defined}


def get_scoring_formula_scope(prep_section=None, prep_question=None, prep_answer=None):
    if prep_answer:
        return "answer"
    if prep_question:
        return "question"
    if prep_section:
        return "section"
    return "exam"

def get_scoring_formula_queryset(exam_pk, prep_section=None, prep_question=None, prep_answer=None):
    queryset = PrepScoringFormula.objects.filter(exam_id=exam_pk)

    if prep_answer:
        queryset = queryset.filter(prep_answer_id=prep_answer)
    elif prep_question:
        queryset = queryset.filter(
            prep_question_id=prep_question,
            prep_answer__isnull=True,
        )
    elif prep_section:
        queryset = queryset.filter(
            prep_section_id=prep_section,
            prep_question__isnull=True,
            prep_answer__isnull=True,
        )
    else:
        queryset = queryset.filter(
            prep_section__isnull=True,
            prep_question__isnull=True,
            prep_answer__isnull=True,
        )

    return queryset.order_by("pk")

def save_scoring_formulas(
    formset,
    *,
    exam_pk,
    scope,
    prep_section=None,
    prep_question=None,
    prep_answer=None,
):
    valid_scopes = {"exam", "section", "question", "answer"}
    if scope not in valid_scopes:
        raise ValueError(f"Invalid scoring formula scope: {scope}")

    instances = formset.save(commit=False)

    for obj in formset.deleted_objects:
        obj.delete()

    for instance in instances:
        if not instance.formula:
            continue

        instance.exam_id = exam_pk
        instance.prep_section = None
        instance.prep_question = None
        instance.prep_answer = None

        if scope == "section":
            instance.prep_section_id = prep_section
            instance.save()
        elif scope == "question":
            instance.prep_question_id = prep_question
            instance.save()
        elif scope == "answer":
            instance.prep_answer_id = prep_answer
            instance.save()
        else:
            instance.save()

    # Exam formulas in global_scoring.tex, the others on the questions and answers (see question_scoring_tex)
    update_exam_latex(Exam.objects.get(pk=exam_pk))

    return instances

