import base64
import csv
import imghdr
import io
import pathlib
import os
import re
import shutil
import time
from decimal import Decimal
from fileinput import filename
from functools import lru_cache

import cv2
from PIL import Image, ImageStat, ImageEnhance
from django.conf import settings
from django.db.models import Sum
from django.http import HttpResponse
from docutils.nodes import entry
from fpdf import FPDF

from examc_app.models import *
import pyzbar.pyzbar as pyzbar
from datetime import datetime

from django.db import transaction
from django.utils import timezone

from examc_app.signing import make_token_for
from examc_app.utils.amc_db_queries import get_questions, get_question_start_page_by_student, get_question_number
from examc_app.utils.amc_functions import get_amc_project_path


IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png"}
UNRECOGNIZED_REVIEW_SCAN_DIR = "unrecognized"


def get_exam_scans_subdir(exam):
    return f"{exam.year.code}/{exam.semester.code}/{exam.code}_{exam.date:%Y%m%d}"


def get_exam_scans_dir(exam):
    return pathlib.Path(settings.SCANS_ROOT) / get_exam_scans_subdir(exam)


def get_scan_relative_path(path):
    return pathlib.Path(path).relative_to(pathlib.Path(settings.SCANS_ROOT)).as_posix()


def is_review_copy_dir_name(name):
    return name.isdigit() and name != "0000"


def iter_review_copy_dirs(scans_dir):
    scans_dir = pathlib.Path(scans_dir)
    if not scans_dir.exists():
        return

    for entry in sorted(os.scandir(scans_dir), key=lambda e: e.name):
        if entry.is_dir() and is_review_copy_dir_name(entry.name):
            yield entry


def iter_review_scan_files(scans_dir):
    for dir_entry in iter_review_copy_dirs(scans_dir):
        for file_entry in sorted(os.scandir(dir_entry.path), key=lambda e: e.name):
            if file_entry.is_file() and pathlib.Path(file_entry.name).suffix.lower() in IMAGE_EXTENSIONS:
                yield pathlib.Path(file_entry.path)


def get_expected_review_qr_data(decoded_objects):
    for obj in decoded_objects:
        if str(obj.type) != "QRCODE":
            continue
        if "CePROExamsQRC" not in str(obj.data) and "eXamcQRC" not in str(obj.data):
            continue
        try:
            data = obj.data.decode("utf-8").split(",")
        except UnicodeDecodeError:
            continue
        if len(data) >= 3 and data[1] and data[2]:
            return data[1], data[2]
    return None


def get_unrecognized_scan_path(unrecognized_dir, upload_order, suffix):
    suffix = suffix or ".jpg"
    candidate = pathlib.Path(unrecognized_dir) / f"unrecognized_{upload_order:06d}{suffix}"
    index = 1
    while candidate.exists():
        candidate = pathlib.Path(unrecognized_dir) / f"unrecognized_{upload_order:06d}.{index}{suffix}"
        index += 1
    return candidate


def normalize_review_copy_no(copy_no):
    try:
        copy_no_int = int(str(copy_no).strip())
    except (TypeError, ValueError):
        raise ValueError("Copy number must be a positive integer.")
    if copy_no_int <= 0:
        raise ValueError("Copy number must be a positive integer.")
    return str(copy_no_int).zfill(4)


def normalize_review_page_no(page_no, width=2):
    try:
        page_no_int = int(str(page_no).strip())
    except (TypeError, ValueError):
        raise ValueError("Page number must be a positive integer.")
    if page_no_int <= 0:
        raise ValueError("Page number must be a positive integer.")
    return str(page_no_int).zfill(width), page_no_int


def parse_review_scan_filename(filename):
    path = pathlib.Path(filename)
    if path.suffix.lower() not in IMAGE_EXTENSIONS:
        return None
    try:
        _prefix, copy_no, page_token = path.stem.rsplit("_", 2)
    except ValueError:
        return None
    if not copy_no.isdigit():
        return None

    base_page_no, extra_suffix = page_token, None
    if "." in page_token:
        base_page_no, extra_suffix = page_token.split(".", 1)
    if not base_page_no.isdigit():
        return None

    extra_suffix_int = None
    if extra_suffix:
        if not extra_suffix.isdigit():
            return None
        extra_suffix_int = int(extra_suffix)

    return {
        "copy_no": copy_no,
        "base_page_no": base_page_no,
        "base_page_int": int(base_page_no),
        "extra_suffix": extra_suffix_int,
        "path": path,
    }


def get_copy_scan_page_rows(copy_dir, copy_no):
    rows = []
    if not copy_dir.exists():
        return rows
    for file_entry in sorted(os.scandir(copy_dir), key=lambda e: e.name):
        if not file_entry.is_file():
            continue
        parsed = parse_review_scan_filename(file_entry.name)
        if parsed and parsed["copy_no"] == copy_no:
            parsed["path"] = pathlib.Path(file_entry.path)
            rows.append(parsed)
    return rows


def get_page_number_width(page_rows):
    page_widths = [len(row["base_page_no"]) for row in page_rows if row["base_page_no"]]
    return max([2] + page_widths)


def assign_unrecognized_review_scan_file(unrecognized_scan, copy_no, page_no, assignment_mode, resolved_by=None):
    if assignment_mode not in {
        UnrecognizedReviewScan.ASSIGNMENT_MODE_NORMAL,
        UnrecognizedReviewScan.ASSIGNMENT_MODE_EXTRA,
    }:
        raise ValueError("Assignment mode must be normal or extra.")

    target_copy_no = normalize_review_copy_no(copy_no)
    source_root = pathlib.Path(settings.SCANS_ROOT).resolve()
    source_path = (source_root / unrecognized_scan.relative_path).resolve()
    try:
        source_path.relative_to(source_root)
    except ValueError:
        raise ValueError("Unrecognized scan path is outside the scans directory.")
    if not source_path.exists():
        raise ValueError("Unrecognized scan file does not exist.")

    exam_scans_dir = get_exam_scans_dir(unrecognized_scan.exam)
    copy_dir = exam_scans_dir / target_copy_no
    if not copy_dir.exists():
        raise ValueError(f"Copy {target_copy_no} does not exist.")

    page_rows = get_copy_scan_page_rows(copy_dir, target_copy_no)
    page_width = get_page_number_width(page_rows)
    target_page_no, target_page_int = normalize_review_page_no(page_no, page_width)
    source_suffix = source_path.suffix or ".jpg"

    existing_base_rows = [
        row for row in page_rows
        if row["base_page_int"] == target_page_int and row["extra_suffix"] is None
    ]

    if assignment_mode == UnrecognizedReviewScan.ASSIGNMENT_MODE_NORMAL:
        if existing_base_rows:
            raise ValueError(f"Copy {target_copy_no} page {target_page_no} already exists.")
        destination = copy_dir / f"copy_{target_copy_no}_{target_page_no}{source_suffix}"
    else:
        if not existing_base_rows:
            raise ValueError(f"Copy {target_copy_no} page {target_page_no} does not exist for extra-page assignment.")
        target_page_no = existing_base_rows[0]["base_page_no"]
        used_suffixes = {
            row["extra_suffix"]
            for row in page_rows
            if row["base_page_int"] == target_page_int and row["extra_suffix"] is not None
        }
        extra_index = 1
        while extra_index in used_suffixes:
            extra_index += 1
        destination = copy_dir / f"copy_{target_copy_no}_{target_page_no}.{extra_index}{source_suffix}"

    if destination.exists():
        raise ValueError(f"Destination file already exists: {destination.name}")

    with transaction.atomic():
        fresh_scan = UnrecognizedReviewScan.objects.select_for_update().get(pk=unrecognized_scan.pk)
        if fresh_scan.resolved:
            raise ValueError("This unrecognized scan has already been assigned.")
        source_parent = source_path.parent
        os.rename(source_path, destination)
        fresh_scan.assigned_copy_no = target_copy_no
        fresh_scan.assigned_page_no = target_page_no
        fresh_scan.assigned_mode = assignment_mode
        fresh_scan.assigned_relative_path = get_scan_relative_path(destination)
        fresh_scan.resolved = True
        fresh_scan.resolved_by = resolved_by
        fresh_scan.resolved_at = timezone.now()
        fresh_scan.save(update_fields=[
            "assigned_copy_no",
            "assigned_page_no",
            "assigned_mode",
            "assigned_relative_path",
            "resolved",
            "resolved_by",
            "resolved_at",
        ])
    if source_parent.name == UNRECOGNIZED_REVIEW_SCAN_DIR:
        try:
            source_parent.rmdir()
        except OSError:
            pass
    return fresh_scan


# Detect QRCodes on scans, split copies in subfolders and detect nb pages
def split_scans_by_copy(exam, tmp_extract_path,progress_recorder,process_count,process_number):

    scans_dir = get_exam_scans_dir(exam)
    os.makedirs(scans_dir, exist_ok=True)
    unrecognized_dir = scans_dir / UNRECOGNIZED_REVIEW_SCAN_DIR

    print("* Start splitting by copy")

    pages_by_copy = []
    pages_count = 0
    last_copy_nr = 0
    last_recognized_scan = None
    pending_unrecognized_ids = []
    scans_files = sorted(os.listdir(tmp_extract_path))


    for upload_order, filename in enumerate(scans_files, start=1):
        print(' -- '+filename)

        process_number += 1
        progress_recorder.set_progress(process_number, process_count, description=str(process_number) + '/' + str(
            process_count) + ' - Splitting scans by copy :'+ filename)

        f = os.path.join(tmp_extract_path, filename)
        # checking if it is a jpeg file
        if imghdr.what(f) == 'jpeg':
            # Read image
            im = cv2.imread(f)
            decodedObjects = pyzbar.decode(im)
            qr_data = get_expected_review_qr_data(decodedObjects)

            if not qr_data:
                os.makedirs(unrecognized_dir, exist_ok=True)
                destination = get_unrecognized_scan_path(unrecognized_dir, upload_order, pathlib.Path(filename).suffix)
                os.rename(f, destination)

                previous = last_recognized_scan or {}
                unrecognized_scan = UnrecognizedReviewScan.objects.create(
                    exam=exam,
                    relative_path=get_scan_relative_path(destination),
                    filename=destination.name,
                    original_filename=filename,
                    upload_order=upload_order,
                    previous_copy_no=previous.get("copy_no", ""),
                    previous_page_no=previous.get("page_no", ""),
                    previous_relative_path=previous.get("relative_path", ""),
                )
                pending_unrecognized_ids.append(unrecognized_scan.pk)
                continue

            copy_nr, page_nr = qr_data
            copy_nr_dir = str(copy_nr).zfill(4)
            page_nr_normalized = str(page_nr).zfill(2)

            if last_copy_nr != 0 and last_copy_nr != copy_nr:
                pages_by_copy.append([last_copy_nr, pages_count])
                pages_count = 0

            subdir = scans_dir / copy_nr_dir
            os.makedirs(subdir, exist_ok=True)

            destination = subdir / f"copy_{copy_nr_dir}_{page_nr_normalized}{pathlib.Path(filename).suffix}"
            os.rename(f, destination)

            current_recognized_scan = {
                "copy_no": copy_nr_dir,
                "page_no": page_nr_normalized,
                "relative_path": get_scan_relative_path(destination),
            }
            if pending_unrecognized_ids:
                UnrecognizedReviewScan.objects.filter(pk__in=pending_unrecognized_ids).update(
                    next_copy_no=current_recognized_scan["copy_no"],
                    next_page_no=current_recognized_scan["page_no"],
                    next_relative_path=current_recognized_scan["relative_path"],
                )
                pending_unrecognized_ids = []

            pages_count += 1
            last_recognized_scan = current_recognized_scan
            last_copy_nr = copy_nr

    if last_copy_nr != 0:
        pages_by_copy.append([last_copy_nr, pages_count])
    json_pages_by_copy = json.dumps(pages_by_copy)

    exam.pages_by_copy = json_pages_by_copy
    exam.save()

    copy_count = len(pages_by_copy)
    return [copy_count,process_number]


def import_scans(exam, path,delete_old,progress_recorder,process_count,process_number):
    print("* Start importing scans")
    scans_dir = str(settings.SCANS_ROOT) + "/" + str(exam.year.code) + "/" + str(exam.semester.code) + "/" + exam.code+"_"+exam.date.strftime("%Y%m%d")
    os.makedirs(scans_dir, exist_ok=True)
    progress_recorder.set_progress(process_number, process_count, description=str(process_number) + '/' + str(
        process_count) + ' - Deleting old scans...')
    process_number += 1
    if delete_old:
        UnrecognizedReviewScan.objects.filter(exam=exam).delete()
        delete_old_scans(exam)
    progress_recorder.set_progress(process_number, process_count, description=str(process_number) + '/' + str(
        process_count) + ' - Deleting old annotations...')
    process_number += 1
    if delete_old:
        PageMarkers.objects.filter(exam=exam).delete()
    progress_recorder.set_progress(process_number, process_count, description=str(process_number) + '/' + str(
        process_count) + ' - Deleting old comments...')
    process_number += 1
    if delete_old:
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

def create_students_from_amc(exam):
    students_csv_file_path = get_amc_project_path(exam,False)+"/students.csv"
    if os.path.exists(students_csv_file_path):
        line_nr = 0
        headers = None
        with open(students_csv_file_path, newline='', encoding="utf-8") as csv_file:
            for fields in csv.reader(csv_file, delimiter=','):
                line_nr += 1
                if line_nr == 1:
                    headers = fields
                else:
                    if len(fields) > 0 and fields[0]:
                        copy_no = fields[headers.index('ID')]
                        sciper = fields[headers.index('SCIPER')]
                        name = fields[headers.index('NAME')]
                        Student.objects.get_or_create(copie_no=copy_no,sciper=sciper,name=name,exam=exam)



def delete_old_scans(exam):
    scans_dir = str(settings.SCANS_ROOT) + "/" + str(exam.year.code) + "/" + str(exam.semester.code) + "/" + exam.code+"_"+exam.date.strftime("%Y%m%d")
    for filename in os.listdir(scans_dir):
        file_path = os.path.join(scans_dir, filename)
        try:
            if os.path.isfile(file_path) or os.path.islink(file_path):
                os.unlink(file_path)
            elif os.path.isdir(file_path):
                shutil.rmtree(file_path)
        except Exception as e:
            print('Failed to delete %s. Reason: %s' % (file_path, e))

    marked_scans_dir = str(settings.MARKED_SCANS_ROOT) + "/" + str(exam.year.code) + "/" + str(exam.semester.code) + "/" + exam.code+"_"+exam.date.strftime("%Y%m%d")
    if os.path.exists(marked_scans_dir):
        for filename in os.listdir(marked_scans_dir):
            file_path = os.path.join(scans_dir, filename)
            try:
                if os.path.isfile(file_path) or os.path.islink(file_path):
                    os.unlink(file_path)
                elif os.path.isdir(file_path):
                    shutil.rmtree(file_path)
            except Exception as e:
                print('Failed to delete %s. Reason: %s' % (file_path, e))

#### TESTING DISPLAYING FULL COPIE JPGS ####
def get_scans_pathes_by_exam(exam):
    scans_dir = str(settings.SCANS_ROOT) + "/" + str(exam.year.code) + "/" + str(
        exam.semester.code) + "/" + exam.code + "_" + exam.date.strftime("%Y%m%d")
    scans_url = "../../scans/" + str(exam.year.code) + "/" + str(
        exam.semester.code) + "/" + exam.code + "_" + exam.date.strftime("%Y%m%d")

    #scans_markers_qs = PageMarkers.objects.filter(exam=exam,copy_no=copy_nr)
    scans_pathes = []
    if os.path.exists(scans_dir):
        for dir in sorted(os.listdir(scans_dir)):
            if not is_review_copy_dir_name(dir):
                continue
            # files = []
            # for filename in sorted(os.listdir(scans_dir + "/" + dir)):
            #     if not filename.endswith("full.jpg"):
            #         files.append(scans_dir + "/"+dir+"/"+filename)
            #
            # scans = [Image.open(x) for x in files]
            # widths, heights = zip(*(i.size for i in scans))
            #
            # total_width = max(widths)
            # max_height = sum(heights)
            #
            # merged_scans = Image.new('RGB', (total_width, max_height))
            #
            # y_offset = 0
            # for im in scans:
            #     merged_scans.paste(im, (0,y_offset))
            #     y_offset += im.height
            #
            # merged_scans.save(scans_dir+"/"+dir+"/"+dir+"_full.jpg")
            scans_path_dict = {}
            scans_path_dict["copy_no"] = dir
            scans_path_dict["path"] = scans_url+"/"+dir+"/"+dir+"_full.jpg"
            # scans_path_dict["marked"] = marked
            # scans_path_dict["comment"] = comment
            # scans_path_dict["marked_by"] = marked_by
            scans_pathes.append(scans_path_dict)

    return scans_pathes
#### END TESTING DISPLAYING FULL COPIE JPGS ###


def get_scans_pathes_by_group(pagesGroup):


    project_subdir = str(pagesGroup.exam.year.code) + "/" + str(pagesGroup.exam.semester.code) + "/" + pagesGroup.exam.code+"_"+pagesGroup.exam.date.strftime("%Y%m%d")
    scans_dir = str(settings.SCANS_ROOT) + "/" + project_subdir
    #scans_url = str(settings.SCANS_URL) + project_subdir

    scans_pathes = []

    scans_markers_qs = PageMarkers.objects.filter(exam=pagesGroup.exam)

    if os.path.exists(scans_dir):
        for dir in sorted(os.listdir(scans_dir)):
            if not is_review_copy_dir_name(dir):
                continue
            for filename in sorted(os.listdir(scans_dir + "/" + dir)):
                if not filename.endswith("full.jpg"):
                    split_filename = filename.split('_')
                    copy_no = split_filename[-2]
                    page_no_real = split_filename[-1].replace('.jpg','')
                    # get only two first char to prevent extra pages with a,b,c suffixes
                    page_no_int = int(page_no_real[0:2])

                    amc_questions_pages = get_question_start_page_by_student(get_amc_project_path(pagesGroup.exam, True) + "/data/", pagesGroup.group_name, int(copy_no))
                    if amc_questions_pages:
                        from_p = amc_questions_pages[0]['page']
                        to_p = from_p+pagesGroup.nb_pages-1
                        if page_no_int >= from_p and page_no_int <= to_p:
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
                            scans_path_dict["path"] = make_token_for(project_subdir+"/"+dir+"/"+filename,str(settings.SCANS_ROOT))
                            scans_path_dict["marked"] = marked
                            scans_path_dict["comment"] = comment
                            #scans_path_dict["marked_by"] = marked_by
                            scans_pathes.append(scans_path_dict)

        scans_pathes = sorted(scans_pathes, key=lambda k: (k['copy_no'], float(k['page_no'])))
    return scans_pathes

### old function rewritten after for best performances
# def get_copies_pages_by_group(pagesGroup):
#
#
#     project_subdir = str(pagesGroup.exam.year.code) + "/" + str(pagesGroup.exam.semester.code) + "/" + pagesGroup.exam.code+"_"+pagesGroup.exam.date.strftime("%Y%m%d")
#     scans_dir = str(settings.SCANS_ROOT) + "/" + project_subdir
#
#     copies_pages_list = []
#
#     scans_markers_qs = PageMarkers.objects.filter(exam=pagesGroup.exam)
#
#     if os.path.exists(scans_dir):
#         for dir in sorted(os.listdir(scans_dir)):
#             for filename in sorted(os.listdir(scans_dir + "/" + dir)):
#                 if not filename.endswith("full.jpg"):
#                     split_filename = filename.split('_')
#                     copy_no = split_filename[-2]
#                     page_no_real = split_filename[-1].replace('.jpg', '')
#                     # get only two first char to prevent extra pages with a,b,c suffixes
#                     page_no_int = int(page_no_real[0:2])
#
#                     amc_questions_pages = get_question_start_page_by_student(get_amc_project_path(pagesGroup.exam, True) + "/data/", pagesGroup.group_name, int(copy_no))
#                     if amc_questions_pages:
#                         from_p = amc_questions_pages[0]['page']
#                         to_p = from_p+pagesGroup.nb_pages-1
#                         if page_no_int >= from_p and page_no_int <= to_p:
#                             marked = False
#                             comment = False
#                             if PagesGroupComment.objects.filter(pages_group=pagesGroup, copy_no=copy_no).all():
#                                 comment = True
#                             pageMarkers = scans_markers_qs.filter(copie_no=str(copy_no).zfill(4),
#                                                                   page_no=str(page_no_real).zfill(2).replace('.', 'x')).first()
#                             if pageMarkers:
#                                 if pageMarkers.markers is not None and pageMarkers.correctorBoxMarked:
#                                     marked = True
#
#                                 #marked_by = pageMarkers.get_users_with_date()
#
#                             copy_page_dict = {}
#                             copy_page_dict["copy_no"] = copy_no
#                             copy_page_dict["page_no"] = page_no_real
#                             copy_page_dict["marked"] = marked
#                             copy_page_dict["comment"] = comment
#                             copies_pages_list.append(copy_page_dict)
#
#         copies_pages_list = sorted(copies_pages_list, key=lambda k: (k['copy_no'], float(k['page_no'])))
#     return copies_pages_list

def get_copies_pages_by_group(pagesGroup):
    print('********************* START GET COPIES')
    exam = pagesGroup.exam
    project_subdir = f"{exam.year.code}/{exam.semester.code}/{exam.code}_{exam.date:%Y%m%d}"
    scans_dir = pathlib.Path(settings.SCANS_ROOT) / project_subdir
    print(scans_dir)

    # ---- DB: pull once, then do O(1) lookups in-memory ----------------------
    # Page markers -> (copy_no_z4, page_no_norm) -> marked_bool
    scans_markers = (
        PageMarkers.objects
        .filter(exam=exam)
        .values("copie_no", "page_no", "markers", "correctorBoxMarked")
    )
    markers_idx = {
        (row["copie_no"], row["page_no"]): bool(row["markers"]) and bool(row["correctorBoxMarked"])
        for row in scans_markers
    }
    grading_scheme_marked_copies = set()
    if pagesGroup.use_grading_scheme:
        grading_scheme_marked_copies = {
            str(copy_nr).zfill(4)
            for copy_nr in (
                PagesGroupGradingSchemeCheckedBox.objects
                .filter(pages_group=pagesGroup)
                .values_list("copy_nr", flat=True)
            )
        }

    # Comments -> set of copy_no strings
    comments_set = set(
        PagesGroupComment.objects
        .filter(pages_group=pagesGroup)
        .values_list("copy_no", flat=True)
    )

    # ---- cache AMC page range per copy_no so we don't recompute -------------
    amc_data_root = pathlib.Path(get_amc_project_path(exam, True)) / "data"

    @lru_cache(maxsize=4096)
    def get_from_to(copy_no_int: int):
        pages = get_question_start_page_by_student(str(amc_data_root) + "/", pagesGroup.group_name, copy_no_int)
        if not pages:
            return None
        from_p = pages[0]["page"]
        to_p = from_p + pagesGroup.nb_pages - 1
        return (from_p, to_p)

    copies_pages_list = []

    if scans_dir.exists():
        # Iterate dirs and files with scandir (faster than listdir + isdir)
        for d_entry in sorted(os.scandir(scans_dir), key=lambda e: e.name):
            if not d_entry.is_dir() or not is_review_copy_dir_name(d_entry.name):
                continue

            dir_path = pathlib.Path(d_entry.path)

            for f_entry in sorted(os.scandir(dir_path), key=lambda e: e.name):
                if not f_entry.is_file():
                    continue
                name = f_entry.name
                if name.endswith("full.jpg"):
                    continue

                # Expect ..._<copy_no>_<page>.jpg
                try:
                    base = name[:-4] if name.lower().endswith(".jpg") else name
                    left, copy_no, page_no_real = base.rsplit("_", 2)
                except ValueError:
                    # filename not matching pattern; skip quickly
                    continue


                # page number checks (first 2 chars)
                try:
                    page_no_int = int(page_no_real[:2])
                except ValueError:
                    continue

                # AMC range gate (cached)
                try:
                    copy_no_int = int(copy_no)
                except ValueError:
                    # copy number malformed; skip
                    continue

                from_to = get_from_to(copy_no_int)
                if not from_to:
                    continue
                from_p, to_p = from_to
                if not (from_p <= page_no_int <= to_p):
                    continue

                copy_has_comment = copy_no in comments_set
                # Normalize keys like before
                copy_no_z4 = str(copy_no).zfill(4)
                page_no_norm = str(page_no_real).zfill(2).replace(".", "x")
                if pagesGroup.use_grading_scheme:
                    marked = copy_no_z4 in grading_scheme_marked_copies and page_no_int == from_p
                else:
                    marked = markers_idx.get((copy_no_z4, page_no_norm), False)
                copies_pages_list.append({
                    "copy_no": copy_no,
                    "page_no": page_no_real,
                    "marked": marked,
                    "comment": copy_has_comment,
                })
    # Sorting: avoid float() (can fail if letters); sort by numeric copy_no then by (first two digits, full tail)
    def page_sort_key(page_no: str):
        head = page_no[:2]
        tail = page_no[2:]
        try:
            head_i = int(head)
        except ValueError:
            head_i = 0
        return (head_i, tail)

    copies_pages_list.sort(key=lambda k: (int(k["copy_no"]), page_sort_key(k["page_no"])))
    return copies_pages_list

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
            if pathlib.Path(image).suffix.lower() not in IMAGE_EXTENSIONS:
                continue

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

            pages_comments = PagesGroupComment.objects.filter(pages_group__exam=exam,copy_no=subdir).order_by('copy_no','pages_group__group_name','parent_id')
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


def updateCorrectorBoxMarked(pageMarkers):
    markers = json.loads(pageMarkers.markers)['markers']
    for marker in markers:
        return None

def get_exam_copies_from_to(exam):
    scans_dir = str(settings.SCANS_ROOT) + "/" + str(exam.year.code) + "/" + str(exam.semester.code) + "/" + exam.code+"_"+exam.date.strftime("%Y%m%d")
    copies_folders = [entry.name for entry in iter_review_copy_dirs(scans_dir)]
    copies = [copy.lstrip('0') for copy in copies_folders]
    return copies


def get_scans_list(exam):
    scans_dir_path = str(settings.SCANS_ROOT) + "/" + str(exam.year.code) + "/" + str(exam.semester.code) + "/" + exam.code + "_" + exam.date.strftime("%Y%m%d")
    scans_dir_path = scans_dir_path.replace(' ', '_')
    result = []
    if os.path.exists(scans_dir_path):
        for entry in [entry.name for entry in iter_review_copy_dirs(scans_dir_path)]:
            entry_path = os.path.join(scans_dir_path, entry)
            copy = {'copy': entry,
                      'pages': []}
            list_dir_pages = sorted(os.listdir(entry_path))
            for child in list_dir_pages:
                #check if marked page exist
                marked_scan_path = (entry_path+"/marked_"+child).replace('scans','marked_scans')
                page = child.replace('.jpg','').replace('_',' ')
                if os.path.exists(marked_scan_path):
                    copy['pages'].append({'page': page+'*','path':marked_scan_path})
                else:
                    copy['pages'].append({'page': page,'path':entry_path+"/"+child})

            result.append(copy)

    return result

def get_scans_list_by_copy(exam,copy_nr):
    scans_dir_path = str(settings.SCANS_ROOT) + "/" + str(exam.year.code) + "/" + str(exam.semester.code) + "/" + exam.code + "_" + exam.date.strftime("%Y%m%d")
    scans_dir_path = scans_dir_path.replace(' ', '_')
    scans_dir_path += "/"+copy_nr
    result = []
    if os.path.exists(scans_dir_path):
        list_dir_copies = sorted(os.listdir(scans_dir_path))
        for entry in list_dir_copies:
            page = entry.replace('.jpg', '').split('_').pop()
            if int(page.split('.')[0]) != 1:
                result.append({'copy_no':copy_nr,'page_no':page})
    return result

def get_scan_url(exam,copy_nr,page_nr):
    scans_dir_path = str(settings.SCANS_ROOT) + "/" + str(exam.year.code) + "/" + str(exam.semester.code) + "/" + exam.code + "_" + exam.date.strftime("%Y%m%d")
    scans_dir_path = scans_dir_path.replace(' ', '_')
    scans_dir_path += "/" + copy_nr
    scans_url = str(exam.year.code) + "/" + str(exam.semester.code) + "/" + exam.code + "_" + exam.date.strftime("%Y%m%d")
    scans_url += "/"+ copy_nr + "/"

    scan_url = ''
    if os.path.exists(scans_dir_path):
        list_dir_copies = sorted(os.listdir(scans_dir_path))
        for entry in list_dir_copies:
            entry_path = os.path.join(scans_dir_path, entry)
            page = entry.replace('.jpg', '').split('_').pop()
            if page == page_nr:
                scan_url = make_token_for(scans_url+entry,str(settings.SCANS_ROOT))
                break
    return scan_url

def get_grading_scheme_checkboxes(grading_scheme_id, copy_nr):
    grading_scheme = QuestionGradingScheme.objects.get(pk=grading_scheme_id)
    grading_scheme_checkboxes_qs = QuestionGradingSchemeCheckBox.objects.filter(questionGradingScheme=grading_scheme).order_by('adjustment','id')
    grading_scheme_checkboxes_list = []
    item_id = None

    # Full points checkbox
    points = (PagesGroupGradingSchemeCheckedBox.objects.filter(pages_group=grading_scheme.pages_group,copy_nr=copy_nr).aggregate(total=Sum("gradingSchemeCheckBox__points"))["total"]) or 0
    checked = False
    if points == grading_scheme.max_points:
        checked = True

    grading_scheme_checkbox = {"item_id":0,"ref":"full","points":grading_scheme.max_points,"name":"FULL","description":"Full points","checked":checked,"adjustment":''}
    grading_scheme_checkboxes_list.append(grading_scheme_checkbox)
    for checkbox in grading_scheme_checkboxes_qs:
        try:
            pggsc = PagesGroupGradingSchemeCheckedBox.objects.get(
                pages_group=grading_scheme.pages_group,
                copy_nr=copy_nr,
                gradingSchemeCheckBox=checkbox
            )
            checked = True
            item_id = pggsc.id
            adjustment = pggsc.adjustment
            ref="pggsc"
        except PagesGroupGradingSchemeCheckedBox.DoesNotExist:
            checked = False
            item_id = checkbox.id
            adjustment = 0
            ref="gsc"

        grading_scheme_checkbox = {"item_id":item_id, "ref": ref,"points":checkbox.points,"name":checkbox.name,"description":checkbox.description,"checked":checked,"adjustment":adjustment}

        if checkbox.name == 'ZERO':
            grading_scheme_checkboxes_list.insert(0,grading_scheme_checkbox)
        else:
            grading_scheme_checkboxes_list.append(grading_scheme_checkbox)

    return grading_scheme_checkboxes_list

def other_grading_scheme_used(grading_scheme, copy_nr):
    pages_group_gs_checkedboxes = PagesGroupGradingSchemeCheckedBox.objects.filter(pages_group=grading_scheme.pages_group, copy_nr=copy_nr).exclude(gradingSchemeCheckBox__questionGradingScheme=grading_scheme)
    if pages_group_gs_checkedboxes:
        return pages_group_gs_checkedboxes[0].gradingSchemeCheckBox.questionGradingScheme
    return None

def get_question_points(grading_scheme, copy_nr):
    points = QuestionGradingSchemeCheckBox.objects.filter(questionGradingScheme=grading_scheme,
                                                          pagesGroupGradingSchemeCheckedBoxes__copy_nr=copy_nr).aggregate(points__sum=Sum('points'))['points__sum']
    if not points:
        points = 0
    try:
        adjust = PagesGroupGradingSchemeCheckedBox.objects.get(pages_group=grading_scheme.pages_group,
                                                               gradingSchemeCheckBox__name="ADJ", copy_nr=copy_nr)
        points += adjust.adjustment
    except PagesGroupGradingSchemeCheckedBox.DoesNotExist:
        pass

    return points
