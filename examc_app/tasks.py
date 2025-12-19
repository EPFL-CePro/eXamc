import csv
import glob
import json
import os
import pathlib
import re
import shutil
import time
import zipfile
from contextlib import closing
from datetime import datetime
from time import sleep

from celery import shared_task
from celery_progress.backend import ProgressRecorder, logger
from django.contrib.sessions.models import Session
from django.http import FileResponse
from fpdf import FPDF

from django.conf import settings
from examc_app.models import Student, StudentQuestionAnswer, Question, Exam, ReviewLock
from examc_app.utils.amc_functions import amc_automatic_data_capture
from examc_app.utils.generate_statistics_functions import generate_exam_stats
from examc_app.utils.results_statistics_functions import update_common_exams, delete_exam_data
from examc_app.utils.review_functions import import_scans, zipdir, generate_marked_pdfs



@shared_task(bind=True)
def import_csv_data(self, temp_csv_file_path, exam_pk):

    try:
        progress_recorder = ProgressRecorder(self)
        exam = Exam.objects.get(pk=exam_pk)

        process_count = 0
        with open(temp_csv_file_path) as csv_file:
            process_count = len(list(csv.reader(csv_file)))+4

        process_number = 1
        progress_recorder.set_progress(0, process_count, description='')
        time.sleep(2)
        progress_recorder.set_progress(process_number, process_count, description=str(process_number)+'/'+str(process_count)+' - Deleting old data...')
        #delete old exam data
        delete_exam_data(exam)
        process_number+=1

        #loop over the lines and save them in db. If error , store as string and then display
        line_nr = 0

        question_list = []
        question_answers = {}
        student_data_list = []

        #progress_recorder.set_progress(process_number, process_count, description=str(process_number)+'/'+str(process_count)+' - Importing data from csv...')

        with open(temp_csv_file_path, newline='') as csv_file:
            for fields in csv.reader(csv_file, delimiter=';'):

                line_nr += 1

                progress_recorder.set_progress(process_number, process_count, description=str(process_number) + '/' + str(process_count) + ' - Importing data from csv : row ' + str(line_nr) + '...')

                if fields[0]:

                    col_nr = 0

                    student_data = StudentQuestionAnswer()
                    student = Student()
                    update_question = False

                    for field in fields:
                        col_nr += 1

                        #remove " if char field delimiter exist
                        field = field.replace('"', '')

                        #add questions from header
                        if line_nr == 1 and col_nr > 6 and (col_nr % 2) > 0:
                            question = Question()
                            question.code = field
                            question.common = False
                            if field.upper().find('SCQ') >= 0:
                                question.question_type_id = 1
                                question.nb_answers = 0
                            elif field.upper().find('MCQ') >= 0:
                                question.question_type_id = 2
                                question.nb_answers = 0
                            elif field.upper().find('TF') >= 0:
                                question.question_type_id = 3
                                question.nb_answers = 2
                            else:
                                question.question_type_id = 4
                                question.nb_answers = 0
                            question.exam = exam
                            question.save()
                            question_list.append(question)
                        elif line_nr > 1:
                            student.exam = exam

                            if col_nr == 1:
                                student.copie_no = field
                            elif col_nr == 2:
                                student.sciper = field
                            elif col_nr == 3:
                                student.name = field
                            elif col_nr == 4:
                                student.section = field
                            elif col_nr == 5:
                                student.email = field
                                student.save()

                            if col_nr > 6:

                                if (col_nr % 2) > 0:

                                    # in case of ',' for decimals
                                    value = field
                                    if type(value) == str:
                                        value = value.replace(',','.')

                                    student_data = StudentQuestionAnswer()
                                    if not field:
                                        student_data.points = 0
                                    else:
                                        student_data.points = float(value)

                                    student_data.student = student
                                    question = Question.objects.get(pk=question_list[int((col_nr-7)/2)].pk)
                                    student_data.question = question

                                    if question.max_points < student_data.points:
                                        question.max_points = student_data.points
                                        update_question = True

                                    if field:
                                        student.points += float(value)
                                else:
                                    student_data.ticked = field
                                    student_data_list.append(student_data)

                                    # add answer to question MCQ/SCQ dictionary
                                    if question.question_type.id <= 2 and field not in (None, "") and len(field) == 1:
                                        if question.code not in question_answers:
                                            question_answers[question.code] = field.split()
                                        else:
                                            answers = question_answers[question.code]
                                            new_answers = field.split()
                                            for new_answer in new_answers:
                                                if new_answer not in answers:
                                                    answers.append(new_answer)

                                            question_answers[question.code] = answers

                                    if student_data.ticked and not (question.question_type.id == 4 and student_data.points == 0):
                                        student.present = True

                                    if update_question:
                                        question.correct_answer = field
                                        question.save()
                                        update_question = False


                    print(student)
                    if line_nr > 1:
                        student.save()

                process_number += 1


        # update questions number of answers
        progress_recorder.set_progress(process_number, process_count, description=str(process_number)+'/'+str(process_count)+' - Updating questions answers...')
        for key, value in question_answers.items():
            question = Question.objects.get(code=key,exam=exam)
            question.nb_answers = len(value)
            question.save()

        process_number+=1

        StudentQuestionAnswer.objects.bulk_create(student_data_list)

        exam.present_students = int(Student.objects.filter(exam=exam, present=True).count())
        exam.save()

        progress_recorder.set_progress(process_number, process_count, description=str(process_number)+'/'+str(process_count)+' - Updating common exams...')
        update_common_exams(exam.pk)

        process_number+=1

        progress_recorder.set_progress(process_number, process_count, description=str(process_number)+'/'+str(process_count)+' - Generating statistics...')

        generate_exam_stats(exam,progress_recorder,process_number,process_count)
        process_number+=1

        progress_recorder.set_progress(process_number, process_count, description=str(process_number)+'/'+str(process_count)+' - Process finished!')

    except Exception as exception:
        self.update_state(state='FAILURE', meta={'exc_type': type(exception).__name__, 'exc_message': "Error during import "+str(exception)})
        os.remove(temp_csv_file_path)
        raise exception

    os.remove(temp_csv_file_path)

    return ' Process finished.'


@shared_task(bind=True)
def import_exam_scans(self, zip_file_path, exam_pk,delete_old):
    """
    Extracts and imports scanned files for an exam upload.

    This function is responsible for extracting scanned files from a zip archive and importing them into the system
    for a specific exam upload process.

    Args:
        request: TThe HTTP request object.
        pk: The primary key of the exam.
        zip_file_path: The file path of the zip archive containing the scanned files.

    Returns:
        return: A message indicating the success or failure of the upload process.
    """

    try:
        progress_recorder = ProgressRecorder(self)

        exam = Exam.objects.get(pk=exam_pk)
        scans_count = 0
        with closing(zipfile.ZipFile(zip_file_path)) as archive:
            scans_count = len(archive.infolist())
        print(scans_count)

        process_count = scans_count+7
        process_number = 1
        progress_recorder.set_progress(0, process_count, description='')
        time.sleep(2)

        # remove
        progress_recorder.set_progress(process_number, process_count, description=str(process_number) + '/' + str(
            process_count) + ' - Extracting zip files...')

        zip_path = str(settings.AUTOUPLOAD_ROOT) + "/" + str(exam.year.code) + "_" + str(
            exam.semester.code) + "_" + exam.code

        if os.path.exists(zip_path):
            shutil.rmtree(zip_path)
        tmp_extract_path = zip_path + "/tmp_extract"

        # extract zip file in tmp dir
        with zipfile.ZipFile(zip_file_path, 'r') as zip_ref:
            print("start extraction")
            zip_ref.extractall(tmp_extract_path)

        dirs = [entry for entry in os.listdir(tmp_extract_path) if os.path.isdir(os.path.join(tmp_extract_path, entry))]

        if dirs:
            tmp_extract_path = os.path.join(tmp_extract_path, dirs[0])

        process_number += 1
        progress_recorder.set_progress(process_number, process_count, description=str(process_number) + '/' + str(
            process_count) + ' - Importing scans...')

        result = import_scans(exam, tmp_extract_path,delete_old,progress_recorder,process_count,process_number)

        process_number = result[1]
        print('******** import and split ok : ')
        nb_copies = result[0]

        # if isinstance(result, tuple) and len(result) == 2:
        #     message, files = result
        # elif isinstance(result, str):
        #     message, files = result, []
        # else:
        #     message, files = "An unexpected error occurred during the upload.", []

        process_number += 1
        progress_recorder.set_progress(process_number, process_count, description=str(process_number) + '/' + str(
            process_count) + ' - Removing tmp files...')

        # remove imported Files (zip + extracted)
        for filename in os.listdir(zip_path):
            file_path = os.path.join(zip_path, filename)

            if os.path.isfile(file_path) or os.path.islink(file_path):
                os.unlink(file_path)
            elif os.path.isdir(file_path):
                shutil.rmtree(file_path)

        process_number += 1
        progress_recorder.set_progress(process_number, process_count, description=str(process_number) + '/' + str(
            process_count) + ' - AMC Automatic datacapture...')
        print('*********** start amc datacapture')

        # scans_folder_path = str(settings.SCANS_ROOT) + "/" + str(exam.year.code) + "/" + str(exam.semester.code) + "/" + exam.code+"_"+exam.date.strftime("%Y%m%d")
        # file_list_path = scans_folder_path + "/list-file"
        # tmp_file_list = open(file_list_path, "a+")
        #
        # files = glob.glob(scans_folder_path + '/**/*.*', recursive=True)
        # for file in files:
        #     tmp_file_list.write(file + "\n")
        # print('start amc automatic data capture')
        # tmp_file_list.close()
        #result = amc_automatic_data_capture(exam,scans_folder_path,True,file_list_path)
        #print('end amc automatic data capture')
        os.remove(zip_file_path)
        shutil.rmtree(zip_path)

    except Exception as exception:
        self.update_state(state='FAILURE', meta={'exc_type': type(exception).__name__, 'exc_message': "Error during import "+str(exception)})
        os.remove(zip_file_path)
        raise exception

    return 'upload_scans_ok'

@shared_task(bind=True)
def generate_marked_files_zip(self,exam_pk, export_type, with_comments):
    try:
        exam = Exam.objects.get(pk=exam_pk)
        scans_dir = str(settings.SCANS_ROOT) + "/" + str(exam.year.code) + "/" + str(exam.semester.code) + "/" + exam.code+"_"+exam.date.strftime("%Y%m%d")
        marked_dir = str(settings.MARKED_SCANS_ROOT) + "/" + str(exam.year.code) + "/" + str(exam.semester.code) + "/" + exam.code+"_"+exam.date.strftime("%Y%m%d")
        export_subdir = 'marked_'+str(exam.year.code) + "_" + str(exam.semester.code) + "_" + exam.code + "_" + datetime.now().strftime('%Y%m%d%H%M%S%f')[:-5]
        export_subdir = export_subdir.replace(" ","_")
        export_tmp_dir = (str(settings.EXPORT_TMP_ROOT) + "/" + export_subdir)

        progress_recorder = ProgressRecorder(self)

        if not os.path.exists(export_tmp_dir):
            os.mkdir(export_tmp_dir)

        # list files from scans dir
        dir_list = [x for x in os.listdir(scans_dir) if x != '0000']
        for dir in sorted(dir_list):

            copy_export_subdir = export_tmp_dir + "/" + dir

            if not os.path.exists(copy_export_subdir):
                os.mkdir(copy_export_subdir)

            for filename in sorted(os.listdir(scans_dir + "/" + dir)):
                # check if a marked file exist, if yes copy it, or copy original scans

                marked_file_path = pathlib.Path(marked_dir + "/" + dir + "/marked_" + filename.replace('.jpeg', '.png'))
                if os.path.exists(marked_file_path):
                    shutil.copyfile(marked_file_path, copy_export_subdir + "/" + filename.replace('.jpeg', '.png'))
                else:
                    shutil.copyfile(scans_dir + "/" + dir + "/" + filename, copy_export_subdir + "/" + filename)

        if int(export_type) > 1:
            generate_marked_pdfs(exam,export_tmp_dir, with_comments, progress_recorder)

            #remove subfolders with img
            for root, dirs, files in os.walk(export_tmp_dir):
                for name in dirs:
                    shutil.rmtree(os.path.join(root, name))

        # zip folder
        zipf = zipfile.ZipFile(export_tmp_dir + ".zip", 'w', zipfile.ZIP_DEFLATED)
        zipdir(export_tmp_dir, zipf)
        zipf.close()

        #remove tmp folder not zipped
        shutil.rmtree(export_tmp_dir)

        return export_subdir+'.zip'

    except Exception as exception:
        self.update_state(state='FAILURE', meta={'exc_type': type(exception).__name__, 'exc_message': "Error during export "+str(exception)})
        print(exception)
        raise exception

@shared_task(bind=True)
def generate_statistics(self,exam_pk):
    try:
        exam = Exam.objects.get(pk=exam_pk)
        logger.info(datetime.now().strftime("%Y-%m-%d %H:%M:%S")+" : Start generating statistics ---> ")

        progress_recorder = ProgressRecorder(self)
        process_count = 5
        if exam.common_exams:
            process_count = len(exam.common_exams.all())+6
        process_number = 1
        progress_recorder.set_progress(0, process_count, description='')

        # update/init overall and common exams if common
        if exam.common_exams.all():
            process_number += 1
            progress_recorder.set_progress(process_number, process_count, description='Updating common exams...')

            if not exam.overall:
                overall_code = '000_' + re.sub(r"\(.*?\)", "", exam.code).strip()
                month_year = exam.date.strftime("%m-%Y")
                overall_code += "_" + month_year
                overall_exam = Exam.objects.get(code=overall_code, semester=exam.semester, year=exam.year)
            else:
                overall_exam = exam
            #overall_exam=update_overall_common_exam(exam)
            generate_exam_stats(overall_exam,progress_recorder,process_number,process_count)
        else:
            generate_exam_stats(exam,progress_recorder,process_number,process_count)

        logger.info(datetime.now().strftime("%Y-%m-%d %H:%M:%S")+" :  -- > End generating stats !")

        process_number += 1
        progress_recorder.set_progress(process_number, process_count, description=str(process_number) + '/' + str(
            process_count) + 'Done!')
        return ' Process finished.'

    except Exception as exception:
        self.update_state(state='FAILURE', meta={'exc_type': type(exception).__name__, 'exc_message': "Error during stats generation "+str(exception)})
        print(exception)
        raise exception

@shared_task
def cleanup_review_locks():
    # Get active user IDs from sessions
    active_user_ids = set()
    now = datetime.now()

    for session in Session.objects.filter(expire_date__gt=now):
        data = session.get_decoded()
        uid = data.get('_auth_user_id')
        if uid:
            active_user_ids.add(int(uid))

    # Delete ReviewLocks where user is no longer active
    deleted_count, _ = ReviewLock.objects.exclude(user_id__in=active_user_ids).delete()
    return f"Deleted {deleted_count} review locks from logged-out users."