from django.contrib.auth.models import User
from django.db.models import QuerySet
from rest_framework import mixins, viewsets

from examc_app.api.datatables import DataTablesFilterBackend
from examc_app.api.serializers.connected_user import ConnectedUserRowSerializer
from examc_app.utils.dashboard import get_dashboard_connected_users_queryset


class ConnectedUsersViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    """
    Last connected Users for the dashboard's "select" table.
    GET /api/users/
    """
    serializer_class = ConnectedUserRowSerializer
    filter_backends = [DataTablesFilterBackend]
    search_fields = ["username"]
    # Column index -> model field(s) for server-side ordering.
    ordering_columns = {
        0: ["username"],
        1: ["last_login"],
    }

    def get_queryset(self) -> QuerySet[User, User]:
        return get_dashboard_connected_users_queryset(self.request.user)