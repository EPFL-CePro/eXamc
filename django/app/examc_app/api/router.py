from rest_framework import routers

from examc_app.api.viewsets.exam import ExamViewSet
from examc_app.api.viewsets.exam_student_presence import ExamStudentPresenceViewSet


examc_router = routers.SimpleRouter()

examc_router.register(r"exams", ExamViewSet, basename="api-exams")
examc_router.register(r"exams/(?P<exam_pk>\d+)/students-presence", ExamStudentPresenceViewSet, basename="api-exam-students-presence")