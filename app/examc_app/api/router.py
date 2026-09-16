from rest_framework import routers

from examc_app.api.viewsets.exam import ExamDataTablesViewSet

examc_router = routers.DefaultRouter()

examc_router.register(r"exams/datatables", ExamDataTablesViewSet, basename="exam-datatables")
