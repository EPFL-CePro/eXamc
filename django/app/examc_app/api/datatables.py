from dataclasses import dataclass
from typing import Any

from django.db.models import Model, Q, F
from django.db.models import QuerySet
from rest_framework.exceptions import ValidationError
from rest_framework.filters import BaseFilterBackend
from rest_framework.pagination import BasePagination
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

MAX_PAGE_LENGTH = 100

def _int(params, key: str, default: int, *, min_value: int = 0, max_value: int | None = None) -> int:
    raw = params.get(key)
    if raw in (None, ""):
        return default
    try:
        value = int(raw)
    except (TypeError, ValueError):
        raise ValidationError({key: "Must be an integer."})
    if value < min_value or (max_value is not None and value > max_value):
        raise ValidationError({key: "Out of range."})
    return value


@dataclass(frozen=True)
class DataTablesRequest:
    draw: int
    start: int
    length: int
    search: str
    order_column: int | None
    order_desc: bool

    @classmethod
    def from_query_params(cls, params) -> "DataTablesRequest":
        order_column = params.get("order[0][column]")
        return cls(
            draw=_int(params, "draw", 1),
            start=_int(params, "start", 0),
            length=_int(params, "length", 10, min_value=1, max_value=MAX_PAGE_LENGTH),
            search=params.get("search[value]", "").strip(),
            order_column=None if order_column in (None, "") else _int(params, "order[0][column]", 0),
            order_desc=params.get("order[0][dir]") == "desc",
        )

    def order(self, queryset: QuerySet, column_map: dict[int, list[str]]) -> QuerySet:
        """
        Orders a Django QuerySet based on column mapping and order direction.

        This function applies ordering to a given QuerySet by using a mapping
        of column indices to field names and the current order direction (ascending
        or descending). It supports null value handling by either placing them last
        when ordering in descending or ascending order.

        :param queryset: A Django QuerySet that will be ordered.
        :param column_map: A dictionary where the keys are column indices and the
            values are lists of field names corresponding to those columns.
        :return: A reordered QuerySet with the specified ordering applied.
        :rtype: QuerySet
        """
        fields = column_map.get(self.order_column) if self.order_column is not None else None
        if not fields:
            return queryset
        return queryset.order_by(
            *(F(f).desc(nulls_last=True) if self.order_desc else F(f).asc(nulls_last=True) for f in fields),
            "pk",
        )
    def page(self, queryset: QuerySet) -> list:
        return list(queryset[self.start:self.start + self.length])

    def response(self, *, total: int, filtered: int, data) -> dict:
        return {"draw": self.draw, "recordsTotal": total, "recordsFiltered": filtered, "data": data}


class DataTablesFilterBackend(BaseFilterBackend):
    """
    Applies DataTables global search and column ordering.
    """

    def filter_queryset(self, request: Request, queryset: QuerySet[Any], view: APIView) -> QuerySet[Any]:
        dt = DataTablesRequest.from_query_params(request.query_params)

        search_fields: list[str] = getattr(view, "search_fields", [])
        if dt.search and search_fields:
            query = Q()
            for field in search_fields:
                query |= Q(**{f"{field}__icontains": dt.search})
            queryset = queryset.filter(query)

        ordering_columns: dict[int, list[str]] = getattr(view, "ordering_columns", {})
        return dt.order(queryset, ordering_columns)


class DataTablesPagination(BasePagination):
    """
    Pages the queryset and wraps results in the DataTables response shape.
    """

    def paginate_queryset(self, queryset: QuerySet[Any], request: Request, view: APIView | None = None) -> list[Model]:
        self.dt = DataTablesRequest.from_query_params(request.query_params)
        self.filtered = queryset.count()
        self.total = view.get_queryset().count() if view is not None else self.filtered  # type: ignore[attr-defined]
        return list(self.dt.page(queryset))

    def get_paginated_response(self, data: Any) -> Response:
        return Response(self.dt.response(total=self.total, filtered=self.filtered, data=data))