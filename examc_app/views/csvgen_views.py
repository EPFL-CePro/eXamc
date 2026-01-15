import os
from datetime import datetime
from io import StringIO
from pathlib import Path

import pandas as pd
import json

from celery.result import AsyncResult
from celery_progress.backend import Progress
from django.views.decorators.cache import never_cache

from django.contrib import messages
from django.http import FileResponse, HttpResponse
from django.shortcuts import render

from examc_app.utils.epflldap import ldap_search
from django.conf import settings

CSV_TYPE_AMC = "a"
STUDENTS_LIST = None
column_name = False
column_number = False


def csvgen(request):
    return render(request, "csvgen/csvgen.html", {"csv_type_AMC": CSV_TYPE_AMC})


# class of both files
class raw_data:
    id = 0
    email = ""
    sciper = ""
    name = ""
    first_name = ""
    last_name = ""
    seat = 0
    class_name = ""
    room = ""

    def __init__(self, id, sciper, name, first_name, last_name, email, seat, class_name, room):
        self.id = id
        self.sciper = sciper
        self.name = name
        self.first_name = first_name
        self.last_name = last_name
        self.email = email
        self.seat = seat
        self.class_name = class_name
        self.room = room


# import both excel file from list of ans and amc function
def import_students_excel(request):
    global STUDENTS_LIST, CSV_TYPE_AMC, column_number, column_name

    auto_export = request.POST.get("auto_export") == "1"  # ou "on" selon ton HTML

    if CSV_TYPE_AMC == "a":
        students_list, column_number, column_name = import_students_excel_AMC(
            request, request.FILES["students_excel_file"]
        )
    else:
        students_list, column_number, column_name = import_students_excel_ANS(
            request, request.FILES["students_excel_file"]
        )

    STUDENTS_LIST = students_list

    if STUDENTS_LIST:
        return build_csv_response(CSV_TYPE_AMC, STUDENTS_LIST)

    return render(
        request,
        "csvgen/csvgen.html",
        {
            "csv_type_AMC": CSV_TYPE_AMC,
            "students_list": STUDENTS_LIST,
            "column_number": column_number,
            "column_name": column_name,
        },
    )

# function used to choice between AMC and ANS
def change_csv_type(request, choice):
    global STUDENTS_LIST, CSV_TYPE_AMC, column_number, column_name
    CSV_TYPE_AMC = choice
    return render(request, "csvgen/csvgen.html", {"csv_type_AMC": CSV_TYPE_AMC})


def import_students_excel_AMC(request, students_file):
    amc_students_list = []
    column_number = None
    column_name = None

    if isinstance(students_file, list):
        df = pd.DataFrame(students_file)
    else:
        list_of_column_names = []
        list_names = ["name", "sciper", "email", "seat", "room"]
        df = pd.DataFrame(pd.read_excel(students_file))
        cols = len(df.axes[1])

        for col in df.columns:
            list_of_column_names.append(str(col).lower())

        # check number of column
        if cols == len(list_names):
            column_number = True
            messages.success(request, "Column number: OK", extra_tags="safe")
        else:
            column_number = False
            messages.error(request, "Column number: Not Ok", extra_tags="safe")
            return [[], column_number, column_name]

        # check headers of the file
        if list_of_column_names == list_names:
            column_name = True
            messages.success(request, "Column name: OK", extra_tags="safe")
        else:
            column_name = False
            messages.error(request, "Column name: Not Ok", extra_tags="safe")
            return [[], column_number, column_name]

        # Normalize sciper to avoid ".0"
        df["sciper"] = pd.to_numeric(df["sciper"], errors="coerce").astype("Int64")

    id_counter = 0
    for _, row in df.iterrows():
        id_counter += 1

        if "sciper" not in row or pd.isna(row["sciper"]):
            messages.error(request, "Missing sciper value in file.", extra_tags="safe")
            continue

        sciper_int = int(row["sciper"])
        sciper_str = str(sciper_int)

        ldap_student_entry = ldap_search.get_entry(sciper_int, "uniqueidentifier")

        print("********* " + sciper_str + " ******")
        print(ldap_student_entry)
        print("***********************")

        if ldap_student_entry:
            first_name = ldap_student_entry.get("givenName", [""])[0]
            first_name = first_name.split(" ")[0]
            full_name = first_name + " " + ldap_student_entry.get("sn", [""])[0]
            email = ldap_student_entry.get("mail", [""])[0]

            seat_value = row["seat"] if "seat" in row and row["seat"] else id_counter
            room_value = row["room"] if "room" in row and row["room"] else ""

            student_row = [
                id_counter,
                sciper_str,      # <= plus de .0
                full_name,
                None,
                None,
                email,
                seat_value,
                None,
                room_value,
            ]
            amc_students_list.append(student_row)
        else:
            messages.error(request, f"Student with sciper {sciper_str} not found in LDAP.", extra_tags="safe")

    return [amc_students_list, column_number, column_name]


def import_students_excel_ANS(request, students_file):
    ans_students_list = []
    column_number = None
    column_name = None

    if isinstance(students_file, list):
        df = pd.DataFrame(students_file)
    else:
        list_of_column_names = []
        list_names = ["class name", "email", "sciper", "name"]
        df = pd.DataFrame(pd.read_excel(students_file))
        cols = len(df.axes[1])

        for col in df.columns:
            list_of_column_names.append(str(col).lower())

        if cols == len(list_names):
            column_number = True
            messages.success(request, "Column number: OK", extra_tags="safe")
        else:
            column_number = False
            messages.error(request, "Column number: Not Ok", extra_tags="safe")
            return [[], column_number, column_name]

        if list_of_column_names == list_names:
            column_name = True
            messages.success(request, "Column name: OK", extra_tags="safe")
        else:
            column_name = False
            messages.error(request, "Column name: Not Ok", extra_tags="safe")
            return [[], column_number, column_name]

        # Normalize sciper to avoid ".0"
        df["sciper"] = pd.to_numeric(df["sciper"], errors="coerce").astype("Int64")

    for _, row in df.iterrows():
        if "sciper" not in row or pd.isna(row["sciper"]):
            messages.error(request, "Missing sciper value in file.", extra_tags="safe")
            continue

        sciper_int = int(row["sciper"])
        sciper_str = str(sciper_int)

        # NOTE: in your original code you used 'uniqueIdentifier' (capital I) here.
        # Keep the one that matches your LDAP helper.
        ldap_student_entry = ldap_search.get_entry(sciper_int, "uniqueIdentifier")

        if ldap_student_entry:
            first_name = ldap_student_entry.get("givenName", [""])[0].split(" ")[0]
            last_name = ldap_student_entry.get("sn", [""])[0]
            email = ldap_student_entry.get("mail", [""])[0]

            class_name_value = row["class name"] if "class name" in row else None

            student_row = [None, sciper_str, None, last_name, first_name, email, None, class_name_value, None]
            ans_students_list.append(student_row)
        else:
            messages.error(request, f"Student with sciper {sciper_str} not found in LDAP.", extra_tags="safe")

    return [ans_students_list, column_number, column_name]


# json to csv
# def export_csv(request):
#     try:
#         choice = request.POST.get("choice")
#         students_list_raw = request.POST.get("students_list")
#         if not students_list_raw:
#             return HttpResponse("Missing students_list", status=400)
#
#         students_list = json.loads(students_list_raw)
#
#         if choice == "a":
#             df = pd.DataFrame(
#                 students_list,
#                 columns=["id", "Sciper", "Name", "col4", "col5", "email", "Seat", "col8", "Room"],
#             )
#             df = df[["id", "Sciper", "Name", "email", "Seat", "Room"]]
#         else:
#             df = pd.DataFrame(
#                 students_list,
#                 columns=["col1", "student number", "col3", "last name", "first name", "email", "col7", "class name", "col9"],
#             )
#             df = df[["class name", "email", "student number", "last name", "first name"]]
#
#         export_file_name = "students_list_" + datetime.now().strftime("%d%m%y_%H%M%S") + ".csv"
#
#         export_root = Path(settings.PRIVATE_MEDIA_ROOT)
#         export_dir = export_root / "csv_exports"  # sous-dossier dédié
#         export_dir.mkdir(parents=True, exist_ok=True)
#
#         file_full_path = export_dir / export_file_name
#         df.to_csv(file_full_path, encoding="utf-8", index=False)
#
#         # Ouvre et force le téléchargement avec un nom propre
#         f = open(file_full_path, "rb")
#         return FileResponse(
#             f,
#             as_attachment=True,
#             filename=export_file_name,
#             content_type="text/csv",
#         )
#
#     except Exception as e:
#         # Pratique pour voir l’erreur côté UI (à enlever en prod)
#         return HttpResponse(f"Export error: {type(e).__name__}: {e}", status=500)

def build_csv_response(choice: str, students_list: list) -> HttpResponse:
    if choice == "a":
        # ton format AMC: [id, sciper, full_name, None, None, email, seat, None, room]
        df = pd.DataFrame(
            students_list,
            columns=["id", "Sciper", "Name", "col4", "col5", "email", "Seat", "col8", "Room"],
        )
        df = df[["id", "Sciper", "Name", "email", "Seat", "Room"]]
    else:
        # ton format ANS: [None, sciper, None, last, first, email, None, class_name, None]
        df = pd.DataFrame(
            students_list,
            columns=["col1", "student number", "col3", "last name", "first name", "email", "col7", "class name", "col9"],
        )
        df = df[["class name", "email", "student number", "last name", "first name"]]

    filename = f"students_list_{datetime.now().strftime('%d%m%y_%H%M%S')}.csv"

    buf = StringIO()
    df.to_csv(buf, index=False, encoding="utf-8")
    csv_text = buf.getvalue()
    buf.close()

    response = HttpResponse(csv_text, content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response