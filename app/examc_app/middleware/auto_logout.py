import datetime
from django.conf import settings
from django.shortcuts import redirect
from django.contrib.auth import logout
from django.utils import timezone

from examc_app.models import ReviewLock
from examc_app.views import force_oidc_logout


class AutoLogoutMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            now = timezone.now()
            last_activity = request.session.get('last_activity')

            if last_activity:
                try:
                    last_activity_dt = datetime.datetime.fromisoformat(last_activity)
                except ValueError:
                    last_activity_dt = None

                if last_activity_dt and timezone.is_naive(last_activity_dt):
                    last_activity_dt = timezone.make_aware(last_activity_dt, timezone.get_current_timezone())

                if last_activity_dt:
                    elapsed = (now - last_activity_dt).total_seconds()
                else:
                    elapsed = 0

                if elapsed > settings.AUTO_LOGOUT_DELAY:

                    # Remove review locks if exist
                    ReviewLock.objects.filter(user=request.user).delete()

                    logout(request)
                    return redirect('force_oidc_logout')

            request.session['last_activity'] = now.isoformat()

        return self.get_response(request)
