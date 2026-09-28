import datetime
import os.path
import re
import shutil
import unicodedata

import pypandoc
from celery import shared_task
from django.contrib.auth.models import User
from django.contrib.sessions.models import Session
from django.core.signing import Signer
from django.db.models import Q, Max
from django.db.models.fields import IntegerField
from django.db.models.functions import Cast
from num2words import num2words

from django.conf import settings
from examc_app.models import ExamUser, ReviewLock
from examc_app.utils.amc_functions import get_amc_project_path, amc_update_documents, get_amc_exam_pdf_url
from examc_app.utils.epflldap.ldap_search import ldap_search_by_sciper

def user_allowed(exam, user_id):
    user = User.objects.get(pk=user_id)
    exam_users = ExamUser.objects.filter(Q(user=user) & (Q(exam=exam) | Q(exam__in=exam.common_exams.all())))
    if exam_users or user.is_superuser:
        return True
    else:
        return False

def get_course_teachers_string(teachers):
    teachers_list = teachers.split('|')
    teachers_str = ''
    for t in teachers_list:
        if t:
            if teachers_str != '':
                teachers_str += ','
            teachers_str += t.split(';')[2]
    return teachers_str

def add_course_teachers_ldap(scipers):
    teachers_list = []
    for sciper in scipers:
        if not sciper:
            continue

        user_entry = ldap_search_by_sciper(sciper)
        email = user_entry['mail'][0]

        user = User.objects.filter(email=email).first()
        if user is None:
            user = User.objects.create(
                username=user_entry['uniqueidentifier'][0],
                first_name=user_entry['givenName'][0],
                last_name=user_entry['sn'][0],
                email=email,
                is_active=True,
            )

        teachers_list.append(user)
    return teachers_list


def convert_html_to_latex(html_string):

    # Convert HTML to LaTeX using Pandoc with the custom filter
    latex_content = pypandoc.convert_text(
        html_string,
        'latex',
        format='html',
    )

    # remove itemsep of itemize if exist
    latex_content = latex_content.replace("\\begin{itemize}","\\begin{itemize}[noitemsep]")
    # remove \tightlist
    latex_content = latex_content.replace("\\tightlist","")
    # add total_pages command if exist
    latex_content = latex_content.replace("{[}TOTAL\\_PAGES{]}","\\totalPages\\")
    # remove verbatim for latex code parts
    latex_content = latex_content.replace("\\begin{verbatim}",'')
    latex_content = latex_content.replace("\\end{verbatim}", '')
    latex_content = latex_content.replace("\\$\\$", '$')

    if latex_content.startswith("$"):
        i = 1
    else:
        i = 0
    content_formulas_list = latex_content.split("$")
    for formula in content_formulas_list:
        if i%2 != 0:
            new_text = formula.replace("\\","").replace('textbackslash ','\\')
            latex_content = latex_content.replace(formula,new_text)
        i += 1

    return latex_content

def search_and_replace(file_path, search_word, replace_word):
   with open(file_path, 'r') as file:
      file_contents = file.read()

      updated_contents = file_contents.replace(search_word, replace_word)

   with open(file_path, 'w') as file:
      file.write(updated_contents)

def update_folders_paths(old_path,new_path):

    if os.path.exists(str(settings.SCANS_ROOT)+old_path):
        shutil.move(str(settings.SCANS_ROOT)+old_path, str(settings.SCANS_ROOT)+new_path)
    if os.path.exists(str(settings.MARKED_SCANS_ROOT)+old_path):
        shutil.move(str(settings.MARKED_SCANS_ROOT)+old_path, str(settings.MARKED_SCANS_ROOT)+new_path)
    if os.path.exists(str(settings.AMC_PROJECTS_ROOT)+old_path):
        shutil.move(str(settings.AMC_PROJECTS_ROOT)+old_path, str(settings.AMC_PROJECTS_ROOT)+new_path)

