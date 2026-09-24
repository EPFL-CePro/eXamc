from typing import Any

from django.contrib.auth.models import User
from django.db.models import QuerySet
from django.middleware.csrf import get_token
from rest_framework import mixins, viewsets

from examc_app.api.datatables import DataTablesFilterBackend, DataTablesPagination
from examc_app.api.permissions import IsSuperUser
from examc_app.api.serializers.impersonation import ImpersonationUserRowSerializer


def impersonable_users() -> "QuerySet[User]":
    return User.objects.filter(is_active=True, is_superuser=False)



class ImpersonationUserViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    """GET /api/impersonation/users/"""
    permission_classes = [IsSuperUser]
    serializer_class = ImpersonationUserRowSerializer
    filter_backends = [DataTablesFilterBackend]
    pagination_class = DataTablesPagination
    search_fields = ["username", "first_name", "last_name", "email"]
    ordering_columns = {
        0: ["username"],
        1: ["first_name", "last_name"],
        2: ["email"],
        3: ["last_login"],
    }

    def get_queryset(self) -> "QuerySet[User]":
        return User.objects.filter(is_active=True, is_superuser=False)

    def get_serializer_context(self) -> dict[str, Any]:
        context = super().get_serializer_context()
        # noinspection PyProtectedMember
        context["csrf_token"] = get_token(self.request._request)
        return context