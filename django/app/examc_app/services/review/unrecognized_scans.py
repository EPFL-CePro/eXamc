import logging

from examc import settings
from examc_app.models import Exam, UnrecognizedReviewScan
from examc_app.signing import make_token_for

logger = logging.getLogger(__name__)


def _page_number_as_int(page_no):
    try:
        return int(str(page_no).split(".", 1)[0])
    except (TypeError, ValueError):
        return None

def _format_unrecognized_scan_suggestion(scan):
    if scan.previous_copy_no and scan.next_copy_no and scan.previous_copy_no == scan.next_copy_no:
        previous_page = _page_number_as_int(scan.previous_page_no)
        next_page = _page_number_as_int(scan.next_page_no)
        if previous_page is not None and next_page is not None and next_page - previous_page == 2:
            page_width = max(len(scan.previous_page_no), len(scan.next_page_no), 2)
            return f"Copy {scan.previous_copy_no}, missing page {previous_page + 1:0{page_width}d}"
        return f"Copy {scan.previous_copy_no}, between pages {scan.previous_page_no} and {scan.next_page_no}"
    if scan.previous_copy_no:
        return f"After copy {scan.previous_copy_no}, page {scan.previous_page_no}"
    if scan.next_copy_no:
        return f"Before copy {scan.next_copy_no}, page {scan.next_page_no}"
    return "No recognized neighbor"


def _format_page_number_like(value, reference):
    page_number = _page_number_as_int(value)
    if page_number is None:
        return ""
    return f"{page_number:0{max(len(str(reference or '')), 2)}d}"


def _get_unrecognized_scan_assignment_defaults(scan: UnrecognizedReviewScan):
    if scan.previous_copy_no and scan.next_copy_no and scan.previous_copy_no == scan.next_copy_no:
        previous_page = _page_number_as_int(scan.previous_page_no)
        next_page = _page_number_as_int(scan.next_page_no)
        if previous_page is not None and next_page is not None and next_page - previous_page == 2:
            page_width = max(len(scan.previous_page_no), len(scan.next_page_no), 2)
            return {
                "copy_no": scan.previous_copy_no,
                "page_no": f"{previous_page + 1:0{page_width}d}",
                "mode": UnrecognizedReviewScan.ASSIGNMENT_MODE_NORMAL,
            }
        return {
            "copy_no": scan.previous_copy_no,
            "page_no": scan.previous_page_no,
            "mode": UnrecognizedReviewScan.ASSIGNMENT_MODE_EXTRA,
        }
    if scan.previous_copy_no:
        return {
            "copy_no": scan.previous_copy_no,
            "page_no": scan.previous_page_no,
            "mode": UnrecognizedReviewScan.ASSIGNMENT_MODE_EXTRA,
        }
    if scan.next_copy_no:
        next_page = _page_number_as_int(scan.next_page_no)
        if next_page and next_page > 1:
            return {
                "copy_no": scan.next_copy_no,
                "page_no": _format_page_number_like(next_page - 1, scan.next_page_no),
                "mode": UnrecognizedReviewScan.ASSIGNMENT_MODE_NORMAL,
            }
        return {
            "copy_no": scan.next_copy_no,
            "page_no": scan.next_page_no,
            "mode": UnrecognizedReviewScan.ASSIGNMENT_MODE_EXTRA,
        }
    return {
        "copy_no": "",
        "page_no": "",
        "mode": UnrecognizedReviewScan.ASSIGNMENT_MODE_NORMAL,
    }


def build_unrecognized_review_scan_context(exam: Exam) -> list:
    rows = []
    scans = UnrecognizedReviewScan.objects.filter(exam=exam, resolved=False).order_by("upload_order", "pk")

    for scan in scans:
        assignment_defaults = _get_unrecognized_scan_assignment_defaults(scan)
        rows.append({
            "id": scan.pk,
            "filename": scan.filename,
            "original_filename": scan.original_filename,
            "upload_order": scan.upload_order,
            "scan_url": make_token_for(scan.relative_path, str(settings.SCANS_ROOT), copy_page_in_url=False),
            "previous_url": (
                make_token_for(scan.previous_relative_path, str(settings.SCANS_ROOT), copy_page_in_url=False)
                if scan.previous_relative_path else ""
            ),
            "previous_label": (
                f"Copy {scan.previous_copy_no}, page {scan.previous_page_no}"
                if scan.previous_copy_no else ""
            ),
            "next_url": (
                make_token_for(scan.next_relative_path, str(settings.SCANS_ROOT), copy_page_in_url=False)
                if scan.next_relative_path else ""
            ),
            "next_label": (
                f"Copy {scan.next_copy_no}, page {scan.next_page_no}"
                if scan.next_copy_no else ""
            ),
            "suggestion": _format_unrecognized_scan_suggestion(scan),
            "assignment_copy_no": assignment_defaults["copy_no"],
            "assignment_page_no": assignment_defaults["page_no"],
            "assignment_mode": assignment_defaults["mode"],
        })

    return rows