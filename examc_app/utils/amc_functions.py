import base64
import csv
import io
import json
import logging
import os
import re
import shutil
import subprocess
import time
import unicodedata
import xml.etree.ElementTree as xmlET
import zipfile
from datetime import datetime
from decimal import Decimal
import html
from pathlib import Path

import chardet
import img2pdf
import pandas as pd
import xmltodict
from PIL import Image
try:
    from pypdf import PdfReader, PdfWriter
except ImportError:
    from PyPDF2 import PdfReader, PdfWriter
from django.conf import settings
from django.contrib.admin.utils import unquote
from django.core.exceptions import ValidationError
from django.core.mail import EmailMessage
from django.core.validators import validate_email
from django.db.models import Q, Sum
from django.template.loader import get_template
from django.utils.html import strip_tags
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.pdfgen import canvas
from reportlab.platypus import LongTable, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from setuptools import glob

from examc_app.decorators import exam_permission_required
from examc_app.models import (
    Student,
    Exam,
    PagesGroupGradingSchemeCheckedBox,
    QuestionGradingSchemeCheckBox,
    PagesGroup,
    PagesGroupStudentReportNote,
)
from examc_app.signing import make_token_for, verify_and_get_path
from examc_app.utils.amc_db_queries import *
from examc_app.utils.zip_security import safe_extract_zip

# Get an instance of a logger
logger = logging.getLogger(__name__)

def safe_filename_part(s: str) -> str:
    # 1) normalize unicode (splits accents from letters)
    s = unicodedata.normalize("NFKD", s)
    # 2) drop diacritics by encoding to ASCII
    s = s.encode("ascii", "ignore").decode("ascii")
    # 3) spaces -> underscores
    s = s.replace(" ", "_")
    # 4) keep only safe chars (letters, digits, underscore, dash, dot)
    s = re.sub(r"[^A-Za-z0-9_.-]+", "", s)
    # 5) avoid empty parts
    return s or "unknown"

def get_amc_update_document_info(exam):
    info = ''
    exam_sujet_filename = get_amc_option_by_key(exam,'doc_question')
    exam_sujet_filepath = get_amc_project_path(exam, False)+"/"+exam_sujet_filename
    if os.path.isfile(exam_sujet_filepath):
        last_modified_ts = os.path.getmtime(exam_sujet_filepath)
        datetime_str = datetime.fromtimestamp(last_modified_ts).strftime('%d.%m.%Y %H:%M:%S')
        info = "Working documents last update: "
        info += datetime_str
    return info

def get_amc_layout_detection_info(exam):
    info = ''
    amc_data_path = get_amc_project_path(exam, False)

    if amc_data_path:
        amc_data_path += "/data/"

        nb_pages_detected = select_count_layout_pages(amc_data_path)

        if nb_pages_detected > 0:
            info = "Processed "+str(nb_pages_detected)+" pages"

    return info

def get_amc_option_by_key(exam,key):
    options_xml_path = get_amc_project_path(exam, False)+"/options.xml"
    option_value = None
    # Open the project xml config and read the contents
    with open(options_xml_path, 'r', encoding='utf-8') as file:
        options_xml = file.read()

        # Use xmltodict to parse and convert
        # the XML document
        options_dict = xmltodict.parse(options_xml)

        # search by key
        option_value = find_value_dict_by_key(options_dict,key)

    # if not found in project config, try in global amc config xml
    if not option_value:
        with open(settings.AMC_CONFIG_FILE, 'r', encoding='utf-8') as file:
            config_xml = file.read()

            # Use xmltodict to parse and convert
            # the XML document
            config_dict = xmltodict.parse(config_xml)

            # search by key
            option_value = find_value_dict_by_key(config_dict, key)

    return option_value

def find_value_dict_by_key(dict,search_key):
    key_value=None
    for key, value in dict.items():
        if isinstance(value,type(dict)):
            key_value=find_value_dict_by_key(value,search_key)
            if key_value:
                return key_value
        elif key == search_key:
            return value

    # try searching in global by addind 'defaut_' in pre key name
    if not key_value and not search_key.startswith("defaut_"):
        key_value = find_value_dict_by_key(dict,'defaut_'+search_key)


    return key_value

def get_project_dir_info(exam):

    project_dir = get_amc_project_path(exam,False)

    data = path_to_dict(project_dir,[],project_dir)
    project_dir_dict = data[0]
    project_files_dict_list = data[1]


    return [project_dir_dict,project_files_dict_list]

def path_to_dict(path,dir_files_dict_list,amc_project_path):
    text = os.path.basename(path)
    dir_node=None
    if path and os.path.isdir(path):
        dir_node = {'text':text,'href':'#pills-'+text,'nodes':[]}
        new_dir_files_node = {'folder':text,'files':latex_files_to_list(path,amc_project_path)}
        dir_files_dict_list.append(new_dir_files_node)
        for dir in sorted(os.listdir(path), key = lambda x:x.upper()):
            data = path_to_dict(os.path.join(path,dir),dir_files_dict_list,amc_project_path)
            if(data[0]):
                dir_node['nodes'].append(data[0])
            if(data[1]):
                dir_files_dict_list = data[1]

        if dir_node and not dir_node['nodes'] and not new_dir_files_node['files']:
            dir_node = None
            pos = len(dir_files_dict_list)-1
            dir_files_dict_list.pop(pos)
        if dir_node and not dir_node['nodes']:
            del dir_node['nodes']
    return [dir_node,dir_files_dict_list]

def latex_files_to_list(path,amc_project_path):
    extensions = ('.tex')
    file_list = []
    for file in sorted(os.listdir(path),key = lambda x:x.upper()):
        if os.path.isfile(os.path.join(path,file)) and file.endswith(extensions):
            path_str = os.path.relpath(path+"/"+file,amc_project_path)#(path+file).replace('/','//')
            file_list.append([os.path.basename(file),path_str])

    return file_list

# ##testing
# def process(request):
#     # If you're getting IP from a form, ensure this value is passed
#     ip = request.POST.get('ip', 'www.google.ch').strip()  # Default IP to google.ch
#     if not re.fullmatch(r"[A-Za-z0-9.\-:]+", ip):
#         raise ValidationError("Invalid host")
#
#     # Load the template that will be used for each line of the subprocess output
#     template = get_template("subprocess.html")
#
#     # Using subprocess to execute the ping command and stream the output
#     with subprocess.Popen(["ping", "-c5", ip], stdout=subprocess.PIPE, bufsize=1,
#                           universal_newlines=True) as p:
#         # Iterate over each line in the stdout of the subprocess
#         for line in p.stdout:
#             # Yield rendered template with each line
#             yield line.strip()  # Strip to remove extra newlines
#
#     # If the subprocess has a non-zero exit code, raise an error
#     if p.returncode != 0:
#         raise subprocess.CalledProcessError(p.returncode, p.args)
#
# def amc_update_documents_subprocess(exam,nb_copies,scoring_only,preview=False):
#     amc_project_path = get_amc_project_path(exam, False)
#     if preview:
#         os.rename(amc_project_path + "/students.csv", amc_project_path + "/students.bck")
#         os.rename(amc_project_path + "/sample.csv", amc_project_path + "/students.csv")
#
#     if scoring_only:
#         command = [
#             "auto-multiple-choice", "prepare",
#             "--mode", "b",
#             "--data", f"{amc_project_path}/data/",
#             "--with", "pdflatex",
#             "--filter", "latex",
#             "--prefix", f"{amc_project_path}/",
#             f"{amc_project_path}/exam.tex",
#         ]
#     else:
#         amc_update_options_xml_by_key(exam, 'nombre_copies', nb_copies)
#         exam_file = get_amc_option_by_key(exam, 'doc_question')
#         correction_file = get_amc_option_by_key(exam, 'doc_catalog')
#         doc_setting = get_amc_option_by_key(exam, 'doc_setting')
#         command = [
#             "auto-multiple-choice", "prepare",
#             "--mode", "s",
#             "--with", "pdflatex",
#             "--filter", "latex",
#             "--prefix", f"{get_amc_project_path(exam,False)}/",
#             f"{get_amc_project_path(exam,False)}/exam.tex",
#             "--data", f"{get_amc_project_path(exam,False)}/data/",
#             "--out-sujet", exam_file,
#             "--out-catalog", correction_file,
#             "--out-calage", doc_setting,
#         ]
#
#     subprocess.Popen(command, stdout=subprocess.PIPE, bufsize=1, universal_newlines=True)



def amc_update_documents(exam,nb_copies,scoring_only,preview=False):

    amc_project_path = get_amc_project_path(exam,False)
    if preview:
        os.rename(amc_project_path+"/students.csv",amc_project_path+"/students.bck")
        os.rename(amc_project_path+"/sample.csv",amc_project_path+"/students.csv")

    if scoring_only:
        command = [
            "auto-multiple-choice", "prepare",
            "--mode", "b",
            "--data", f"{amc_project_path}/data/",
            "--with", "pdflatex",
            "--filter", "latex",
            "--prefix", f"{amc_project_path}/",
            f"{amc_project_path}/exam.tex",
        ]
        result = subprocess.run(command, capture_output=True, text=True)
    else:
        amc_update_options_xml_by_key(exam,'nombre_copies',nb_copies)
        exam_file = get_amc_option_by_key(exam,'doc_question')
        correction_file = get_amc_option_by_key(exam,'doc_catalog')
        doc_setting = get_amc_option_by_key(exam,'doc_setting')
        command = [
            "auto-multiple-choice", "prepare",
            "--mode", "s",
            "--with", "pdflatex",
            "--filter", "latex",
            "--prefix", f"{get_amc_project_path(exam,False)}/",
            f"{get_amc_project_path(exam,False)}/exam.tex",
            "--data", f"{get_amc_project_path(exam,False)}/data/",
            "--out-sujet", exam_file,
            "--out-catalog", correction_file,
            "--out-calage", doc_setting,
        ]
        result = subprocess.run(command, capture_output=True, text=True)

    if preview:
        os.rename(amc_project_path+"/students.csv",amc_project_path+"/sample.csv")
        os.rename(amc_project_path+"/students.bck",amc_project_path+"/students.csv")

    return result.stdout


def amc_layout_detection(exam):
    project_path = get_amc_project_path(exam,False)
    doc_setting = get_amc_option_by_key(exam,'doc_setting')
    command = [
        "auto-multiple-choice", "meptex",
        "--src", f"{project_path}/{doc_setting}",
        "--data", f"{project_path}/data/",
    ]
    result = subprocess.run(command, capture_output=True, text=True)
    if result.stderr:
        return "ERR:"+result.stderr
    else:
        return result.stdout

def amc_automatic_datacapture_subprocess(request,exam,file_path,from_review,file_list_path=None):
    logger.info(
        "AMC datacapture started exam=%s from_review=%s file_list_path=%s",
        exam.pk,
        from_review,
        file_list_path,
    )
    project_path = get_amc_project_path(exam, False)
    tmp_dir_path = None

    try:
        if not from_review:
            tmp_dir_path = project_path + "/tmp"
            if os.path.exists(tmp_dir_path):
                try:
                    shutil.rmtree(tmp_dir_path)
                except Exception:
                    logger.exception("AMC datacapture failed removing tmp dir exam=%s path=%s", exam.pk, tmp_dir_path)
            os.mkdir(tmp_dir_path)

            tmp_extract_path = tmp_dir_path + "/tmp_extract"
            file_name = f"exam_{exam.pk}_amc_scans.zip"
            tmp_file_path = tmp_dir_path + "/" + file_name
            logger.info("AMC datacapture upload extraction started exam=%s tmp_file=%s", exam.pk, tmp_file_path)
            with open(tmp_file_path, 'wb') as temp_file:
                for chunk in file_path.chunks():
                    temp_file.write(chunk)
                    # extract zip file in tmp dir
            with zipfile.ZipFile(tmp_file_path, 'r') as zip_ref:
                # Security hardening: validated extraction (no traversal/symlink/oversized archive).
                safe_extract_zip(zip_ref, tmp_extract_path)

                file_list_path = tmp_dir_path + "/list-file"
                tmp_file_list = open(file_list_path, "a+")

                files = glob.glob(tmp_extract_path + '/**/*.*', recursive=True)
                for file in files:
                    tmp_file_list.write(file + "\n")

                tmp_file_list.close()
                logger.info(
                    "AMC datacapture upload extraction completed exam=%s extracted_count=%s file_list_path=%s",
                    exam.pk,
                    len(files),
                    file_list_path,
                )

        # prepare scan images (see amc doc)
        command = ["auto-multiple-choice", "getimages", "--list", file_list_path]
        if not from_review:
            command.extend(["--copy-to", f"{project_path}/scans"])

        logger.info("AMC datacapture getimages started exam=%s command=%s", exam.pk, command)
        yield "Getting images ...\n"
        getimages_result = subprocess.run(command, capture_output=True, text=True)
        logger.info(
            "AMC datacapture getimages completed exam=%s returncode=%s stdout_len=%s stderr_len=%s",
            exam.pk,
            getimages_result.returncode,
            len(getimages_result.stdout or ""),
            len(getimages_result.stderr or ""),
        )
        if getimages_result.stderr:
            logger.warning("AMC datacapture getimages stderr exam=%s stderr=%s", exam.pk, getimages_result.stderr)

        os.rename(file_list_path, file_list_path + ".txt")
        file_list_path += ".txt"
        logger.info("AMC datacapture file list renamed exam=%s file_list_path=%s", exam.pk, file_list_path)

        box_prop = get_amc_option_by_key(exam, "box_size_proportion")

        # analyse scans
        command = [
            "auto-multiple-choice", "analyse",
            "--prop", box_prop,
            "--data", f"{project_path}/data/",
            "--projet", project_path,
            "--liste-fichiers", file_list_path,
            "--try-three",
        ]

        logger.info("AMC datacapture analyse started exam=%s command=%s", exam.pk, command)
        yield "Automatic data capture ...\n"
        errors = ''
        with subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            bufsize=1,
            universal_newlines=True,
        ) as process:
            for line in process.stdout:
                logger.info("AMC analyse exam=%s output=%s", exam.pk, line.strip())
                if "ERR:" in line:
                    errors += line
                yield line

            returncode = process.wait()
            logger.info("AMC datacapture analyse completed exam=%s returncode=%s", exam.pk, returncode)
            if returncode:
                raise subprocess.CalledProcessError(returncode, process.args)

        # check consistency between AMC page recognition and review pages
        logger.info("AMC datacapture consistency check started exam=%s", exam.pk)
        yield "Checking data consistency ...\n"
        check_pages_recognition_consistency(exam)
        logger.info("AMC datacapture consistency check completed exam=%s", exam.pk)

        if tmp_dir_path:
            shutil.rmtree(tmp_dir_path)
            logger.info("AMC datacapture tmp dir removed exam=%s path=%s", exam.pk, tmp_dir_path)
        # if file_list_path:
        #     os.remove(file_list_path)
        if errors:
            logger.warning("AMC datacapture analyse reported errors exam=%s errors=%s", exam.pk, errors)
            yield "\n\n**************************\nERRORS: \n-------\n\n"+errors+"\n**************************\n\n"
        logger.info("AMC datacapture completed exam=%s from_review=%s", exam.pk, from_review)
    except GeneratorExit:
        logger.warning("AMC datacapture client disconnected exam=%s from_review=%s", exam.pk, from_review)
        raise
    except (BrokenPipeError, ConnectionResetError):
        logger.warning("AMC datacapture connection interrupted exam=%s from_review=%s", exam.pk, from_review, exc_info=True)
        raise
    except Exception:
        logger.exception("AMC datacapture failed exam=%s from_review=%s file_list_path=%s", exam.pk, from_review, file_list_path)
        raise

def check_pages_recognition_consistency(exam):
    project_path = get_amc_project_path(exam, False)

    capture_pages = select_capture_pages(project_path+"/data/")

    for capture_page in capture_pages:
        #yield " -- copy "+ str(capture_page['student']) + " page " + str(capture_page['page']) + "\n"
        filename = capture_page['src'].split("/")[-1]
        filename_split = filename.split('.')
        if len(filename_split) > 2:
            new_filename_path = capture_page['src'].replace(filename,'')
            new_filename = 'copy_'+str(capture_page['student']).zfill(4)+"_"+str(capture_page['page']).zfill(2)+"."+filename_split[2]
            new_filename = new_filename_path+new_filename
            if '%HOME' in new_filename:
                shutil.move(capture_page['src'].replace('%HOME',str(Path.home())),new_filename.replace('%HOME',str(Path.home())))
            else:
                shutil.move(capture_page['src'],new_filename)
            update_capture_page_src(project_path+"/data/",capture_page['student'],capture_page['page'],new_filename)



def amc_automatic_data_capture(exam,file_path,from_review,file_list_path=None):
    project_path = get_amc_project_path(exam, False)

    if not from_review:
        tmp_dir_path = project_path+"/tmp"
        if os.path.exists(tmp_dir_path):
            try:
                shutil.rmtree(tmp_dir_path)
            except Exception as e:
                t = ''
        os.mkdir(tmp_dir_path)

        tmp_extract_path = tmp_dir_path + "/tmp_extract"
        file_name = f"exam_{exam.pk}_amc_scans.zip"
        tmp_file_path = tmp_dir_path + "/" + file_name
        with open(tmp_file_path, 'wb') as temp_file:
            for chunk in file_path.chunks():
                temp_file.write(chunk)
                # extract zip file in tmp dir
        with zipfile.ZipFile(tmp_file_path, 'r') as zip_ref:
            print("start extraction")
            # Security hardening: validated extraction (no traversal/symlink/oversized archive).
            safe_extract_zip(zip_ref, tmp_extract_path)

            file_list_path = tmp_dir_path+"/list-file"
            tmp_file_list = open(file_list_path, "a+")

            files = glob.glob(tmp_extract_path+'/**/*.*', recursive=True)
            for file in files:
                tmp_file_list.write(file + "\n")

            tmp_file_list.close()
    print('amc getimages')

    # prepare scan images (see amc doc)
    command = ["auto-multiple-choice", "getimages", "--list", file_list_path]
    if not from_review:
        command.extend(["--copy-to", f"{project_path}/scans"])

    with subprocess.Popen(command, stdout=subprocess.PIPE, bufsize=1,universal_newlines=True) as process:
        for line in process.stdout:
            print(line.strip())
    # if result.stderr:
    #     print("err : " + result.stderr)
    #     return "ERR:" + result.stderr
    # else:

    if not from_review:
        # replace tmp scans dir with scans dir to file_list_path
        # rename file_list_path to .txt
        # finally send this file as parameter to analyse
        with open(file_list_path,'r') as file:
            data = file.read()
            data = data.replace(tmp_extract_path,project_path+'/scans')
        with open(file_list_path,'w') as file:
            file.write(data)

    os.rename(file_list_path,file_list_path+".txt")
    file_list_path+=".txt"
    box_prop = get_amc_option_by_key(exam, "box_size_proportion")
    print("before analyse")
    # analyse scans
    print("amc analyse")
    command = [
        "auto-multiple-choice", "analyse",
        "--prop", box_prop,
        "--data", f"{project_path}/data/",
        "--projet", project_path,
        "--liste-fichiers", file_list_path,
        "--try-three",
    ]
    with subprocess.Popen(command, stdout=subprocess.PIPE, bufsize=1, universal_newlines=True) as process:
        for line in process.stdout:
            print(line.strip())

    print("end analyse")
    os.remove(file_list_path)
    return 'ok'


def amc_update_options_xml_by_key(exam,key,value):

    # Open original file
    options_xml_path = get_amc_project_path(exam,False)+"/options.xml"
    xml = xmlET.parse(options_xml_path)
    root = xml.getroot()

    # find element and modify value
    element =  root.find(key)
    element.text = value

    # Write back to file
    # et.write('file.xml')
    xml.write(get_amc_project_path(exam,False)+"/options.xml")


def get_amc_exam_pdf_path(exam):
    file_name = get_amc_option_by_key(exam,'doc_question')
    file_path = get_amc_project_path(exam,False)+"/"+file_name
    return file_path

def get_amc_exam_pdf_url(exam):
    file_name = get_amc_option_by_key(exam, 'doc_question')
    file_url = get_amc_project_url(exam) + "/" + file_name
    return file_url

def get_amc_catalog_pdf_path(exam):
    file_name = get_amc_option_by_key(exam,'doc_catalog')
    file_path = get_amc_project_path(exam,False)+"/"+file_name
    return file_path

def get_amc_project_path(exam,even_if_not_exist):
    amc_project_path = str(settings.AMC_PROJECTS_ROOT)+"/"+str(exam.year.code)+"/"+str(exam.semester.code)+"/"+exam.code+"_"+exam.date.strftime("%Y%m%d")

    #print('****************** amc_project_path : ' + amc_project_path)
    if os.path.isdir(amc_project_path):
        return amc_project_path
    elif even_if_not_exist:
        return amc_project_path
    else:
        return None

def get_amc_project_url(exam):
    amc_project_url = str(settings.AMC_PROJECTS_URL)+str(exam.year.code)+"/"+str(exam.semester.code)+"/"+exam.code+"_"+exam.date.strftime("%Y%m%d")
    return amc_project_url

def get_amc_data_capture_manual_data(exam):
    amc_project_path = get_amc_project_path(exam, False)


    if amc_project_path:
        amc_extra_pages_path = amc_project_path+"/scans/extra/"
        amc_data_path = amc_project_path+"/data/"
        amc_project_url = get_amc_project_url(exam)
        amc_threshold = get_amc_option_by_key(exam,"seuil")
        data_pages = select_manual_datacapture_pages(amc_data_path,amc_project_url,amc_threshold)

        # get extra_pages
        extra_pages = get_extra_pages(amc_extra_pages_path,amc_project_url+"/scans/extra/")
        data_pages += extra_pages
        data_pages = sorted(data_pages, key=lambda k: (float(k['copy']), float(k['page'])))

        # if data_pages and '%HOME' in data_pages[0]['source']:
        #     app_home_path = str(settings.BASE_DIR).replace(str(Path.home()),'%HOME')
        #     for data in data_pages:
        #         data['source'] = data['source'].replace(app_home_path,'')

        data_copies = []
        for data in data_pages:
            data_questions_id = select_manual_datacapture_questions(amc_data_path,data)
            questions_ids = ''
            if data_questions_id:
                for qid in data_questions_id:
                    questions_ids += '%' + str(qid['question_id']) + '%'
                    if 'why' in qid.keys():
                        if qid['why'] == 'E':
                            questions_ids += '|INV|'
                        elif qid['why'] == 'V':
                            questions_ids += '|EMP|'

            if not data['copy'] in data_copies:
                data_copies.append(data['copy'])

            data['questions_ids'] = questions_ids + '%'

        data_questions = select_questions(amc_data_path)

        return [data_pages, data_questions, data_copies]

    return None

def get_extra_pages(amc_extra_pages_path,amc_extra_pages_url=None,student=None):
    extra_pages_data = []
    if not amc_extra_pages_url:
        amc_extra_pages_url = amc_extra_pages_path
    if os.path.exists(amc_extra_pages_path):
        extra_subdirs = os.listdir(amc_extra_pages_path)
        for subdir in extra_subdirs:
            if not student or (str(student) == subdir.lstrip("0") ):
                for file in os.listdir(amc_extra_pages_path+subdir):
                    filepath = amc_extra_pages_url+subdir+"/"+file
                    copy = file.split('_')[1].lstrip('0')
                    page = file.split('_')[2].replace('.jpg','').lstrip('0')
                    extra_page = {'copy':copy,'mse':0.0,'page':page,'sensitivity':0.0,'source':filepath,'timestamp_auto':0}
                    extra_pages_data.append(extra_page)

    return extra_pages_data

def get_amc_marks_positions_data(exam,copy,page):
    amc_data_path = get_amc_project_path(exam, False)

    if amc_data_path:
        amc_data_path += "/data/"
        data_positions = select_marks_positions(amc_data_path,copy,page,float(get_amc_option_by_key(exam,"seuil")))

        for idx, item in enumerate(data_positions):
            item["checked"] = False
            if (item["bvalue"] >= float(get_amc_option_by_key(exam, "seuil")) and item["manual"] == -1.0) or item[
                "manual"] == 1.0:
                item["checked"] = True

            data_positions[idx] = item

        return data_positions

def update_amc_mark_zone_data(exam,zoneid,copy,page):
    amc_data_path = get_amc_project_path(exam, False)

    if amc_data_path:
        amc_data_path += "/data/"

        data_zones = select_data_zones(amc_data_path,zoneid)

        manual = data_zones[0]['manual']
        bvalue = data_zones[0]['bvalue']
        if (manual == -1.0 and bvalue >= float(get_amc_option_by_key(exam,"seuil"))) or manual == 1.0:
            manual = "0.0"
        else:
            manual = "1.0"

        update_data_zone(amc_data_path,manual,zoneid, copy, page)

def _is_valid_amc_options_xml(options_xml_path):
    try:
        with open(options_xml_path, "r", encoding="utf-8", errors="ignore") as options_file:
            first_line = options_file.readline().strip()
            second_line = options_file.readline().strip()
        return (
            first_line == '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            and second_line == "<project>"
        )
    except OSError:
        return False

def _find_amc_project_dir(extracted_root_path):
    candidates = []

    for current_root, _, files in os.walk(extracted_root_path):
        if "options.xml" not in files:
            continue

        options_xml_path = os.path.join(current_root, "options.xml")
        if _is_valid_amc_options_xml(options_xml_path):
            relative_depth = len(Path(current_root).relative_to(extracted_root_path).parts)
            candidates.append((relative_depth, current_root))

    if not candidates:
        return None

    # Prefer the closest directory to archive root if multiple candidates exist.
    candidates.sort(key=lambda item: (item[0], item[1]))
    return candidates[0][1]

def create_amc_project_dir_from_zip(exam,zip_file):
    file_name = f"exam_{exam.pk}_amc_project.zip"
    temp_file_path = os.path.join(settings.AUTOUPLOAD_ROOT, file_name)

    os.makedirs(os.path.dirname(temp_file_path), exist_ok=True)

    with open(temp_file_path, 'wb') as temp_file:
        for chunk in zip_file.chunks():
            temp_file.write(chunk)

    zip_path = str(settings.AUTOUPLOAD_ROOT) + "/" + str(exam.year.code) + "_" + str(exam.semester.code) + "_" + exam.code
    tmp_extract_path = zip_path + "/tmp_extract"

    os.makedirs(zip_path, exist_ok=True)
    if os.path.exists(tmp_extract_path):
        shutil.rmtree(tmp_extract_path)

    # extract zip file in tmp dir
    with zipfile.ZipFile(temp_file_path, 'r') as zip_ref:
        print("start extraction")
        # Security hardening: validated extraction (no traversal/symlink/oversized archive).
        safe_extract_zip(zip_ref, tmp_extract_path)

    project_dir_path = _find_amc_project_dir(tmp_extract_path)
    if not project_dir_path:
        shutil.rmtree(tmp_extract_path, ignore_errors=True)
        return 'The zip file does not contain a valid AMC project folder with an options.xml starting with <project>!'

    # move to destination amc_projects
    amc_project_path = get_amc_project_path(exam, True)
    # Remove destination folder if it exists
    if os.path.exists(amc_project_path):
        shutil.rmtree(amc_project_path)
    shutil.move(project_dir_path, amc_project_path)

    # Remove remaining extracted files (wrapper folders, etc.).
    if os.path.exists(tmp_extract_path):
        shutil.rmtree(tmp_extract_path, ignore_errors=True)

    return 'AMC project folder uploaded !'

def get_automatic_data_capture_summary(exam):

    amc_data_path = get_amc_project_path(exam, False)
    amc_data_url = get_amc_project_url(exam)

    if amc_data_path:
        amc_data_path += "/data/"

        nb_copies = select_nb_copies(amc_data_path)

        data_missing_pages = []
        nb_unrecognized_pages = []

        if nb_copies > 0:
            data_missing_pages = select_missing_pages(amc_data_path)
            nb_unrecognized_pages = count_unrecognized_pages(amc_data_path)

        prev_stud = None
        incomplete_copies = []
        missing_pages = []
        for missing_page in data_missing_pages:

            if prev_stud and missing_page.get("student") != prev_stud:
                incomplete_copy = {"copy_no":prev_stud,"missing_pages":missing_pages}
                incomplete_copies.append(incomplete_copy)
                missing_pages = []

            missing_pages.append(missing_page.get("page"))
            prev_stud = missing_page.get("student")

        if missing_pages :
            incomplete_copy = {"copy_no": prev_stud, "missing_pages": missing_pages}
            incomplete_copies.append(incomplete_copy)

        data_overwritten_pages = select_overwritten_pages(amc_data_path)

        return [nb_copies, incomplete_copies,nb_unrecognized_pages,data_overwritten_pages]

    return None

def get_copy_page_zooms(exam,copy,page):
    amc_data_path = get_amc_project_path(exam, False)
    zooms_data = None
    if amc_data_path:
        amc_data_path += "/data/"

        zooms_data = select_copy_page_zooms(amc_data_path, copy, page)

        #decode bytes imagedata to base64
        for idx, item in enumerate(zooms_data):
            imagedata = base64.b64encode(item["imagedata"])
            item["imagedata"] = imagedata.decode()
            item["checked"] = False
            if (item["bvalue"] >= float(get_amc_option_by_key(exam,"seuil")) and item["manual"] == -1) or item["manual"] == 1:
                item["checked"] = True

            zooms_data[idx] = item

    return zooms_data

def add_unrecognized_page_to_project(exam,copy,page,extra,img_filename):
    amc_data_path = get_amc_project_path(exam, False)
    if amc_data_path:

        if extra:

            #page = select_copy_question_page(amc_data_path+'/data/', copy, question)
            copy_extra_folder_path = amc_data_path + "/scans/extra/" + copy.zfill(4)
            #create extra folder for copy if not exist
            Path(copy_extra_folder_path).mkdir(parents=True, exist_ok=True)

            # #list files and get last extraNumber
            last_exNum = 0
            #
            for f in os.listdir(copy_extra_folder_path):
                curr_page = int(f.split('_')[-1].split(".")[0])
                curr_exNum = int(f.split(".")[1])
                if curr_page == page and curr_exNum > last_exNum:
                    last_exNum = curr_exNum

            new_exNum = str(last_exNum + 1)
            filename = "copy_"+str(copy).zfill(4)+"_"+str(page)+"."+new_exNum+".jpg"

            #get scan path unsigned
            extra_path = str(verify_and_get_path(unquote(img_filename.replace('/protected/?token=',''))))
            #move to extra folder
            shutil.copy(extra_path, copy_extra_folder_path+'/'+extra_path.split('/')[-1].replace('marked_',''))

            #remove as unrecognized page
            delete_unrecognized_page(amc_data_path+'/data/',extra_path)

        else:
            one=1#todo

def get_students_csv_headers(exam):
    amc_data_path = get_amc_project_path(exam, False)
    if amc_data_path:

        students_file = get_amc_option_by_key(exam,"listeetudiants").replace("%PROJET",amc_data_path)

        with open(students_file,'r', encoding="utf-8") as csv_file:

            csv_reader = csv.DictReader(csv_file)
            dict_from_csv = dict(list(csv_reader)[0])
            return list(dict_from_csv.keys())

def get_automatic_association_code(exam):
    amc_data_path = get_amc_project_path(exam, False)
    if amc_data_path:
        association_code = get_amc_option_by_key(exam, "assoc_code")
        if association_code:
            return association_code

#     return "Pre-association"
#
# def amc_mark(exam,update_scoring_strategy):
#     if update_scoring_strategy == 'true':
#         result = amc_update_documents(exam,None,True)
#
#     project_path = get_amc_project_path(exam, False)
#     threshold = get_amc_option_by_key(exam, "seuil")
#     threshold_up = get_amc_option_by_key(exam, 'seuil_up')
#     grain = get_amc_option_by_key(exam, "note_grain")
#     round = get_amc_option_by_key(exam, "note_arrondi")
#     notemin = get_amc_option_by_key(exam, "note_min")
#     notemax = get_amc_option_by_key(exam, "note_max")
#     plafond = get_amc_option_by_key(exam, "note_max_plafond")
#     result = subprocess.run(['auto-multiple-choice note '
#                              '--data "' + project_path + '/data/" '
#                              '--seuil ' + threshold + ' '
#                              '--seuil-up '  + threshold_up + ' '
#                              '--grain ' + grain + ' '
#                              '--arrondi ' + round + ' '
#                              '--notemin ' + notemin + ' '
#                              '--notemax ' + notemax + ' '
#                              '--plafond ' + plafond + ' ']
#                             , shell=True
#                             , capture_output=True
#                             , text=True)
#     if result.stderr:
#         return "ERR:" + result.stderr
#     else:
#         return result.stdout

def amc_mark(exam,update_scoring_strategy):
    print("************** Start marking")
    if update_scoring_strategy == 'true':
        result = amc_update_documents(exam,None,True)

    project_path = get_amc_project_path(exam, False)
    threshold = get_amc_option_by_key(exam, "seuil")
    threshold_up = get_amc_option_by_key(exam, 'seuil_up')
    grain = get_amc_option_by_key(exam, "note_grain")
    round_grade = get_amc_option_by_key(exam, "note_arrondi")
    notemin = get_amc_option_by_key(exam, "note_min")
    notemax = get_amc_option_by_key(exam, "note_max")
    plafond = get_amc_option_by_key(exam, "note_max_plafond")
    yield "Start marking ...\n"

    command = [
        "auto-multiple-choice", "note",
        "--data", f"{project_path}/data/",
        "--seuil", threshold,
        "--seuil-up", threshold_up,
        "--grain", grain,
        "--arrondi", round_grade,
        "--notemin", notemin,
        "--notemax", notemax,
        "--plafond", plafond,
    ]
    errors = ''
    with subprocess.Popen(command,stdout=subprocess.PIPE, bufsize=1,universal_newlines=True) as process:
        with open(project_path+'/amc-compiled.amc', 'r') as file:
            # Read each line in the file
            for line in file:
                if 'ETU' in line:
                    info_str = 'Student Nr. '+line.split('=')[1].split('}')[0] + ' \n'
                    print(info_str)
                    yield info_str

        if  process.returncode and process.returncode != 0:
            raise subprocess.CalledProcessError(process.returncode, process.args)

    if errors:
        yield "\n\n**************************\nERRORS: \n-------\n\n" + errors + "\n**************************\n\n"

def amc_mark_subprocess(request, exam,update_scoring_strategy):
    if update_scoring_strategy == 'true':
        result = amc_update_documents(exam,None,True)

    project_path = get_amc_project_path(exam, False)
    threshold = get_amc_option_by_key(exam, "seuil")
    threshold_up = get_amc_option_by_key(exam, 'seuil_up')
    grain = get_amc_option_by_key(exam, "note_grain")
    round_grade = get_amc_option_by_key(exam, "note_arrondi")
    notemin = get_amc_option_by_key(exam, "note_min")
    notemax = get_amc_option_by_key(exam, "note_max")
    plafond = get_amc_option_by_key(exam, "note_max_plafond")

    command = [
        "auto-multiple-choice", "note",
        "--data", f"{project_path}/data/",
        "--seuil", threshold,
        "--seuil-up", threshold_up,
        "--grain", grain,
        "--arrondi", round_grade,
        "--notemin", notemin,
        "--notemax", notemax,
    ]
    errors = ''
    with subprocess.Popen(command,stdout=subprocess.PIPE, bufsize=1,universal_newlines=True) as process:
        with open(project_path+'/amc-compiled.amc', 'r') as file:
            # Read each line in the file
            for line in file:
                if 'ETU' in line:
                    info_str = 'Student Nr. '+line.split('=')[1].split('}')[0] + ' \n'
                    print(info_str)
                    yield info_str

        if  process.returncode and process.returncode != 0:
            raise subprocess.CalledProcessError(process.returncode, process.args)

    if errors:
        yield "\n\n**************************\nERRORS: \n-------\n\n" + errors + "\n**************************\n\n"

def get_amc_mean(exam):
    amc_data_path = get_amc_project_path(exam, False)
    if amc_data_path:
        return get_mean(amc_data_path+"/data/")

def get_questions_scoring_details_list(exam):
    questions_scoring_details_list = []
    amc_data_path = get_amc_project_path(exam, False)
    if amc_data_path:
        data = get_questions_scoring_details(amc_data_path + "/data/")

        last_copy = 0
        q_scoring_details_copy = {}
        q_question_scoring = {}
        q_question_scoring_list = []
        new_copy = False;
        for row in data:
            for key,value in row.items():
                if key == 'copy' and value != last_copy:
                    if last_copy != 0:
                        q_question_scoring_list.append(q_question_scoring)
                        q_scoring_details_copy['questions'] = q_question_scoring_list
                        q_question_scoring_list = []
                        q_question_scoring = {}
                        questions_scoring_details_list.append(q_scoring_details_copy)
                    q_scoring_details_copy = {'copy':value}
                    new_copy = True
                    last_copy = value

                if new_copy and key not in ['question','score','max_question','mark']:
                    q_scoring_details_copy[key] = value
                elif key == 'mark':
                    new_copy = False

                elif not new_copy and key in ['question','score','max_question']:
                    if key == 'question':
                        if q_question_scoring:
                            q_question_scoring_list.append(q_question_scoring)
                            q_question_scoring = {}

                    q_question_scoring[key] = value

        q_question_scoring_list.append(q_question_scoring)
        q_scoring_details_copy['questions'] = q_question_scoring_list
        questions_scoring_details_list.append(q_scoring_details_copy)

    return questions_scoring_details_list

def amc_automatic_association(exam,assoc_primary_key):
    project_path = get_amc_project_path(exam, False)
    amc_update_options_xml_by_key(exam,'liste_key',assoc_primary_key)
    students_list = get_amc_option_by_key(exam, 'listeetudiants').replace('%PROJET',project_path)
    command = [
        "auto-multiple-choice", "association-auto",
        "--data", f"{project_path}/data/",
        "--pre-association",
        "--liste", students_list,
        "--liste-key", assoc_primary_key,
    ]
    result = subprocess.run(command, capture_output=True, text=True)
    if result.stderr:
        return "ERR:" + result.stderr
    else:
        sync_student_amc_ids_from_association(exam)
        return result.stdout

def check_students_csv_file(file):

    with open(file,'rb') as csvfile:
        data = csvfile.read()
        #check encoding
        encoding = chardet.detect(bytearray(data))['encoding']
        if encoding.upper() != "UTF-8" and "ASCII" not in encoding.upper():
            return "Wrong encoding : Encoding must be UTF-8 !"

    with open(file, newline="") as csvfile:
        data = csvfile.read()
        # #check delimiter comma
        try:
            dialect = csv.Sniffer().sniff(data, delimiters=",")
        except:
            return "Wrong delimiter : Delimiter must be comma !"

    #check data (ID,NAME unique)
    df = pd.read_csv(file)
    data_list = [list(row) for row in df.values]
    id_list = []
    name_list = []
    for row in data_list:
        if row[0] in id_list:
            return "Duplicate ID : ID must be unique!"
        id_list.append(row[0])

        if row[1] in name_list:
            return "Duplicate NAME : NAME must be unique!"
        name_list.append(row[1])

    return "ok"


def get_annotated_pdfs_dir(exam):
    return Path(get_amc_project_path(exam, False)) / "cr" / "corrections" / "pdf"


def get_annotated_zip_path(exam):
    corrections_path = Path(get_amc_project_path(exam, False)) / "cr" / "corrections"
    zip_filename = f"annotated_pdfs_{exam.code}_{exam.year.code}_{exam.semester.code}.zip"
    return corrections_path / zip_filename


def cleanup_previous_annotated_outputs(exam):
    annotated_pdfs_dir = get_annotated_pdfs_dir(exam)
    annotated_pdfs_dir.mkdir(parents=True, exist_ok=True)

    deleted_pdfs = 0
    for pdf_path in annotated_pdfs_dir.glob("*.pdf"):
        if not pdf_path.is_file():
            continue
        pdf_path.unlink()
        deleted_pdfs += 1

    annotated_zip_path = get_annotated_zip_path(exam)
    zip_deleted = False
    if annotated_zip_path.exists():
        annotated_zip_path.unlink()
        zip_deleted = True

    logger.info(
        "AMC previous annotated outputs cleaned exam=%s deleted_pdfs=%s zip_deleted=%s zip=%s",
        exam.pk,
        deleted_pdfs,
        zip_deleted,
        annotated_zip_path,
    )
    return deleted_pdfs, zip_deleted


def get_annotated_pdf_mtimes(annotated_pdfs_dir):
    annotated_pdfs_dir = Path(annotated_pdfs_dir)
    if not annotated_pdfs_dir.exists():
        return {}

    mtimes = {}
    for pdf_path in annotated_pdfs_dir.glob("*.pdf"):
        if not pdf_path.is_file():
            continue
        try:
            mtimes[pdf_path] = pdf_path.stat().st_mtime_ns
        except OSError:
            continue
    return mtimes


def count_updated_annotated_pdfs(annotated_pdfs_dir, initial_mtimes):
    annotated_pdfs_dir = Path(annotated_pdfs_dir)
    if not annotated_pdfs_dir.exists():
        return 0

    count = 0
    for pdf_path in annotated_pdfs_dir.glob("*.pdf"):
        if not pdf_path.is_file():
            continue
        try:
            if initial_mtimes.get(pdf_path) != pdf_path.stat().st_mtime_ns:
                count += 1
        except OSError:
            continue
    return count


def run_amc_annotate_command(command, exam, single_file, progress_callback=None):
    annotated_pdfs_dir = get_annotated_pdfs_dir(exam)
    total = 1 if single_file else Student.objects.filter(exam=exam).count()
    initial_mtimes = get_annotated_pdf_mtimes(annotated_pdfs_dir)
    last_done = -1
    last_update_at = 0

    if progress_callback:
        progress_callback(
            done=0,
            total=total,
            message=f"Generating AMC annotations: 0/{total} files generated",
        )

    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    while True:
        try:
            stdout, stderr = process.communicate(timeout=2)
            break
        except subprocess.TimeoutExpired:
            done = count_updated_annotated_pdfs(annotated_pdfs_dir, initial_mtimes)
            if total:
                done = min(done, total)

            now = time.time()
            if progress_callback and (done != last_done or now - last_update_at >= 10):
                progress_callback(
                    done=done,
                    total=total,
                    message=f"Generating AMC annotations: {done}/{total} files generated",
                )
                last_done = done
                last_update_at = now

    done = count_updated_annotated_pdfs(annotated_pdfs_dir, initial_mtimes)
    if total:
        done = min(done, total)
    if progress_callback:
        progress_callback(
            done=done,
            total=total,
            message=f"Generating AMC annotations: {done}/{total} files generated",
        )

    return subprocess.CompletedProcess(command, process.returncode, stdout, stderr)


def amc_annotate(exam, single_file, add_grading_scheme_report, progress_callback=None):
    project_path = get_amc_project_path(exam, False)
    assoc_primary_key = get_amc_option_by_key(exam,'liste_key')
    students_list = get_amc_option_by_key(exam, 'listeetudiants').replace('%PROJET',project_path)
    filename_model = get_amc_option_by_key(exam,'modele_regroupement')
    verdict = get_amc_option_by_key(exam,'verdict').replace('\n','\r\n')
    verdict_q = get_amc_option_by_key(exam,'verdict_q')
    verdict_qc = get_amc_option_by_key(exam,'verdict_qc')
    symbols = get_annotation_symbols(exam)
    annote_position = get_amc_option_by_key(exam,'annote_position')
    command = [
        "auto-multiple-choice", "annotate",
        "--project", project_path,
        "--names-file", students_list,
        "--association-key", assoc_primary_key,
        "--filename-model", filename_model,
        "--symbols", symbols,
        "--verdict", verdict,
        "--verdict-question", verdict_q,
        "--verdict-question-cancelled", verdict_qc,
        "--position", annote_position,
        "--compose", "0",
    ]
    if single_file:
        command.extend(["--single-output", "annotated_papers.pdf"])

    logger.info(
        "AMC annotate command started exam=%s single_file=%s add_grading_scheme_report=%s command=%s",
        exam.pk,
        single_file,
        add_grading_scheme_report,
        command,
    )
    if progress_callback:
        progress_callback(message="Cleaning previous annotated outputs...")
    cleanup_previous_annotated_outputs(exam)

    result = run_amc_annotate_command(
        command,
        exam,
        single_file,
        progress_callback=progress_callback,
    )
    logger.info(
        "AMC annotate command completed exam=%s returncode=%s stdout_len=%s stderr_len=%s",
        exam.pk,
        result.returncode,
        len(result.stdout or ""),
        len(result.stderr or ""),
    )
    if result.stderr:
        logger.error("AMC annotate command stderr exam=%s stderr=%s", exam.pk, result.stderr)
        return "ERR:" + result.stderr
    else:

        student_report_data = get_student_report_data(project_path+"/data/")
        report_type = 2 if single_file else 1
        generated_rows = [
            row for row in student_report_data
            if int(row.get("type") or 0) == report_type
        ]
        generated_count = 1 if single_file else len(generated_rows)
        logger.info(
            "AMC annotate reports registered exam=%s report_type=%s report_rows=%s generated_count=%s",
            exam.pk,
            report_type,
            len(generated_rows),
            generated_count,
        )
        if progress_callback and not add_grading_scheme_report:
            progress_callback(
                done=generated_count,
                total=generated_count,
                message=f"{generated_count}/{generated_count} files generated",
            )

        for st_rep in student_report_data:
            add_extra_to_annotated_pdf(st_rep['student'], st_rep['file'], project_path)

        if add_grading_scheme_report:
            add_grading_schemes_reports(
                exam.id,
                single_file=single_file,
                progress_callback=progress_callback,
            )

        return result.stdout

def add_extra_to_annotated_pdf(student, annotated_file, amc_project_path):
    amc_extra_pages_path = amc_project_path+"/scans/extra/"
    amc_annoted_pdfs_path = amc_project_path+"/cr/corrections/pdf/"
    extra_pdf_tmp_path = amc_extra_pages_path+str(student).zfill(4)+"/"
    extra_pages = get_extra_pages(amc_extra_pages_path,None,student)
    extra_pages = sorted(extra_pages, key=lambda d: int(d['page'].split('.')[0]))

    #set A4 for img conversion to pdf page
    a4inpt = (img2pdf.mm_to_pt(210), img2pdf.mm_to_pt(297))
    layout_fun = img2pdf.get_layout_fun(a4inpt)

    if extra_pages:
        added_pages = 0
        for extra_page in extra_pages:
            with Image.open(extra_page['source']) as img:
                pdf = img2pdf.convert(extra_page['source'],layout_fun=layout_fun)
                with open(extra_pdf_tmp_path+"tmp_extra.pdf","wb") as file:
                    file.write(pdf)
                    file.close()

            extra_pdf = PdfReader(extra_pdf_tmp_path+"tmp_extra.pdf", 'rb')
            annotated_pdf = PdfReader(amc_annoted_pdfs_path+annotated_file, 'rb')
            final_annotated_pdf = PdfWriter()

            page_to_add = extra_pdf.pages[0]

            page_added = False
            for i in range(len(annotated_pdf.pages)):
                final_annotated_pdf.add_page(annotated_pdf.pages[i])
                if not page_added and i+1 == int(extra_page['page'].split(".")[0])+added_pages:
                    final_annotated_pdf.add_page(page_to_add)
                    added_pages += 1
                    page_added = True


            with open(amc_annoted_pdfs_path+annotated_file, 'wb') as f:
                final_annotated_pdf.write(f)

            os.remove(extra_pdf_tmp_path+"tmp_extra.pdf")

def get_annotation_symbols(exam):
    symb_0_0_color = get_amc_option_by_key(exam,'symbole_0_0_color')
    symb_0_0_type = get_amc_option_by_key(exam, 'symbole_0_0_type')
    symb_0_1_color = get_amc_option_by_key(exam, 'symbole_0_1_color')
    symb_0_1_type = get_amc_option_by_key(exam, 'symbole_0_1_type')
    symb_1_0_color = get_amc_option_by_key(exam, 'symbole_1_0_color')
    symb_1_0_type = get_amc_option_by_key(exam, 'symbole_1_0_type')
    symb_1_1_color = get_amc_option_by_key(exam, 'symbole_1_1_color')
    symb_1_1_type = get_amc_option_by_key(exam, 'symbole_1_1_type')

    symbols_string = "0-0:"+symb_0_0_type
    if symb_0_0_type != 'none':
        symbols_string += ":"+symb_0_0_color
    symbols_string += ",0-1:" + symb_0_1_type
    if symb_0_1_type != 'none':
        symbols_string += ":" + symb_0_1_color
    symbols_string += ",1-0:" + symb_1_0_type
    if symb_1_0_type != 'none':
        symbols_string += ":" + symb_1_0_color
    symbols_string += ",1-1:" + symb_1_1_type
    if symb_1_1_type != 'none':
        symbols_string += ":" + symb_1_1_color

    return symbols_string

def check_annotated_papers_available(exam):
    project_path = get_amc_project_path(exam,False)
    annotated_path = project_path+"/cr/corrections/pdf/"
    pdf_list = [os.path.join(annotated_path, f) for f in os.listdir(annotated_path) if f.endswith(".pdf")]
    if len(pdf_list) > 0:
        return True
    else:
        return False

def resolve_annotated_pdf_path(annotated_pdfs_dir, filename):
    annotated_pdf_path = Path(filename or "")
    if not annotated_pdf_path.is_absolute():
        annotated_pdf_path = Path(annotated_pdfs_dir) / annotated_pdf_path
    return annotated_pdf_path


def copy_number_candidates(copy_nr):
    if copy_nr is None or copy_nr == "":
        return []

    value = str(copy_nr).strip()
    return list(dict.fromkeys([
        value,
        value.zfill(4),
        value.zfill(2),
        value.lstrip("0") or "0",
    ]))


def report_row_amc_copy_nr(report_row):
    return report_row.get("amc_copy") or report_row.get("student")


def find_student_for_association_value(exam, assoc_primary_key, associated_student):
    if associated_student is None or str(associated_student).strip() == "":
        return None

    associated_student = str(associated_student).strip()
    if assoc_primary_key == "ID":
        return (
            Student.objects
            .filter(
                Q(copie_no__in=copy_number_candidates(associated_student))
                | Q(amc_id__in=copy_number_candidates(associated_student)),
                exam=exam,
            )
            .first()
        )
    if assoc_primary_key == "SCIPER":
        return Student.objects.filter(exam=exam, sciper=associated_student).first()
    if assoc_primary_key == "NAME":
        return Student.objects.filter(exam=exam, name=associated_student).first()

    return (
        Student.objects
        .filter(exam=exam)
        .filter(
            Q(copie_no=associated_student)
            | Q(amc_id=associated_student)
            | Q(sciper=associated_student)
            | Q(name=associated_student)
        )
        .first()
    )


def sync_student_amc_ids_from_association(exam):
    project_path = get_amc_project_path(exam, False)
    if not project_path:
        return 0

    amc_data_path = project_path + "/data/"
    assoc_primary_key = get_amc_option_by_key(exam, "liste_key")
    associations = select_student_association_data(amc_data_path)

    Student.objects.filter(exam=exam).update(amc_id="0")
    updated_count = 0
    for association in associations:
        amc_copy_nr = association.get("amc_copy")
        associated_student = association.get("associated_student")
        if amc_copy_nr is None or associated_student is None:
            continue

        student = find_student_for_association_value(exam, assoc_primary_key, associated_student)
        if not student:
            logger.warning(
                "No student found while syncing AMC id exam=%s assoc_key=%s associated_student=%s amc_copy=%s",
                exam.pk,
                assoc_primary_key,
                associated_student,
                amc_copy_nr,
            )
            continue

        student.amc_id = str(amc_copy_nr)
        student.save(update_fields=["amc_id"])
        updated_count += 1

    logger.info(
        "Student AMC ids synced from association exam=%s assoc_key=%s updated=%s associations=%s",
        exam.pk,
        assoc_primary_key,
        updated_count,
        len(associations),
    )
    return updated_count


def empty_student_amc_id(value):
    return value is None or str(value).strip() in ("", "0", "None")


def student_amc_copy_nr(student):
    if not empty_student_amc_id(student.amc_id):
        return student.amc_id
    return student.copie_no


def update_student_amc_id_if_missing(student, amc_copy_nr):
    if empty_student_amc_id(student.amc_id) and amc_copy_nr not in (None, "", "0"):
        student.amc_id = str(amc_copy_nr)
        student.save(update_fields=["amc_id"])
        logger.info(
            "Backfilled student AMC id student_pk=%s copy=%s amc_id=%s",
            student.pk,
            student.copie_no,
            student.amc_id,
        )


def find_student_for_amc_report(exam, report_row):
    assoc_primary_key = get_amc_option_by_key(exam, "liste_key")
    amc_copy_nr = report_row_amc_copy_nr(report_row)
    amc_copy_candidates = copy_number_candidates(amc_copy_nr)
    if amc_copy_candidates:
        student = (
            Student.objects
            .filter(exam=exam, amc_id__in=amc_copy_candidates)
            .first()
        )
        if student:
            return student

    associated_student = report_row.get("associated_student")
    if associated_student:
        student = find_student_for_association_value(exam, assoc_primary_key, associated_student)
        if student:
            update_student_amc_id_if_missing(student, amc_copy_nr)
            return student

    copy_candidates = []
    for value in (amc_copy_nr, report_row.get("copy")):
        if value is None or value == "":
            continue
        copy_candidates.extend(copy_number_candidates(value))

    student = (
        Student.objects
        .filter(exam=exam, copie_no__in=list(dict.fromkeys(copy_candidates)))
        .first()
    )
    if student:
        update_student_amc_id_if_missing(student, amc_copy_nr)
    return student


def add_grading_schemes_reports(exam_pk, single_file=False, progress_callback=None):
    exam = Exam.objects.get(pk=exam_pk)

    project_path = Path(get_amc_project_path(exam, False))
    amc_data_path = str(project_path / "data") + "/"
    annotated_pdfs_dir = project_path / "cr" / "corrections" / "pdf"
    report_type = 2 if single_file else 1
    report_rows = [
        row for row in get_student_report_data(amc_data_path)
        if int(row.get("type") or 0) == report_type
    ]
    logger.info(
        "AMC grading scheme report append started exam=%s single_file=%s report_type=%s report_rows=%s",
        exam_pk,
        single_file,
        report_type,
        len(report_rows),
    )
    if single_file:
        filename = next((row.get("file") for row in report_rows if row.get("file")), "annotated_papers.pdf")
        annotated_pdf_path = resolve_annotated_pdf_path(annotated_pdfs_dir, filename)
        if not annotated_pdf_path.exists():
            raise FileNotFoundError(f"Missing annotated PDF: {annotated_pdf_path}")

        if report_rows:
            student_reports = []
            for row in sorted(report_rows, key=lambda r: (int(r.get("student") or 0), int(r.get("copy") or 0))):
                student = find_student_for_amc_report(exam, row)
                if not student:
                    raise RuntimeError(f"No eXamc student found for AMC report row {row}.")
                student_reports.append((student, report_row_amc_copy_nr(row)))
        else:
            student_reports = [
                (student, student_amc_copy_nr(student))
                for student in Student.objects.filter(exam=exam).order_by("copie_no", "pk")
            ]

        total = len(student_reports)
        if progress_callback:
            progress_callback(
                done=0,
                total=total,
                message=f"Adding grading scheme reports: 0/{total} reports added",
            )

        pdf_parts = [annotated_pdf_path.read_bytes()]
        for index, (student, amc_copy_nr) in enumerate(student_reports, start=1):
            logger.info(
                "AMC grading scheme report generated exam=%s mode=single student_pk=%s student_copy=%s amc_copy=%s index=%s total=%s target=%s",
                exam_pk,
                student.pk,
                student.copie_no,
                amc_copy_nr,
                index,
                total,
                annotated_pdf_path,
            )
            pdf_parts.append(
                build_grading_report_pdf_bytes(
                    exam_pk,
                    student.id,
                    amc_copy_nr=amc_copy_nr,
                )
            )
            if progress_callback:
                progress_callback(
                    done=index,
                    total=total,
                    message=f"Adding grading scheme reports: {index}/{total} reports added",
                )
        annotated_pdf_path.write_bytes(concat_pdfs(*pdf_parts))
        logger.info(
            "AMC grading scheme report append completed exam=%s mode=single target=%s total=%s",
            exam_pk,
            annotated_pdf_path,
            total,
        )
        return

    if not report_rows:
        raise RuntimeError(f"No AMC annotated PDF report rows found for type {report_type}.")

    total = len(report_rows)
    if progress_callback:
        progress_callback(
            done=0,
            total=total,
            message=f"Adding grading scheme reports: 0/{total} files generated",
        )

    for index, row in enumerate(report_rows, start=1):
        student = find_student_for_amc_report(exam, row)
        if not student:
            raise RuntimeError(f"No eXamc student found for AMC report row {row}.")

        annotated_pdf_path = resolve_annotated_pdf_path(annotated_pdfs_dir, row.get("file"))
        if not annotated_pdf_path.exists():
            raise FileNotFoundError(f"Missing annotated PDF: {annotated_pdf_path}")

        annotated_pdf_bytes = annotated_pdf_path.read_bytes()
        grading_scheme_report_bytes = build_grading_report_pdf_bytes(
            exam_pk,
            student.id,
            amc_copy_nr=report_row_amc_copy_nr(row),
        )
        merged = concat_pdfs(annotated_pdf_bytes, grading_scheme_report_bytes)
        annotated_pdf_path.write_bytes(merged)
        logger.info(
            "AMC grading scheme report appended exam=%s student_pk=%s student_copy=%s amc_copy=%s index=%s total=%s target=%s",
            exam_pk,
            student.pk,
            student.copie_no,
            report_row_amc_copy_nr(row),
            index,
            total,
            annotated_pdf_path,
        )
        if progress_callback:
            progress_callback(
                done=index,
                total=total,
                message=f"Adding grading scheme reports: {index}/{total} files generated",
            )

    logger.info("AMC grading scheme report append completed exam=%s total=%s", exam_pk, total)

def concat_pdfs(*pdfs_bytes: bytes) -> bytes:
    writer = PdfWriter()

    for pdf in pdfs_bytes:
        reader = PdfReader(io.BytesIO(pdf))
        for page in reader.pages:
            writer.add_page(page)

    out = io.BytesIO()
    writer.write(out)
    out.seek(0)
    return out.getvalue()

def create_annotated_zip(exam):
    corrections_path = Path(get_amc_project_path(exam, False)) / "cr" / "corrections"
    zip_path = get_annotated_zip_path(exam)
    # Creating the ZIP file
    archived = shutil.make_archive(str(zip_path.with_suffix("")), 'zip', str(corrections_path / "pdf"))

    if zip_path.exists():
        return archived
    else:
        return False

def amc_generate_results(exam):
    project_path = get_amc_project_path(exam,False)
    results_csv_path = project_path+"/exports/"+exam.code+"_amc_raw.csv"
    students_list = get_amc_option_by_key(exam, 'listeetudiants').replace('%PROJET', project_path)

    command = [
        "auto-multiple-choice", "export",
        "--data", f"{project_path}/data/",
        "--module", "CSV",
        "--fich-noms", students_list,
        "--o", results_csv_path,
        "--sort", "l",
        "--useall", "1",
        "--option-out", "ticked=AB",
        "--option", "columns=ID,SCIPER,NAME,SECTION,EMAIL",
        "--option", "separateur=;",
    ]
    result = subprocess.run(command, capture_output=True, text=True)
    if result.stderr:
        return "ERR:" + result.stderr
    else:
        return result.stdout

def get_amc_results_file_path(exam):
    project_path = get_amc_project_path(exam, False)
    results_csv_path = project_path + "/exports/" + exam.code + "_amc_raw.csv"
    if os.path.exists(results_csv_path):
        return results_csv_path

    return None

def get_amc_manual_association_data(exam):
    project_path = get_amc_project_path(exam, False)
    amc_assoc_img_path = ""
    if project_path:
        amc_assoc_img_path = str(Path(project_path) / "cr") + "/"

    def _assoc_image_relpath(raw_image_path: str) -> str:
        """Convert AMC association image path/url to path relative to AMC_PROJECTS_ROOT."""
        path_value = str(raw_image_path or "").strip()
        if not path_value:
            return ""

        # Common case from SQL: "/amc_projects/<year>/<sem>/<exam>/cr/<file>"
        amc_url_prefix = str(settings.AMC_PROJECTS_URL).rstrip("/") + "/"
        if path_value.startswith(amc_url_prefix):
            return path_value[len(amc_url_prefix):]

        # If a full filesystem path is returned, relativize it against AMC root.
        amc_root = Path(settings.AMC_PROJECTS_ROOT).resolve()
        candidate = Path(path_value)
        try:
            candidate_resolved = candidate.resolve()
            return str(candidate_resolved.relative_to(amc_root))
        except Exception:
            pass

        # Fallback for mixed/legacy strings containing "/amc_projects/".
        marker = "/amc_projects/"
        if marker in path_value:
            return path_value.split(marker, 1)[1]

        return path_value.lstrip("/")

    def _resolve_existing_assoc_relpath(rel_path: str) -> str:
        """Best-effort fix when DB image path does not map to an existing file."""
        if not rel_path or not project_path:
            return rel_path

        amc_root = Path(settings.AMC_PROJECTS_ROOT).resolve()
        rel_candidate = Path(rel_path)
        file_candidate = (amc_root / rel_candidate).resolve()
        if file_candidate.exists():
            return rel_path

        cr_dir = Path(project_path).resolve() / "cr"
        if not cr_dir.exists():
            return rel_path

        # Try exact filename match anywhere under cr/
        file_name = rel_candidate.name
        if file_name:
            exact_name_matches = [p for p in cr_dir.rglob("*") if p.is_file() and p.name.lower() == file_name.lower()]
            if exact_name_matches:
                try:
                    return str(exact_name_matches[0].resolve().relative_to(amc_root))
                except Exception:
                    return rel_path

        # Fallback to stem match.
        stem = rel_candidate.stem
        if stem:
            exact_stem_matches = [p for p in cr_dir.rglob("*") if p.is_file() and p.stem.lower() == stem.lower()]
            if exact_stem_matches:
                try:
                    return str(exact_stem_matches[0].resolve().relative_to(amc_root))
                except Exception:
                    return rel_path

        return rel_path

    if project_path:
        amc_data_path = project_path+"/data/"
        data_assoc = select_associations(amc_data_path,amc_assoc_img_path)

        students_list = get_amc_option_by_key(exam, 'listeetudiants').replace('%PROJET', project_path)
        file = open(students_list, "r",encoding='utf-8')
        students_data = list(csv.reader(file, delimiter=","))

        # signing images
        for assoc in data_assoc:
            rel_path = _assoc_image_relpath(assoc.get("image_path"))
            rel_path = _resolve_existing_assoc_relpath(rel_path)
            signed_url = make_token_for(rel_path, str(settings.AMC_PROJECTS_ROOT))
            if "?token=" in signed_url:
                signed_url = f"{settings.SIGNED_FILES_URL}?token={signed_url.split('?token=', 1)[1]}"
            assoc["image_path"] = signed_url

        return {"data_assoc":json.dumps(data_assoc),"data_students":json.dumps(students_data)}

    return ''
def set_amc_manual_association(exam,copy_nr,student_id):
    project_path = get_amc_project_path(exam, False)
    result = ''
    if project_path:
        amc_data_path = project_path + "/data/"
        result = update_association(amc_data_path, copy_nr, student_id)
        sync_student_amc_ids_from_association(exam)

    return result

def get_amc_send_annotated_papers_data(exam):
    project_path = get_amc_project_path(exam, False)

    if project_path:
        amc_data_path = project_path + "/data/"
        data = select_students_report(amc_data_path)

        students_list_file = get_amc_option_by_key(exam, 'listeetudiants').replace('%PROJET', project_path)
        students_list = None
        with open(students_list_file, 'r') as f:
            dict_reader = csv.DictReader(f)
            students_list = list(dict_reader)

        students_data = []
        assoc_key = get_amc_option_by_key(exam, 'liste_key')
        for copy in data:
            for student in students_list:
                if student[assoc_key] == copy['copy']:
                    merged_dict = copy.copy()
                    for key, value in student.items():
                        if key != assoc_key:
                            merged_dict[key] = value
                    students_data.append(merged_dict)


        return students_data

    return ''

def amc_send_annotated_papers(exam,selected_students,email_subject,email_body,email_column):

    result = 'ok'
    project_path = get_amc_project_path(exam, False)
    amc_data_path = project_path+"/data/"
    result_list = []
    count_sent = 0
    count_error = 0
    for student in selected_students:
        student_send_result = student["copy"] + " - " + student["email"] + " : "
        try:
            validate_email(student['email'])
        except ValidationError as e:
            student_send_result += "Failed to send email: " + repr(e)
            logger.error(result)
            count_error += 1
            update_report_student(amc_data_path, student["id"], time.time(), 100, repr(e))
            result_list.append(student_send_result)
        else:
            # Create EmailMessage object
            email = EmailMessage(
                email_subject,  # Subject
                email_body,  # HTML content
                'noreply-cepro-exams@epfl.ch',  # From email address
                [student['email']]  # To email addresses
            )

            annotated_pdf_path = get_annotated_pdf_path(amc_data_path,student["id"])

            # Set content type to HTML
            email.content_subtype = "html"
            email.attach_file(project_path+"/cr/corrections/pdf/"+annotated_pdf_path)

            try:
                # Send email
                email.send()
                student_send_result += "email sent !"
                count_sent += 1
                update_report_student(amc_data_path, student["id"], time.time(), 1,'')
            except Exception as e:
                student_send_result += "Failed to send email: "+repr(e)
                logger.error(result)
                count_error += 1
                update_report_student(amc_data_path,student["id"],time.time(),100,repr(e))
                result_list.append(student_send_result)

    return [count_sent, count_error, result_list]


def wrap_canvas_text_lines(c, text, max_width, font_name="Helvetica", font_size=10):
    """Wrap text to fit a ReportLab canvas width and preserve explicit new lines."""
    if not text:
        return []

    c.setFont(font_name, font_size)
    wrapped_lines = []
    paragraphs = text.replace('\r\n', '\n').replace('\r', '\n').split('\n')

    for paragraph in paragraphs:
        words = paragraph.split()
        if not words:
            wrapped_lines.append("")
            continue

        current = words[0]
        for word in words[1:]:
            candidate = f"{current} {word}"
            if c.stringWidth(candidate, font_name, font_size) <= max_width:
                current = candidate
            else:
                wrapped_lines.append(current)
                current = word
        wrapped_lines.append(current)

    return wrapped_lines




def clean_report_text(value) -> str:
    """Return plain text suitable for ReportLab paragraphs."""
    if not value:
        return ""

    text = str(value)
    text = re.sub(r"(?i)<br\s*/?>", "\n", text)
    text = re.sub(r"(?i)</p\s*>", "\n", text)
    text = re.sub(r"(?i)</li\s*>", "\n", text)
    text = strip_tags(text)
    text = html.unescape(text)
    lines = [" ".join(line.split()) for line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n")]
    return "\n".join(line for line in lines if line).strip()


def report_paragraph(value, style):
    """Build a paragraph that preserves explicit line breaks."""
    text = clean_report_text(value)
    if not text:
        return Paragraph("&nbsp;", style)
    return Paragraph(html.escape(text).replace("\n", "<br/>"), style)


def build_long_table(rows, col_widths, repeat_rows=1):
    try:
        return LongTable(rows, colWidths=col_widths, repeatRows=repeat_rows, splitByRow=1, splitInRow=1)
    except TypeError:
        return LongTable(rows, colWidths=col_widths, repeatRows=repeat_rows, splitByRow=1)


def build_grading_report_pdf_bytes(exam_pk, student_pk, amc_copy_nr=None, review_copy_nr=None) -> bytes:
    """
    Generate grading report and return the content in bytes.
    """
    exam = Exam.objects.get(pk=exam_pk)
    amc_data_path = get_amc_project_path(exam, False)

    if not amc_data_path:
        return None

    amc_data_path += "/data/"
    student = Student.objects.get(pk=student_pk)
    review_copy_nr = str(review_copy_nr if review_copy_nr is not None else student.copie_no)
    amc_copy_nr = str(amc_copy_nr if amc_copy_nr is not None else student_amc_copy_nr(student))
    copy_candidates = list(dict.fromkeys(
        copy_number_candidates(review_copy_nr) + copy_number_candidates(amc_copy_nr)
    ))

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=2 * cm,
        rightMargin=2 * cm,
        topMargin=3.2 * cm,
        bottomMargin=2.2 * cm,
    )
    width, height = A4
    table_width = width - doc.leftMargin - doc.rightMargin

    styles = getSampleStyleSheet()
    question_style = ParagraphStyle(
        "GradingReportQuestion",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=12,
        leading=15,
        spaceBefore=8,
        spaceAfter=6,
    )
    body_style = ParagraphStyle(
        "GradingReportBody",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=8,
        leading=10,
        splitLongWords=1,
    )
    body_center_style = ParagraphStyle(
        "GradingReportBodyCenter",
        parent=body_style,
        alignment=1,
    )
    header_style = ParagraphStyle(
        "GradingReportHeader",
        parent=body_center_style,
        fontName="Helvetica-Bold",
    )
    total_label_style = ParagraphStyle(
        "GradingReportTotalLabel",
        parent=body_style,
        fontName="Helvetica-Bold",
    )
    total_center_style = ParagraphStyle(
        "GradingReportTotalCenter",
        parent=body_center_style,
        fontName="Helvetica-Bold",
    )
    note_title_style = ParagraphStyle(
        "GradingReportNoteTitle",
        parent=body_style,
        fontName="Helvetica-Bold",
        spaceBefore=6,
        spaceAfter=2,
    )
    note_style = ParagraphStyle(
        "GradingReportNote",
        parent=body_style,
        leftIndent=0.2 * cm,
        spaceAfter=8,
    )

    def draw_header_footer(canvas_obj, doc_obj):
        canvas_obj.saveState()
        canvas_obj.setFont("Helvetica-Bold", 18)
        canvas_obj.drawString(doc.leftMargin, height - 2 * cm, "Grading Report")
        canvas_obj.setLineWidth(1)
        canvas_obj.line(doc.leftMargin, height - 2.4 * cm, width - doc.rightMargin, height - 2.4 * cm)
        canvas_obj.setFont("Helvetica", 10)
        canvas_obj.drawCentredString(width / 2, 1.2 * cm, str(doc_obj.page))
        canvas_obj.restoreState()

    story = []

    pages_groups = PagesGroup.objects.filter(exam__pk=exam_pk, use_grading_scheme=True)
    for pages_group in pages_groups:
        pages_group_grading_schemes = PagesGroupGradingSchemeCheckedBox.objects.filter(
            pages_group=pages_group,
            copy_nr__in=copy_candidates,
        )

        if not pages_group_grading_schemes.exists():
            continue

        valid_checked_boxes = (
            pages_group_grading_schemes
            .filter(gradingSchemeCheckBox__isnull=False)
            .select_related("gradingSchemeCheckBox__questionGradingScheme")
        )
        first_checked_box = None
        for candidate in copy_candidates:
            first_checked_box = valid_checked_boxes.filter(copy_nr=candidate).first()
            if first_checked_box:
                break
        if not first_checked_box:
            logger.warning(
                "Skipping grading report section without valid checked boxes exam=%s student=%s pages_group=%s copy_nr=%s",
                exam_pk,
                student_pk,
                pages_group.pk,
                amc_copy_nr,
            )
            continue
        grading_copy_nr = first_checked_box.copy_nr

        grading_scheme_id = (
            first_checked_box
            .gradingSchemeCheckBox
            .questionGradingScheme
            .id
        )

        all_grading_scheme_checkboxes = QuestionGradingSchemeCheckBox.objects.filter(
            questionGradingScheme_id=grading_scheme_id,
        ).order_by("position", "pk")

        max_points = all_grading_scheme_checkboxes.aggregate(points__sum=Sum("points"))["points__sum"] or Decimal("0.00")
        grading_scheme_checkboxes = list(
            all_grading_scheme_checkboxes
            .exclude(name__in=("ZERO", "ADJ"))
            .order_by("position", "pk")
        )
        adjustment_checkbox = all_grading_scheme_checkboxes.filter(name="ADJ").first()
        if adjustment_checkbox:
            grading_scheme_checkboxes.append(adjustment_checkbox)

        table_rows = [[
            Paragraph("Title", header_style),
            Paragraph("Text", header_style),
            Paragraph("Points", header_style),
            Paragraph("Validated", header_style),
        ]]
        points = Decimal("0.00")

        for grading_scheme_checkbox in grading_scheme_checkboxes:
            pg_checked_box_item = PagesGroupGradingSchemeCheckedBox.objects.filter(
                pages_group=pages_group,
                gradingSchemeCheckBox_id=grading_scheme_checkbox.id,
                copy_nr=grading_copy_nr,
            ).first()
            pg_checked_box = pg_checked_box_item is not None

            add_row = not (
                grading_scheme_checkbox.name == "ZERO"
                or (
                    grading_scheme_checkbox.name == "ADJ"
                    and (not pg_checked_box_item or pg_checked_box_item.adjustment == 0)
                )
            )
            if not add_row:
                continue

            if pg_checked_box:
                if grading_scheme_checkbox.name == "ADJ":
                    row_points = pg_checked_box_item.adjustment
                    max_points += row_points
                else:
                    row_points = grading_scheme_checkbox.points
                points += row_points
            else:
                row_points = grading_scheme_checkbox.points

            title = "Adjustment" if grading_scheme_checkbox.name == "ADJ" else grading_scheme_checkbox.name
            table_rows.append([
                report_paragraph(title, body_style),
                report_paragraph(grading_scheme_checkbox.description, body_style),
                report_paragraph(row_points, body_center_style),
                report_paragraph("Yes" if pg_checked_box else "No", body_center_style),
            ])

        table_rows.append([
            Paragraph("Total", total_label_style),
            Paragraph("&nbsp;", total_label_style),
            report_paragraph(max_points, total_center_style),
            report_paragraph(points, total_center_style),
        ])

        question_num = get_question_number(amc_data_path, amc_copy_nr, pages_group.group_name)
        story.append(Paragraph(f"Question {question_num}:", question_style))

        col_widths = [
            table_width * 0.22,
            table_width * 0.50,
            table_width * 0.13,
            table_width * 0.15,
        ]
        table = build_long_table(table_rows, col_widths)
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("ALIGN", (2, 0), (3, -1), "CENTER"),
            ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 5),
            ("RIGHTPADDING", (0, 0), (-1, -1), 5),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        story.append(table)

        student_note_obj = PagesGroupStudentReportNote.objects.filter(
            pages_group=pages_group,
            copy_nr=grading_copy_nr,
        ).first()
        student_note = student_note_obj.content if student_note_obj else ""
        if clean_report_text(student_note):
            story.append(Paragraph("Comment:", note_title_style))
            story.append(report_paragraph(student_note, note_style))

        story.append(Spacer(1, 0.5 * cm))

    if not story:
        story.append(Paragraph("No grading scheme report data.", body_style))

    doc.build(story, onFirstPage=draw_header_footer, onLaterPages=draw_header_footer)
    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes

def draw_table(c, data, x, y, col_widths):
    """
    Dessine un tableau ReportLab à la position x,y (y = haut du tableau).
    Retourne la hauteur du tableau.
    """
    table = Table(data, colWidths=col_widths)

    table.setStyle(TableStyle([
        # header row style
        ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('ALIGN', (1, 0), (2, 0), 'CENTER'),   # Points + Validated centered in header

        # body alignment for numeric columns
        ('ALIGN', (1, 1), (2, -1), 'CENTER'),  # Points + Validated values centered

        # total row bold
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),

        # grid + padding
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))

    w, h = table.wrap(0, 0)
    table.drawOn(c, x, y - h)
    return h
