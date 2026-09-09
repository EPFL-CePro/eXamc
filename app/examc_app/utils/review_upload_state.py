import time


REVIEW_UPLOAD_PENDING_AMC_IMPORT_SESSION_KEY = "review_upload_pending_amc_imports"
REVIEW_UPLOAD_PENDING_TTL_SECONDS = 24 * 3600


def _normalise_exam_pk(exam_pk):
    return str(int(exam_pk))


def _prune_pending_amc_imports(raw_pending):
    if not isinstance(raw_pending, dict):
        return {}

    now_ts = int(time.time())
    min_ts = now_ts - REVIEW_UPLOAD_PENDING_TTL_SECONDS
    pruned = {}
    for exam_pk, meta in raw_pending.items():
        if not isinstance(meta, dict):
            continue
        created_at = int(meta.get("created_at", 0))
        if created_at < min_ts:
            continue
        try:
            normalised_exam_pk = _normalise_exam_pk(exam_pk)
        except (TypeError, ValueError):
            continue
        pruned[normalised_exam_pk] = {
            "created_at": created_at,
            "upload_task_id": str(meta.get("upload_task_id") or ""),
        }
    return pruned


def get_pending_amc_imports(request):
    pending = _prune_pending_amc_imports(
        request.session.get(REVIEW_UPLOAD_PENDING_AMC_IMPORT_SESSION_KEY, {})
    )
    request.session[REVIEW_UPLOAD_PENDING_AMC_IMPORT_SESSION_KEY] = pending
    request.session.modified = True
    return pending


def set_pending_amc_import(request, exam_pk, upload_task_id=None):
    pending = get_pending_amc_imports(request)
    pending[_normalise_exam_pk(exam_pk)] = {
        "created_at": int(time.time()),
        "upload_task_id": str(upload_task_id or ""),
    }
    request.session[REVIEW_UPLOAD_PENDING_AMC_IMPORT_SESSION_KEY] = pending
    request.session.modified = True


def clear_pending_amc_import(request, exam_pk):
    pending = get_pending_amc_imports(request)
    pending.pop(_normalise_exam_pk(exam_pk), None)
    request.session[REVIEW_UPLOAD_PENDING_AMC_IMPORT_SESSION_KEY] = pending
    request.session.modified = True


def has_pending_amc_import(request, exam_pk):
    return _normalise_exam_pk(exam_pk) in get_pending_amc_imports(request)


def get_pending_amc_import_upload_task_id(request, exam_pk):
    meta = get_pending_amc_imports(request).get(_normalise_exam_pk(exam_pk), {})
    return meta.get("upload_task_id") or ""
