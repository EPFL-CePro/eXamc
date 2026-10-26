from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from datetime import datetime
from io import BytesIO
from typing import Any, Final, TypedDict
from zipfile import ZIP_DEFLATED, ZipFile

import pandas as pd
from django.contrib import messages
from django.core.files.uploadedfile import UploadedFile
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render

from examc_app.utils.epflldap import ldap_search

# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------

LdapEntry = Mapping[str, Sequence[str]]
StudentRow = dict[str, Any]
StudentsFile = UploadedFile | list[dict[str, Any]]
ColumnCheck = bool | None


class Person(TypedDict):
    first_name: str
    last_name: str
    email: str


RowBuilder = Callable[[pd.Series, int, Person, str], StudentRow]


class CsvTypeConfig(TypedDict):
    template_name: str
    input_columns: list[str]
    example: dict[str, Any]
    output_columns: list[str]
    build_row: RowBuilder


class ImportResult(TypedDict):
    students: list[StudentRow]
    column_number: ColumnCheck
    column_name: ColumnCheck


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _value_or[T](row: pd.Series, key: str, default: T) -> Any | T:
    """Return row[key] if it holds a real value, otherwise default (handles NaN)."""
    value = row.get(key)
    return value if pd.notna(value) and value != "" else default


def _ldap_identity(entry: LdapEntry) -> Person:
    """Extract first name (first word only), last name and email from an LDAP entry."""

    def first(attr: str) -> str:
        return (entry.get(attr) or [""])[0]

    return Person(
        first_name=first("givenName").split(" ")[0],
        last_name=first("sn"),
        email=first("mail"),
    )


def _amc_row(row: pd.Series, index: int, person: Person, sciper: str) -> StudentRow:
    return {
        "id": index,
        "Sciper": sciper,
        "Name": f"{person['first_name']} {person['last_name']}",
        "email": person["email"],
        "Seat": _value_or(row, "seat", index),
        "Room": _value_or(row, "room", ""),
    }


def _ans_row(row: pd.Series, index: int, person: Person, sciper: str) -> StudentRow:
    return {
        "class name": _value_or(row, "class name", None),
        "email": person["email"],
        "student number": sciper,
        "last name": person["last_name"],
        "first name": person["first_name"],
    }


# One entry per export format: everything that differs between AMC and ANS lives here.
CSV_TYPES: Final[dict[str, CsvTypeConfig]] = {
    "amc": {
        "template_name": "amc_students_template.xlsx",
        "input_columns": ["name", "sciper", "email", "seat", "room"],
        "example": {
            "name": "Doe John",
            "sciper": 123456,
            "email": "john.doe@example.com",
            "seat": 1,
            "room": "CO 1",
        },
        "output_columns": ["id", "Sciper", "Name", "email", "Seat", "Room"],
        "build_row": _amc_row,
    },
    "ans": {
        "template_name": "ans_students_template.xlsx",
        "input_columns": ["class name", "email", "sciper", "name"],
        "example": {
            "class name": "Section A",
            "email": "john.doe@example.com",
            "sciper": 123456,
            "name": "Doe John",
        },
        "output_columns": ["class name", "email", "student number", "last name", "first name"],
        "build_row": _ans_row,
    },
}


DEFAULT_CSV_TYPE: Final[str] = "amc"


def _get_config(choice: str) -> CsvTypeConfig:
    """Config for "amc" or "ans"; anything unknown falls back to AMC."""
    return CSV_TYPES.get(choice, CSV_TYPES[DEFAULT_CSV_TYPE])


def _report(request: HttpRequest, ok: bool | None, label: str) -> None:
    if ok:
        messages.success(request, f"{label}: OK", extra_tags="safe")
    else:
        messages.error(request, f"{label}: Not Ok", extra_tags="safe")


def _normalize_headers(columns: pd.Index) -> list[str]:
    """Lowercase (and trim) headers so 'Sciper', 'SCIPER ' and 'sciper' all match."""
    return [str(col).strip().lower() for col in columns]


def _load_dataframe(
    request: HttpRequest,
    students_file: StudentsFile,
    expected_columns: list[str],
) -> tuple[pd.DataFrame | None, ColumnCheck, ColumnCheck]:
    """
    Read the uploaded file (or an in-memory list), normalize headers and validate them.
    Returns (df or None if invalid, column_number, column_name).
    """
    column_number: ColumnCheck = None
    column_name: ColumnCheck = None

    if isinstance(students_file, list):
        df = pd.DataFrame(students_file)
        df.columns = _normalize_headers(df.columns)
    else:
        df = pd.read_excel(students_file)
        df.columns = _normalize_headers(df.columns)

        column_number = len(df.columns) == len(expected_columns)
        _report(request, column_number, "Number of columns")
        if not column_number:
            return None, column_number, column_name

        column_name = list(df.columns) == expected_columns
        _report(request, column_name, "Column name")
        if not column_name:
            return None, column_number, column_name

    # Normalize sciper to avoid ".0"
    if "sciper" in df.columns:
        df["sciper"] = pd.to_numeric(df["sciper"], errors="coerce").astype("Int64")

    return df, column_number, column_name


def import_students(
    request: HttpRequest,
    students_file: StudentsFile,
    choice: str,
) -> ImportResult:
    """Shared import logic for AMC and ANS."""
    config = _get_config(choice)
    df, column_number, column_name = _load_dataframe(
        request, students_file, config["input_columns"]
    )

    students: list[StudentRow] = []
    if df is not None:
        for index, (_, row) in enumerate(df.iterrows(), start=1):
            if pd.isna(row.get("sciper")):
                messages.error(request, "Missing sciper value in file.", extra_tags="safe")
                continue

            sciper = int(row["sciper"])
            entry: LdapEntry | None = ldap_search.get_entry(sciper, "uniqueIdentifier")
            if not entry:
                messages.error(
                    request,
                    f"Student with sciper {sciper} not found in LDAP.",
                    extra_tags="safe",
                )
                continue

            students.append(config["build_row"](row, index, _ldap_identity(entry), str(sciper)))

    return ImportResult(
        students=students,
        column_number=column_number,
        column_name=column_name,
    )


def build_csv_response(choice: str, students_list: list[StudentRow]) -> HttpResponse:
    config = _get_config(choice)
    df = pd.DataFrame(students_list, columns=config["output_columns"])

    filename = f"students_list_{datetime.now().strftime('%d%m%y_%H%M%S')}.csv"
    response = HttpResponse(df.to_csv(index=False), content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


# ---------------------------------------------------------------------------
# Views
# ---------------------------------------------------------------------------

def download_csvgen_templates(request: HttpRequest) -> HttpResponse:
    zip_buffer = BytesIO()
    with ZipFile(zip_buffer, "w", ZIP_DEFLATED) as archive:
        for config in CSV_TYPES.values():
            excel_buffer = BytesIO()
            pd.DataFrame([config["example"]], columns=config["input_columns"]).to_excel(
                excel_buffer, index=False
            )
            archive.writestr(config["template_name"], excel_buffer.getvalue())

    response = HttpResponse(zip_buffer.getvalue(), content_type="application/zip")
    response["Content-Disposition"] = 'attachment; filename="csvgen_templates.zip"'
    return response


def _render_page(request: HttpRequest, csv_type: str, **context: Any) -> HttpResponse:
    return render(
        request,
        "public/csvgen.html",
        {
            "csv_type": csv_type,
            **context
        }
    )


def csvgen(request: HttpRequest) -> HttpResponse:
    """GET shows the page; POST converts the uploaded file, so the URL never changes."""
    if request.method == "POST":
        return import_students_excel(request)
    return _render_page(request, DEFAULT_CSV_TYPE)


def import_students_excel(request: HttpRequest) -> HttpResponse:
    # The file type comes with the upload: no global state shared between users
    csv_type = request.POST.get("csv_type", DEFAULT_CSV_TYPE)
    if csv_type not in CSV_TYPES:
        csv_type = DEFAULT_CSV_TYPE

    students_file = request.FILES.get("students_excel_file")
    if not isinstance(students_file, UploadedFile):
        messages.error(request, "No file uploaded.")
        return _render_page(request, csv_type)

    result = import_students(request, students_file, csv_type)
    if result["students"]:
        return build_csv_response(csv_type, result["students"])

    return _render_page(
        request,
        csv_type,
        students_list=result["students"],
        COLUMN_NUMBER=result["column_number"],
        COLUMN_NAME=result["column_name"],
    )