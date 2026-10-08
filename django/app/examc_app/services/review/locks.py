from datetime import timedelta

from django.conf import settings
from django.utils import timezone

from examc_app.models import ReviewLock


def cleanup_expired_review_locks():
    timeout_seconds = max(1, int(getattr(settings, 'REVIEW_LOCK_TIMEOUT', settings.AUTO_LOGOUT_DELAY)))
    lock_threshold = timezone.now() - timedelta(seconds=timeout_seconds)
    ReviewLock.objects.filter(updated_at__lt=lock_threshold).delete()