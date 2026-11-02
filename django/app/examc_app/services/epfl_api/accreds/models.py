from dataclasses import dataclass, field
from typing import Any, Self


def _text(data: dict[str, Any], key: str) -> str:
    value = data.get(key)
    return value.strip() if isinstance(value, str) else ""


def _int(data: dict[str, Any], key: str) -> int | None:
    value = data.get(key)
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _dict(data: dict[str, Any], key: str) -> dict[str, Any]:
    value = data.get(key)
    return value if isinstance(value, dict) else {}


@dataclass(frozen=True, slots=True)
class EpflApiUnit:
    """models.Unit"""
    id: int | None = None
    name: str = ""
    labelen: str = ""
    labelfr: str = ""
    path: str = ""

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> Self:
        return cls(id=_int(data, "id"), name=_text(data, "name"), labelen=_text(data, "labelen"),
                   labelfr=_text(data, "labelfr"), path=_text(data, "path"))


@dataclass(frozen=True, slots=True)
class EpflApiLabel:
    """models.Position, models.Status and models.Class: the shared fields"""
    id: int | None = None
    name: str = ""
    labelen: str = ""
    labelfr: str = ""

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> Self:
        return cls(id=_int(data, "id"), name=_text(data, "name"), labelen=_text(data, "labelen"),
                   labelfr=_text(data, "labelfr"))


@dataclass(frozen=True, slots=True)
class EpflApiAccred:
    """models.Accred of the EPFL Accred API: the fields we use, the full payload in raw."""
    persid: str
    unitid: int | None = None
    order: int | None = None
    state: str = ""
    unit: EpflApiUnit = field(default_factory=EpflApiUnit)
    position: EpflApiLabel = field(default_factory=EpflApiLabel)
    status: EpflApiLabel = field(default_factory=EpflApiLabel)
    accred_class: EpflApiLabel = field(default_factory=EpflApiLabel)
    raw: dict[str, Any] = field(default_factory=dict, repr=False, compare=False)

    @property
    def unit_name(self) -> str:
        return self.unit.name

    @property
    def position_label(self) -> str:
        return self.position.labelen

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> Self:
        persid = _int(data, "persid")
        return cls(
            # The API gives an integer, the rest of the app uses SCIPERs as strings
            persid=str(persid) if persid is not None else "",
            unitid=_int(data, "unitid"),
            order=_int(data, "order"),
            state=_text(data, "state"),
            unit=EpflApiUnit.from_api(_dict(data, "unit")),
            position=EpflApiLabel.from_api(_dict(data, "position")),
            status=EpflApiLabel.from_api(_dict(data, "status")),
            accred_class=EpflApiLabel.from_api(_dict(data, "class")),
            raw=data,
        )