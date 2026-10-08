from django.contrib.auth.models import User
from django.utils import timezone
from rest_framework import serializers


class ConnectedUserRowSerializer(serializers.Serializer):
    username = serializers.CharField()
    last_login = serializers.SerializerMethodField()

    @staticmethod
    def get_last_login(user: User) -> str:
        if user.last_login is None:
            return ""

        return timezone.localtime(user.last_login).strftime("%Y-%m-%d %H:%M:%S")
