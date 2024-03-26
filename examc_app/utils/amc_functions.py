import os
import shutil
import sqlite3
import zipfile

import xmltodict
import subprocess
import xml.etree.ElementTree as xmlET
from datetime import datetime



from django.conf import settings

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
        con = sqlite3.connect(amc_data_path + "layout.sqlite")
        cur = con.cursor()

        select_count_layout_page = ("SELECT count(*) FROM layout_page")

        query = cur.execute(select_count_layout_page)

        nb_pages_detected = query.fetchall()[0][0]

        if nb_pages_detected > 0:
            info = "Processed "+str(nb_pages_detected)+" pages"

        cur.close()
        con.close()
    return info

def get_amc_option_by_key(exam,key):
    options_xml_path = get_amc_project_path(exam, False)+"/options.xml"
    option_value = ''
    # Open the file and read the contents
    with open(options_xml_path, 'r', encoding='utf-8') as file:
        options_xml = file.read()

        # Use xmltodict to parse and convert
        # the XML document
        options_dict = xmltodict.parse(options_xml)

        # search by key
        option_value = find_value_dict_by_key(options_dict,key)
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

def amc_update_documents(exam,nb_copies):
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
    # if result.stderr:
    #     return "ERR:"+result.stderr
    # else:
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

def amc_automatic_data_capture(exam,zip_file):
    project_path = get_amc_project_path(exam, False)
    tmp_dir_path = project_path+"/tmp"
    if not os.path.exists(tmp_dir_path):
        os.mkdir(tmp_dir_path)

    file_list_path = tmp_dir_path+"/list-file"
    tmp_file_list = open(file_list_path, "a")

    file_name = f"exam_{exam.pk}_amc_scans.zip"
    tmp_file_path = tmp_dir_path+"/"+file_name

    with open(tmp_file_path, 'wb') as temp_file:
        for chunk in zip_file.chunks():
            temp_file.write(chunk)

    tmp_extract_path = tmp_dir_path + "/tmp_extract"

    # extract zip file in tmp dir
    with zipfile.ZipFile(tmp_file_path, 'r') as zip_ref:
        print("start extraction")
        zip_ref.extractall(tmp_extract_path)

    i = 0
    for file in os.listdir(tmp_extract_path):
        if os.path.isdir(file):
            for file in os.listdir(file):
                i += 1
                tmp_file_list.write(tmp_extract_path+file+"\n")
        else:
            i += 1
            tmp_file_list.write(tmp_extract_path + "/" + file + "\n")

    tmp_file_list.close()

    # prepare scan images (see amc doc)
    result = subprocess.run(['auto-multiple-choice getimages '
                             '--list "' + file_list_path + '" '
                             '--copy-to "' + project_path + '/scans" ']
                            , shell=True
                            , capture_output=True
                            , text=True)
    if result.stderr:
        return "ERR:" + result.stderr
    else:

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

        # analyse scans
        result = subprocess.run(['auto-multiple-choice analyse '
                             '--data "'+project_path+'/data/" '
                             '--projet "'+project_path+'" '
                             '--liste-fichiers "'+file_list_path+'" ']
                            , shell=True
                            , capture_output=True
                            , text=True)
        

        if result.stderr:
            return "ERR:" + result.stderr
        else:
            return result.stdout


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

def get_amc_catalog_pdf_path(exam):
    file_name = get_amc_option_by_key(exam,'doc_catalog')
    file_path = get_amc_project_path(exam,False)+"/"+file_name
    return file_path

def get_amc_project_path(exam,even_if_not_exist):
    amc_project_path = str(settings.AMC_PROJECTS_ROOT)+"/"+str(exam.year)+"/"+str(exam.semester)+"/"+exam.code
    if os.path.isdir(amc_project_path):
        return amc_project_path
    elif even_if_not_exist:
        return amc_project_path
    else:
        return None

def get_amc_project_url(exam):
    amc_project_url = str(settings.AMC_PROJECTS_URL)+"/"+str(exam.year)+"/"+str(exam.semester)+"/"+exam.code
    return amc_project_url

def get_amc_data_capture_manual_data(exam):
    amc_data_path = get_amc_project_path(exam, False)

    if amc_data_path:
        amc_data_path += "/data/"
        amc_data_url = get_amc_project_url(exam)
        con = sqlite3.connect(amc_data_path + "capture.sqlite")
        cur = con.cursor()

        # Attach scoring db
        cur.execute("ATTACH DATABASE '" + amc_data_path + "scoring.sqlite' as scoring")

        select_amc_pages_str = ("SELECT "
                                "   student as copy,"
                                "   page as page, "
                                "   mse as mse, "
                                "   REPLACE(src,'%PROJET','" + amc_data_url + "') as source, "
                                                                              "   (SELECT ROUND(10*(0.007 - MIN(ABS(1.0 * cz.black / cz.total - 0.007))) / 0.007,2) FROM capture_zone cz WHERE cz.student = cp.student AND cz.page = cp.page) as sensitivity "
                                                                              "FROM capture_page cp "
                                                                              "ORDER BY copy, page")

        query = cur.execute(select_amc_pages_str)

        colname_pages = [d[0] for d in query.description]
        data_pages = [dict(zip(colname_pages, r)) for r in query.fetchall()]

        for data in data_pages:
            query = cur.execute("SELECT DISTINCT(id_a), "
                                "sc.why as why "
                                "FROM capture_zone cz "
                                "INNER JOIN scoring.scoring_score sc ON sc.student = " + str(
                data['copy']) + " AND sc.question = cz.id_a "
                                "WHERE type = 4 "
                                "AND cz.student = " + str(data['copy']) +
                                " AND cz.page = " + str(data['page']))
            colname_questions_id = [d[0] for d in query.description]
            data_questions_id = [dict(zip(colname_questions_id, r)) for r in query.fetchall()]
            questions_ids = ''
            for qid in data_questions_id:
                questions_ids += '%' + str(qid['id_a'])
                if qid['why'] == 'E':
                    questions_ids += '|INV|'
                elif qid['why'] == 'V':
                    questions_ids += '|EMP|'

            data['questions_ids'] = questions_ids + '%'

        cur.close()
        cur.connection.close()

        con = sqlite3.connect(amc_data_path + "layout.sqlite")
        cur = con.cursor()
        select_amc_questions_str = ("SELECT * FROM layout_question")

        query = cur.execute(select_amc_questions_str)

        colname_questions = [d[0] for d in query.description]
        data_questions = [dict(zip(colname_questions, r)) for r in query.fetchall()]

        cur.close()
        cur.connection.close()

        return [data_pages, data_questions]

def get_amc_marks_positions_data(exam,copy,page):
    amc_data_path = get_amc_project_path(exam, False)

    if amc_data_path:
        amc_data_path += "/data/"
        con = sqlite3.connect(amc_data_path + "capture.sqlite")
        cur = con.cursor()

        # Attach scoring db
        cur.execute("ATTACH DATABASE '" + amc_data_path + "scoring.sqlite' as scoring")

        select_mark_position_str = ("SELECT cp.zoneid, "
                                    "cp.corner, "
                                    "cp.x, "
                                    "cp.y, "
                                    "cz.manual,"
                                    "cz.black, "
                                    "sc.why "
                                    "FROM capture_position cp "
                                    "INNER JOIN capture_zone cz ON cz.zoneid = cp.zoneid "
                                    "LEFT OUTER JOIN scoring.scoring_score sc ON sc.student = " + str(
            copy) + " AND sc.question = cz.id_a "
                    "WHERE cp.zoneid in "
                    "   (SELECT cz2.zoneid from capture_zone cz2 WHERE cz2.student = " + str(
            copy) + " AND cz2.page = " + str(page) + ") "
                                                     "AND cp.type = 1 "
                                                     "AND cz.type = 4 "
                                                     "ORDER BY cp.zoneid, cp.corner ")

        query = cur.execute(select_mark_position_str)

        colname_positions = [d[0] for d in query.description]
        data_positions = [dict(zip(colname_positions, r)) for r in query.fetchall()]

        cur.close()
        cur.connection.close()

        return data_positions

def update_amc_mark_zone_data(exam,zoneid):
    amc_data_path = get_amc_project_path(exam, False)

    if amc_data_path:
        amc_data_path += "/data/"
        con = sqlite3.connect(amc_data_path + "capture.sqlite")
        cur = con.cursor()

        select_mark_zone_str = ("SELECT manual FROM capture_zone WHERE zoneid = " + str(zoneid))

        query = cur.execute(select_mark_zone_str)

        colname_zones = [d[0] for d in query.description]
        data_zones = [dict(zip(colname_zones, r)) for r in query.fetchall()]

        print(data_zones)

        manual = data_zones[0]['manual']
        if manual == -1.0 or manual == 1.0:
            manual = "0.0"
        else:
            manual = "1.0"

        update_mark_zone_str = ("UPDATE capture_zone SET manual = " + manual + " WHERE zoneid = " + str(zoneid))

        cur.execute(update_mark_zone_str)
        con.commit()

        cur.close()
        con.close()

def create_amc_project_dir_from_zip(exam,zip_file):
    file_name = f"exam_{exam.pk}_amc_project.zip"
    temp_file_path = os.path.join(settings.AUTOUPLOAD_ROOT, file_name)

    os.makedirs(os.path.dirname(temp_file_path), exist_ok=True)

    with open(temp_file_path, 'wb') as temp_file:
        for chunk in zip_file.chunks():
            temp_file.write(chunk)

    zip_path = str(settings.AUTOUPLOAD_ROOT) + "/" + str(exam.year) + "_" + str(exam.semester) + "_" + exam.code
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
    shutil.move(tmp_extract_path, amc_project_path)

    return 'AMC project folder uploaded !'

def get_automatic_data_capture_summary(exam):

    amc_data_path = get_amc_project_path(exam, False)

    if amc_data_path:
        amc_data_path += "/data/"
        con = sqlite3.connect(amc_data_path + "capture.sqlite")
        cur = con.cursor()

        # Attach scoring db
        cur.execute("ATTACH DATABASE '" + amc_data_path + "layout.sqlite' as layout")

        select_nb_copies_str = ("SELECT COUNT(*) "
                                    "FROM (SELECT student,copy "
                                    "   FROM capture_page "
                                    "   WHERE timestamp_auto>0 OR timestamp_manual>0)"
                                    " GROUP BY student, copy")

        query = cur.execute(select_nb_copies_str)

        nb_copies = len(query.fetchall())
        select_missing_pages_str = ("SELECT enter.student AS student,enter.page AS page ,capture_page.copy AS copy "
                                    "FROM (SELECT student,page "
                                    "       FROM layout_box "
                                    "       WHERE role=1 "
                                    "       UNION "
                                    "       SELECT student,page "
                                    "       FROM layout_namefield) AS enter, "
                                    "       capture_page "
                                    "ON enter.student=capture_page.student "
                                    "EXCEPT SELECT student,page,copy FROM capture_page "
                                    "ORDER BY student,copy,page")

        query = cur.execute(select_missing_pages_str)

        colname_missing_pages = [d[0] for d in query.description]
        data_missing_pages = [dict(zip(colname_missing_pages, r)) for r in query.fetchall()]

        cur.close()
        cur.connection.close()

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

        incomplete_copy = {"copy_no": prev_stud, "missing_pages": missing_pages}
        incomplete_copies.append(incomplete_copy)




    return [nb_copies, incomplete_copies]