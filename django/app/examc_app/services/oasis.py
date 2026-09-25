import json
import re
from http.client import HTTPException
from typing import Mapping, Any, Iterable
from urllib.error import URLError, HTTPError
from urllib.parse import urlencode
from urllib.request import urlopen, Request

from django.conf import settings

OASIS_TIMEOUT_SECONDS = 20

def _is_complete_teacher(row):
    required_fields = (
        "coursCode",
        "enseignantSciper",
        "enseignantPrenom",
        "enseignantNom",
        "curriculumAnneeAcademique",
    )

    return (
            row.get("enseignantRole") == "Enseignement"
            and all(
        isinstance(row.get(field), str) and row[field].strip()
        for field in required_fields
    )
    )


class OasisError(Exception):
    """Configuration, communication or response OASIS error."""


def _validate_year(academic_year):
    if not isinstance(academic_year, str):
        raise ValueError("Academic year must be a string.")

    if not re.fullmatch(r"[0-9]{4}-[0-9]{4}", academic_year):
        raise ValueError("Expected format : 2024-2025.")

    start, end = map(int, academic_year.split("-"))
    if end != start + 1:
        raise ValueError("Academic year must cover two consecutive years.")


def _get_list(
    path: str,
    *,
    params: Mapping[str, Any] | None = None,
    required_fields: Iterable[str] = (),
) -> list[dict[str, Any]]:
    base_url = settings.OASIS_BASE_URL
    bearer = settings.OASIS_BEARER

    if not base_url or not bearer:
        raise OasisError("OASIS configuration is incomplete.")

    url = f"{base_url.rstrip('/')}/{path.lstrip('/')}"
    if params:
        url = f"{url}?{urlencode(params, doseq=True)}"

    request = Request(
        url,
        headers={
            "Authorization": f"Bearer {bearer}",
            "Accept": "application/json",
        },
        method="GET",
    )

    try:
        with urlopen(request, timeout=OASIS_TIMEOUT_SECONDS) as response:
            body = response.read()
    except HTTPError as exc:
        raise OasisError(f"OASIS returns HTTP error {exc.code}.") from exc
    except URLError as exc:
        if isinstance(exc.reason, TimeoutError):
            raise OasisError("OASIS does not reply within the specified time limit.") from exc
        raise OasisError("Impossible to join OASIS.") from exc
    except TimeoutError as exc:
        raise OasisError("OASIS does not reply within the specified time limit.") from exc
    except (HTTPException, OSError) as exc:
        raise OasisError("Impossible to join OASIS.") from exc

    try:
        data = json.loads(body)
    except ValueError as exc:
        raise OasisError("OASIS response is not a valid JSON.") from exc

    if not isinstance(data, list):
        raise OasisError("Unexpected OASIS Format : a list is expected.")

    items: list[dict[str, Any]] = []
    for item in data:
        if not isinstance(item, dict):
            raise OasisError("One OASIS entry is not a JSON object.")

        for field in required_fields:
            value = item.get(field)
            if not isinstance(value, str) or not value.strip():
                raise OasisError(f"OASIS field absent or invalid : {field}.")

        items.append(item)

    return items

def get_courses(academic_year):
    """Returns courses from academic year with OASIS fields names."""
    _validate_year(academic_year)

    # Retrieve the list before validating individual course fields.
    data = _get_list(f"cours/{academic_year}")

    courses = [
        item
        for item in data
        if isinstance(item.get("coursCode"), str)
           and item["coursCode"].strip()
    ]

    for course in courses:
        for field in ("coursNomFr", "curriculumAnneeAcademique"):
            value = course.get(field)
            if not isinstance(value, str) or not value.strip():
                raise OasisError(
                    f"OASIS field absent or invalid: {field} "
                    f"for course {course['coursCode']}."
                )

        if course["curriculumAnneeAcademique"] != academic_year:
            raise OasisError(
                "OASIS returned courses from another academic year."
            )

    return courses


def get_course_teachers(academic_year, course_code):
    """Returns teachers from course deduplicated by SCIPER."""
    _validate_year(academic_year)

    if not isinstance(course_code, str) or not course_code.strip():
        raise ValueError("Course code is mandatory.")

    course_code = course_code.strip()

    teachers = _get_list(
        f"enseignant-cours/{academic_year}",
        params={
            "code-cours": course_code,
            "type": "Enseignement",
        },
    )

    teachers_by_sciper = {}

    for teacher in teachers:

        if not _is_complete_teacher(teacher):
            continue

        if (
                teacher["coursCode"] != course_code
                or teacher["curriculumAnneeAcademique"] != academic_year
        ):
            raise OasisError("OASIS returned an assignment that was not part of the course.")

        if "enseignantRole" not in teacher:
            raise OasisError("The teacher’s role is missing from the answer.")

        if teacher["enseignantRole"] == "Enseignement":
            teachers_by_sciper[teacher["enseignantSciper"]] = teacher

    return list(teachers_by_sciper.values())


def get_teachers_names_by_course(academic_year):
    """Return teachers (sciper + full name) grouped by course, deduplicated by SCIPER."""
    _validate_year(academic_year)

    rows = _get_list(
        f"enseignant-cours/{academic_year}",
        params={"type": "Enseignement"},
    )

    grouped = {}

    for row in rows:

        if not _is_complete_teacher(row):
            continue

        course_code = row["coursCode"]

        if row["curriculumAnneeAcademique"] != academic_year:
            raise OasisError("OASIS returned teachers from another academic year.")

        sciper = row["enseignantSciper"].strip()
        full_name = (
            f'{row["enseignantPrenom"].strip()} '
            f'{row["enseignantNom"].strip()}'
        )

        grouped.setdefault(course_code, {})[sciper] = full_name

    return {
        code: sorted(
            ({"sciper": sciper, "name": name} for sciper, name in teachers.items()),
            key=lambda t: t["name"].casefold(),
        )
        for code, teachers in grouped.items()
    }
