import json

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.db.models import Max
from django.http import HttpResponse, HttpResponseBadRequest, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render

from examc_app.decorators import exam_permission_required
from examc_app.forms import (
    CreateExamProjectForm,
    CreatePrepQuestionForm,
    ExamFirstPageForm,
    PrepQuestionAnswerForm,
    PrepQuestionForm,
    PrepScoringFormulaFormSet,
    PrepSectionForm,
)
from examc_app.models import (
    AcademicYear,
    Course,
    Exam,
    ExamUser,
    PrepQuestion,
    PrepQuestionAnswer,
    PrepScoringFormula,
    PrepSection,
    Semester,
)
from examc_app.utils.amc_functions import get_amc_project_path
from examc_app.utils.global_functions import add_course_teachers_ldap
from examc_app.utils.preparation_html_to_latex_functions import (
    render_first_page_tex_from_html,
    update_exam_latex,
)
from examc_app.views import logger


# -------------------------
# Small context helpers
# -------------------------

def _get_sections(exam):
    return list(exam.prepSections.all().order_by("position", "pk"))


def _get_questions(section):
    return list(section.prepQuestions.all().order_by("position", "pk"))


def _get_answers(question):
    return list(question.prepAnswers.all().order_by("position", "pk"))


def _build_section_form(section, *, data=None):
    return PrepSectionForm(
        data=data,
        instance=section,
        prefix=f"section-{section.pk}",
    )


def _build_question_form(question, *, data=None):
    return PrepQuestionForm(
        data=data,
        instance=question,
        prefix=f"question-{question.pk}",
    )


def _build_answer_form(answer, *, data=None):
    return PrepQuestionAnswerForm(
        data=data,
        instance=answer,
        prefix=f"answer-{answer.pk}",
    )


def _build_sections_list_context(exam):
    sections = _get_sections(exam)

    section_items = [
        {
            "section": section,
            "section_form": _build_section_form(section),
            "questions": _get_questions(section),
        }
        for section in sections
    ]

    return {
        "sections": sections,
        "section_items": section_items,
    }


def _renumber_sections(exam):
    sections = _get_sections(exam)
    for index, section in enumerate(sections, start=1):
        if section.position != index:
            section.position = index
            section.save(update_fields=["position"])
    return _get_sections(exam)


def _renumber_questions(section):
    questions = _get_questions(section)
    for index, question in enumerate(questions, start=1):
        if question.position != index:
            question.position = index
            question.save(update_fields=["position"])
    return _get_questions(section)


def _renumber_answers(question):
    answers = _get_answers(question)
    for index, answer in enumerate(answers, start=1):
        if answer.position != index:
            answer.position = index
            answer.save(update_fields=["position"])
    return _get_answers(question)


# -------------------------
# Create exam project
# -------------------------

@login_required
def create_exam_project(request):
    if request.method == "POST":
        form = CreateExamProjectForm(request.POST)
        if form.is_valid():
            course_id = form.cleaned_data["course"]
            date = form.cleaned_data["date"]
            year_id = form.cleaned_data["year"]
            semester_id = form.cleaned_data["semester"]

            semester = Semester.objects.get(pk=semester_id)
            year = AcademicYear.objects.get(pk=year_id)
            course = Course.objects.get(pk=course_id)
            teachers = add_course_teachers_ldap(course.teachers)

            exam = Exam.objects.create(
                code=course.code,
                name=course.name,
                semester=semester,
                year=year,
                date=date,
            )

            for teacher in teachers:
                ExamUser.objects.create(
                    user=teacher,
                    exam=exam,
                    group_id=2,
                )

            return redirect("examInfo", exam_pk=exam.pk)

        logger.info("INVALID")
        logger.info(form.errors)
        return render(
            request,
            "exam/create_exam_project.html",
            {
                "user_allowed": True,
                "form": form,
                "nav_url": "create_exam_project",
            },
        )

    form = CreateExamProjectForm()
    return render(
        request,
        "exam/create_exam_project.html",
        {
            "user_allowed": True,
            "form": form,
            "nav_url": "create_exam_project",
        },
    )


# -------------------------
# Main page
# -------------------------

@exam_permission_required(["manage"])
def exam_preparation_view(request, exam_pk):
    exam = get_object_or_404(Exam, pk=exam_pk)
    first_page_form = ExamFirstPageForm(instance=exam)

    return render(
        request,
        "exam/preparation/exam_preparation.html",
        {
            "exam_selected": exam,
            "fp_txt_form": first_page_form,
            "nav_url": "exam_preparation",
            **_build_sections_list_context(exam),
        },
    )


# -------------------------
# First page
# -------------------------

@exam_permission_required(["manage"])
def prep_first_page_panel(request, exam_pk):
    exam = get_object_or_404(Exam, pk=exam_pk)

    if request.method == "POST":
        form = ExamFirstPageForm(request.POST, instance=exam)
        saved = form.is_valid()

        if saved:
            form.save()
            exam.refresh_from_db()

            amc_project_path = get_amc_project_path(exam, False)
            amc_project_template_path = f"{settings.AMC_PROJECTS_ROOT}/templates/base"
            template_first_page_latex_path = f"{amc_project_template_path}/first_page_template.tex"
            first_page_latex_path_output = f"{amc_project_path}/first_page.tex"

            render_first_page_tex_from_html(
                exam,
                exam.first_page_text,
                template_first_page_latex_path,
                first_page_latex_path_output,
            )
    else:
        form = ExamFirstPageForm(instance=exam)
        saved = False

    return render(
        request,
        "exam/preparation/_prep_first_page_card.html",
        {
            "exam_selected": exam,
            "fp_txt_form": form,
            "saved": saved,
        },
    )


# -------------------------
# Sections
# -------------------------

@exam_permission_required(["manage"])
def prep_sections_list(request, exam_pk):
    exam = get_object_or_404(Exam, pk=exam_pk)

    return render(
        request,
        "exam/preparation/_prep_sections_list.html",
        {
            "exam_selected": exam,
            **_build_sections_list_context(exam),
        },
    )


@exam_permission_required(["manage"])
def prep_section_panel(request, exam_pk, section_id):
    section = get_object_or_404(PrepSection, pk=section_id, exam_id=exam_pk)

    if request.method == "POST":
        form = _build_section_form(section, data=request.POST)
        saved = form.is_valid()

        if saved:
            form.save()
            section.refresh_from_db()
            update_exam_latex(section.exam)
    else:
        form = _build_section_form(section)
        saved = False

    questions = _get_questions(section)

    return render(
        request,
        "exam/preparation/_prep_section_card.html",
        {
            "exam_selected": section.exam,
            "section": section,
            "section_form": form,
            "questions": questions,
            "expanded": True,
            "saved": saved,
        },
    )


@exam_permission_required(["manage"])
def reorder_prep_sections(request, exam_pk):
    if request.method != "POST":
        return HttpResponseBadRequest("Invalid method")

    exam = get_object_or_404(Exam, pk=exam_pk)

    try:
        payload = json.loads(request.body)
        sections_data = payload.get("sections", [])
    except (json.JSONDecodeError, TypeError):
        return HttpResponseBadRequest("Invalid JSON")

    section_map = {section.id: section for section in exam.prepSections.all()}

    for item in sections_data:
        try:
            section_id = int(item["id"])
            position = int(item["position"])
        except (KeyError, TypeError, ValueError):
            continue

        section = section_map.get(section_id)
        if section and section.position != position:
            section.position = position
            section.save(update_fields=["position"])

    return render(
        request,
        "exam/preparation/_prep_sections_list.html",
        {
            "exam_selected": exam,
            **_build_sections_list_context(exam),
        },
    )


@exam_permission_required(["manage"])
def add_prep_section(request, exam_pk):
    exam = get_object_or_404(Exam, pk=exam_pk)

    next_position = (exam.prepSections.aggregate(max_pos=Max("position"))["max_pos"] or 0) + 1

    section = PrepSection.objects.create(
        exam=exam,
        title="New section",
        section_text="",
        position=next_position,
    )

    return render(
        request,
        "exam/preparation/_prep_section_card.html",
        {
            "exam_selected": exam,
            "section": section,
            "section_form": _build_section_form(section),
            "questions": _get_questions(section),
            "expanded": True,
            "saved": False,
        },
    )


@exam_permission_required(["manage"])
def delete_prep_section(request, exam_pk, section_id):
    exam = get_object_or_404(Exam, pk=exam_pk)
    section = get_object_or_404(PrepSection, pk=section_id, exam=exam)

    section.delete()
    _renumber_sections(exam)
    update_exam_latex(exam)

    return render(
        request,
        "exam/preparation/_prep_sections_list.html",
        {
            "exam_selected": exam,
            **_build_sections_list_context(exam),
        },
    )


# -------------------------
# Questions
# -------------------------

@exam_permission_required(["manage"])
def prep_question_panel(request, exam_pk, question_id):
    question = get_object_or_404(
        PrepQuestion,
        pk=question_id,
        prep_section__exam_id=exam_pk,
    )

    if request.method == "POST":
        form = _build_question_form(question, data=request.POST)
        saved = form.is_valid()

        if saved:
            form.save()
            question.refresh_from_db()
            update_exam_latex(question.prep_section.exam)
    else:
        form = _build_question_form(question)
        saved = False

    answers = _get_answers(question)

    return render(
        request,
        "exam/preparation/_prep_question_block.html",
        {
            "exam_selected": question.prep_section.exam,
            "section": question.prep_section,
            "question": question,
            "question_form": form,
            "answers": answers,
            "saved": saved,
        },
    )


@exam_permission_required(["manage"])
def add_prep_question(request, exam_pk, section_id):
    exam = get_object_or_404(Exam, pk=exam_pk)
    section = get_object_or_404(PrepSection, pk=section_id, exam=exam)

    if request.method == "POST":
        form = CreatePrepQuestionForm(request.POST)

        if form.is_valid():
            question_type = form.cleaned_data["question_type"]
            nb_answers = form.cleaned_data.get("nb_answers") or 0
            title = form.cleaned_data.get("title") or "New question"

            next_position = (section.prepQuestions.aggregate(max_pos=Max("position"))["max_pos"] or 0) + 1

            question = PrepQuestion.objects.create(
                prep_section=section,
                question_type=question_type,
                title=title,
                question_text="",
                position=next_position,
            )

            if question_type.code in ["SCQ", "MCQ"]:
                for i in range(nb_answers):
                    PrepQuestionAnswer.objects.create(
                        prep_question=question,
                        title=f"Answer {i + 1}",
                        answer_text="",
                        is_correct=False,
                        position=i + 1,
                    )
            elif question_type.code == "TF":
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

            update_exam_latex(section.exam)

            return render(
                request,
                "exam/preparation/_prep_questions_list.html",
                {
                    "exam_selected": exam,
                    "section": section,
                    "questions": _get_questions(section),
                },
            )

        return render(
            request,
            "exam/preparation/_prep_add_question_form.html",
            {
                "exam_selected": exam,
                "form": form,
                "section": section,
            },
        )

    form = CreatePrepQuestionForm(initial={"section_pk": section_id})

    return render(
        request,
        "exam/preparation/_prep_add_question_form.html",
        {
            "exam_selected": exam,
            "form": form,
            "section": section,
        },
    )


@exam_permission_required(["manage"])
def delete_prep_question(request, exam_pk, question_id):
    question = get_object_or_404(
        PrepQuestion,
        pk=question_id,
        prep_section__exam_id=exam_pk,
    )
    section = question.prep_section

    question.delete()
    _renumber_questions(section)
    update_exam_latex(section.exam)

    return render(
        request,
        "exam/preparation/_prep_questions_list.html",
        {
            "exam_selected": section.exam,
            "section": section,
            "questions": _get_questions(section),
        },
    )


# -------------------------
# Answers
# -------------------------

@exam_permission_required(["manage"])
def prep_answers_block(request, exam_pk, question_id):
    question = get_object_or_404(
        PrepQuestion,
        pk=question_id,
        prep_section__exam_id=exam_pk,
    )

    return render(
        request,
        "exam/preparation/_prep_answers_block.html",
        {
            "exam_selected": question.prep_section.exam,
            "question": question,
            "answers": _get_answers(question),
        },
    )


@exam_permission_required(["manage"])
def prep_answer_panel(request, exam_pk, answer_id):
    answer = get_object_or_404(
        PrepQuestionAnswer,
        pk=answer_id,
        prep_question__prep_section__exam_id=exam_pk,
    )

    if request.method == "POST":
        form = _build_answer_form(answer, data=request.POST)
        saved = form.is_valid()

        if saved:
            form.save()
            answer.refresh_from_db()
            update_exam_latex(answer.prep_question.prep_section.exam)
    else:
        form = _build_answer_form(answer)
        saved = False

    return render(
        request,
        "exam/preparation/_prep_answer_row.html",
        {
            "exam_selected": answer.prep_question.prep_section.exam,
            "question": answer.prep_question,
            "answer": answer,
            "answer_form": form,
            "saved": saved,
        },
    )


@exam_permission_required(["manage"])
def add_prep_answer(request, exam_pk, question_id):
    question = get_object_or_404(
        PrepQuestion,
        pk=question_id,
        prep_section__exam_id=exam_pk,
    )

    next_position = (question.prepAnswers.aggregate(max_pos=Max("position"))["max_pos"] or 0) + 1

    PrepQuestionAnswer.objects.create(
        prep_question=question,
        title="New answer",
        answer_text="",
        is_correct=False,
        position=next_position,
    )

    update_exam_latex(question.prep_section.exam)

    return render(
        request,
        "exam/preparation/_prep_answers_block.html",
        {
            "exam_selected": question.prep_section.exam,
            "question": question,
            "answers": _get_answers(question),
        },
    )


@exam_permission_required(["manage"])
def delete_prep_answer(request, exam_pk, answer_id):
    answer = get_object_or_404(
        PrepQuestionAnswer,
        pk=answer_id,
        prep_question__prep_section__exam_id=exam_pk,
    )
    question = answer.prep_question

    answer.delete()
    _renumber_answers(question)
    update_exam_latex(question.prep_section.exam)

    return render(
        request,
        "exam/preparation/_prep_answers_block.html",
        {
            "exam_selected": question.prep_section.exam,
            "question": question,
            "answers": _get_answers(question),
        },
    )


@exam_permission_required(["manage"])
def exam_preview_pdf(request, exam_pk):
    return HttpResponse("")


# -------------------------
# Scoring formulas
# -------------------------

def _get_scoring_formula_scope(prep_section=None, prep_question=None, prep_answer=None):
    if prep_answer:
        return "answer"
    if prep_question:
        return "question"
    if prep_section:
        return "section"
    return "exam"


def _get_scoring_formula_queryset(exam_pk, prep_section=None, prep_question=None, prep_answer=None):
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


@exam_permission_required(["manage"])
def scoring_formulas_modal(request, exam_pk):
    if request.method == "GET":
        prep_section = request.GET.get("prep_section") or None
        prep_question = request.GET.get("prep_question") or None
        prep_answer = request.GET.get("prep_answer") or None

        scope = _get_scoring_formula_scope(
            prep_section=prep_section,
            prep_question=prep_question,
            prep_answer=prep_answer,
        )

        queryset = _get_scoring_formula_queryset(
            exam_pk=exam_pk,
            prep_section=prep_section,
            prep_question=prep_question,
            prep_answer=prep_answer,
        )

        formset = PrepScoringFormulaFormSet(
            queryset=queryset,
            form_kwargs={
                "scope": scope,
                "exam_pk": exam_pk,
                "prep_section": prep_section,
                "prep_question": prep_question,
                "prep_answer": prep_answer,
            },
        )

        return render(
            request,
            "exam/preparation/_prep_scoring_formulas_modal_body.html",
            {
                "formset": formset,
                "exam_pk": exam_pk,
                "prep_section": prep_section,
                "prep_question": prep_question,
                "prep_answer": prep_answer,
                "scope": scope,
            },
        )

    if request.method == "POST":
        prep_section = request.POST.get("prep_section") or None
        prep_question = request.POST.get("prep_question") or None
        prep_answer = request.POST.get("prep_answer") or None

        scope = _get_scoring_formula_scope(
            prep_section=prep_section,
            prep_question=prep_question,
            prep_answer=prep_answer,
        )

        queryset = _get_scoring_formula_queryset(
            exam_pk=exam_pk,
            prep_section=prep_section,
            prep_question=prep_question,
            prep_answer=prep_answer,
        )

        formset = PrepScoringFormulaFormSet(
            request.POST,
            queryset=queryset,
            form_kwargs={
                "scope": scope,
                "exam_pk": exam_pk,
                "prep_section": prep_section,
                "prep_question": prep_question,
                "prep_answer": prep_answer,
            },
        )

        if formset.is_valid():
            instances = formset.save(commit=False)

            for obj in formset.deleted_objects:
                obj.delete()

            for instance in instances:
                if not instance.formula:
                    continue

                instance.exam_id = exam_pk

                if scope == "exam":
                    instance.prep_section = None
                    instance.prep_question = None
                    instance.prep_answer = None
                elif scope == "section":
                    instance.prep_section_id = prep_section
                    instance.prep_question = None
                    instance.prep_answer = None
                elif scope == "question":
                    instance.prep_section = None
                    instance.prep_question_id = prep_question
                    instance.prep_answer = None
                elif scope == "answer":
                    instance.prep_section = None
                    instance.prep_question = None
                    instance.prep_answer_id = prep_answer

                instance.save()

            return JsonResponse(
                {
                    "success": True,
                    "message": "Formulas saved successfully.",
                }
            )

        html = render(
            request,
            "exam/preparation/_prep_scoring_formulas_modal_body.html",
            {
                "formset": formset,
                "exam_pk": exam_pk,
                "prep_section": prep_section,
                "prep_question": prep_question,
                "prep_answer": prep_answer,
                "scope": scope,
            },
        ).content.decode("utf-8")

        return JsonResponse(
            {
                "success": False,
                "html": html,
            }
        )

    return JsonResponse(
        {
            "success": False,
            "message": "Invalid request method.",
        },
        status=400,
    )


@exam_permission_required(["manage"])
def delete_scoring_formula(request, exam_pk, pk):
    if request.method != "POST":
        return JsonResponse(
            {
                "success": False,
                "message": "Invalid request method.",
            },
            status=405,
        )

    obj = get_object_or_404(PrepScoringFormula, pk=pk, exam_id=exam_pk)
    obj.delete()

    return JsonResponse(
        {
            "success": True,
            "message": "Scoring formula deleted successfully.",
        }
    )