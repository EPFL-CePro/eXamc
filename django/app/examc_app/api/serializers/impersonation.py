from django.contrib.auth.models import User
from django.urls import reverse
from django.utils.html import format_html
from django.utils.safestring import SafeString
from django.utils.timezone import localtime
from rest_framework import serializers


def render_impersonate_button(user: User, csrf_token: str) -> SafeString:
    return format_html(
        '<form method="post" action="{}" class="d-inline">'
        '<input type="hidden" name="csrfmiddlewaretoken" value="{}">'
        '<button type="submit" class="btn btn-dark btn-sm">'
        '<i class="fa-solid fa-user-secret" style="margin-right:5px;"></i>Impersonate'
        '</button>'
        '</form>',
        reverse("impersonate_start", kwargs={"user_pk": user.pk}),
        csrf_token,
    )


class ImpersonationUserRowSerializer(serializers.Serializer):
    username = serializers.CharField()
    name = serializers.SerializerMethodField()
    email = serializers.EmailField()
    last_login = serializers.DateTimeField()
    action = serializers.SerializerMethodField()

    # noinspection PyMethodMayBeStatic
    def get_name(self, user: User) -> str:
        return f"{user.first_name} {user.last_name}".strip()

    def get_action(self, user: User) -> SafeString:
        csrf_token: str = self.context["csrf_token"]
        return render_impersonate_button(user, csrf_token)