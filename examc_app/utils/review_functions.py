import base64
import imghdr
import io
import pathlib
import os
import re
import shutil
import time

import cv2
from PIL import Image, ImageStat, ImageEnhance
from django.conf import settings
from fpdf import FPDF
from ldap3.extend import paged_search_accumulator
from shapely import Polygon

from examc_app.models import *
import pyzbar.pyzbar as pyzbar
from datetime import datetime




# from examc_app.views import *

# Detect QRCodes on scans, split copies in subfolders and detect nb pages
def split_scans_by_copy(exam, tmp_extract_path,progress_recorder,process_count,process_number):
    #extra_letters = ['a','b','c','d','e','f','g','h','i','j','k','l','m','n','o','p','q','r','t','u','v','w','x','y','z']

    scans_dir = str(settings.SCANS_ROOT) + "/" + str(exam.year.code) + "/" + str(exam.semester.code) + "/" + exam.code

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

        process_number += 1
        progress_recorder.set_progress(process_number, process_count, description=str(process_number) + '/' + str(
            process_count) + ' - Splitting scans by copy :'+ filename)

        f = os.path.join(tmp_extract_path, filename)
        # checking if it is a jpeg file
        if imghdr.what(f) == 'jpeg':
            # Read image
            im = cv2.imread(f)
            decodedObjects = pyzbar.decode(im)
            if len(decodedObjects) > 0:
                for obj in decodedObjects:
                    if str(obj.type) == 'QRCODE' and 'CePROExamsQRC' in str(obj.data):
                        data = obj.data.decode("utf-8").split(',')
                        copy_nr = data[1]
                        page_nr = data[2]
            else:
                extra_i += 1

            #print("copy "+str(copy_nr)+" / page "+str(page_nr))

            copy_nr_dir = str(copy_nr).zfill(4)
            subdir = os.path.join(scans_dir, copy_nr_dir)
            if not os.path.exists(subdir):
                os.mkdir(subdir)

            page_nr_w_extra = str(page_nr)
            page_nr_w_extra = page_nr_w_extra.zfill(2)
            if extra_i > 0:
                page_nr_w_extra += "x" + str(extra_i)

            os.rename(f, subdir + "/copy_" + str(copy_nr).zfill(4) + "_" + str(page_nr_w_extra) + pathlib.Path(
                filename).suffix)

            pages_count += 1
            if last_copy_nr != 0 and last_copy_nr != copy_nr:
                pages_by_copy.append([last_copy_nr, pages_count])
                pages_count = 0
                copy_count += 1

            if last_page_nr != page_nr:
                extra_i = 0

            last_copy_nr = copy_nr

    pages_by_copy.append([last_copy_nr, pages_count])
    json_pages_by_copy = json.dumps(pages_by_copy)

    exam.pages_by_copy = json_pages_by_copy
    exam.save()

    copy_count += 1
    return [copy_count,process_number]


def import_scans(exam, path,progress_recorder,process_count,process_number):
    print("* Start importing scans")
    scans_dir = str(settings.SCANS_ROOT) + "/" + str(exam.year.code) + "/" + str(exam.semester.code) + "/" + exam.code
    os.makedirs(scans_dir, exist_ok=True)
    progress_recorder.set_progress(process_number, process_count, description=str(process_number) + '/' + str(
        process_count) + ' - Deleting old scans...')
    process_number += 1
    delete_old_scans(exam)
    progress_recorder.set_progress(process_number, process_count, description=str(process_number) + '/' + str(
        process_count) + ' - Deleting old annotations...')
    process_number += 1
    PageMarkers.objects.filter(exam=exam).delete()
    progress_recorder.set_progress(process_number, process_count, description=str(process_number) + '/' + str(
        process_count) + ' - Deleting old comments...')
    process_number += 1
    PagesGroupComment.objects.filter(pages_group__exam=exam).delete()
    count = 0
    for tmp_scan in os.listdir(path):
        count += 1

    print(str(count) + " scans imported")
    process_number += 1
    progress_recorder.set_progress(process_number, process_count, description=str(process_number) + '/' + str(
        process_count) + ' - Splitting scans by copy...')
    result = split_scans_by_copy(exam, path,progress_recorder,process_count,process_number)

    return result


def delete_old_scans(exam):
    scans_dir = str(settings.SCANS_ROOT) + "/" + str(exam.year.code) + "/" + str(exam.semester.code) + "/" + exam.code
    for filename in os.listdir(scans_dir):
        file_path = os.path.join(scans_dir, filename)
        try:
            if os.path.isfile(file_path) or os.path.islink(file_path):
                os.unlink(file_path)
            elif os.path.isdir(file_path):
                shutil.rmtree(file_path)
        except Exception as e:
            print('Failed to delete %s. Reason: %s' % (file_path, e))

    marked_scans_dir = str(settings.MARKED_SCANS_ROOT) + "/" + str(exam.year.code) + "/" + str(exam.semester.code) + "/" + exam.code
    for filename in os.listdir(marked_scans_dir):
        file_path = os.path.join(scans_dir, filename)
        try:
            if os.path.isfile(file_path) or os.path.islink(file_path):
                os.unlink(file_path)
            elif os.path.isdir(file_path):
                shutil.rmtree(file_path)
        except Exception as e:
            print('Failed to delete %s. Reason: %s' % (file_path, e))

def get_scans_path_for_group(pagesGroup):
    scans_dir = str(settings.SCANS_ROOT) + "/" + str(pagesGroup.exam.year.code) + "/" + str(
        pagesGroup.exam.semester.code) + "/" + pagesGroup.exam.code
    scans_url = "../../scans/" + str(pagesGroup.exam.year.code) + "/" + str(
        pagesGroup.exam.semester.code) + "/" + pagesGroup.exam.code

    for dir in sorted(os.listdir(scans_dir)):
        for filename in sorted(os.listdir(scans_dir + "/" + dir)):
            split_filename = filename.split('_')
            page_no_real = split_filename[-1].split('.')[0].replace('x', '.')
            # get only two first char to prevent extra pages with a,b,c suffixes
            page_no_int = int(page_no_real[0:2])
            if page_no_int == pagesGroup.page_from:
                return scans_url + "/" + dir + "/" + filename


def get_scans_pathes_by_group(pagesGroup):
    scans_dir = str(settings.SCANS_ROOT) + "/" + str(pagesGroup.exam.year.code) + "/" + str(
        pagesGroup.exam.semester.code) + "/" + pagesGroup.exam.code
    scans_url = "../../scans/" + str(pagesGroup.exam.year.code) + "/" + str(
        pagesGroup.exam.semester.code) + "/" + pagesGroup.exam.code

    scans_pathes = []

    scans_markers_qs = PageMarkers.objects.filter(exam=pagesGroup.exam)



    for dir in sorted(os.listdir(scans_dir)):
        for filename in sorted(os.listdir(scans_dir + "/" + dir)):
            split_filename = filename.split('_')
            copy_no = split_filename[-2]
            page_no_real = split_filename[-1].split('.')[0].replace('x', '.')
            # get only two first char to prevent extra pages with a,b,c suffixes
            page_no_int = int(page_no_real[0:2])
            if page_no_int >= pagesGroup.page_from and page_no_int <= pagesGroup.page_to:
                marked = False
                comment = None
                if PagesGroupComment.objects.filter(pages_group=pagesGroup, copy_no=copy_no).all():
                    comment = True
                pageMarkers = scans_markers_qs.filter(copie_no=str(copy_no).zfill(4),
                                                      page_no=str(page_no_real).zfill(2).replace('.', 'x')).first()
                if pageMarkers:
                    if pageMarkers.markers is not None and pageMarkers.correctorBoxMarked:
                        marked = True

                    #marked_by = pageMarkers.get_users_with_date()

                scans_path_dict = {}
                scans_path_dict["copy_no"] = copy_no
                scans_path_dict["page_no"] = page_no_real.lstrip("0")
                scans_path_dict["path"] = scans_url + "/" + dir + "/" + filename
                scans_path_dict["marked"] = marked
                scans_path_dict["comment"] = comment
                #scans_path_dict["marked_by"] = marked_by
                scans_pathes.append(scans_path_dict)

    return scans_pathes

#
# def generate_marked_files_zip(exam, export_type):
#     scans_dir = str(settings.SCANS_ROOT) + "/" + str(exam.year.code) + "/" + str(exam.semester.code) + "/" + exam.code
#     marked_dir = str(settings.MARKED_SCANS_ROOT) + "/" + str(exam.year.code) + "/" + str(exam.semester.code) + "/" + exam.code
#     export_tmp_dir = str(settings.EXPORT_TMP_ROOT) + "/" + str(exam.year.code) + "_" + str(
#         exam.semester.code) + "_" + exam.code + "_" + datetime.datetime.now().strftime('%Y%m%d%H%M%S%f')[:-5]
#
#     task_id = None
#
#     if not os.path.exists(export_tmp_dir):
#         os.mkdir(export_tmp_dir)
#
#     # list files from scans dir
#     for dir in sorted(os.listdir(scans_dir)):
#
#         copy_export_subdir = export_tmp_dir + "/" + dir
#
#         if not os.path.exists(copy_export_subdir):
#             os.mkdir(copy_export_subdir)
#
#         for filename in sorted(os.listdir(scans_dir + "/" + dir)):
#             # check if a marked file exist, if yes copy it, or copy original scans
#
#             marked_file_path = pathlib.Path(marked_dir + "/" + dir + "/marked_" + filename.replace('.jpeg', '.png'))
#             if os.path.exists(marked_file_path):
#                 shutil.copyfile(marked_file_path, copy_export_subdir + "/" + filename.replace('.jpeg', '.png'))
#             else:
#                 shutil.copyfile(scans_dir + "/" + dir + "/" + filename, copy_export_subdir + "/" + filename)
#
#     if int(export_type) > 1:
#         task = generate_marked_pdfs.delay(export_tmp_dir, export_type)
#         task_id = task.task_id
#         #generate_marked_pdfs(export_tmp_dir, export_type)
#
#         #remove subfolders with img
#         for root, dirs, files in os.walk(export_tmp_dir):
#             for name in dirs:
#                 shutil.rmtree(os.path.join(root, name))
#
#     # zip folder
#     zipf = zipfile.ZipFile(export_tmp_dir + ".zip", 'w', zipfile.ZIP_DEFLATED)
#     zipdir(export_tmp_dir, zipf)
#     zipf.close()
#
#     #remove tmp folder not zipped
#     shutil.rmtree(export_tmp_dir)
#
#     return [task_id,export_tmp_dir + ".zip"]


def generate_marked_pdfs(exam,files_path, with_comments=False, progress_recorder=None):
    scans_count = len(os.listdir(files_path))

    process_count = scans_count
    process_number = 1
    progress_recorder.set_progress(0, process_count, description='')
    time.sleep(2)
    progress_recorder.set_progress(process_number, process_count, description=str(process_number) + '/' + str(
        process_count) + ' - Extracting zip files...')

    for subdir in sorted(os.listdir(files_path)):
        progress_recorder.set_progress(process_number, process_count, description=str(process_number) + '/' + str(
            process_count) + ' - Generating pdfs files...')

        pdf = FPDF(orientation='P', unit='mm', format='A4')
        pdf.set_auto_page_break(0)
        pdf.set_margins(0,0,0)
        for image in sorted(os.listdir(files_path + "/" + subdir)):
            pdf.add_page()

            # force image to sRGB if grayscale
            img_path = files_path + "/" + subdir + "/" + image
            if is_grayscale(img_path):

                img = cv2.imread(img_path, cv2.IMREAD_GRAYSCALE)
                img_path = files_path + "/" + subdir + "/rgb" + image
                img_rgb = cv2.cvtColor(img, cv2.COLOR_GRAY2RGB)
                cv2.imwrite(img_path, img_rgb)
                pdf.image(img_path, 0,0,pdf.epw)

            pdf.image(img_path,w=pdf.epw)


        if with_comments == '1':

            pages_comments = PagesGroupComment.objects.filter(pages_group__exam=exam,copy_no=subdir).order_by('copy_no','pages_group__page_from','parent_id')
            if pages_comments:
                pdf.add_page()

            pdf.set_font("Helvetica", "", 8)
            pdf.set_auto_page_break(1)
            generate_comments_pdf_pages(exam,None,subdir,pdf)

        pdf.output(files_path + "/copy_" + subdir + ".pdf", "F")

        process_number += 1

    return ' Process finished. '

def generate_comments_pdf_pages(exam,parent,copy_no,pdf,margin_left=10):
    pages_comments = PagesGroupComment.objects.filter(pages_group__exam=exam, copy_no=copy_no, parent=parent).order_by('pages_group_id')
    last_pages_group_id = None
    for comment in pages_comments.all():
        pdf.ln()
        pdf.ln()
        pdf.set_margins(margin_left, 10, 10)

        if not parent and (last_pages_group_id is None or last_pages_group_id != comment.pages_group_id):
            pdf.multi_cell(new_x="LEFT", w=190, txt='', fill=True)
            pdf.set_font(style="B")
            pdf.set_text_color(255,255,255)
            pdf.multi_cell(new_x="LEFT", w=190, txt=comment.pages_group.group_name,fill=True)
            pdf.multi_cell(new_x="LEFT", w=190, txt='', fill=True)
            pdf.ln()
            pdf.set_text_color(0,0,0)


        date_str = comment.created.strftime('%Y-%m-%d %H:%M:%S')
        if comment.modified:
            date_str = comment.modified.strftime('%Y-%m-%d %H:%M:%S')
        text = comment.user.first_name + ' ' + comment.user.last_name
        text += '( ' + date_str + ' )'
        pdf.set_font(style="I")
        pdf.set_fill_color(215, 215, 215)
        pdf.multi_cell(new_x="LEFT", w=100, txt='', fill=True)
        pdf.multi_cell(new_x="LEFT", w=100, txt=text, fill=True)
        pdf.multi_cell(new_x="LEFT", w=100, txt='', fill=True)
        pdf.set_fill_color(245, 245, 245)
        pdf.set_font(style="")
        pdf.multi_cell(new_x="LEFT", w=100, txt='', fill=True)
        pdf.multi_cell(new_x="LEFT", w=100, txt=comment.content, fill=True)
        pdf.multi_cell(new_x="LEFT", w=100, txt='', fill=True)
        if comment.children.all():
            generate_comments_pdf_pages(exam,comment,copy_no,pdf,margin_left+10)

        last_pages_group_id = comment.pages_group_id

def is_grayscale(path):
    im = Image.open(path).convert("RGB")
    stat = ImageStat.Stat(im)
    if sum(stat.sum)/3 == stat.sum[0]: #check the avg with any element value
        return True #if grayscale
    else:
        return False #else its colour

def zipdir(path, ziph):
    # ziph is zipfile handle
    for root, dirs, files in os.walk(path):
        for file in files:
            ziph.write(os.path.join(root, file),
                       os.path.relpath(os.path.join(root, file),os.path.join(path, '..')))


# def generate_marked_pdfs(files_path, export_type):
#     for subdir in os.listdir(files_path):
#         pdf = FPDF(orientation='P', unit='mm', format='A4')
#         pdf.set_auto_page_break(0)
#
#         for image in os.listdir(files_path + "/" + subdir):
#             pdf.add_page()
#             pdf.image(files_path + "/" + subdir + "/" + image, 0, 0, 210)
#
#         pdf.output(files_path + "/copy_" + subdir + ".pdf", "F")


def updateCorrectorBoxMarked(pageMarkers):
    markers = json.loads(pageMarkers.markers)['markers']
    for marker in markers:
        return None




def check_if_markers_intersect(corrector_box_marker_set, other_marker_set):
    corr_box_marker_data = json.loads(corrector_box_marker_set)['markers']
    other_markers_data = json.loads(other_marker_set)['markers']
    corr_box_coords = None
    for marker in corr_box_marker_data:
        left = marker['left']
        top = marker['top']
        width = marker['width']
        height = marker['height']
        a = (left, top)
        b = (left + width, top)
        c = (left + width, top + height)
        d = (left, top + height)
        corr_box_coords = [a, b, c, d]

    other_coords = []
    for marker in other_markers_data:
        if marker['typeName'] == 'ArrowMarker':
            left = marker['x1']
            top = marker['y1']
            width = marker['x2']-left
            height = marker['y2']-top
            a = (left, top)
            b = (left + width, top)
            c = (left + width, top + height)
            d = (left, top + height)
        else:
            left = marker['left']
            top = marker['top']
            width = marker['width']
            height = marker['height']
            a = (left, top)
            b = (left + width, top)
            c = (left + width, top + height)
            d = (left, top + height)
        other_coords.append([marker,[a, b, c, d]])

    corr_box_polygon = Polygon(corr_box_coords)

    for other_coord in other_coords:
        other_polygon = Polygon(other_coord[1])

        if other_polygon.intersects(corr_box_polygon):
            #change fill color to black to ensure good detection with AMC
            old_marker_str = json.dumps(other_coord[0])
            new_marker = other_coord[0]
            if(new_marker['typeName'] == 'FreehandMarker'):
                dataUrlPattern = re.compile('data:image/(png|jpeg);base64,(.*)$')
                img_data = dataUrlPattern.match(new_marker['drawingImgUrl']).group(2)
                img_data = base64.b64decode(img_data)
                img_file = Image.open(io.BytesIO(img_data))
                img_file = img_file.convert("L")
                enhancer = ImageEnhance.Brightness(img_file)
                # to reduce brightness by 50%, use factor 0.5
                img_file = enhancer.enhance(0.5)
                buffered = io.BytesIO()
                img_file.save(buffered, format="PNG")
                img_str = base64.b64encode(buffered.getvalue())
                img_data_url =  u'data:image/png;base64,'+img_str.decode('utf-8')


                new_marker['drawingImgUrl'] = img_data_url
            else:
                new_marker['fillColor'] = 'black'

            return [old_marker_str, json.dumps(new_marker)]

    return None