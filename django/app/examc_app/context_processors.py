from datetime import datetime

from django.utils import timezone
from constance import config as cc

from examc import settings


def maintenance_notice(request):
    # Don’t show inside Django admin
    if request.path.startswith("/admin/"):
        return {"planned_maintenance": {"show": False}}

    now = timezone.localtime()
    start, end = cc.MAINT_START, cc.MAINT_END
    show = False

    # Show only BEFORE the window starts (heads-up banner)
    if cc.MAINT_BANNER_ENABLED and isinstance(start, datetime) and isinstance(end,datetime) and now < start:
        show_from = cc.MAINT_BANNER_FROM or now
        show = show_from <= now

        # Optional bypasses configured in Constance
        if show and cc.MAINT_BYPASS_AUTHENTICATED and getattr(request.user, "is_authenticated", False):
            show = False
        if show and cc.MAINT_BYPASS_STAFF and getattr(request.user, "is_staff", False):
            show = False

    return {
        "planned_maintenance": {
            "show": bool(show),
            "start": start,
            "end": end,
            "message": (cc.MAINT_MESSAGE or "").strip(),
        }
    }

def app_metadata(request):
    return {
        "APP_NAME": getattr(settings, "APP_NAME", "eXamc"),
        "APP_VERSION": getattr(settings, "APP_VERSION", "dev"),
        "APP_LICENSE": getattr(settings, "APP_LICENSE", ""),
        "APP_OWNER": getattr(settings, "APP_OWNER", ""),
    }
