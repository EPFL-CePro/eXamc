from django.db.models import QuerySet
from rest_framework import mixins, viewsets

from examc_app.api.datatables import DataTablesFilterBackend
from examc_app.api.filters.exam import ExamRoleFilterBackend
from examc_app.api.serializers.exam import ExamRowSerializer
from examc_app.models import Exam
from examc_app.utils.dashboard import get_dashboard_exam_queryset


class ExamViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    """
    Exams for the dashboard's "select" table.

    GET /api/exams/?filter=<role>
    """
    serializer_class = ExamRowSerializer
    filter_backends = [ExamRoleFilterBackend, DataTablesFilterBackend]
    search_fields = ["code", "name"]
    # Column index -> model field(s) for server-side ordering.
    # Computed columns (role, modules, review, actions) are orderable: false in the JS config.
    ordering_columns = {
        0: ["code"],  # exam
        1: ["date"],  # date
    }

    def get_queryset(self) -> "QuerySet[Exam]":
        return get_dashboard_exam_queryset(self.request.user)