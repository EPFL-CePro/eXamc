import re
from collections.abc import Iterable
from dataclasses import dataclass, replace

from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from ldap3.core.exceptions import LDAPException

from examc_app.utils.epflldap.ldap_search import LDAP_search, ldap_search_by_sciper
from examc_app.utils.epflldap.utils import EpflLdapException


class PersonDirectoryError(Exception):
    """Impossible to get an email from directory."""


@dataclass(frozen=True)
class DirectoryPerson:
    sciper: str
    first_name: str
    last_name: str
    email: str | None
    # Study section of a student (e.g. "MX" for MX-BA1), None for the other people
    section: str | None = None


# SCIPERs per LDAP query: keeps the filter short
LDAP_BATCH_SIZE = 100


def get_institutional_email(sciper) -> str | None:
    sciper = str(sciper).strip()

    # Validate the value before filtring in LDAP.
    if not re.fullmatch(r"[0-9]{6}", sciper):
        raise ValueError("SCIPER must have six digits.")

    try:
        entry = ldap_search_by_sciper(sciper)
    except (LDAPException, EpflLdapException, OSError) as exc:
        raise PersonDirectoryError("LDAP search failed.") from exc

    if entry is None:
        return None

    # The existing utility may return an user_facing_exception instead of raising one.
    if not isinstance(entry, dict):
        raise PersonDirectoryError("Invalid LDAP response.")

    values = entry.get("mail") or []
    if isinstance(values, str):
        values = [values]

    if not isinstance(values, (list, tuple)):
        raise PersonDirectoryError("Invalid LDAP mail field.")

    emails = {
        value.strip()
        for value in values
        if isinstance(value, str) and value.strip()
    }

    if not emails:
        raise PersonDirectoryError("No available email for this entry.")

    if len(emails) > 1:
        raise PersonDirectoryError("Multiple LDAP emails: ambiguous selection.")

    email = emails.pop()

    try:
        validate_email(email)
    except ValidationError as exc:
        raise PersonDirectoryError("LDAP email is invalid.") from exc

    return email


def _first_value(entry, attribute) -> str:
    values = entry.get(attribute) or []
    if isinstance(values, str):
        values = [values]
    return next((value.strip() for value in values if isinstance(value, str) and value.strip()), "")


def _student_section(result) -> str | None:
    """Section of a student entry (DN "ou=mx-ba1,ou=mx-s,ou=etu,o=epfl,c=ch", ou "MX-BA1" -> "MX")."""
    if ",ou=etu," not in str(result.get("dn", "")).lower():
        return None
    section = _first_value(result["attributes"], "ou").split("-")[0].upper()
    return section or None


def get_people_by_sciper(scipers: Iterable) -> dict[str, DirectoryPerson]:
    """
    First name, last name, email and section of each SCIPER found in the EPFL LDAP, by SCIPER.
    The SCIPERs not found are missing from the result. Raises PersonDirectoryError if LDAP fails.
    """
    scipers = sorted({str(sciper).strip() for sciper in scipers})
    for sciper in scipers:
        # Validate the values before filtering in LDAP.
        if not re.fullmatch(r"[0-9]{6}", sciper):
            raise ValueError("SCIPER must have six digits.")

    people = {}
    for start in range(0, len(scipers), LDAP_BATCH_SIZE):
        batch = scipers[start:start + LDAP_BATCH_SIZE]
        pattern = "(|" + "".join(f"(uniqueIdentifier={sciper})" for sciper in batch) + ")"
        try:
            response = LDAP_search(pattern_search=pattern)
        except (LDAPException, EpflLdapException, OSError) as exc:
            raise PersonDirectoryError("LDAP search failed.") from exc

        for result in response or []:
            entry = result.get("attributes") if isinstance(result, dict) else None
            if not entry:
                continue
            sciper = _first_value(entry, "uniqueIdentifier")
            if sciper not in batch:
                continue
            section = _student_section(result)
            # A person has one entry per accreditation: the first one is kept, the section comes from
            # the student entry (a student can also be an assistant)
            if sciper in people:
                if section and not people[sciper].section:
                    people[sciper] = replace(people[sciper], section=section)
                continue

            email = _first_value(entry, "mail") or None
            if email:
                try:
                    validate_email(email)
                except ValidationError:
                    email = None

            people[sciper] = DirectoryPerson(
                sciper=sciper,
                first_name=_first_value(entry, "givenName"),
                last_name=_first_value(entry, "sn"),
                email=email,
                section=section,
            )

    return people
