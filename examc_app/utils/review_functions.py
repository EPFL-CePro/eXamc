# SCANS IMPORT functions
import csv

from django.conf import settings
from examc_app.models import *
from django.core.files.storage import FileSystemStorage
from PIL import Image
import pyzbar.pyzbar as pyzbar
from PIL import Image
import numpy as np
import cv2
import os
import imghdr
import json
import shutil
import pathlib
import datetime
import zipfile
from fpdf import FPDF

from django.db.models import Q


# Detect QRCodes on scans, split copies in subfolders and detect nb pages
def split_scans_by_copy(exam,tmp_extract_path):

    #extra_letters = ['a','b','c','d','e','f','g','h','i','j','k','l','m','n','o','p','q','r','t','u','v','w','x','y','z']

    scans_dir = str(settings.SCANS_ROOT)+"/"+str(exam.year)+"/"+str(exam.semester)+"/"+exam.code

    print("* Start splitting by copy")

    copy_nr = 0
    page_nr = 0
    pages_by_copy = []
    extra_i = 0
    pages_count = 0
    last_copy_nr = 0
    last_page_nr = 0
    copy_count = 0
    scans_files = sorted(os.listdir(tmp_extract_path))
    for filename in scans_files:
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

            copy_nr_dir = str(copy_nr).zfill(4)
            subdir = os.path.join(scans_dir,copy_nr_dir)
            if not os.path.exists(subdir):
              os.mkdir(subdir)

            page_nr_w_extra = str(page_nr)
            page_nr_w_extra = page_nr_w_extra.zfill(2)
            if extra_i > 0:
              page_nr_w_extra+="x"+str(extra_i)

            os.rename(f,subdir+"/copy_"+str(copy_nr).zfill(4)+"_"+str(page_nr_w_extra)+pathlib.Path(filename).suffix)

            pages_count+=1
            if last_copy_nr != 0 and last_copy_nr != copy_nr:
              pages_by_copy.append([last_copy_nr,pages_count])
              pages_count=0
              copy_count += 1

            if last_page_nr != page_nr:
              extra_i = 0

            last_copy_nr = copy_nr

    pages_by_copy.append([last_copy_nr,pages_count])
    json_pages_by_copy = json.dumps(pages_by_copy)

    exam.pages_by_copy = json_pages_by_copy
    exam.save()

    copy_count += 1
    return copy_count

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
    if user in exam_users or user.is_superuser:
        return True
    else:
        return False

def get_scans_path_for_group(examPagesGroup):
    scans_dir = str(settings.SCANS_ROOT) + "/" + str(examPagesGroup.exam.year) + "/" + str(examPagesGroup.exam.semester) + "/" + examPagesGroup.exam.code
    scans_url = "../../scans/" + str(examPagesGroup.exam.year) + "/" + str(examPagesGroup.exam.semester) + "/" + examPagesGroup.exam.code

    for dir in sorted(os.listdir(scans_dir)):
        for filename in sorted(os.listdir(scans_dir + "/" + dir)):
            split_filename = filename.split('_')
            page_no_real = split_filename[-1].split('.')[0].replace('x', '.')
            # get only two first char to prevent extra pages with a,b,c suffixes
            page_no_int = int(page_no_real[0:2])
            if page_no_int == examPagesGroup.page_from:
                return scans_url+"/"+dir+"/"+filename


def get_scans_pathes_by_group(examPagesGroup):

    scans_dir = str(settings.SCANS_ROOT)+"/"+str(examPagesGroup.exam.year)+"/"+str(examPagesGroup.exam.semester)+"/"+examPagesGroup.exam.code
    scans_url = "../../scans/"+str(examPagesGroup.exam.year)+"/"+str(examPagesGroup.exam.semester)+"/"+examPagesGroup.exam.code

    scans_pathes = []

    scans_markers_qs = ScanMarkers.objects.filter(exam=examPagesGroup.exam)

    for dir in sorted(os.listdir(scans_dir)):
        for filename in sorted(os.listdir(scans_dir+"/"+dir)):
            split_filename = filename.split('_')
            copy_no = split_filename[-2]
            page_no_real = split_filename[-1].split('.')[0].replace('x','.')
            # get only two first char to prevent extra pages with a,b,c suffixes
            page_no_int = int(page_no_real[0:2])
            if page_no_int >= examPagesGroup.page_from and page_no_int <= examPagesGroup.page_to:
                marked = False
                comment = None
                scanMarkers = scans_markers_qs.filter(copie_no=str(copy_no).zfill(4), page_no=str(page_no_real).zfill(2).replace('.','x')).first()
                if scanMarkers :
                  if ExamPagesGroupComment.objects.filter(pages_group=examPagesGroup, copy_no=scanMarkers.copie_no).exists():
                    comment = True
                  if scanMarkers.markers is not None:
                    marked = True

                scans_path_dict = {}
                scans_path_dict["copy_no"] = copy_no
                scans_path_dict["page_no"] = page_no_real.lstrip("0")
                scans_path_dict["path"] = scans_url+"/"+dir+"/"+filename
                scans_path_dict["marked"] = marked
                scans_path_dict["comment"] = comment
                scans_pathes.append(scans_path_dict)

    return scans_pathes

def generate_marked_files_zip(exam, export_type):

  scans_dir = str(settings.SCANS_ROOT)+"/"+str(exam.year)+"/"+str(exam.semester)+"/"+exam.code
  marked_dir = str(settings.MARKED_SCANS_ROOT)+"/"+str(exam.year)+"/"+str(exam.semester)+"/"+exam.code
  export_tmp_dir = str(settings.EXPORT_TMP_ROOT)+"/"+str(exam.year)+"_"+str(exam.semester)+"_"+exam.code+"_"+datetime.datetime.now().strftime('%Y%m%d%H%M%S%f')[:-5]

  if not os.path.exists(export_tmp_dir):
    os.mkdir(export_tmp_dir)

  # list files from scans dir
  for dir in sorted(os.listdir(scans_dir)):

    copy_export_subdir = export_tmp_dir+"/"+dir

    if not os.path.exists(copy_export_subdir):
      os.mkdir(copy_export_subdir)

    for filename in sorted(os.listdir(scans_dir+"/"+dir)):
        # check if a marked file exist, if yes copy it, or copy original scans

        marked_file_path = pathlib.Path(marked_dir+"/"+dir+"/marked_"+filename.replace('.jpeg','.png'))
        if os.path.exists(marked_file_path):
          shutil.copyfile(marked_file_path,copy_export_subdir+"/"+filename.replace('.jpeg','.png'))
        else:
          shutil.copyfile(scans_dir+"/"+dir+"/"+filename,copy_export_subdir+"/"+filename)

  if int(export_type) > 1:
    generate_marked_pdfs(export_tmp_dir,export_type)

    #remove subfolders with img
    for root, dirs, files in os.walk(export_tmp_dir):
      for name in dirs:
        shutil.rmtree(os.path.join(root,name))

  # zip folder
  zipf = zipfile.ZipFile(export_tmp_dir+".zip", 'w', zipfile.ZIP_DEFLATED)
  zipdir(export_tmp_dir, zipf)
  zipf.close()

  #remove tmp folder not zipped
  shutil.rmtree(export_tmp_dir)

  return export_tmp_dir+".zip"



def zipdir(path, ziph):
# ziph is zipfile handle
  for root, dirs, files in os.walk(path):
      for file in files:
          ziph.write(os.path.join(root, file),
          os.path.relpath(os.path.join(root, file),
          os.path.join(path, '..')))

def generate_marked_pdfs(files_path, export_type):

  for subdir in os.listdir(files_path):
    pdf = FPDF(orientation='P', unit='mm', format='A4')
    pdf.set_auto_page_break(0)

    for image in os.listdir(files_path+"/"+subdir):
      pdf.add_page()
      pdf.image(files_path+"/"+subdir+"/"+image, 0, 0, 210)

    pdf.output(files_path+"/copy_"+subdir+".pdf","F")

def updateCorrectorBoxMarked(scanMarkers):
    markers = json.loads(scanMarkers.markers)['markers']
    for marker in markers:
        return None


