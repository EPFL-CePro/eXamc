from rest_framework import viewsets

from examc_app.api.serializers import ExamSerializer
from examc_app.models import Exam


class ExamViewSet(viewsets.ModelViewSet):
    queryset = Exam.objects.all()
    serializer_class = ExamSerializer