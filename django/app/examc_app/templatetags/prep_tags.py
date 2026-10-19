from django import template
from django.utils.html import format_html

from examc_app.utils.preparation_functions import get_applied_scorings, scoring_info_text

register = template.Library()

@register.simple_tag
def prep_scoring_info(exam, kind, pk):
    """
    The scoring formula applied to a question (kind "question") or an answer (kind "answer") of the exam, with its
    level (see get_applied_scorings). `data-prep-scoring-*` lets the page update the text when the formulas change.
    The formulas of the exam are read once per exam object, that is once per request.
    """
    scorings = getattr(exam, "_prep_applied_scorings", None)
    if scorings is None:
        scorings = exam._prep_applied_scorings = get_applied_scorings(exam)

    return format_html(
        '<span class="prep-scoring-info" data-prep-scoring-kind="{}" data-prep-scoring-id="{}">{}</span>',
        kind, pk, scoring_info_text(scorings["questions" if kind == "question" else "answers"].get(pk)))
