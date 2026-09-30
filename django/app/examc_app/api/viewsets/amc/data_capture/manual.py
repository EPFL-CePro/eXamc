from typing import Callable, Any

from rest_framework import viewsets
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response

from examc_app.api.decorators import exam_permission_required, ExamScopedViewMixin
from examc_app.services.amc.data_capture.manual import get_amc_data_capture_manual_data
from examc_app.utils.global_functions import user_allowed

# DataTables column index -> sort key(s)
ORDERING_COLUMNS: dict[str, Callable[[dict[str, Any]], tuple[Any, ...]]] = {
    "copy": lambda r: (r["copy"], r["page"]),
    "page": lambda r: (r["page"], r["copy"]),
    "mse": lambda r: (r["mse"] or 0,),
    "sensitivity": lambda r: (r["sensitivity"] or 0,),  # None sensitivity sorts as 0
    "timestamp_manual": lambda r: (1 if r["timestamp_manual"] else 0, r["copy"], r["page"]),
}

def _int_param(params, name: str, default: int) -> int:
    try:
        return int(params.get(name, default))
    except (TypeError, ValueError):
        return default


class AmcDataCaptureManualViewSet(ExamScopedViewMixin, viewsets.ViewSet):
    permission_classes = [IsAuthenticated]

    @exam_permission_required(["manage"])
    def list(self, request: Request, exam_pk: str) -> Response:
        if not user_allowed(self.exam, request.user.id):
            raise PermissionDenied("Not allowed for this exam.")

        data = get_amc_data_capture_manual_data(self.exam)
        if data is None:
            raise NotFound("No AMC project found for this exam.")

        params = request.query_params
        rows = data["pages"]
        records_total = len(rows)

        # search on copy / page
        search = params.get("search[value]", "").strip()
        if search:
            rows = [r for r in rows if search in str(r["copy"]) or search in str(r["page"])]

        # type / question filters (same markers as questions_ids)
        question_id = _int_param(params, "question", 0)
        marker = f"%{question_id}%" if question_id > 0 else ""
        marker += {"invalid": "|INV|", "empty": "|EMP|"}.get(params.get("type", "all"), "")
        if marker:
            rows = [r for r in rows if marker in r["questions_ids"]]
        records_filtered = len(rows)

        # ordering
        order_column = params.get("order[0][column]", "")
        sort_key = ORDERING_COLUMNS.get(params.get(f"columns[{order_column}][data]", ""))
        if sort_key:
            rows = sorted(rows, key=sort_key, reverse=params.get("order[0][dir]") == "desc")

        # paging (length -1 = "All")
        start = _int_param(params, "start", 0)
        length = _int_param(params, "length", 25)
        if length != -1:
            rows = rows[start:start + length]

        return Response({
            "draw": _int_param(params, "draw", 0),
            "recordsTotal": records_total,
            "recordsFiltered": records_filtered,
            "data": rows,
            "questions": data["questions"],
            "copies": data["copies"],
        })