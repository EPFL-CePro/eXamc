from typing import Any

from examc_app.models import Exam

from django.utils.html import format_html, format_html_join
from django.utils.safestring import mark_safe
from rest_framework import serializers

from examc_app.utils.dashboard import build_exam_card

_NOT_BUILT = object()

class ExamDataTableRowSerializer(serializers.Serializer):
    exam = serializers.SerializerMethodField()
    date = serializers.SerializerMethodField()
    role = serializers.SerializerMethodField()
    modules = serializers.SerializerMethodField()
    review = serializers.SerializerMethodField()
    actions = serializers.SerializerMethodField()
    DT_RowAttr = serializers.SerializerMethodField()

    def _card(self, exam: Exam) -> dict[str, Any] | None:
        card = getattr(exam, "_card_cache", _NOT_BUILT)
        if card is _NOT_BUILT:
            card = build_exam_card(self.context["request"].user, exam)
            exam._card_cache = card
        return card


    # noinspection PyMethodMayBeStatic
    def get_exam(self, exam):
        return format_html(
            "<strong>{}</strong><br><span class='dashboard-muted'>{}</span>",
            exam.code, exam.name,
        )

    # noinspection PyMethodMayBeStatic
    def get_date(self, exam):
        if exam.date is None: return ""
        return exam.date.strftime("%Y-%m-%d")

    def get_role(self, exam):
        card = self._card(exam)
        if card is None: return None

        return card["role"]

    def get_modules(self, exam):
        card = self._card(exam)
        if card is None: return None

        value = card["module_badges"]

        if not value:
            return None
        return format_html(
            '<div class="dashboard-badges">{}</div>',
            format_html_join("", '<span class="badge badge-secondary">{}</span>', ((b,) for b in value)),
        )

    def get_review(self, exam):
        card = self._card(exam)
        if card is None: return None

        value = card["review_progress"]

        if not value:
            return mark_safe('<span class="dashboard-muted">-</span>')

        bar_class = "bg-success" if value["percent"] == 100 else "bg-warning"

        return format_html(
            '<div class="dashboard-muted">{} / {}</div>'
            '<div class="progress dashboard-review-progress">'
            '<div class="progress-bar {}" role="progressbar" style="width: {}%;" '
            'aria-valuenow="{}" aria-valuemin="0" aria-valuemax="100"></div></div>',
            value["graded"], value["total"], bar_class, value["percent"], value["percent"],
        )

    def get_actions(self, exam: Exam):
        card = self._card(exam)
        if card is None: return None

        value = card["actions"]

        return format_html(
            '<div class="dashboard-actions">{}</div>',
            format_html_join(
                "",
                '<a class="btn btn-dark btn-sm" href="{}">'
                '<i class="fa-solid {} dashboard-action-icon"></i>{}</a>',
                ((a["url"], a["icon"], a["label"]) for a in value),
            )
        )

    def get_DT_RowAttr(self, exam: Exam):
        card = self._card(exam)
        if card is None: return None

        return {
            "class": "dashboard-exam-row",
            "data-filters": " ".join(card.get("filter_tags", [])),
            "data-search": card.get("search_text", ""),
        }
