"""Periodic housekeeping tasks (run by celery beat)."""

from datetime import timedelta

from celery import shared_task
from django.conf import settings
from django.contrib.sessions.models import Session
from django.utils import timezone

from examc_app.models import ReviewLock
from examc_app.services.jobs import fail_if_stale


@shared_task(name="examc_app.tasks.fail_stale_jobs")
def fail_stale_jobs() -> int:
    """Marks the jobs that stopped reporting progress as failed; returns how many."""
    backend = fail_stale_jobs.app.backend
    return sum(
        fail_if_stale(key.decode().removeprefix("celery-task-meta-"))
        for key in backend.client.scan_iter(match="celery-task-meta-*")
    )


@shared_task(name="examc_app.tasks.cleanup_review_locks")
def cleanup_review_locks():
    now = timezone.now()
    timeout_seconds = max(1, int(getattr(settings, 'REVIEW_LOCK_TIMEOUT', settings.AUTO_LOGOUT_DELAY)))
    lock_threshold = now - timedelta(seconds=timeout_seconds)

    expired_deleted_count, _ = ReviewLock.objects.filter(updated_at__lt=lock_threshold).delete()

    # Get active user IDs from sessions
    active_user_ids = set()

    for session in Session.objects.filter(expire_date__gt=now):
        data = session.get_decoded()
        uid = data.get('_auth_user_id')
        if uid:
            active_user_ids.add(int(uid))

    # Delete ReviewLocks where user is no longer active
    inactive_deleted_count, _ = ReviewLock.objects.exclude(user_id__in=active_user_ids).delete()
    total = expired_deleted_count + inactive_deleted_count
    return (
        f"Deleted {total} review locks "
        f"(expired={expired_deleted_count}, inactive_user={inactive_deleted_count})."
    )
