from django.contrib.auth import get_user_model


IMPERSONATOR_SESSION_KEY = "impersonator_user_id"
IMPERSONATED_SESSION_KEY = "impersonated_user_id"


def clear_impersonation_session(session):
    session.pop(IMPERSONATOR_SESSION_KEY, None)
    session.pop(IMPERSONATED_SESSION_KEY, None)


class ImpersonationMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.impersonator = None
        request.real_user = request.user

        if not request.user.is_authenticated:
            clear_impersonation_session(request.session)
            return self.get_response(request)

        impersonator_id = request.session.get(IMPERSONATOR_SESSION_KEY)
        impersonated_id = request.session.get(IMPERSONATED_SESSION_KEY)
        if not impersonator_id or not impersonated_id:
            return self.get_response(request)

        User = get_user_model()
        try:
            impersonator = User.objects.get(pk=impersonator_id, is_active=True)
            impersonated = User.objects.get(pk=impersonated_id, is_active=True)
        except User.DoesNotExist:
            clear_impersonation_session(request.session)
            return self.get_response(request)

        if not impersonator.is_superuser or impersonated.is_superuser:
            clear_impersonation_session(request.session)
            return self.get_response(request)

        request.impersonator = impersonator
        request.real_user = impersonator
        request.user = impersonated

        return self.get_response(request)
