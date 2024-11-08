import base64
import csv
import json
import logging
import os
import shutil
import subprocess
import time
import xml.etree.ElementTree as xmlET
import zipfile
from datetime import datetime
from pathlib import Path

import chardet
import img2pdf
import pandas as pd
import xmltodict
from PIL import Image
from PyPDF2 import PdfReader, PdfWriter
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.mail import EmailMessage
from django.core.validators import validate_email
from django.template.loader import get_template
from setuptools import glob

from examc_app.utils.amc_db_queries import *

# Get an instance of a logger
logger = logging.getLogger(__name__)

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

    return key_value

def get_project_dir_info(exam):

    project_dir = get_amc_project_path(exam,False)

    data = path_to_dict(project_dir,[])
    project_dir_dict = data[0]
    project_files_dict_list = data[1]


    return [project_dir_dict,project_files_dict_list]

def path_to_dict(path,dir_files_dict_list):
    text = os.path.basename(path)
    dir_node=None
    if path and os.path.isdir(path):
        dir_node = {'text':text,'href':'#pills-'+text,'nodes':[]}
        new_dir_files_node = {'folder':text,'files':latex_files_to_list(path)}
        dir_files_dict_list.append(new_dir_files_node)
        for dir in sorted(os.listdir(path), key = lambda x:x.upper()):
            data = path_to_dict(os.path.join(path,dir),dir_files_dict_list)
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

def latex_files_to_list(path):
    extensions = ('.tex')
    file_list = []
    for file in sorted(os.listdir(path),key = lambda x:x.upper()):
        if os.path.isfile(os.path.join(path,file)) and file.endswith(extensions):
            path_str = path+"/"+file#(path+file).replace('/','//')
            file_list.append([os.path.basename(file),path_str])

    return file_list

##testing
def process(request):
    # If you're getting IP from a form, ensure this value is passed
    ip = request.POST.get('ip', 'www.google.ch')  # Default IP to google.ch

    # Load the template that will be used for each line of the subprocess output
    template = get_template("subprocess.html")

    # Using subprocess to execute the ping command and stream the output
    with subprocess.Popen([f'ping -c5 {ip}'], shell=True, stdout=subprocess.PIPE, bufsize=1,
                          universal_newlines=True) as p:
        # Iterate over each line in the stdout of the subprocess
        for line in p.stdout:
            # Yield rendered template with each line
            yield line.strip()  # Strip to remove extra newlines

    # If the subprocess has a non-zero exit code, raise an error
    if p.returncode != 0:
        raise subprocess.CalledProcessError(p.returncode, p.args)

def amc_update_documents_subprocess(exam,nb_copies,scoring_only,preview=False):
    amc_project_path = get_amc_project_path(exam, False)
    if preview:
        os.rename(amc_project_path + "/students.csv", amc_project_path + "/students.bck")
        os.rename(amc_project_path + "/sample.csv", amc_project_path + "/students.csv")

    if scoring_only:
        command = ['auto-multiple-choice prepare '
                     '--mode b '
                     '--data "' + amc_project_path + '/data/" '
                                                     '--with pdflatex '
                                                     '--filter latex '
                                                     '--prefix "'
                     + amc_project_path + '/" "'
                     + amc_project_path + '/exam.tex" ']
    else:
        amc_update_options_xml_by_key(exam, 'nombre_copies', nb_copies)
        exam_file = get_amc_option_by_key(exam, 'doc_question')
        correction_file = get_amc_option_by_key(exam, 'doc_catalog')
        doc_setting = get_amc_option_by_key(exam, 'doc_setting')
        command = ['auto-multiple-choice prepare '
                                 '--mode s '
                                 '--with pdflatex '
                                 '--filter latex '
                                 '--prefix "'
                                 +get_amc_project_path(exam,False)+'/" "'
                                 +get_amc_project_path(exam,False)+'/exam.tex" '
                                 '--data "'+get_amc_project_path(exam,False)+'/data/" '
                                 '--out-sujet "'+exam_file+'" '
                                 '--out-catalog "'+correction_file+'" '
                                 '--out-calage "'+doc_setting+'" ']

    subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, bufsize=1, universal_newlines=True)



def amc_update_documents(exam,nb_copies,scoring_only,preview=False):

    amc_project_path = get_amc_project_path(exam,False)
    if preview:
        os.rename(amc_project_path+"/students.csv",amc_project_path+"/students.bck")
        os.rename(amc_project_path+"/sample.csv",amc_project_path+"/students.csv")

    if scoring_only:
        result = subprocess.run(['auto-multiple-choice prepare '
                                 '--mode b '
                                 '--data "' + amc_project_path+ '/data/" '
                                 '--with pdflatex '
                                 '--filter latex '
                                 '--prefix "'
                                 +amc_project_path+'/" "'
                                 +amc_project_path+'/exam.tex" ']
                                , shell=True
                                , capture_output=True
                                , text=True)
    else:
        amc_update_options_xml_by_key(exam,'nombre_copies',nb_copies)
        exam_file = get_amc_option_by_key(exam,'doc_question')
        correction_file = get_amc_option_by_key(exam,'doc_catalog')
        doc_setting = get_amc_option_by_key(exam,'doc_setting')
        result = subprocess.run(['auto-multiple-choice prepare '
                                 '--mode s '
                                 '--with pdflatex '
                                 '--filter latex '
                                 '--prefix "'
                                 +get_amc_project_path(exam,False)+'/" "'
                                 +get_amc_project_path(exam,False)+'/exam.tex" '
                                 '--data "'+get_amc_project_path(exam,False)+'/data/" '
                                 '--out-sujet "'+exam_file+'" '
                                 '--out-catalog "'+correction_file+'" '
                                 '--out-calage "'+doc_setting+'" ']
                                ,shell=True
                                , capture_output=True
                                , text=True)

    if preview:
        os.rename(amc_project_path+"/students.csv",amc_project_path+"/sample.csv")
        os.rename(amc_project_path+"/students.bck",amc_project_path+"/students.csv")

    return result.stdout


def amc_layout_detection(exam):
    project_path = get_amc_project_path(exam,False)
    doc_setting = get_amc_option_by_key(exam,'doc_setting')
    result = subprocess.run(['auto-multiple-choice meptex '
                             '--src "'+project_path+'/'+doc_setting+'" '
                             '--data "'+project_path+'/data/"']
                            ,shell=True
                            , capture_output=True
                            , text=True)
    if result.stderr:
        return "ERR:"+result.stderr
    else:
        return result.stdout

def amc_automatic_datacapture_subprocess(request,exam,file_path,from_review,file_list_path=None):
    project_path = get_amc_project_path(exam, False)
    tmp_dir_path = None

    if not from_review:
        tmp_dir_path = project_path + "/tmp"
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
            zip_ref.extractall(tmp_extract_path)

            file_list_path = tmp_dir_path + "/list-file"
            tmp_file_list = open(file_list_path, "a+")

            files = glob.glob(tmp_extract_path + '/**/*.*', recursive=True)
            for file in files:
                tmp_file_list.write(file + "\n")

            tmp_file_list.close()

    # prepare scan images (see amc doc)
    command = ['auto-multiple-choice getimages '
                             '--list "' + file_list_path + '" ']
    if not from_review:
        command[0] += ' --copy-to "' + project_path + '/scans" '

    yield "Getting images ...\n"
    subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, bufsize=1,universal_newlines=True)

    os.rename(file_list_path, file_list_path + ".txt")
    file_list_path += ".txt"

    box_prop = get_amc_option_by_key(exam, "box_size_proportion")

    # analyse scans
    command = ['auto-multiple-choice analyse '
                             '--prop ' + box_prop + ' '
                             '--data "' + project_path + '/data/" '
                            '--projet "' + project_path + '" '
                            '--liste-fichiers "' + file_list_path + '" '
                            '--try-three ']

    yield "Automatic data capture ...\n"
    errors = ''
    with subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, bufsize=1,universal_newlines=True) as process:
        for line in process.stdout:
            print(line.strip())
            if "ERR:" in line:
                errors += line
            yield line

        if  process.returncode and process.returncode != 0:
            raise subprocess.CalledProcessError(process.returncode, process.args)

    # check consistency between AMC page recognition and review pages
    yield "Checking data consistency ...\n"
    check_pages_recognition_consistency(exam)

    if tmp_dir_path:
        shutil.rmtree(tmp_dir_path)
    if file_list_path:
        os.remove(file_list_path)
    if errors:
        yield "\n\n**************************\nERRORS: \n-------\n\n"+errors+"\n**************************\n\n"

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
            zip_ref.extractall(tmp_extract_path)

            file_list_path = tmp_dir_path+"/list-file"
            tmp_file_list = open(file_list_path, "a+")

            files = glob.glob(tmp_extract_path+'/**/*.*', recursive=True)
            for file in files:
                tmp_file_list.write(file + "\n")

            tmp_file_list.close()
    print('amc getimages')

    # prepare scan images (see amc doc)
    command = ['auto-multiple-choice getimages '
               '--list "' + file_list_path + '" ']
    if not from_review:
        command[0] += ' --copy-to "' + project_path + '/scans" '

    result = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, bufsize=1, universal_newlines=True)
    with subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, bufsize=1,universal_newlines=True) as process:
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
    command = ['auto-multiple-choice analyse '
               '--prop ' + box_prop + ' '
                '--data "' + project_path + '/data/" '
                '--projet "' + project_path + '" '
                '--liste-fichiers "' + file_list_path + '" '
                '--try-three ']
    with subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, bufsize=1, universal_newlines=True) as process:
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

        if data_pages and '%HOME' in data_pages[0]['source']:
            app_home_path = str(settings.BASE_DIR).replace(str(Path.home()),'%HOME')
            for data in data_pages:
                data['source'] = data['source'].replace(app_home_path,'')

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

def create_amc_project_dir_from_zip(exam,zip_file):
    file_name = f"exam_{exam.pk}_amc_project.zip"
    temp_file_path = os.path.join(settings.AUTOUPLOAD_ROOT, file_name)

    os.makedirs(os.path.dirname(temp_file_path), exist_ok=True)

    with open(temp_file_path, 'wb') as temp_file:
        for chunk in zip_file.chunks():
            temp_file.write(chunk)

    zip_path = str(settings.AUTOUPLOAD_ROOT) + "/" + str(exam.year.code) + "_" + str(exam.semester.code) + "_" + exam.code
    tmp_extract_path = zip_path + "/tmp_extract"

    # extract zip file in tmp dir
    with zipfile.ZipFile(temp_file_path, 'r') as zip_ref:
        print("start extraction")
        zip_ref.extractall(tmp_extract_path)

    if not os.path.isfile(tmp_extract_path + "/options.xml"):
        dirs = [entry for entry in os.listdir(tmp_extract_path) if os.path.isdir(os.path.join(tmp_extract_path, entry))]
        tmp_extract_path += "/" + dirs[0]
        if not os.path.isfile(tmp_extract_path + "/options.xml"):
            return 'The zip file does not contains options.xml file in the two first level of folders !'

    # move to destination amc_projects
    amc_project_path = get_amc_project_path(exam, True)
    # Remove destination folder if it exists
    if os.path.exists(amc_project_path):
        shutil.rmtree(amc_project_path)
    shutil.move(tmp_extract_path, amc_project_path)

    return 'AMC project folder uploaded !'

def get_automatic_data_capture_summary(exam):

    amc_data_path = get_amc_project_path(exam, False)
    amc_data_url = get_amc_project_url(exam)

    if amc_data_path:
        amc_data_path += "/data/"

        nb_copies = select_nb_copies(amc_data_path)

        data_missing_pages = []
        data_unrecognized_pages = []

        if nb_copies > 0:
            data_missing_pages = select_missing_pages(amc_data_path)
            data_unrecognized_pages = select_unrecognized_pages(amc_data_path,amc_data_url)

        if data_unrecognized_pages and '%HOME' in data_unrecognized_pages[0]['filepath']:
            app_home_path = str(settings.BASE_DIR).replace(str(Path.home()),'%HOME')
            for data in data_unrecognized_pages:
                data['source'] = data['filepath'].replace(app_home_path,'')

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

    return [nb_copies, incomplete_copies,data_unrecognized_pages,data_overwritten_pages]

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

def add_unrecognized_page_to_project(exam,copy,question,extra,img_filename):
    amc_data_path = get_amc_project_path(exam, False)
    if amc_data_path:

        if extra:

            page = select_copy_question_page(amc_data_path+'/data/', copy, question)
            copy_extra_folder_path = amc_data_path + "/scans/extra/" + copy.zfill(4)
            #create extra folder for copy if not exist
            Path(copy_extra_folder_path).mkdir(parents=True, exist_ok=True)

            #list files and get last extraNumber
            last_exNum = 0

            for f in os.listdir(copy_extra_folder_path):
                curr_page = int(f.split("/")[-1].split(".")[0].split("x")[0].split("_")[-1])
                curr_exNum = int(f.split("/")[-1].split(".")[0].split("x")[1])
                if curr_page == page and curr_exNum > last_exNum:
                    last_exNum = curr_exNum

            new_exNum = str(last_exNum + 1).zfill(2)
            #filename = "copy_"+str(copy).zfill(4)+"_"+str(page).zfill(2)+"x"+new_exNum+".jpg"

            #move to extra folder
            shutil.move(str(settings.BASE_DIR)+img_filename, copy_extra_folder_path+'/'+img_filename.split('/')[-1])

            #remove as unrecognized page
            delete_unrecognized_page(amc_data_path+'/data/',img_filename)

def get_students_csv_headers(exam):
    amc_data_path = get_amc_project_path(exam, False)
    if amc_data_path:

        students_file = get_amc_option_by_key(exam,"listeetudiants").replace("%PROJET",amc_data_path)

        with open(students_file) as csv_file:

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
    yield "Start marking ...\n"

    command = ['auto-multiple-choice note '
                             '--data "' + project_path + '/data/" '
                             '--seuil ' + threshold + ' '
                             '--seuil-up '  + threshold_up + ' '
                             '--grain ' + grain + ' '
                             '--arrondi ' + round_grade + ' '
                             '--notemin ' + notemin + ' '
                             '--notemax ' + notemax + ' '
                             '--plafond ' + plafond + ' ']
    errors = ''
    with subprocess.Popen(command,shell=True,stdout=subprocess.PIPE, bufsize=1,universal_newlines=True) as process:
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

                if new_copy and key not in ['question','score','max_question']:
                    q_scoring_details_copy[key] = value
                    if key == 'mark':
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
    result = subprocess.run(['auto-multiple-choice association-auto '
                                  '--data "' + project_path + '/data/" '
                                  '--pre-association '
                                  '--liste "' + students_list + '" '
                                  '--liste-key ' + assoc_primary_key + ' ']
                            , shell=True
                            , capture_output=True
                            , text=True)
    if result.stderr:
        return "ERR:" + result.stderr
    else:
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

def amc_annotate(exam,single_file):
    project_path = get_amc_project_path(exam, False)
    assoc_primary_key = get_amc_option_by_key(exam,'liste_key')
    students_list = get_amc_option_by_key(exam, 'listeetudiants').replace('%PROJET',project_path)
    filename_model = get_amc_option_by_key(exam,'modele_regroupement')
    verdict = get_amc_option_by_key(exam,'verdict').replace('\n','\r\n')
    verdict_q = get_amc_option_by_key(exam,'verdict_q').replace('"','\\"')
    verdict_qc = get_amc_option_by_key(exam,'verdict_qc').replace('"','\\"')
    symbols = get_annotation_symbols(exam)
    annote_position = get_amc_option_by_key(exam,'annote_position')
    single_file_option = ''
    if single_file:
        single_file_option = '--single-output'

    result = subprocess.run(['auto-multiple-choice annotate '
                                  '--project "' + project_path + '" '
                                  '--names-file "' + students_list + '" '
                                  '--association-key "' + assoc_primary_key + '" '
                                  '--filename-model "' + filename_model + '" '
                                  ''+single_file_option + ' '
                                  '--symbols "' + symbols + '" '
                                  '--verdict "' + verdict + '" '
                                  '--verdict-question "' + verdict_q + '" '
                                  '--verdict-question-cancelled "' + verdict_qc + '" '
                                  '--position "'+ annote_position + '" '
                                  '--compose 0']
                            , shell=True
                            , capture_output=True
                            , text=True)
    if result.stderr:
        return "ERR:" + result.stderr
    else:

        student_report_data = get_student_report_data(project_path+"/data/")
        for st_rep in student_report_data:
            add_extra_to_annotated_pdf(st_rep['student'], st_rep['file'], project_path)

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

def create_annotated_zip(exam):
    corrections_path = get_amc_project_path(exam,False)+'/cr/corrections/'
    zip_filename = "annotated_pdfs_"+exam.code+"_"+exam.year.code+"_"+str(exam.semester.code)
    # Creating the ZIP file
    archived = shutil.make_archive(corrections_path+zip_filename, 'zip', corrections_path+'pdf')

    if os.path.exists(corrections_path+zip_filename+".zip"):
        return archived
    else:
        return False

def amc_generate_results(exam):
    project_path = get_amc_project_path(exam,False)
    results_csv_path = project_path+"/exports/"+exam.code+"_amc_raw.csv"
    students_list = get_amc_option_by_key(exam, 'listeetudiants').replace('%PROJET', project_path)

    result = subprocess.run(['auto-multiple-choice export '
                                '--data "' + project_path + '/data/" '
                                '--module CSV '
                                '--fich-noms "' + students_list + '" '
                                '--o "' + results_csv_path + '" '
                                '--sort l '
                                '--useall 1 '
                                '--option-out ticked=AB '
                                '--option columns=ID,SCIPER,NAME,SECTION,EMAIL '
                                '--option separateur=";" ']
                                , shell=True
                                , capture_output=True
                                , text=True)
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
    amc_assoc_img_path = get_amc_project_url(exam) + "/cr/"

    if project_path:
        amc_data_path = project_path+"/data/"
        data_assoc = select_associations(amc_data_path,amc_assoc_img_path)

        students_list = get_amc_option_by_key(exam, 'listeetudiants').replace('%PROJET', project_path)
        file = open(students_list, "r")
        students_data = list(csv.reader(file, delimiter=","))

        return {"data_assoc":json.dumps(data_assoc),"data_students":json.dumps(students_data)}

    return ''
def set_amc_manual_association(exam,copy_nr,student_id):
    project_path = get_amc_project_path(exam, False)
    result = ''
    if project_path:
        amc_data_path = project_path + "/data/"
        result = update_association(amc_data_path, copy_nr, student_id)

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
