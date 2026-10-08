import logging

from celery.result import AsyncResult

logger = logging.getLogger(__name__)

ACTIVE_CELERY_STATES = ("PENDING", "RECEIVED", "STARTED", "PROGRESS", "RETRY")

def is_celery_task_active(task_id: str | None) -> bool:
    return get_celery_task_status(task_id) in ACTIVE_CELERY_STATES

def get_celery_task_status(task_id: str | None) -> str | None:
    if not task_id:
        return None
    try:
        return AsyncResult(task_id).state
    except Exception:
        logger.warning("Unable to read celery task state task_id=%s", task_id, exc_info=True)
        return None