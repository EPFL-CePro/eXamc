"""Scoring formulas: dialog, deletion and what each question and answer applies."""

from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_POST

from examc_app.decorators import exam_permission_required
from examc_app.forms.preparation import PrepScoringFormulaFormSet
from examc_app.models import Exam, PrepScoringFormula
from examc_app.utils.preparation_functions import (
    ensure_exam_not_finalized,
    get_applied_scorings,
    get_scoring_formula_queryset,
    get_scoring_formula_scope,
    save_scoring_formulas,
    scoring_badges,
    scoring_info_text,
)
from examc_app.utils.preparation_latex_functions import update_exam_latex


@exam_permission_required(["manage"])
def scoring_infos(request, exam_pk):
    """The text next to the Scoring button of each question and answer, and the one on the Scoring button of each
    level (see get_applied_scorings), read again by the page when the dialog of the formulas is closed."""
    exam = get_object_or_404(Exam, pk=exam_pk)
    scorings = get_applied_scorings(exam)

    return JsonResponse({
        "questions": {str(pk): scoring_info_text(info) for pk, info in scorings["questions"].items()},
        "answers": {str(pk): scoring_info_text(info) for pk, info in scorings["answers"].items()},
        "badges": scoring_badges(scorings["defined"]),
    })


@exam_permission_required(["manage"])
def scoring_formulas_modal(request, exam_pk):
    if request.method == "GET":
        prep_section = request.GET.get("prep_section") or None
        prep_question = request.GET.get("prep_question") or None
        prep_answer = request.GET.get("prep_answer") or None

        scope = get_scoring_formula_scope(
            prep_section=prep_section,
            prep_question=prep_question,
            prep_answer=prep_answer,
        )

        queryset = get_scoring_formula_queryset(
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

        scope = get_scoring_formula_scope(
            prep_section=prep_section,
            prep_question=prep_question,
            prep_answer=prep_answer,
        )

        queryset = get_scoring_formula_queryset(
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
            save_scoring_formulas(
                formset,
                exam_pk=exam_pk,
                scope=scope,
                prep_section=prep_section,
                prep_question=prep_question,
                prep_answer=prep_answer,
            )

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
@require_POST
def delete_scoring_formula(request, exam_pk, pk):
    exam = get_object_or_404(Exam, pk=exam_pk)
    locked = ensure_exam_not_finalized(exam)
    if locked:
        return locked

    obj = get_object_or_404(PrepScoringFormula, pk=pk, exam_id=exam_pk)
    obj.delete()
    # The formula is removed from global_scoring.tex or from its questions and answers
    update_exam_latex(exam)

    return JsonResponse(
        {
            "success": True,
            "message": "Scoring formula deleted successfully.",
        }
    )
