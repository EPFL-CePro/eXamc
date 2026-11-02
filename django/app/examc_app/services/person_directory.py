import re
from collections.abc import Iterable
from dataclasses import dataclass

from django.core.exceptions import ValidationError
from django.core.validators import validate_email

from examc_app.services.epfl_api.accreds.models import EpflApiAccred
from examc_app.services.epfl_api.accreds.search import accreds_search
from examc_app.services.epfl_api.people.search import (
    get_multiple_person_by_scipers,
    get_person_by_identifier,
)
from examc_app.services.epfl_api.utils import EpflApiException


class PersonDirectoryError(Exception):
    """Impossible to get an email from the directory."""


@dataclass(frozen=True)
class DirectoryPerson:
    sciper: str
    first_name: str
    last_name: str
    email: str | None
    # Study section of a student (e.g. "MX" for MX-BA1), None for the other people
    section: str | None = None


# SCIPERs per API query: keeps the URL short
API_BATCH_SIZE = 100

SCIPER_RE = re.compile(r"[0-9]{6}")
# Student accreditation units look like "MX-BA1" or "IN-MA3": the section is the prefix
STUDENT_UNIT_RE = re.compile(r"([A-Z]+)-(?:BA|MA)[0-9]+")


def _validate_sciper(sciper) -> str:
    sciper = str(sciper).strip()
    # Validate the value before sending it to the API.
    if not SCIPER_RE.fullmatch(sciper):
        raise ValueError("SCIPER must have six digits.")
    return sciper


def _clean_str(value) -> str:
    return value.strip() if isinstance(value, str) else ""


def _valid_email_or_none(value) -> str | None:
    email = _clean_str(value)
    if not email:
        return None
    try:
        validate_email(email)
    except ValidationError:
        return None
    return email


def get_institutional_email(sciper) -> str | None:
    sciper = _validate_sciper(sciper)

    try:
        person = get_person_by_identifier(sciper)
    except (EpflApiException, OSError) as exc:
        raise PersonDirectoryError("EPFL API search failed.") from exc

    if person is None:
        return None

    email = _clean_str(person.email)
    if not email:
        raise PersonDirectoryError("No available email for this person.")

    try:
        validate_email(email)
    except ValidationError as exc:
        raise PersonDirectoryError("EPFL API email is invalid.") from exc

    return email


def _student_section(accred: EpflApiAccred) -> str | None:
    """Section of a student accreditation (unit "MX-BA1" -> "MX"), None for the others."""
    match = STUDENT_UNIT_RE.fullmatch(accred.unit_name.upper())
    return match.group(1) if match else None


def _sections_by_sciper(accreds: list[EpflApiAccred], batch: list[str]) -> dict[str, str]:
    """First student section found for each SCIPER (a student can also be an assistant)."""
    sections: dict[str, str] = {}
    for accred in accreds:
        if accred.persid not in batch or accred.persid in sections:
            continue
        section = _student_section(accred)
        if section:
            sections[accred.persid] = section
    return sections


def get_people_by_sciper(scipers: Iterable) -> dict[str, DirectoryPerson]:
    """
    First name, last name, email and section of each SCIPER found in the EPFL API, by SCIPER.
    The SCIPERs not found are missing from the result. Raises PersonDirectoryError if the API fails.
    """
    scipers = sorted({_validate_sciper(sciper) for sciper in scipers})

    people: dict[str, DirectoryPerson] = {}
    for start in range(0, len(scipers), API_BATCH_SIZE):
        batch = scipers[start:start + API_BATCH_SIZE]

        try:
            persons = get_multiple_person_by_scipers(batch)
            accreds = accreds_search(persid=",".join(batch))
        except (EpflApiException, OSError) as exc:
            raise PersonDirectoryError("EPFL API search failed.") from exc

        sections = _sections_by_sciper(accreds, batch)

        for person in persons:
            sciper = person.sciper or person.id
            if sciper not in batch or sciper in people:
                continue

            people[sciper] = DirectoryPerson(
                sciper=sciper,
                first_name=person.firstname,
                last_name=person.lastname,
                email=_valid_email_or_none(person.email),
                section=sections.get(sciper),
            )

    return people