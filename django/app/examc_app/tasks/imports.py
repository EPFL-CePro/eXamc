"""Tasks that import data into an exam: results from a CSV file, scanned copies from a zip."""

import csv
import os
import shutil
import time
import zipfile

from celery import shared_task
from celery_progress.backend import ProgressRecorder, logger
from django.conf import settings

from examc_app.models import Exam, Question, Student, StudentQuestionAnswer
from examc_app.services.jobs import update_job_progress
from examc_app.utils.generate_statistics_functions import generate_exam_stats
from examc_app.utils.results_statistics_functions import delete_exam_data
from examc_app.utils.review_functions import import_scans
from examc_app.utils.zip_security import safe_extract_zip


@shared_task(bind=True, name="examc_app.tasks.import_csv_data")
def import_csv_data(self, temp_csv_file_path, exam_pk: int):

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
        #update_common_exams(exam.pk)

        process_number+=1

        progress_recorder.set_progress(process_number, process_count, description=str(process_number)+'/'+str(process_count)+' - Generating statistics...')

        generate_exam_stats(exam,progress_recorder,process_number,process_count)
        process_number+=1

        progress_recorder.set_progress(process_number, process_count, description=str(process_number)+'/'+str(process_count)+' - Process finished!')

    except Exception as exception:
        logger.exception("Import failed for exam %s", exam_pk)
        update_job_progress(self, error=f"Error during import: {exception}", error_type=type(exception).__name__)
    finally:
        # The temporary CSV goes, whatever happened (update_job_progress above ends the task by raising)
        if os.path.exists(temp_csv_file_path):
            os.remove(temp_csv_file_path)

    return ' Process finished.'


@shared_task(bind=True, name="examc_app.tasks.import_exam_scans")
def import_exam_scans(self, zip_file_path: str, exam_pk: int, delete_old: bool) -> str:
    """
    Extracts a zip of scanned copies and imports them for an exam.

    Progress is reported through celery_progress (``current``, ``total`` and ``description``),
    which ``upload_scans_status`` passes on to the page.

    :param zip_file_path: The uploaded zip. Removed once the task is over, whether it worked or not.
    :param exam_pk: The primary key of the exam.
    :param delete_old: Whether to delete the existing scans, with their annotations and comments, first.
    :return: ``"upload_scans_ok"``.
    """
    progress = ProgressRecorder(self)
    extract_root = None

    try:
        exam = Exam.objects.get(pk=exam_pk)
        extract_root = os.path.join(
            str(settings.AUTOUPLOAD_ROOT),
            f"{exam.year.code}_{exam.semester.code}_{exam.code}",
        )
        tmp_extract_path = os.path.join(extract_root, "tmp_extract")

        with zipfile.ZipFile(zip_file_path) as archive:
            # Folders are entries too, but aren't scans.
            scans_count = sum(1 for info in archive.infolist() if not info.is_dir())

            # Extracting, starting the import, one step per scan (in import_scans), cleaning up.
            total = scans_count + 3
            step = 1
            progress.set_progress(step, total, description="Extracting the zip file…")

            # Leftovers from an earlier upload of this exam.
            shutil.rmtree(extract_root, ignore_errors=True)
            # Security hardening: validated extraction (no traversal/symlink/oversized archive).
            safe_extract_zip(archive, tmp_extract_path)

        # A zip of a folder: import what's inside it.
        dirs = [
            entry
            for entry in os.listdir(tmp_extract_path)
            if os.path.isdir(os.path.join(tmp_extract_path, entry))
        ]
        if dirs:
            tmp_extract_path = os.path.join(tmp_extract_path, dirs[0])

        step += 1
        progress.set_progress(step, total, description="Importing the scans…")
        nb_copies, step = import_scans(
            exam, tmp_extract_path, delete_old, progress, total, step
        )
        logger.info("Imported %s copies for exam %s", nb_copies, exam_pk)

        progress.set_progress(total, total, description="Removing temporary files…")
    finally:
        # Celery records the failure itself when an exception goes through here.
        if os.path.exists(zip_file_path):
            os.remove(zip_file_path)
        if extract_root:
            shutil.rmtree(extract_root, ignore_errors=True)

    return "upload_scans_ok"
