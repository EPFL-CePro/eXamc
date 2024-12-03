import os
from datetime import datetime
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
    return render(request, 'csvgen/csvgen.html', {"csv_type_AMC": CSV_TYPE_AMC})


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

    # if request.POST:
    if CSV_TYPE_AMC == "a":
        results = import_students_excel_AMC(request, request.FILES["students_excel_file"])
        STUDENTS_LIST = results[0]
        column_number = results[1]
        column_name = results[2]

    else:
        results = import_students_excel_ANS(request, request.FILES["students_excel_file"])
        STUDENTS_LIST = results[0]
        column_number = results[1]
        column_name = results[2]

    return render(request, 'csvgen/csvgen.html',
                  {"csv_type_AMC": CSV_TYPE_AMC, "students_list": STUDENTS_LIST, "column_number": column_number,
                   "column_name": column_name})


# function used to choice between AMC and ANS
def change_csv_type(request, choice):
    global STUDENTS_LIST, CSV_TYPE_AMC, column_number, column_name

    CSV_TYPE_AMC = choice
    return render(request, 'csvgen/csvgen.html', {"csv_type_AMC": CSV_TYPE_AMC})


def import_students_excel_AMC(request, students_file):
    amc_students_list = []
    column_number = None
    column_name = None

    if isinstance(students_file, list):
        df = pd.DataFrame(students_file)

    else:
        list_of_column_names = []
        list_names = ['name', 'sciper', 'email', 'seat', 'room']
        df = pd.DataFrame(pd.read_excel(students_file))
        cols = len(df.axes[1])

        for col in df.columns:
            list_of_column_names.append(col.lower())

        # check number of column
        if cols == len(list_names):
            column_number = True
            messages.success(request, 'Column number: OK', extra_tags='safe')
        else:
            column_number = False
            return messages.error(request, 'Column number: Not Ok', extra_tags='safe')

        # check headers of the file
        if list_of_column_names == list_names:
            column_name = True
            messages.success(request, 'Column name: OK', extra_tags='safe')
        else:
            column_name = False
            return messages.error(request, 'Column name: Not Ok', extra_tags='safe')

    id = 0
    for index, row in df.iterrows():
        id += 1
        ldap_student_entry = ldap_search.get_entry(int(row[1]), 'uniqueidentifier')
        print("********* "+str(int(row[1]))+ " ******")
        print(ldap_student_entry)
        print("***********************")

        if ldap_student_entry:
            first_name = ldap_student_entry.get('givenName', [''])[0]
            first_name = first_name.split(' ')[0]
            full_name = first_name + " " + ldap_student_entry.get('sn', [''])[0]
            email = ldap_student_entry.get('mail', [''])[0]

            student_row = [id, row[1], full_name, None, None, email, row[3] if row[3] else id, None, row[4] if row[4] else '']
            amc_students_list.append(student_row)
        else:
            messages.error(request, f'Student with sciper {row[1]} not found in LDAP.', extra_tags='safe')

    return [amc_students_list, column_number, column_name]



def import_students_excel_ANS(request, students_file):
    ans_students_list = []
    column_number = None
    column_name = None
    if isinstance(students_file, list):
        df = pd.DataFrame(students_file)

    else:
        list_of_column_names = []
        list_names = ['class name', 'email', 'sciper', 'name']
        df = pd.DataFrame(pd.read_excel(students_file))
        cols = len(df.axes[1])

    for col in df.columns:
        list_of_column_names.append(col.lower())

    if cols == len(list_names):
        column_number = True
        messages.success(request, 'Column number: OK', extra_tags='safe')
    else:
        column_number = False
        return messages.error(request, 'Column number: Not Ok', extra_tags='safe')

    if list_of_column_names == list_names:
        column_name = True
        messages.success(request, 'Column name: OK', extra_tags='safe')
    # else:
    #     column_name = False
    #     return messages.error(request, 'Column name: Not Ok', extra_tags='safe')

    for index, row in df.iterrows():
        ldap_student_entry = ldap_search.get_entry(row[2], 'uniqueIdentifier')

        if ldap_student_entry:
            first_name = ldap_student_entry.get('givenName', [''])[0]
            first_name = first_name.split(' ')[0]
            last_name = ldap_student_entry.get('sn', [''])[0]

            student_row = [None, row[2], None, last_name, first_name, row[1], None, row[0], None]
            ans_students_list.append(student_row)
        else:
            messages.error(request, f'Student with sciper {row[2]} not found in LDAP.', extra_tags='safe')

    return [ans_students_list, column_number, column_name]


# json to csv
def export_csv(request):
    choice = request.POST.get("choice")
    students_list = json.loads(request.POST.get("students_list"))

    if choice == 'a':
        df = pd.DataFrame(students_list, columns=['id', 'Sciper', 'Name', 'email', 'Seat', 'Room'])
    else:
        df = pd.DataFrame(students_list, columns=['class name', 'email', 'student number', 'last name', 'first name'])

    export_file_name = "students_list_" + str(datetime.now().strftime("%d%m%y_%H%M%S") + ".csv")
    file_path = str(settings.EXPORT_TMP_ROOT) + "/" + export_file_name
    # Create the folder
    os.makedirs(file_path, exist_ok=True)

    df.to_csv(file_path + "/" + export_file_name, mode="w", encoding="utf-8", index=False)
    f = open(file_path + "/" + export_file_name, 'rb')
    response = FileResponse(f)

    return response
