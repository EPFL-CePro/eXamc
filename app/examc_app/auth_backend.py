from mozilla_django_oidc.auth import OIDCAuthenticationBackend
from django.conf import settings

class ExamcOIDCBackend(OIDCAuthenticationBackend):
    def get_userinfo(self, access_token, id_token, payload):
        return payload or {}

    def create_user(self, claims):
        """
        Called only the first time a user logs in.
        """
        user = super().create_user(claims)
        self.update_user(user, claims)
        return user

    def update_user(self, user, claims):
        """
        Called every login — keeps user info in sync.
        """
        user.username = claims.get("gaspar", user.username)  # or "preferred_username"
        user.first_name = claims.get("given_name", "")
        user.last_name = claims.get("family_name", "")
        user.email = claims.get("email", user.email)

        groups = set(claims.get("groups", []))
        superuser_groups = set(getattr(settings, "OIDC_SUPERUSER_GROUPS", []))
        staff_groups = set(getattr(settings, "OIDC_STAFF_GROUPS", []))

        user.is_superuser = bool(groups.intersection(superuser_groups))
        user.is_staff = bool(groups.intersection(staff_groups))
        user.save()
        return user
