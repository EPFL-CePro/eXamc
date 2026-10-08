from typing import Any

from django.http import HttpRequest

from examc_app.services.celery_tasks import is_celery_task_active
from examc_app.utils.review_upload_state import (
    get_pending_amc_import_upload_task_id,
    has_pending_amc_import,
)


def _get_upload_scan_pending_context(request: HttpRequest, exam_pk: int, task_id: str | None = None) -> dict[str, Any]:
    active_task_id = task_id
    if not active_task_id:
        pending_task_id = get_pending_amc_import_upload_task_id(request, exam_pk)
        if is_celery_task_active(pending_task_id):
            active_task_id = pending_task_id

    return {
        "task_id": active_task_id,
        "pending_amc_import": has_pending_amc_import(request, exam_pk),
        "upload_task_active": bool(active_task_id),
    }
