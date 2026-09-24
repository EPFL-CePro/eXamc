from typing import Any

from django.db.models import QuerySet
from rest_framework.filters import BaseFilterBackend
from rest_framework.request import Request
from rest_framework.views import APIView


class ExamRoleFilterBackend(BaseFilterBackend):
    """Restricts exams to those where the current user has the given role (?filter=<role>)."""

    def filter_queryset(self, request: Request, queryset: QuerySet[Any], view: APIView) -> QuerySet[Any]:
        role = request.query_params.get("filter", "").strip()
        if not role or role == "all":
            return queryset
        return queryset.filter(exam_users__user=request.user, exam_users__role=role).distinct()