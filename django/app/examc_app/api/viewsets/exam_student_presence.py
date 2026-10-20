from collections import defaultdict

from django.db.models import IntegerField, OuterRef, Q, Subquery
from django.db.models.functions import Cast
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.request import Request
from rest_framework.response import Response

from examc_app.api.datatables import DataTablesRequest
from examc_app.api.decorators import exam_permission_required
from examc_app.api.serializers.exam_student_presence import (
    StudentPresenceRowSerializer,
    StudentPresenceSerializer,
    render_presence_toggle,
)
from examc_app.models import Scale, Student, StudentScaleGrade
from examc_app.services.student.presence import set_student_presence

# DataTables column index -> field(s) for server-side ordering. "pk" breaks ties so pages stay stable.
# One column per scale follows these (added in list()), so these indices never shift.
ORDER_COLUMN_MAP = {
    0: ["copie_no_number", "copie_no", "pk"],  # copy numbers are text: sort "2" before "10"
    1: ["sciper", "pk"],
    2: ["name", "pk"],
    3: ["present", "pk"],
    4: ["points", "pk"],
}


class ExamStudentPresenceViewSet(viewsets.ViewSet):
    """
    GET   /api/exams/<exam_pk>/students-presence/                 -> DataTables server-side protocol
    PATCH /api/exams/<exam_pk>/students-presence/<pk>/presence/   -> {"present": bool}
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
        filtered = students.count()

        # Scales in the same order as the scale columns of the table. Grades are matched by
        # scale name like generate_isa_csv, because a common exam's scales are copies.
        scales = list(Scale.objects.filter(exam_id=exam_pk).order_by("pk"))

        # Sortable values that aren't plain columns: the copy number as a number, each scale's grade
        students = students.annotate(copie_no_number=Cast("copie_no", IntegerField()))
        order_columns = dict(ORDER_COLUMN_MAP)
        for index, scale in enumerate(scales, start=len(ORDER_COLUMN_MAP)):
            field = f"scale_grade_{scale.pk}"
            grade = StudentScaleGrade.objects.filter(student=OuterRef("pk"), scale__name=scale.name).values("grade")[:1]
            students = students.annotate(**{field: Subquery(grade)})
            order_columns[index] = [field, "pk"]

        page = list(dt.page(dt.order(students, order_columns)))

        # {student_pk: {scale_pk: grade}} for this page, in one query
        scale_pk_by_name = {scale.name: scale.pk for scale in scales}
        scale_values: dict[int, dict[int, str]] = defaultdict(dict)
        grades = StudentScaleGrade.objects.filter(
            student__in=page,
            scale__name__in=scale_pk_by_name,
        ).values_list("student_id", "scale__name", "grade")
        for student_id, scale_name, grade in grades:
            scale_values[student_id][scale_pk_by_name[scale_name]] = str(grade)

        serializer = StudentPresenceRowSerializer(
            page,
            many=True,
            context={"request": request, "scale_values": scale_values},
        )

        return Response(
            dt.response(
                total=base_qs.count(),
                filtered=filtered,
                data=serializer.data,
            )
        )

    # Not named "patch": DRF would also route PATCH on the list URL to a method with that name.
    # url_name="patch" keeps the route name "api-exam-students-presence-patch" used by reverse().
    @action(detail=True, methods=["patch"], url_path="presence", url_name="patch")
    @exam_permission_required(["manage", "see_results"])
    def set_presence(self, request: Request, exam_pk: int, pk: int) -> Response:
        serializer = StudentPresenceSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        result = set_student_presence(
            exam_pk=exam_pk,
            student_pk=pk,
            present=serializer.validated_data["present"],
        )
        return Response(
            {
                "student": result.student.pk,
                "present": result.student.present,
                "updated": result.updated,
                "present_students": result.present_students,
                "task_id": result.task_id,
                "html": render_presence_toggle(result.student),
            }
        )