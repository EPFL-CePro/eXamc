from dataclasses import dataclass, field
from typing import Any, Self


@dataclass(frozen=True, slots=True)
class EpflApiPerson:
    """models.Person of the EPFL Persons API: the fields we use, the full payload in raw."""
    id: str
    sciper: str = ""
    firstname: str = ""
    lastname: str = ""
    display: str = ""
    email: str = ""
    username: str = ""
    account: dict[str, Any] = field(default_factory=dict)
    position: dict[str, Any] = field(default_factory=dict)
    studies: list[dict[str, Any]] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict, repr=False, compare=False)

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> Self:
        def text(key: str) -> str:
            value = data.get(key)
            return value.strip() if isinstance(value, str) else ""

        def mapping(key: str) -> dict[str, Any]:
            value = data.get(key)
            return value if isinstance(value, dict) else {}

        studies = data.get("studies")
        return cls(
            id=text("id"),
            sciper=text("sciper"),
            firstname=text("firstname"),
            lastname=text("lastname"),
            display=text("display"),
            email=text("email"),
            username=text("username"),
            account=mapping("account"),
            position=mapping("position"),
            studies=[s for s in studies if isinstance(s, dict)] if isinstance(studies, list) else [],
            raw=data,
        )

    def get_full_name(self) -> str:
        """Returns the full name of the person."""
        return f"{self.firstname} {self.lastname}"

    def __str__(self) -> str:
        return f"{self.id};{self.firstname};{self.lastname};{self.email}"