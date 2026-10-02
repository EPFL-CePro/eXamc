from django.shortcuts import get_object_or_404
from rest_framework import status, viewsets
from rest_framework.exceptions import PermissionDenied
from rest_framework.request import Request
from rest_framework.response import Response

from examc_app.api.decorators import exam_permission_required
from examc_app.api.serializers.prep_student import PrepStudentRowSerializer, PrepStudentUpdateSerializer
from examc_app.models import Exam, PrepStudent
from examc_app.services.person_directory import PersonDirectoryError
from examc_app.services.student.prep_import import StudentsFileError, correct_prep_student


class PrepStudentViewSet(viewsets.ViewSet):
    """
    GET   /api/exams/<exam_pk>/prep-students/       -> {"data": [...]}, all the students of the exam.
          An exam has at most ~550 students: DataTables searches and sorts them in the browser.
    PATCH /api/exams/<exam_pk>/prep-students/<pk>/  -> the corrected student (see correct_prep_student)
    """
    lookup_value_regex = r"\d+"

    @exam_permission_required(["manage"])
    def list(self, request: Request, exam_pk: str) -> Response:
        students = PrepStudent.objects.filter(exam_id=exam_pk).order_by("copy_no")
        return Response({"data": PrepStudentRowSerializer(students, many=True).data})

    @exam_permission_required(["manage"])
    def partial_update(self, request: Request, exam_pk: str, pk: str) -> Response:
        if get_object_or_404(Exam, pk=exam_pk).is_finalized:
            raise PermissionDenied("This exam is finalized. Unlock editing before making changes.")

        student = get_object_or_404(PrepStudent, pk=pk, exam_id=exam_pk)
        serializer = PrepStudentUpdateSerializer(student, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)

        try:
            student = correct_prep_student(student, serializer.validated_data)
        except StudentsFileError as error:
            return Response({"errors": error.errors}, status=status.HTTP_400_BAD_REQUEST)
        except PersonDirectoryError:
            return Response({"errors": ["The EPFL directory could not be reached: please try again later."]},
                            status=status.HTTP_503_SERVICE_UNAVAILABLE)

        return Response(PrepStudentRowSerializer(student).data)
