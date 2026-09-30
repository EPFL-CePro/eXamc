from collections.abc import Callable
from typing import Any

from django.http import QueryDict
from rest_framework import viewsets
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response

from examc_app.api.decorators import exam_permission_required, ExamScopedViewMixin
from examc_app.services.amc.data_capture.manual import get_amc_data_capture_manual_data
from examc_app.utils.global_functions import user_allowed

# Question states, with the label shown in the State column's list
QUESTION_STATES = {"invalid": "Invalid", "empty": "Empty"}


def _problem_count(row: dict[str, Any]) -> int:
    return sum(row["state_counts"].values())


# DataTables column data name -> sort key
ORDERING_COLUMNS: dict[str, Callable[[dict[str, Any]], tuple[Any, ...]]] = {
    "copy": lambda r: (r["copy"], r["page"]),
    "page": lambda r: (r["page"], r["copy"]),
    "states": lambda r: (len(r["states"]), "invalid" in r["states"], r["copy"], r["page"]),
    "mse": lambda r: (r["mse"] or 0,),
    "sensitivity": lambda r: (r["sensitivity"] or 0,),  # None sensitivity sorts as 0
    "timestamp_manual": lambda r: (1 if r["timestamp_manual"] else 0, r["copy"], r["page"]),
}


def _int_param(params: QueryDict, name: str, default: int) -> int:
    try:
        return int(params.get(name, default))
    except (TypeError, ValueError):
        return default


def _column_index(params: QueryDict, data_name: str) -> str | None:
    """Index of the DataTables column whose `data` is data_name."""
    for key, value in params.items():
        if value == data_name and key.startswith("columns[") and key.endswith("][data]"):
            return key[len("columns["):-len("][data]")]
    return None


def _column_list(params: QueryDict, data_name: str) -> list[str]:
    """Values selected in a column's ColumnControl searchList (sent as [list][] or [list][0], [list][1]...)."""
    index = _column_index(params, data_name)
    if index is None:
        return []
    prefix = f"columns[{index}][columnControl][list]"
    return [v for key in params if key.startswith(prefix) for v in params.getlist(key)]


class AmcDataCaptureManualViewSet(ExamScopedViewMixin, viewsets.ViewSet):
    """
    Pages needing manual data capture, in DataTables server-side format.

    GET /api/exams/<exam_pk>/amc-data-capture-manual/
    """
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

        # Questions + State lists (ColumnControl): keep pages having a question matching both.
        # Several values in one list are combined with OR.
        question_ids = {int(v) for v in _column_list(params, "page_questions") if v.isdigit()}
        states = {v for v in _column_list(params, "states") if v in QUESTION_STATES}
        if question_ids or states:
            rows = [
                r for r in rows
                if any(
                    (not question_ids or q["id"] in question_ids) and (not states or q["state"] in states)
                    for q in r["page_questions"]
                )
            ]
        records_filtered = len(rows)

        # ordering, by the clicked column's data name (robust to column reordering)
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
            "copies": data["copies"],
            # options for the ColumnControl searchLists, keyed by column data name
            "columnControl": {
                "page_questions": [{"label": q["name"], "value": q["question"]} for q in data["questions"]],
                "states": [{"label": label, "value": value} for value, label in QUESTION_STATES.items()],
            },
        })