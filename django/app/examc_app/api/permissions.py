from rest_framework import permissions
from rest_framework.request import Request
from rest_framework.views import APIView


class IsSuperUser(permissions.BasePermission):
    def has_permission(self, request: Request, view: APIView) -> bool:
        return bool(request.user and request.user.is_superuser)
