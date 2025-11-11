from django.apps import AppConfig
from django.contrib.auth import get_user_model
from simple_history import register

class ExamcAppConfig(AppConfig):
    name = "examc_app"
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self):
        User = get_user_model()
        if not hasattr(User, "history"):
            register(User, app=self.name)
        from .constance_hooks import recompute_now
        recompute_now()