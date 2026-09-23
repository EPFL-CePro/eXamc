from django.db.models import Q
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.request import Request
from rest_framework.response import Response

from examc_app.api.datatables import DataTablesRequest
from examc_app.api.decorators import exam_permission_required
from examc_app.api.serializers.student_presence import (
    StudentPresenceRowSerializer,
    StudentPresenceSerializer,
    render_presence_toggle,
)
from examc_app.models import Student
from examc_app.services.student.presence import set_student_presence

# DataTables column index -> model field(s) for server-side ordering.
# Scale columns come after these, so these indices never shift.
ORDER_COLUMN_MAP = {
    0: ["copie_no"],
    1: ["sciper"],
    2: ["name"],
    3: ["present"],
    4: ["points"],
}


class ExamStudentPresenceViewSet(viewsets.ViewSet):
    """
    GET   /api/exams/<exam_pk>/students-presence/             -> DataTables server-side protocol
    PATCH /api/exams/<exam_pk>/students-presence/<pk>/presence/ -> {"present": bool}
    """
    lookup_value_regex = r"\d+"

    @exam_permission_required(["manage", "see_results"])
    def list(self, request: Request, exam_pk: str) -> Response:
        dt = DataTablesRequest.from_query_params(request.query_params)
        base_qs = Student.objects.filter(exam_id=exam_pk)
        students = base_qs

        if dt.search:
            students = students.filter(
                Q(copie_no__icontains=dt.search)
                | Q(sciper__icontains=dt.search)
                | Q(name__icontains=dt.search)
            )

        students = dt.order(students, ORDER_COLUMN_MAP)
        serializer = StudentPresenceRowSerializer(
            dt.page(students), many=True, context={"request": request}
        )

        return Response(dt.response(
            total=base_qs.count(),
            filtered=students.count(),
            data=serializer.data,
        ))

    @action(detail=True, methods=["patch"])
    @exam_permission_required(["manage", "see_results"])
    def presence(self, request: Request, exam_pk: str, pk: str) -> Response:
        serializer = StudentPresenceSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        result = set_student_presence(
            exam_pk=exam_pk,
            student_pk=pk,
            present=serializer.validated_data["present"],
        )
        return Response({
            "student": result.student.pk,
            "present": result.student.present,
            "updated": result.updated,
            "present_students": result.present_students,
            "task_id": result.task_id,
            "html": render_presence_toggle(result.student),
        })