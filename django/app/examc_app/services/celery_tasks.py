import logging

from celery.result import AsyncResult

logger = logging.getLogger(__name__)

ACTIVE_CELERY_STATES = ("PENDING", "RECEIVED", "STARTED", "PROGRESS", "RETRY")

def is_celery_task_active(task_id: str | None) -> bool:
    if not task_id:
        return False
    try:
        return AsyncResult(task_id).state in ACTIVE_CELERY_STATES
    except Exception:
        logger.warning("Unable to read celery task state task_id=%s", task_id, exc_info=True)
        return False