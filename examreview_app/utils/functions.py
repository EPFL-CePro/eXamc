# SCANS IMPORT functions
from django.conf import settings
from examreview_app.models import *
from django.core.files.storage import FileSystemStorage
import pyzbar.pyzbar as pyzbar
from PIL import Image
import numpy as np
import cv2
import os
import imghdr
import json
import shutil
import pathlib

from django.db.models import Q


# Detect QRCodes on scans, split copies in subfolders and detect nb pages
def split_scans_by_copy(exam,tmp_extract_path):

    #extra_letters = ['a','b','c','d','e','f','g','h','i','j','k','l','m','n','o','p','q','r','t','u','v','w','x','y','z']

    scans_dir = str(settings.SCANS_ROOT)+"/"+str(exam.year)+"/"+str(exam.semester)+"/"+exam.code

    print("* Start splitting by copy")

    copy_nr = 0;
    page_nr = 0
    pages_by_copy = []
    extra_i = 0
    pages_count = 0
    last_copy_nr = 0
    last_page_nr = 0
    for filename in sorted(os.listdir(tmp_extract_path)):
        f = os.path.join(tmp_extract_path, filename)
        # checking if it is a jpeg file
        if imghdr.what(f) == 'jpeg':
            # Read image
            im = cv2.imread(f)
            decodedObjects = pyzbar.decode(im)
            if len(decodedObjects)>0:
              for obj in decodedObjects:
                  if str(obj.type) == 'QRCODE' and 'CePROExamsQRC' in str(obj.data) :
                    data = obj.data.decode("utf-8").split(',')
                    copy_nr = data[1]
                    page_nr = data[2]
            else:
              extra_i+=1

            #print("copy "+str(copy_nr)+" / page "+str(page_nr))

            copy_nr_dir = "copy_"+str(copy_nr).zfill(3)
            subdir = os.path.join(scans_dir,copy_nr_dir)
            if not os.path.exists(subdir):
              os.mkdir(subdir)

            page_nr_w_extra = page_nr
            page_nr_w_extra = page_nr_w_extra.zfill(2)
            if extra_i > 0:
              page_nr_w_extra+="x"+str(extra_i)

            os.rename(f,subdir+"/copy_"+str(copy_nr).zfill(4)+"_"+str(page_nr_w_extra)+pathlib.Path(filename).suffix)

            pages_count+=1
            if last_copy_nr != 0 and last_copy_nr != copy_nr:
              pages_by_copy.append([last_copy_nr,pages_count])
              pages_count=0

            if last_page_nr != page_nr:
              extra_i = 0

            last_copy_nr = copy_nr

    pages_by_copy.append([last_copy_nr,pages_count])
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
        count+=1

    print(str(count)+" scans imported")

    nb_copies = split_scans_by_copy(exam, path)

    return "Imported "+str(nb_copies)+" copies ("+str(count)+" scans)"

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

def get_scans_pathes_by_group(examPagesGroup):

    scans_dir = str(settings.SCANS_ROOT)+"/"+str(examPagesGroup.exam.year)+"/"+str(examPagesGroup.exam.semester)+"/"+examPagesGroup.exam.code
    scans_url = "../../scans/"+str(examPagesGroup.exam.year)+"/"+str(examPagesGroup.exam.semester)+"/"+examPagesGroup.exam.code

    scans_pathes = []

    scans_markers_qs = ScanMarkers.objects.filter(exam=examPagesGroup.exam)

    for dir in sorted(os.listdir(scans_dir)):
        for filename in sorted(os.listdir(scans_dir+"/"+dir)):
            split_filename = filename.split('_')
            copy_no = int(split_filename[-2])
            page_no_real = split_filename[-1].split('.')[0].replace('x','.')
            # get only two first char to prevent extra pages with a,b,c suffixes
            page_no_int = int(page_no_real[0:2])
            if page_no_int >= examPagesGroup.page_from and page_no_int <= examPagesGroup.page_to:
                marked = False
                scanMarkers = scans_markers_qs.filter(copie_no=str(copy_no).zfill(4), page_no=str(page_no_real).zfill(2).replace('.','x')).first()
                if scanMarkers and scanMarkers.markers is not None:
                   marked = True
                scans_path_dict = {}
                scans_path_dict["copy_no"] = copy_no
                scans_path_dict["page_no"] = page_no_real.lstrip("0")
                scans_path_dict["path"] = scans_url+"/"+dir+"/"+filename
                scans_path_dict["marked"] = marked
                scans_pathes.append(scans_path_dict)

    return scans_pathes
