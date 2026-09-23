from dataclasses import dataclass

from django.db.models import QuerySet
from rest_framework.exceptions import ValidationError

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
        fields = column_map.get(self.order_column) if self.order_column is not None else None
        if not fields:
            return queryset
        return queryset.order_by(*(f"-{f}" if self.order_desc else f for f in fields))

    def page(self, queryset: QuerySet) -> list:
        return list(queryset[self.start:self.start + self.length])

    def response(self, *, total: int, filtered: int, data) -> dict:
        return {"draw": self.draw, "recordsTotal": total, "recordsFiltered": filtered, "data": data}