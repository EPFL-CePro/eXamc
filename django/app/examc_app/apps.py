from django.apps import AppConfig
from django.contrib.auth import get_user_model
from simple_history import register

class ExamcAppConfig(AppConfig):
    name = "examc_app"
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self):
        user = get_user_model()
        if not hasattr(user, "history"):
            register(user, app=self.name)