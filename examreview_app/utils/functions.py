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

# Detect QRCodes on scans, split copies in subfolders and detect nb pages
def split_scans_by_copy(exam):
    scans_dir = str(settings.SCANS_ROOT)+"/"+str(exam.year)+"/"+str(exam.semester)+"/"+exam.code

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
            os.rename(f,current_subdir+"/"+os.path.basename(f))
            print(copy_nr)
    pages_by_copy.append([copy_nr,page_nr])
    json_pages_by_copy = json.dumps(pages_by_copy)

    exam.pages_by_copy = json_pages_by_copy
    exam.save()
    print(exam)

def import_scans(exam, files):
    scans_dir = str(settings.SCANS_ROOT)+"/"+str(exam.year)+"/"+str(exam.semester)+"/"+exam.code
    os.makedirs(scans_dir, exist_ok=True)
    delete_old_scans(exam)

    for tmp_scan in files:
        fs = FileSystemStorage(location=scans_dir) #defaults to   MEDIA_ROOT
        scan = fs.save(tmp_scan.name, tmp_scan)
        print(scan)

    split_scans_by_copy(exam)

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
