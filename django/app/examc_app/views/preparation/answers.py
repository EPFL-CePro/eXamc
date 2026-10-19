"""Answers of a question: panel, add, delete and reorder."""

import json

from django.http import HttpResponseBadRequest
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_POST

from examc_app.decorators import exam_permission_required
from examc_app.models import Exam, PrepQuestion, PrepQuestionAnswer
from examc_app.utils.preparation_functions import (
    build_answer_form,
    create_prep_answer,
    ensure_exam_not_finalized,
    is_exam_locked,
    get_answers,
    renumber_answers,
)
from examc_app.utils.preparation_latex_functions import update_exam_latex

from ._htmx import with_save_feedback


@exam_permission_required(["manage"])
def prep_answer_panel(request, exam_pk, answer_id):
    answer = get_object_or_404(
        PrepQuestionAnswer,
        pk=answer_id,
        prep_question__prep_section__exam_id=exam_pk,
    )

    if request.method == "POST":
        locked = ensure_exam_not_finalized(answer.prep_question.prep_section.exam)
        if locked:
            return locked

        form = build_answer_form(answer, data=request.POST)
        saved = form.is_valid()

        if saved:
            form.save()
            answer.refresh_from_db()
            update_exam_latex(answer.prep_question.prep_section.exam)
    else:
        form = build_answer_form(answer)
        saved = False

    response = render(
        request,
        "exam/preparation/_prep_answer_row.html",
        {
            "exam_selected": answer.prep_question.prep_section.exam,
            "question": answer.prep_question,
            "answer": answer,
            "answer_form": form,
            "saved": saved,
            "is_exam_locked": is_exam_locked(answer.prep_question.prep_section.exam),
        },
    )
    return with_save_feedback(request, response, saved)


@exam_permission_required(["manage"])
@require_POST
def add_prep_answer(request, exam_pk, question_id):
    exam = Exam.objects.get(pk=exam_pk)

    locked = ensure_exam_not_finalized(exam)
    if locked:
        return locked

    question = get_object_or_404(
        PrepQuestion,
        pk=question_id,
        prep_section__exam_id=exam_pk,
    )

    create_prep_answer(question)

    update_exam_latex(question.prep_section.exam)

    return render(
        request,
        "exam/preparation/_prep_answers_block.html",
        {
            "exam_selected": question.prep_section.exam,
            "question": question,
            "answers": get_answers(question),
        },
    )


@exam_permission_required(["manage"])
@require_POST
def delete_prep_answer(request, exam_pk, answer_id):
    exam = Exam.objects.get(pk=exam_pk)
    locked = ensure_exam_not_finalized(exam)
    if locked:
        return locked

    answer = get_object_or_404(
        PrepQuestionAnswer,
        pk=answer_id,
        prep_question__prep_section__exam_id=exam_pk,
    )
    question = answer.prep_question

    answer.delete()
    renumber_answers(question)
    update_exam_latex(question.prep_section.exam)

    return render(
        request,
        "exam/preparation/_prep_answers_block.html",
        {
            "exam_selected": question.prep_section.exam,
            "question": question,
            "answers": get_answers(question),
        },
    )


@exam_permission_required(["manage"])
def reorder_prep_answers(request, exam_pk, question_id):
    if request.method != "POST":
        return HttpResponseBadRequest("Invalid method")

    question = get_object_or_404(
        PrepQuestion,
        pk=question_id,
        prep_section__exam_id=exam_pk,
    )

    locked = ensure_exam_not_finalized(question.prep_section.exam)
    if locked:
        return locked

    try:
        payload = json.loads(request.body)
        answers_data = payload.get("answers", [])
    except (json.JSONDecodeError, TypeError):
        return HttpResponseBadRequest("Invalid JSON")

    answer_map = {answer.id: answer for answer in question.prepAnswers.all()}

    for item in answers_data:
        try:
            answer_id = int(item["id"])
            position = int(item["position"])
        except (KeyError, TypeError, ValueError):
            continue

        answer = answer_map.get(answer_id)
        if answer and answer.position != position:
            answer.position = position
            answer.save(update_fields=["position"])

    update_exam_latex(question.prep_section.exam)

    return render(
        request,
        "exam/preparation/_prep_answers_block.html",
        {
            "exam_selected": question.prep_section.exam,
            "question": question,
            "answers": get_answers(question),
            "is_exam_locked": is_exam_locked(question.prep_section.exam),
        },
    )
