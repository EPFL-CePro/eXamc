import json
from urllib.parse import urlparse

from django.contrib import messages
from django.http import HttpRequest, JsonResponse
from django.shortcuts import redirect, render
from django.utils.http import url_has_allowed_host_and_scheme

from examc_app.exceptions import UserFacingError, log_user_facing_error

#: extra_tags marking the messages the base template shows in the error modal.
ERROR_MODAL_TAG = "error-modal"


def _wants_json(request: HttpRequest) -> bool:
    return (
        request.headers.get("x-requested-with") == "XMLHttpRequest"
        or "application/json" in request.headers.get("accept", "")
    )


def _safe_referer(request: HttpRequest) -> str | None:
    """The page the user came from, if it's on this site and isn't the page that just failed."""
    referer = request.headers.get("referer")
    if not referer:
        return None
    if not url_has_allowed_host_and_scheme(referer, allowed_hosts={request.get_host()},
                                           require_https=request.is_secure()):
        return None
    if urlparse(referer).path == request.path:  # avoid redirecting to the failing page in a loop
        return None
    return referer


class UserFacingErrorMiddleware:
    """Shows a UserFacingError in a modal instead of a 500 page."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)

    def process_exception(self, request: HttpRequest, exception: Exception):
        if not isinstance(exception, UserFacingError):
            return None

        log_user_facing_error(exception, request.method, request.path)

        if _wants_json(request):
            return JsonResponse(exception.to_dict(), status=exception.status_code)

        referer = _safe_referer(request)
        if referer:
            messages.error(request, json.dumps(exception.to_dict()), extra_tags=ERROR_MODAL_TAG)
            return redirect(referer)

        # No page to go back to (direct link, bookmark...): show the error page instead.
        return render(request, "errors/user_facing_error.html",
                      {"error": exception.to_dict()}, status=exception.status_code)