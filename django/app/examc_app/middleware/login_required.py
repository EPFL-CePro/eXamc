import logging
import re

from django.conf import settings
from django.shortcuts import render
from django.template.response import TemplateResponse

logger = logging.getLogger(__name__)


class LoginRequiredMiddleware:
    """
    Show a 403 "unauthorized" page to unauthenticated users,
    except on paths matching LOGIN_REQUIRED_IGNORE_PATHS.
    """

    def __init__(self, get_response):
        self.get_response = get_response
        self.open_urls = [
            re.compile(pattern)
            for pattern in getattr(settings, "LOGIN_REQUIRED_IGNORE_PATHS", [])
        ]

    def is_open(self, path: str) -> bool:
        return any(pattern.match(path) for pattern in self.open_urls)

    def __call__(self, request):
        if not request.user.is_authenticated and not self.is_open(request.path_info):
            logger.info("Unauthenticated access blocked: %s", request.get_full_path())
            return render(
                request,
                "unauthorized.html",
                { "next": request.get_full_path() },
                status=403,
            )
        return self.get_response(request)