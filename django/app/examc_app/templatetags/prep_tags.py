from django import template
from django.utils.html import format_html
from django.utils.safestring import mark_safe

from examc_app.utils.preparation_functions import (
    get_applied_scorings,
    scoring_badge_text,
    scoring_info_text,
    scoring_lock_reason,
)

register = template.Library()

def applied_scorings(exam) -> dict:
    """The formulas of the exam are read once per exam object, that is once per request."""
    scorings = getattr(exam, "_prep_applied_scorings", None)
    if scorings is None:
        scorings = exam._prep_applied_scorings = get_applied_scorings(exam)
    return scorings


@register.simple_tag
def prep_scoring_info(exam, kind, pk):
    """
    The scoring formula applied to a question (kind "question") or an answer (kind "answer") of the exam, with its
    level (see get_applied_scorings). `data-prep-scoring-*` lets the page update the text when the formulas change.
    """
    scorings = applied_scorings(exam)

    return format_html(
        '<span class="prep-scoring-info" data-prep-scoring-kind="{}" data-prep-scoring-id="{}">{}</span>',
        kind, pk, scoring_info_text(scorings["questions" if kind == "question" else "answers"].get(pk)))


@register.simple_tag
def prep_scoring_badge(exam, kind, pk=0):
    """
    The small frame in a Scoring button with what the level has formulas for (see scoring_badge_text): kind is "exam"
    (pk 0), "section", "question" or "answer". Hidden when the level has none; the page updates it when they change.
    """
    text = scoring_badge_text(applied_scorings(exam)["defined"][kind].get(pk))

    return format_html(
        '<span class="badge prep-badge" data-prep-scoring-badge-kind="{}" data-prep-scoring-badge-id="{}"{}>{}</span>',
        kind, pk, "" if text else mark_safe(' style="display: none"'), text)


@register.simple_tag
def prep_scoring_lock(exam) -> str:
    """
    Why the Scoring buttons are disabled (AMC works on the project: see scoring_lock_reason), or "". They stay enabled
    once the exam is final. Read once per exam object, that is once per request.
    """
    reason = getattr(exam, "_prep_scoring_lock", None)
    if reason is None:
        reason = exam._prep_scoring_lock = scoring_lock_reason(exam) or ""
    return reason

