import datetime
from django.conf import settings
from django.shortcuts import redirect
from django.contrib.auth import logout

from examc_app.models import ReviewLock
from examc_app.views import force_oidc_logout


class AutoLogoutMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            now = datetime.datetime.now()
            last_activity = request.session.get('last_activity')

            if last_activity:
                elapsed = (now - datetime.datetime.fromisoformat(last_activity)).total_seconds()
                if elapsed > settings.AUTO_LOGOUT_DELAY:

                    # Remove review locks if exist
                    ReviewLock.objects.filter(user=request.user).delete()

                    logout(request)
                    return redirect('force_oidc_logout')

            request.session['last_activity'] = now.isoformat()

        return self.get_response(request)

