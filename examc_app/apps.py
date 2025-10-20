from django.apps import AppConfig
from django.contrib.auth import get_user_model
from simple_history import register


from examc import settings


class ExamcAppConfig(AppConfig):
    name = 'examc_app'

    def ready(self):
        User = get_user_model()
        # create HistoricalUser dans examc app
        register(User, app=self.name)