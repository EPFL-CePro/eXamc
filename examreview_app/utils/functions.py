# SCANS IMPORT functions
from django.conf import settings
from examreview_app.models import *
from django.core.files.storage import FileSystemStorage
import pyzbar.pyzbar as pyzbar
import numpy as np
import cv2
import os
import imghdr
import json
import shutil
import pathlib

from django.db.models import Q


# Detect QRCodes on scans, split copies in subfolders and detect nb pages
def split_scans_by_copy(exam):
    scans_dir = str(settings.SCANS_ROOT)+"/"+str(exam.year)+"/"+str(exam.semester)+"/"+exam.code

    print("* Start splitting by copy")

    copy_nr = 0;
    current_subdir = scans_dir
    page_nr = 0
    pages_by_copy = []
    for filename in sorted(os.listdir(scans_dir)):
        f = os.path.join(scans_dir, filename)
        # checking if it is a jpeg file
        if imghdr.what(f) == 'jpeg':
            # Read image
            im = cv2.imread(f)
            decodedObjects = pyzbar.decode(im)
            for obj in decodedObjects:
                if str(obj.type) == 'QRCODE' and 'first-page' in str(obj.data) :
                    if copy_nr > 0:
                        pages_by_copy.append([copy_nr,page_nr])

                    copy_nr += 1
                    copy_nr_dir = "copy_"+str(copy_nr).zfill(3)
                    subdir = os.path.join(scans_dir,copy_nr_dir)
                    os.mkdir(subdir)
                    current_subdir = subdir
                    page_nr = 0


            page_nr += 1
            os.rename(f,current_subdir+"/copy_"+str(copy_nr).zfill(4)+"_"+str(page_nr).zfill(2)+pathlib.Path(filename).suffix)
            print(copy_nr)
    pages_by_copy.append([copy_nr,page_nr])
    json_pages_by_copy = json.dumps(pages_by_copy)

    exam.pages_by_copy = json_pages_by_copy
    exam.save()

    return copy_nr

def import_scans(exam, path):
    print("* Start importing scans")
    scans_dir = str(settings.SCANS_ROOT)+"/"+str(exam.year)+"/"+str(exam.semester)+"/"+exam.code
    os.makedirs(scans_dir, exist_ok=True)
    delete_old_scans(exam)
    count=0
    for tmp_scan in os.listdir(path):
        print(tmp_scan)
        shutil.copy(path+"/"+tmp_scan,scans_dir+"/"+tmp_scan)
        count+=1
        # fs = FileSystemStorage(location=scans_dir) #defaults to   MEDIA_ROOT
        # scan = fs.save(tmp_scan.name, tmp_scan)

    print(str(count)+" scans imported")

    nb_copies = split_scans_by_copy(exam)

    return "Imported "+str(nb_copies)+" copies ("+count+" scans)"

def delete_old_scans(exam):
    scans_dir = str(settings.SCANS_ROOT)+"/"+str(exam.year)+"/"+str(exam.semester)+"/"+exam.code
    for filename in os.listdir(scans_dir):
        file_path = os.path.join(scans_dir, filename)
        try:
            if os.path.isfile(file_path) or os.path.islink(file_path):
                os.unlink(file_path)
            elif os.path.isdir(file_path):
                shutil.rmtree(file_path)
        except Exception as e:
            print('Failed to delete %s. Reason: %s' % (file_path, e))

def user_allowed(exam, user_id):
    exam_users = User.objects.filter(Q(exam=exam) | Q(exam__in=exam.common_exams.all()))
    user = User.objects.get(pk=user_id)
    print("coucou")
    if user in exam_users or user.is_superuser:
        return True
    else:
        return False

def get_scans_pathes_by_group(exam):

    scans_pathes_list = {}
    scans_dir = str(settings.SCANS_ROOT)+"/"+str(exam.year)+"/"+str(exam.semester)+"/"+exam.code
    scans_url = "../../scans/"+str(exam.year)+"/"+str(exam.semester)+"/"+exam.code

    for group in exam.examPagesGroup.all():


        scans_pathes = []

        for dir in sorted(os.listdir(scans_dir)):
            for filename in sorted(os.listdir(scans_dir+"/"+dir)):
                split_filename = filename.split('_')
                copy_no = int(split_filename[-2])
                page_no = int(split_filename[-1].split('.')[0])
                if page_no >= group.page_from and page_no <= group.page_to:
                    scans_path_dict = {}
                    scans_path_dict["copy_no"] = copy_no
                    scans_path_dict["page_no"] = page_no
                    scans_path_dict["path"] = scans_url+"/"+dir+"/"+filename
                    scans_pathes.append(scans_path_dict)

        scans_pathes_list[group.group_name.replace(" ","")] = scans_pathes
    return scans_pathes_list
