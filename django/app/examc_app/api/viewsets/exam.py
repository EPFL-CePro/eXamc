from django.db.models import Q
from rest_framework import mixins, viewsets
from rest_framework.response import Response

from examc_app.api.datatables import DataTablesRequest
from examc_app.api.serializers.exam import ExamDataTableRowSerializer
from examc_app.utils.dashboard import get_dashboard_exam_queryset

# DataTables column index -> model field(s) for server-side ordering.
# Computed columns (role, modules, review, actions) are orderable: false in the JS config.
ORDER_COLUMN_MAP = {
    0: ["code"],  # exam
    1: ["date"],  # date
}


class ExamDataTablesViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    """
    Exams for the dashboard's "select" table.

    GET /api/exams/datatables/ -> DataTables server-side protocol
    """
    serializer_class = ExamDataTableRowSerializer

    def get_queryset(self):
        return get_dashboard_exam_queryset(self.request.user)

    def list(self, request, *args, **kwargs):
        dt = DataTablesRequest.from_query_params(request.query_params)
        base_qs = self.get_queryset()
        exams = base_qs

        if dt.search:
            exams = exams.filter(Q(code__icontains=dt.search) | Q(name__icontains=dt.search))

        role = request.query_params.get("filter", "").strip()
        if role and role != "all":
            exams = exams.filter(exam_users__user=request.user, exam_users__role=role).distinct()

        exams = dt.order(exams, ORDER_COLUMN_MAP)
        serializer = self.get_serializer(dt.page(exams), many=True)

        return Response(dt.response(
            total=base_qs.count(),
            filtered=exams.count(),
            data=serializer.data,
        ))