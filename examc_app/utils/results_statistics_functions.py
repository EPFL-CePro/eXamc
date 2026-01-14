# RESULTS & STATISTICS FUNCTIONS
#------------------------------------------
import _io
import csv
import io
import operator
import os
from decimal import *

import numpy as np
import pdfkit
from django.conf import settings
from django.db import transaction
from django.db.models import Sum, FloatField, Subquery
from django.db.models.functions import Cast
from django.template.loader import get_template

from examc_app.models import *

SCALE_COPY_FIELDS = (
    "total_points",
    "points_to_add",
    "min_grade",
    "max_grade",
    "rounding",
    "formula",
    "final",
)

def clone_scale(src: "Scale", *, exam) -> "Scale":
    data = {f: getattr(src, f) for f in SCALE_COPY_FIELDS}
    return src.__class__(exam=exam, name=src.name, **data)

def update_common_exams_scales(overall_exam_pk):
    overall_exam = Exam.objects.get(pk=overall_exam_pk)
    children = list(overall_exam.common_exams.all())

    # --- Parent scales
    parent_scales = list(overall_exam.scales.all())
    parent_by_name = {s.name: s for s in parent_scales}
    parent_names = set(parent_by_name.keys())

    # --- Child names (existing)
    child_to_names = {
        c.id: set(c.scales.values_list("name", flat=True))
        for c in children
    }

    to_create = []

    # 1) Parent -> Children
    for child in children:
        missing = parent_names - child_to_names[child.id]
        for name in missing:
            to_create.append(clone_scale(parent_by_name[name], exam=child))

    # 2) Children -> Parent (only names common to ALL children)
    if children:
        common_names = set.intersection(*(child_to_names[c.id] for c in children))
    else:
        common_names = set()

    missing_in_parent = common_names - parent_names

    if missing_in_parent:
        # pick a source child scale per name (first child that has it)
        # (all children should have it, but this avoids assumptions)
        for name in missing_in_parent:
            src = (
                overall_exam.scales.model.objects
                .filter(exam__in=children, name=name)
                .order_by("exam_id")   # deterministic
                .first()
            )
            if src:
                to_create.append(clone_scale(src, exam=overall_exam))

    with transaction.atomic():
        if to_create:
            overall_exam.scales.model.objects.bulk_create(to_create)

def update_common_exams_users(overall_exam_pk):
    overall_exam = Exam.objects.get(pk=overall_exam_pk)
    for comex in overall_exam.common_exams.all():
        for exam_user in comex.exam_users.all():
            if not overall_exam.exam_users.filter(user=exam_user.user).exists() and exam_user.group.pk != 3:
                new_exam_user = ExamUser()
                new_exam_user.user = exam_user.user
                new_exam_user.exam = overall_exam
                new_exam_user.group = exam_user.group
                new_exam_user.save()
                overall_exam.exam_users.add(new_exam_user)
    overall_exam.save()

@transaction.atomic
def update_common_exams_questions(overall_exam_pk):
    overall_exam = Exam.objects.select_for_update().get(pk=overall_exam_pk)

    child_exams = overall_exam.common_exams.all()
    child_count = child_exams.count()

    # get questions removed from common
    removed_questions_codes = set(
        Question.objects
        .filter(exam=overall_exam, removed_from_common=True)
        .values_list("code", flat=True)
    )

    # If no children, just clear and exit
    overall_exam.questions.all().delete()
    if child_count == 0:
        return

    common_codes = (
        Question.objects
        .filter(exam__in=child_exams)
        .values('code')
        .annotate(exam_cnt=Count('exam_id', distinct=True))
        .filter(exam_cnt=child_count)
        .values('code')
    )

    # All candidate questions across children for those codes
    # Order so we deterministically pick one per code (lowest id)
    candidates = (
        Question.objects
        .filter(exam__in=child_exams, code__in=Subquery(common_codes))
        .order_by('code', 'id')
        .select_related('section', 'question_type')
    )

    # Deduplicate by code (MySQL doesn't support DISTINCT ON)
    picked = {}
    for q in candidates:
        picked.setdefault(q.code, q)

    # Clone into parent exam (create NEW instances; don't mutate q)
    new_questions = []
    for q in picked.values():
        removed = q.code in removed_questions_codes
        new_questions.append(Question(
            code=q.code,
            section=q.section,
            question_type=q.question_type,
            max_points=q.max_points,
            nb_answers=q.nb_answers,
            correct_answer=q.correct_answer,
            discriminatory_factor=q.discriminatory_factor,
            upper_correct=q.upper_correct,
            lower_correct=q.lower_correct,
            di_calculation=q.di_calculation,
            tot_answers=q.tot_answers,
            remark=q.remark,
            upper_avg=q.upper_avg,
            lower_avg=q.lower_avg,
            question_text=q.question_text,
            formula=q.formula,
            exam=overall_exam,
            removed_from_common=removed
        ))

    Question.objects.bulk_create(new_questions, ignore_conflicts=True)

def update_common_exams(overall_pk):

    exam = Exam.objects.get(pk=overall_pk)
    #exam.common_exams.clear()
    #commons = Exam.objects.filter(name=exam.name,year__code=exam.year.code,semester__code=exam.semester.code)
    common_list = [e for e in exam.common_exams.all()]
    if common_list:
        common_list.append(exam)
        common_list_bis = common_list
        for common in common_list:
            if common.pk != exam.pk :
                new_commons = []
                for common_bis in common_list_bis:
                    if common_bis.pk != common.pk:
                        new_commons.append(common_bis)
                common.common_exams.set(new_commons)
                common.save()
    return exam

def remove_common_exams(overall_pk):
    return None

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
    if maxD > 3:
        maxD = 3

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

# def import_exams_csv(csv_file):
#
#     decoded_file = csv_file.read().decode('utf-8')
#     io_csv_string = io.StringIO(decoded_file)
#     line_nr = 0
#
#     for fields in csv.reader(io_csv_string, delimiter=';'):
#
#         users = []
#         if line_nr > 0:
#
#             # create primary user, user profile if not exist
#             # UserProfile will be created automatically on User create
#             user_profile = UserProfile.objects.filter(sciper=fields[4])
#
#             if not user_profile:
#                 primary_user = User()
#                 primary_user.username = fields[4]
#                 primary_user.first_name = fields[5]
#                 primary_user.last_name = fields[6]
#                 primary_user.is_staff = True
#                 primary_user.is_active = True
#                 primary_user.save()
#             else:
#                 primary_user = User.objects.get(pk=UserProfile.objects.get(sciper=fields[4]).user.id)
#
#             print(primary_user.id)
#
#             #users.append(user)
#
#             # update UserProfile
#             user_profile = UserProfile.objects.get(user=primary_user)
#             user_profile.sciper = fields[4]
#             user_profile.save()
#
#             # secondary teachers
#             if fields[7]:
#                 sec_teachers = fields[7].split('|')
#                 for sec_teacher in sec_teachers:
#                     sec_teacher_infos = sec_teacher.split(',')
#
#                     user_profile = UserProfile.objects.filter(sciper=sec_teacher_infos[0])
#
#                     if not user_profile:
#                         user = User()
#                         user.username = sec_teacher_infos[0]
#                         user.first_name = sec_teacher_infos[1]
#                         user.last_name = sec_teacher_infos[2]
#                         user.is_staff = True
#                         user.is_active = True
#                         user.save()
#                     else:
#                         user = User.objects.get(pk=UserProfile.objects.get(sciper=sec_teacher_infos[0]).user.id)
#
#                     users.append(user)
#
#                     # update UserProfile
#                     user_profile = UserProfile.objects.get(user=user)
#                     user_profile.sciper = sec_teacher_infos[0]
#                     user_profile.save()
#
#             # create exam
#             exam = Exam()
#             exam.code = fields[0]
#             exam.name = fields[1]
#             exam.year.code = fields[2]
#             exam.semester.code = fields[3]
#             exam.save()
#             #exam.exam_users.users.add(*users)
#             #exam.save()
#
#         line_nr += 1
#
#     return True

def get_common_list(exam):
    common_list = []
    common_list.append(exam)
    if exam.common_exams.all():
        commons = list(exam.common_exams.all())
        common_list.extend(commons)
        common_list.sort(key=operator.attrgetter('code'))
    return common_list

def get_questions_stats_by_teacher(exam):
    question_stat_list = []

    com_questions = Question.objects.filter(removed_from_common=False,common=True,exam=exam)

    for question in com_questions:
        question_stat = {'question':question}
        teacher_list = []

        for comex in exam.common_exams.all():
            exam_user = ExamUser.objects.filter(exam=comex,group__id=2).first()
            teacher = {'teacher':exam_user.user.last_name.replace("-","_")}

            section_list = Student.objects.filter(present=True,exam=comex).values_list('section', flat=True).order_by().distinct()
            teacher.update({'sections':section_list})

            present_students = comex.present_students if comex.present_students > 0 else 1
            answer_list = StudentQuestionAnswer.objects.filter(student__exam=comex, student__present=True, question__code=question.code).values('ticked').order_by('ticked').annotate(percent=Cast(100 / present_students * Count('ticked'), FloatField()))

            na_answers = 0
            new_answer_list = []
            for answer in answer_list.iterator():
                if answer.get('ticked') == '' or (question.question_type == 1 and len(answer.get('ticked')) > 1):
                    na_answers += comex.present_students*answer.get('percent')/100
                else:
                    new_answer_list.append({'ticked':answer.get('ticked'),'percent':answer.get('percent')})
            na_answers = na_answers if na_answers > 0 else 1
            new_answer_list.append({'ticked':'NA','percent':100/present_students*na_answers})


            teacher.update({'answers':new_answer_list})

            teacher_list.append(teacher)

        question_stat.update({'teachers':teacher_list})
        question_stat_list.append(question_stat)

    return question_stat_list