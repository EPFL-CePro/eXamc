# RESULTS & STATISTICS FUNCTIONS
#------------------------------------------
import _io
import csv
import io
import os
from decimal import *

import numpy as np
import pdfkit
from django.conf import settings
from django.db.models import Sum
from django.template.loader import get_template

from examc_app.models import *
from userprofile.models import UserProfile


def update_common_exams(pk):

    exam = Exam.objects.get(pk=pk)
    #exam.common_exams.clear()
    #commons = Exam.objects.filter(name=exam.name,year__code=exam.year.code,semester__code=exam.semester.code)
    common_list = exam.common_exams
    if common_list:
        common_list.add(exam)
        common_list_bis = common_list
        for common in common_list.all():
            if common.pk != exam.pk :
                common.common_exams.clear()
                for common_bis in common_list.all():
                    if common_bis.pk != common.pk:
                        common.common_exams.add(common_bis)
                        common.save()
    return exam

def clamp(n, minn, maxn):
    return max(min(maxn, n), minn)

def generate_isa_csv(exam,scale,folder_path):
    f = open(folder_path+"/"+exam.code+"_"+exam.code+"_"+exam.date.strftime("%Y%m%d")+"_ISA.csv", 'w', newline='', encoding='utf-8')
    writer = csv.writer(f)
    for student in exam.students.all():
        try:
            grade = StudentScaleGrade.objects.get(student=student,scale__name=scale.name)
            row = str(student.sciper)+";"+str(grade.grade)
        except StudentScaleGrade.DoesNotExist:
            row = str(student.sciper+";NA")

        writer.writerow([row])

    f.close()

    return True

def generate_scale_pdf(exam,scale,folder_path):

    scale_list = {}
    grade_list = np.arange(float(scale.min_grade),float(scale.max_grade)+0.25,0.25)

    #get exam max points
    max_pts = Question.objects.filter(exam=exam).values('max_points').aggregate(Sum('max_points')).get('max_points__sum')
    #get max decimal places of students points
    all_pts = Student.objects.filter(exam=exam).values_list('points',flat=True)
    maxD = get_max_decimal_places(all_pts)

    if maxD > 0:
        decimal_string_from = f"{0.000000:.{maxD}f}"
        decimal_string_to = f"{0.000000:.{maxD-1}f}1"
    else:
        decimal_string_from = "0"
        decimal_string_to = "1"
    point_list = np.arange(Decimal(decimal_string_from), max_pts, Decimal(decimal_string_to))

    last_step = Decimal(decimal_string_from)

    last_point = 0

    for grade in grade_list:
        for point in point_list:
            # set to grade 1 if points <= 0
            #if point <= 0:
            #    pt_grade = 1
            #else:
            pt_grade = Decimal(((point+scale.points_to_add) / scale.total_points * 5 + 1)*4).quantize(Decimal('1'),rounding=ROUND_HALF_UP) / 4

            if pt_grade > grade and pt_grade <= scale.max_grade:
                scale_list[grade] = str(round(last_step,maxD))+"-"+str(round(last_point,maxD))
                last_step = point
                break
            last_point = point

    scale_list[grade_list[-1]] = str(round(last_step,2))+"- max"

    template = get_template(settings.SCALE_PDF_TEMPLATE)

    html = template.render({"EXAM": exam,"SCALE":scale_list})  # Renders the template with the context data.

    pdfkit.from_string(html, output_path = folder_path+"/"+exam.code+"_"+exam.date.strftime("%Y%m%d")+"_SCALE.pdf")#, configuration = config)

    return True

def generate_students_data_csv(exam,folder_path):
    logger.info('start')
    f = open(folder_path+"/"+exam.code+"_"+exam.code+"_"+exam.date.strftime("%Y%m%d")+"_DATA.csv", 'w', newline='', encoding='utf-8')
    writer = csv.writer(f, delimiter=";")
    data = []

    # header
    row = ["COPIE_NO","SCIPER","NAME","PRESENT","POINTS"]
    for q in exam.questions.all():
        row.append(q.code+":TICKED")
        row.append(q.code+":POINTS")
    data.append(row)

    i=1

    students_data = StudentQuestionAnswer.objects.filter(student__in=exam.students.all()).order_by('student__pk', 'question__pk')
    last_student_pk = 0
    for sd in students_data:
        i+=1
        if last_student_pk != sd.student.pk:
            if last_student_pk != 0:
                data.append(row)
            row = [str(sd.student.copie_no),str(sd.student.sciper),sd.student.name,str(sd.student.present),str(sd.student.points)]
            last_student_pk = sd.student.pk


        row.append(sd.ticked)
        row.append(sd.points)

    data.append(row)
    writer.writerows(data);
    f.close()

    return True

def zipdir(path, ziph):
    # ziph is zipfile handle
    for root, dirs, files in os.walk(path):
        for file in files:
            ziph.write(os.path.join(root, file),
            os.path.relpath(os.path.join(root, file),
            os.path.join(path, '..')))

def get_max_decimal_places(data):
    maxD = 0
    for value in data:
        exp = value.normalize().as_tuple().exponent*-1
        if exp > maxD:
            maxD = exp

    return maxD

# file import
def delete_exam_data(exam):
    Question.objects.filter(exam=exam).delete()
    Student.objects.filter(exam=exam).delete()

# def import_csv_data_old(csv_file, exam):
#
#     #delete old exam data
#     delete_exam_data(exam)
#
#     if type(csv_file) != _io.TextIOWrapper:
#         decoded_file = csv_file.read().decode('utf-8')
#         io_csv_string = io.StringIO(decoded_file)
#     else:
#         io_csv_string = csv_file
#
#     #loop over the lines and save them in db. If error , store as string and then display
#     line_nr = 0
#
#     question_list = []
#     question_answers = {}
#     student_data_list = []
#
#     for fields in csv.reader(io_csv_string, delimiter=';'):
#
#         line_nr += 1
#
#         if fields[0]:
#
#             col_nr = 0
#
#             student_data = StudentQuestionAnswer()
#             student = Student()
#             update_question = False
#
#             for field in fields:
#                 col_nr += 1
#
#                 #remove " if char field delimiter exist
#                 field = field.replace('"', '')
#
#                 #add questions from header
#                 if line_nr == 1 and col_nr > 6 and (col_nr % 2) > 0:
#                     question = Question()
#                     question.code = field
#                     question.common = False
#                     if field.upper().find('SCQ') >= 0:
#                         question.question_type_id = 1
#                         question.nb_answers = 0
#                     elif field.upper().find('MCQ') >= 0:
#                         question.question_type_id = 2
#                         question.nb_answers = 0
#                     elif field.upper().find('TF') >= 0:
#                         question.question_type_id = 3
#                         question.nb_answers = 2
#                     else:
#                         question.question_type_id = 4
#                         question.nb_answers = 0
#                     question.exam = exam
#                     question.save()
#                     question_list.append(question)
#                 elif line_nr > 1:
#                     student.exam = exam
#
#                     if col_nr == 1:
#                         student.copie_no = field
#                     elif col_nr == 2:
#                         student.sciper = field
#                     elif col_nr == 3:
#                         student.name = field
#                     elif col_nr == 4:
#                         student.section = field
#                     elif col_nr == 5:
#                         student.email = field
#                         student.save()
#
#                     if col_nr > 6:
#
#                         if (col_nr % 2) > 0:
#
#                             # in case of ',' for decimals
#                             value = field
#                             if type(value) == str:
#                                 value = value.replace(',','.')
#
#                             student_data = StudentQuestionAnswer()
#                             if not field:
#                                 student_data.points = 0
#                             else:
#                                 student_data.points = float(value)
#
#                             student_data.student = student
#                             question = Question.objects.get(pk=question_list[int((col_nr-7)/2)].pk)
#                             student_data.question = question
#
#                             if question.max_points < student_data.points:
#                                 question.max_points = student_data.points
#                                 update_question = True
#
#                             if field:
#                                 student.points += float(value)
#                         else:
#                             student_data.ticked = field
#                             student_data_list.append(student_data)
#
#                             # add answer to question MCQ/SCQ dictionary
#                             if question.question_type.id <= 2 and field not in (None, "") and len(field) == 1:
#                                 if question.code not in question_answers:
#                                     question_answers[question.code] = field.split()
#                                 else:
#                                     answers = question_answers[question.code]
#                                     new_answers = field.split()
#                                     for new_answer in new_answers:
#                                         if new_answer not in answers:
#                                             answers.append(new_answer)
#
#                                     question_answers[question.code] = answers
#
#                             if student_data.ticked and not (question.question_type.id == 4 and student_data.points == 0):
#                                 student.present = True
#
#                             if update_question:
#                                 question.correct_answer = field
#                                 question.save()
#                                 update_question = False
#
#
#             print(student)
#             if line_nr > 1:
#                 student.save()
#
#     # update questions number of answers
#     for key, value in question_answers.items():
#         question = Question.objects.get(code=key,exam=exam)
#         question.nb_answers = len(value)
#         question.save()
#
#     StudentQuestionAnswer.objects.bulk_create(student_data_list)
#
#     exam.present_students = int(Student.objects.filter(exam=exam, present=True).count())
#     exam.save()
#
#     update_common_exams(exam.pk)
#
#     generate_exam_stats(exam)
#
#     return True

def import_exams_csv(csv_file):

    decoded_file = csv_file.read().decode('utf-8')
    io_csv_string = io.StringIO(decoded_file)
    line_nr = 0

    for fields in csv.reader(io_csv_string, delimiter=';'):

        users = []
        if line_nr > 0:

            # create primary user, user profile if not exist
            # UserProfile will be created automatically on User create
            user_profile = UserProfile.objects.filter(sciper=fields[4])

            if not user_profile:
                primary_user = User()
                primary_user.username = fields[4]
                primary_user.first_name = fields[5]
                primary_user.last_name = fields[6]
                primary_user.is_staff = True
                primary_user.is_active = True
                primary_user.save()
            else:
                primary_user = User.objects.get(pk=UserProfile.objects.get(sciper=fields[4]).user.id)

            print(primary_user.id)

            #users.append(user)

            # update UserProfile
            user_profile = UserProfile.objects.get(user=primary_user)
            user_profile.sciper = fields[4]
            user_profile.save()

            # secondary teachers
            if fields[7]:
                sec_teachers = fields[7].split('|')
                for sec_teacher in sec_teachers:
                    sec_teacher_infos = sec_teacher.split(',')

                    user_profile = UserProfile.objects.filter(sciper=sec_teacher_infos[0])

                    if not user_profile:
                        user = User()
                        user.username = sec_teacher_infos[0]
                        user.first_name = sec_teacher_infos[1]
                        user.last_name = sec_teacher_infos[2]
                        user.is_staff = True
                        user.is_active = True
                        user.save()
                    else:
                        user = User.objects.get(pk=UserProfile.objects.get(sciper=sec_teacher_infos[0]).user.id)

                    users.append(user)

                    # update UserProfile
                    user_profile = UserProfile.objects.get(user=user)
                    user_profile.sciper = sec_teacher_infos[0]
                    user_profile.save()

            # create exam
            exam = Exam()
            exam.code = fields[0]
            exam.name = fields[1]
            exam.year.code = fields[2]
            exam.semester.code = fields[3]
            exam.save()
            #exam.exam_users.users.add(*users)
            #exam.save()

        line_nr += 1

    return True