from rest_framework import routers

from examc_app.api.viewsets import ExamViewSet

examc_router = routers.DefaultRouter()
examc_router.register(r"exams", ExamViewSet)