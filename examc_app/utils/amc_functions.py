import os
import xmltodict
import subprocess
import xml.etree.ElementTree as xmlET
from datetime import datetime



from django.conf import settings

def get_amc_update_document_info(exam):
    info = ''
    exam_sujet_filename = get_amc_option_by_key(exam,'doc_question')
    exam_sujet_filepath = str(settings.AMC_PROJECTS_ROOT)+"/2024/1/CS-119h_final/"+exam_sujet_filename
    if os.path.isfile(exam_sujet_filepath):
        last_modified_ts = os.path.getmtime(exam_sujet_filepath)
        datetime_str = datetime.fromtimestamp(last_modified_ts).strftime('%d.%m.%Y %H:%M:%S')
        info = "Working documents last update: "
        info += datetime_str
    return info
def get_amc_option_by_key(exam,key):
    options_xml_path = str(settings.AMC_PROJECTS_ROOT)+"/2024/1/CS-119h_final/options.xml"
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
            path_str = (path+file).replace('/','//')
            file_list.append([os.path.basename(file),path_str])

    return file_list

def amc_update_documents(exam,nb_copies):
    amc_update_options_xml_by_key(exam,'nombre_copies',nb_copies)
    exam_file = get_amc_option_by_key(exam,'doc_question')
    correction_file = get_amc_option_by_key(exam,'doc_solution')
    result = subprocess.run(['auto-multiple-choice prepare '
                             '--mode s '
                             '--with pdflatex '
                             '--filter latex '
                             '--prefix '
                             +get_amc_project_path(exam,False)+'/ '
                             +get_amc_project_path(exam,False)+'/exam.tex '
                             '--data '+get_amc_project_path(exam,False)+'/data/ '
                             '--out-sujet '+exam_file+' '
                             '--out-corrige '+correction_file+' ']
                            ,shell=True
                            , capture_output=True
                            , text=True)
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
    xml.write(get_amc_project_path(exam,False)+"options.xml")

def get_amc_exam_pdf_path(exam):
    file_name = get_amc_option_by_key(exam,'doc_question')
    file_path = get_amc_project_path(exam,False)+file_name
    return file_path

def get_amc_catalog_pdf_path(exam):
    file_name = get_amc_option_by_key(exam,'doc_solution')
    file_path = str(settings.AMC_PROJECTS_ROOT) + '/2024/1/CS-119h_final/'+file_name
    return file_path

def get_amc_project_path(exam,even_if_not_exist):
    amc_project_path = str(settings.AMC_PROJECTS_ROOT)+"/"+str(exam.year)+"/"+str(exam.semester)+"/"+exam.code+"/"
    if os.path.isdir(amc_project_path):
        return amc_project_path
    elif even_if_not_exist:
        return amc_project_path
    else:
        return None

def get_amc_project_url(exam):
    amc_project_url = str(settings.AMC_PROJECTS_URL)+"/"+str(exam.year)+"/"+str(exam.semester)+"/"+exam.code+"/"
    return amc_project_url