"""Questions of a section: panel, add, delete, reorder and import from a .tex file."""

import json

from django.http import HttpResponse, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_POST

from examc_app.decorators import exam_permission_required
from examc_app.forms.preparation import CreatePrepQuestionForm
from examc_app.models import Exam, PrepQuestion, PrepSection
from examc_app.services.preparation.questions_import import (
    QuestionsImportError,
    TEMPLATE_PATH as QUESTIONS_TEMPLATE_PATH,
    decode_questions_file,
    import_questions,
    parse_questions_tex,
)
from examc_app.utils.preparation_functions import (
    build_question_form,
    create_prep_question,
    ensure_exam_not_finalized,
    is_exam_locked,
    get_answers,
    get_questions,
    renumber_questions,
    update_open_answers,
)
from examc_app.utils.preparation_latex_functions import update_exam_latex

from ._htmx import with_save_feedback


@exam_permission_required(["manage"])
def prep_question_panel(request, exam_pk, question_id):
    question = get_object_or_404(
        PrepQuestion,
        pk=question_id,
        prep_section__exam_id=exam_pk,
    )

    if request.method == "POST":
        exam = Exam.objects.get(pk=exam_pk)
        locked = ensure_exam_not_finalized(exam)
        if locked:
            return locked

        form = build_question_form(question, data=request.POST)
        saved = form.is_valid()

        if saved:
            form.save()
            question.refresh_from_db()

            if question.question_type.code == 'OPEN':
                update_open_answers(question)

            update_exam_latex(question.prep_section.exam)
    else:
        form = build_question_form(question)
        saved = False

    answers = get_answers(question)

    response = render(
        request,
        "exam/preparation/partials/_prep_question_block.html",
        {
            "exam_selected": question.prep_section.exam,
            "section": question.prep_section,
            "question": question,
            "question_form": form,
            "answers": answers,
            "saved": saved,
            "is_exam_locked": is_exam_locked(question.prep_section.exam),
        },
    )
    return with_save_feedback(request, response, saved)


@exam_permission_required(["manage"])
def add_prep_question(request, exam_pk, section_id):
    exam = get_object_or_404(Exam, pk=exam_pk)
    section = get_object_or_404(PrepSection, pk=section_id, exam=exam)

    if request.method == "POST":
        locked = ensure_exam_not_finalized(exam)
        if locked:
            return locked

        form = CreatePrepQuestionForm(request.POST)

        if form.is_valid():
            question_type = form.cleaned_data["question_type"]
            nb_answers = form.cleaned_data.get("nb_answers") or 0
            title = form.cleaned_data.get("title") or "New question"

            create_prep_question(
                section=section,
                question_type=question_type,
                title=title,
                nb_answers=nb_answers,
            )

            update_exam_latex(section.exam)

            return render(
                request,
                "exam/preparation/partials/_prep_questions_list.html",
                {
                    "exam_selected": exam,
                    "section": section,
                    "questions": get_questions(section),
                },
            )

        return render(
            request,
            "exam/preparation/partials/_prep_add_question_form.html",
            {
                "exam_selected": exam,
                "form": form,
                "section": section,
            },
        )

    form = CreatePrepQuestionForm(initial={"section_pk": section_id})

    return render(
        request,
        "exam/preparation/partials/_prep_add_question_form.html",
        {
            "exam_selected": exam,
            "form": form,
            "section": section,
        },
    )


@exam_permission_required(["manage"])
@require_POST
def delete_prep_question(request, exam_pk, question_id):
    exam = Exam.objects.get(pk=exam_pk)

    locked = ensure_exam_not_finalized(exam)
    if locked:
        return locked

    question = get_object_or_404(
        PrepQuestion,
        pk=question_id,
        prep_section__exam_id=exam_pk,
    )
    section = question.prep_section

    question.delete()
    renumber_questions(section)
    update_exam_latex(section.exam)

    return render(
        request,
        "exam/preparation/partials/_prep_questions_list.html",
        {
            "exam_selected": section.exam,
            "section": section,
            "questions": get_questions(section),
        },
    )


@exam_permission_required(["manage"])
@require_POST
def reorder_prep_questions(request, exam_pk, section_id):
    section = get_object_or_404(PrepSection, pk=section_id, exam_id=exam_pk)

    locked = ensure_exam_not_finalized(section.exam)
    if locked:
        return locked

    try:
        payload = json.loads(request.body)
        questions_data = payload.get("questions", [])
    except (json.JSONDecodeError, TypeError):
        return HttpResponseBadRequest("Invalid JSON")

    question_map = {question.id: question for question in section.prepQuestions.all()}

    for item in questions_data:
        try:
            question_id = int(item["id"])
            position = int(item["position"])
        except (KeyError, TypeError, ValueError):
            continue

        question = question_map.get(question_id)
        if question and question.position != position:
            question.position = position
            question.save(update_fields=["position"])

    update_exam_latex(section.exam)

    return render(
        request,
        "exam/preparation/partials/_prep_questions_list.html",
        {
            "exam_selected": section.exam,
            "section": section,
            "questions": get_questions(section),
            "is_exam_locked": is_exam_locked(section.exam),
        },
    )


@exam_permission_required(["manage"])
def import_prep_questions(request, exam_pk, section_id):
    """Adds the questions of an uploaded .tex file at the end of a section (see services.preparation.questions_import).
    Nothing is created when the file has a problem: the form is shown again with them."""
    exam = get_object_or_404(Exam, pk=exam_pk)
    section = get_object_or_404(PrepSection, pk=section_id, exam=exam)
    form_template = "exam/preparation/_prep_import_questions_form.html"
    form_context = {"exam_selected": exam, "section": section}

    if request.method != "POST":
        return render(request, form_template, form_context)

    locked = ensure_exam_not_finalized(exam)
    if locked:
        return locked

    def show_errors(errors):
        # The errors replace the form in the modal, not the list of the questions
        response = render(request, form_template, {**form_context, "errors": errors})
        response["HX-Retarget"] = "#modalImportQuestionsBody"
        response["HX-Reswap"] = "innerHTML"
        return response

    uploaded_file = request.FILES.get("questions_file")
    if not uploaded_file:
        return show_errors(["No file selected."])

    try:
        parsed_questions = parse_questions_tex(decode_questions_file(uploaded_file.read()))
        import_questions(section, parsed_questions)
    except QuestionsImportError as error:
        return show_errors(error.errors)

    update_exam_latex(exam)

    return render(
        request,
        "exam/preparation/partials/_prep_questions_list.html",
        {
            "exam_selected": exam,
            "section": section,
            "questions": get_questions(section),
        },
    )


@exam_permission_required(["manage"])
def download_prep_questions_template(request, exam_pk):
    response = HttpResponse(QUESTIONS_TEMPLATE_PATH.read_text(encoding="utf-8"), content_type="application/x-tex")
    response["Content-Disposition"] = 'attachment; filename="questions_import_template.tex"'
    return response
