from mozilla_django_oidc.auth import OIDCAuthenticationBackend

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

        print("OIDC claims keys: %s", list(claims.keys()))
        print("groups: %s", claims.get("groups"))
        print("picture: %s", claims.get("picture"))
        print("roles: %s", claims.get("roles"))
        groups = list(claims.get("groups", []))
        if "CePro_admin_IT_AppGrpU" in groups:
            user.is_superuser = True
            user.is_staff = True  # usually needed to access Django admin
        else:
            user.is_superuser = False  # optional: decide if you want to remove superuser status
            user.is_staff = False

        user.save()
        return user