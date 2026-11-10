import datetime

from django.conf import settings
from django.shortcuts import redirect
from django.urls import reverse
from django.utils import timezone

from examc_app.models import ReviewLock

# Set when the session expired: only the logout page and the OIDC logout are reachable then
LOGOUT_PENDING_KEY = 'auto_logout_pending'


def _session_expired(request) -> bool:
    last_activity = request.session.get('last_activity')
    if not last_activity:
        return False
    try:
        last = datetime.datetime.fromisoformat(last_activity)
    except ValueError:
        return False
    if timezone.is_naive(last):
        last = timezone.make_aware(last, timezone.get_current_timezone())
    return (timezone.now() - last).total_seconds() > settings.AUTO_LOGOUT_DELAY


class AutoLogoutMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        self.allowed_paths: set[str] | None = None  # resolved on first use (URLconf loaded)

    def __call__(self, request):
        if request.user.is_authenticated:
            if self.allowed_paths is None:
                self.allowed_paths = {reverse('force_oidc_logout'), reverse('oidc_logout')}

            if request.session.get(LOGOUT_PENDING_KEY) or _session_expired(request):
                if not request.session.get(LOGOUT_PENDING_KEY):
                    ReviewLock.objects.filter(user=request.user).delete()
                    request.session[LOGOUT_PENDING_KEY] = True
                if request.path not in self.allowed_paths:
                    return redirect('force_oidc_logout')
            else:
                request.session['last_activity'] = timezone.now().isoformat()

        return self.get_response(request)