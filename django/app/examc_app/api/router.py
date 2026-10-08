from rest_framework import routers

from examc_app.api.viewsets.amc.data_capture.manual import AmcDataCaptureManualViewSet
from examc_app.api.viewsets.connected_user import ConnectedUsersViewSet
from examc_app.api.viewsets.exam import ExamViewSet

from examc_app.api.viewsets.exam_student_presence import ExamStudentPresenceViewSet
from examc_app.api.viewsets.impersonation import ImpersonationUserViewSet
from examc_app.api.viewsets.prep_student import PrepStudentViewSet


examc_router = routers.SimpleRouter()

examc_router.register(
    r"exams",
    ExamViewSet,
    basename="api-exams"
)

examc_router.register(
r"connected-users",
    ConnectedUsersViewSet,
    basename="api-connected-users"
)

examc_router.register(
    r"exams/(?P<exam_pk>\d+)/students-presence",
    ExamStudentPresenceViewSet,
    basename="api-exam-students-presence"
)
examc_router.register(r"exams/(?P<exam_pk>\d+)/prep-students", PrepStudentViewSet, basename="api-exam-prep-students")


examc_router.register(
    r"impersonation/users",
    ImpersonationUserViewSet,
    basename="api-impersonation-users"
)

examc_router.register(
    r"exams/(?P<exam_pk>\d+)/amc-data-capture-manual",
    AmcDataCaptureManualViewSet,
    basename="api-amc-data-capture-manual",
)