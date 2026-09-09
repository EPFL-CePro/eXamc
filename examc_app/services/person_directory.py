import re

from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from ldap3.core.exceptions import LDAPException

from examc_app.utils.epflldap.ldap_search import ldap_search_by_sciper
from examc_app.utils.epflldap.utils import EpflLdapException


class PersonDirectoryError(Exception):
    """Impossible to get an email from directory."""


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

    # The existing utility may return an exception instead of raising one.
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