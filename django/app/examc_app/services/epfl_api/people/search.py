from urllib.parse import quote

from examc_app.services.epfl_api.people.models import EpflApiPerson
from examc_app.services.epfl_api.utils import EpflApiException, epfl_api_get

PERSONS_API_BASE_URL = "/persons"


def get_multiple_person_by_scipers(sciper_list: list[str]) -> list[EpflApiPerson]:
    """
    Search the persons directory by a list of SCIPER.
    """
    if not sciper_list: return []

    data = epfl_api_get(path=PERSONS_API_BASE_URL, params={"ids": ",".join(sciper_list)})
    if not isinstance(data, dict): return []

    persons = data.get("persons")
    if not isinstance(persons, list): return []
    return [EpflApiPerson.from_api(p) for p in persons if isinstance(p, dict)]


def get_person_by_identifier(identifier: str | int) -> EpflApiPerson | None:
    """
    Get a person by an identifier: SCIPER, Camipro card ID, email or username
    """
    identifier = str(identifier).strip()
    if not identifier: return None

    data = epfl_api_get(f"{PERSONS_API_BASE_URL}/{quote(identifier, safe='')}")
    return EpflApiPerson.from_api(data) if isinstance(data, dict) else None