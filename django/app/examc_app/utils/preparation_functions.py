import os
import re
import shutil
import subprocess
import tempfile
from functools import lru_cache
from pathlib import Path

from django.db.models import Max, QuerySet, Model
from django.http import HttpResponseForbidden

from examc import settings
from examc_app.forms import PrepQuestionAnswerForm, PrepSectionForm, PrepQuestionForm
from examc_app.models import PrepScoringFormula, PrepSection, PrepQuestionAnswer, PrepQuestion, Exam, Question
from examc_app.utils.amc_functions import get_amc_project_path
from examc_app.utils.preparation_latex_functions import update_question_scoring_latex_file, update_answer_scoring_latex_file, update_global_scoring_latex_file


# -------------------------
# Query / context helpers
# -------------------------
def get_sections(exam):
    return list(exam.prepSections.all().order_by("position", "pk"))


def get_questions(section):
    return list(section.prepQuestions.all().order_by("position", "pk"))


def get_answers(question):
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

def ensure_exam_not_finalized(exam):
    if exam.is_finalized:
        return HttpResponseForbidden(
            "This exam is finalized. Unlock editing before making changes."
        )
    return None

def create_prep_section(exam, title="New section", section_text=""):
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

    answer = PrepQuestionAnswer.objects.create(
        prep_question=question,
        title=title,
        answer_text=answer_text,
        is_correct=is_correct,
        position=next_position,
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

def get_exam_preview_pdf_path(exam):
    amc_project_path = Path(get_amc_project_path(exam, False))
    return amc_project_path / "exam.pdf"


def get_exam_preview_job_dir(exam, job_id):
    preview_dir = Path(settings.PRIVATE_MEDIA_ROOT) / "exam_previews" / str(exam.pk) / str(job_id)
    preview_dir.mkdir(parents=True, exist_ok=True)
    return preview_dir


def compile_exam_preview(exam, job_id, timeout=30):
    amc_project_path = Path(get_amc_project_path(exam, False))
    root_latex_file_path = amc_project_path / "exam.tex"

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
                cwd=str(tmp_path),
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
            update_question_scoring_latex_file(prep_question)
        elif scope == "answer":
            instance.prep_answer_id = prep_answer
            instance.save()
            update_answer_scoring_latex_file(prep_answer)

    if scope == "exam":
        exam_scoring_formulas = PrepScoringFormula.objects.filter(exam_id=exam_pk,prep_section_id=None,prep_question_id=None,prep_answer_id=None)
        update_global_scoring_latex_file(exam_scoring_formulas, exam_pk)

    return instances

