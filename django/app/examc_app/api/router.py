from rest_framework import routers

from examc_app.api.viewsets.exam import ExamDataTablesViewSet
from examc_app.api.viewsets.student_presence import ExamStudentPresenceViewSet

examc_router = routers.SimpleRouter()

examc_router.register(r"exams/datatables", ExamDataTablesViewSet, basename="exam-datatables")
examc_router.register(r"exams/(?P<exam_pk>\d+)/students-presence", ExamStudentPresenceViewSet, basename="exam-students-presence")