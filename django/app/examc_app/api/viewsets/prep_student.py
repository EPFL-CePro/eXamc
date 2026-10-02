from django.db.models import Q
from rest_framework import viewsets
from rest_framework.request import Request
from rest_framework.response import Response

from examc_app.api.datatables import DataTablesRequest
from examc_app.api.decorators import exam_permission_required
from examc_app.api.serializers.prep_student import PrepStudentRowSerializer
from examc_app.models import PrepStudent

# DataTables column index -> model field(s) for server-side ordering
ORDER_COLUMN_MAP = {
    0: ["copy_no"],
    1: ["sciper"],
    2: ["last_name", "first_name"],
    3: ["first_name"],
    4: ["email"],
    5: ["section"],
    6: ["room"],
    7: ["seat"],
}


class PrepStudentViewSet(viewsets.ViewSet):
    """
    GET /api/exams/<exam_pk>/prep-students/ -> DataTables server-side protocol
    """

    @exam_permission_required(["manage"])
    def list(self, request: Request, exam_pk: str) -> Response:
        dt = DataTablesRequest.from_query_params(request.query_params)
        base_qs = PrepStudent.objects.filter(exam_id=exam_pk)
        students = base_qs

        if dt.search:
            query = (
                Q(last_name__icontains=dt.search)
                | Q(first_name__icontains=dt.search)
                | Q(email__icontains=dt.search)
                | Q(section__icontains=dt.search)
                | Q(room__icontains=dt.search)
                | Q(seat__icontains=dt.search)
            )
            # sciper and copy_no are integers: compared exactly
            if dt.search.isdigit():
                query |= Q(sciper=int(dt.search)) | Q(copy_no=int(dt.search))
            students = students.filter(query)

        students = dt.order(students, ORDER_COLUMN_MAP)
        serializer = PrepStudentRowSerializer(dt.page(students), many=True)

        return Response(dt.response(
            total=base_qs.count(),
            filtered=students.count(),
            data=serializer.data,
        ))
