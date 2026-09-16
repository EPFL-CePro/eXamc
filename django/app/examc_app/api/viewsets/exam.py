from django.db.models import Q
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from examc_app.api.serializers.exam import ExamSerializer, ExamDataTableRowSerializer
from examc_app.models import Exam
from examc_app.utils.dashboard import get_dashboard_exam_queryset, build_exam_card


class ExamViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]

    queryset = Exam.objects.all()
    serializer_class = ExamSerializer

    def get_queryset(self):
        user = self.request.user

        if user.is_superuser: return Exam.objects.all()
        return Exam.objects.filter(overall=False, exam_users__user=user).distinct()


# DataTables column index -> real queryset field(s), for server-side ordering.
# Only actual model fields can be ordered this way; computed columns
# (role, modules, review and actions) are intentionally excluded here
# and marked orderable: false in the JS config.
ORDER_COLUMN_MAP = {
    0: ["code"],   # exam
    1: ["date"],   # date
}

class ExamDataTablesViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Exposes exams for the dashboard's "select" table.

    GET /api/exams/datatable/           -> DataTables-protocol list (draw/start/length/order/search)
    GET /api/exams/datatable/{pk}/      -> retrieve (from ReadOnlyModelViewSet, standard DRF shape)
    """
    permission_classes = [IsAuthenticated]
    serializer_class = ExamDataTableRowSerializer

    def get_queryset(self):
        return get_dashboard_exam_queryset(self.request.user)

    def get_serializer(self, *args, **kwargs):
        kwargs["user"] = self.request.user
        kwargs["build_card"] = build_exam_card

        return super().get_serializer(*args, **kwargs)

    def list(self, request, *args, **kwargs):
        params = request.query_params
        user = request.user

        base_qs = self.get_queryset()
        exams = base_qs

        search_value = params.get("search[value]", "").strip()

        if search_value:
            exams = exams.filter(
                Q(code__icontains=search_value) | Q(name__icontains=search_value)
            )

        custom_filter = params.get("filter", "").strip()
        if custom_filter and custom_filter != "all":
            exams = exams.filter(exam_users__user=user, exam_users__role=custom_filter).distinct()

        records_total = base_qs.count()
        records_filtered = exams.count()

        order_col_index = params.get("order[0][column]")
        order_dir = params.get("order[0][dir]", "asc")

        if order_col_index is not None:
            fields = ORDER_COLUMN_MAP.get(int(order_col_index))
            if fields:
                if order_dir == "desc":
                    fields = [f"-{f}" for f in fields]
                exams = exams.order_by(*fields)

        start = int(params.get("start", 0))
        length = int(params.get("length", 10))
        page_exams = list(exams[start:start + length]) if length != -1 else list(exams)

        serializer = self.get_serializer(page_exams, many=True)

        return Response({
            "draw": int(params.get("draw", 1)),
            "recordsTotal": records_total,
            "recordsFiltered": records_filtered,
            "data": serializer.data,
        })