# FUNCTIONS AND CLASSES FOR GENERATING STATISTICS
#------------------------------------------
import datetime
import math
import re
from statistics import *

from django.db import IntegrityError, transaction
from django.db.models import Max, Q, FloatField
from scipy import stats

from examc_app.utils.results_statistics_functions import *

# Get an instance of a logger
logger = logging.getLogger(__name__)

# GLOBAL VAR

COLORS = ['lightblue','orange', 'lightgreen', 'red', 'lightgray']
DISCRIMINATORY_FACTOR = 27

from ..models import *

# GENERATE STATISTICS
#-------------------------------------------------
# def generate_statistics(exam):
#
#     logger.info(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")+" : Start generating statistics ---> ")
#
#     # update/init overall and common exams if common
#     if exam.common_exams.all():
#         overall_exam=update_overall_common_exam(exam)
#         generate_exam_stats(overall_exam)
#     else:
#         #overall_exam=update_overall_common_exam(exam)
#         generate_exam_stats(exam)
#
#     logger.info(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")+" :  -- > End generating stats !")
#
#     return True

# def update_overall_common_exam(exam):
#     if not exam.overall:
#         overall_code = '000_'+re.sub(r"\(.*?\)", "", exam.code).strip()
#         month_year = exam.date.strftime("%m-%Y")
#         overall_code += "_"+month_year
#         overall_exam, created = Exam.objects.get_or_create(code = overall_code,semester = exam.semester,year = exam.year)
#         if created:
#             overall_exam.name = 'COMMON'
#             overall_exam.pdf_catalog_name = exam.pdf_catalog_name
#             overall_exam.overall = True
#             overall_exam.date = exam.date
#             overall_exam.save()
#
#         # delete existing stats and questions
#         Question.objects.filter(exam__pk=overall_exam.pk).delete()
#         AnswerStatistic.objects.filter(question__exam=overall_exam).delete()
#         ScaleStatistic.objects.filter(exam=overall_exam).delete()
#         ScaleDistribution.objects.filter(scale_statistic__exam=overall_exam).delete()
#
#
#         # copy common questions
#         for question in exam.questions.all().filter(common=True):
#             question.pk = None
#             question.exam = overall_exam
#             question.save()
#     else:
#         overall_exam = exam
#
#     # init common exams
#     overall_exam = update_common_exams(overall_exam.pk)
#     # logger.info(overall_exam.questions.all())
#     # update overall present students
#     overall_exam.present_students = int(Student.objects.filter(exam__in=overall_exam.common_exams.all(), present=True).count())
#     overall_exam.save()
#
#
#     # copy scales from other commons
#     for comex in overall_exam.common_exams.all():
#         for scale in comex.scales.all():
#             if not Exam.objects.filter(pk=overall_exam.pk, scales__name=scale.name).exists():
#                 overall_exam.scales.add(scale)
#                 overall_exam.save()
#          # copy scales to other commons
#         for scale in overall_exam.scales.all():
#             scale_comex, created = Scale.objects.get_or_create(exam=comex,name = scale.name,total_points=scale.total_points)
#             if created:
#                 scale_comex.total_points = scale.total_points
#                 scale_comex.points_to_add = scale.points_to_add
#                 scale_comex.min_grade = scale.min_grade
#                 scale_comex.max_grade = scale.max_grade
#                 scale_comex.rounding = scale.rounding
#                 scale_comex.formula = scale.formula
#                 scale_comex.save()
#         # update common questions to other commons
#         for question in comex.questions.all():
#             overall_question = Question.objects.filter(code=question.code, exam=overall_exam).first()
#             if overall_question :
#                 # logger.info(comex)
#                 # logger.info(question.code)
#                 # logger.info(comex.pk)
#                 question.common = True
#                 question.question_type = overall_question.question_type
#                 question.nb_answers = overall_question.nb_answers
#                 question.max_points = overall_question.max_points
#             else:
#                 question.common = False
#             question.save()
#
#     return overall_exam

def generate_exam_stats(exam,progress_recorder,process_number,process_count):
    logger.info("GEN STATS for "+exam.code)
    # reset statistic
    reset_statistics(exam)

    scale_statistic_list = []
    student_scales_grades_list = []
    question_statistic_list = []
    distribution_list_all = []

    color_pos = 0

    try:
        with transaction.atomic():

            if exam.overall:

                # if overall generate stats for all common exams
                common_list = exam.common_exams.all().filter(~Q(pk=exam.pk),overall=False)
                print(common_list)
                for com_exam in common_list:
                    generate_exam_stats(com_exam,progress_recorder,process_number,process_count)

                discriminatory_count = round(exam.get_sum_common_students() * 27 / 100)

                student_list = Student.objects.filter(exam__in=exam.common_exams.all(),present=True)
                student_lower_list = Student.objects.filter(exam__in=exam.common_exams.all(), present=True).order_by('points')[:discriminatory_count]
                student_upper_list = Student.objects.filter(exam__in=exam.common_exams.all(), present=True).order_by('-points')[:discriminatory_count]

            else:
                process_number += 1
                progress_recorder.set_progress(process_number, process_count, description='Generating stats for exam : '+exam.code)

                discriminatory_count = round(exam.present_students * 27 / 100)
                student_list = exam.students.all()
                student_lower_list = Student.objects.filter(exam=exam, present=True).order_by('points')[:discriminatory_count]
                student_upper_list = Student.objects.filter(exam=exam, present=True).order_by('-points')[:discriminatory_count]


            student_lower_list = list(student_lower_list)
            student_upper_list = list(student_upper_list)

            if exam.is_overall():
                question_list = Question.objects.filter(exam=exam,removed_from_common=False).all()
            else:
                question_list = exam.questions.all()

            process_number += 1
            progress_recorder.set_progress(process_number, process_count,
                                           description='Generating stats for exam : ' + exam.code + '(scale stats & students grades)')
            for scale in exam.scales.all():
                all_grades = []
                distribution_list = [0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0]

                for student in student_list:

                    grade = 0

                    if student.present:

                        #Define decimal half rounding up to be sure that x.5 are rounded up and not down as done with round()
                        #Set grade to 1 if points egal or less than zero
                        #if student.points <= 0:
                        #    grade = 1
                        #else:

                        if scale.rounding == 1:
                            roundint = 4
                        elif scale.rounding == 2 :
                            roundint = 2
                        else :
                            roundint = 0

                        if(scale.rounding == 3):
                            grade = Decimal((student.points+scale.points_to_add) / scale.total_points * (scale.max_grade-scale.min_grade) + scale.min_grade)
                        else :
                            grade = Decimal(((student.points+scale.points_to_add) / scale.total_points * (scale.max_grade-scale.min_grade) + scale.min_grade)*roundint).quantize(Decimal('1'),rounding=ROUND_HALF_UP) / roundint

                        # IF COMMON and specific indiv part calculation, recalc with formula
                        # String = "INDIV POINTS;COMMON POINTS;FORMULA with SIP=students indiv points and SCP=students common points from studentsdata"
                        # example "16;64;SIP*16/13"
                        if exam.common_exams and exam.indiv_formula:
                            indiv_points = 0
                            common_points = 0
                            for sd in student.data.all():
                                if sd.question.common:
                                    common_points += sd.points
                                else:
                                    indiv_points += sd.points

                            formula_arr = exam.indiv_formula.split(";")
                            ind_max_points = Decimal(formula_arr[0])
                            com_max_points = Decimal(formula_arr[1])
                            print(indiv_points)
                            indiv_formula = formula_arr[2].replace("SIP",str(indiv_points)).replace("SCP",str(common_points)).replace("IP",str(ind_max_points)).replace("CP",str(com_max_points))
                            indiv_points = Decimal(eval(indiv_formula))
                            if indiv_points>ind_max_points:
                                indiv_points=ind_max_points
                            print(indiv_formula)
                            print(indiv_points)

                            grade = Decimal(((indiv_points+common_points+scale.points_to_add) / scale.total_points * (scale.max_grade-scale.min_grade) + scale.min_grade)*roundint).quantize(Decimal('1'),rounding=ROUND_HALF_UP) / roundint



                        if grade > scale.max_grade:
                            grade = scale.max_grade
                        if grade < scale.min_grade:
                            grade = scale.min_grade

                        all_grades.append(grade)

                        for i in [float(j) / 4 for j in range(4, 25, 1)]:
                            if grade == i:
                                distribution_list[int((i-1)*4)] += 1

                        # calculate grade by scale only on exam, not overall
                        if not exam.overall:
                            student_scale_grade = StudentScaleGrade()
                            student_scale_grade.student = student
                            student_scale_grade.scale = scale
                            student_scale_grade.grade = grade
                            student_scales_grades_list.append(student_scale_grade)

                # print(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")+" :  - student scales grades ok !")

                avg = 0
                med = 0
                std = 0
                if all_grades:
                    avg = mean(all_grades)
                    med = median(all_grades)
                    std = stdev(all_grades)
                scale_statistic = ScaleStatistic()
                scale_statistic.exam = exam
                scale_statistic.scale = scale
                scale_statistic.average = avg
                scale_statistic.stddev = std
                scale_statistic.median = med
                scale_statistic.section = 'global'
                scale_statistic.save()

                # if exam.overall:
                #     logger.info(distribution_list)
                #     logger.info(scale_statistic)

                i = 1
                for dist in distribution_list:
                    es_dist = ScaleDistribution()
                    es_dist.scale_statistic = scale_statistic
                    es_dist.grade = i-(i-1)+(i-1)*0.25
                    es_dist.quantity = dist
                    distribution_list_all.append(es_dist)
                    i += 1

                color_pos += 1

            ScaleDistribution.objects.bulk_create(distribution_list_all)
            StudentScaleGrade.objects.bulk_create(student_scales_grades_list)
            #print(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")+" :  - scales stats ok !")

            process_number += 1
            progress_recorder.set_progress(process_number, process_count,
                                           description='Generating stats for exam : ' + exam.code + '(questions & answers stats)')
            #Statistics on questions
            for question in question_list:
                answer_statistic_list = []
                #print(question.code+" - max points:"+str(question.max_points))
                if question.question_type.id == 4:
                    #print(" XXXXX ")
                    # print(question)
                    # print(str(discriminatory_count))
                    # print(exam)
                    #print(StudentQuestionAnswer.objects.filter(question=question,student__in=list(student_lower_list),student__present=True))
                    if exam.overall:
                        question.lower_avg = math.ceil(StudentQuestionAnswer.objects.filter(question__code=question.code, student__in=list(student_lower_list), student__present=True).aggregate(sum=Sum('points'))['sum'] / discriminatory_count * 100000) / 100000
                        question.upper_avg = math.ceil(StudentQuestionAnswer.objects.filter(question__code=question.code, student__in=list(student_upper_list), student__present=True).aggregate(sum=Sum('points'))['sum'] / discriminatory_count * 100000) / 100000
                    else:
                        question.lower_avg = math.ceil(StudentQuestionAnswer.objects.filter(question=question, student__in=list(student_lower_list), student__present=True).aggregate(sum=Sum('points'))['sum'] / discriminatory_count * 100000) / 100000
                        question.upper_avg = math.ceil(StudentQuestionAnswer.objects.filter(question=question, student__in=list(student_upper_list), student__present=True).aggregate(sum=Sum('points'))['sum'] / discriminatory_count * 100000) / 100000

                    if question.max_points>0:
                        question.di_calculation = math.ceil((Decimal(question.upper_avg)-Decimal(question.lower_avg)) / question.max_points*100000)/100000
                    else:
                        question.di_calculation = 0;
                else:
                    if exam.overall:
                        for comex in exam.common_exams.all():
                            if comex.questions.all():
                                q = Question.objects.get(code=question.code,exam=comex)
                                question.tot_answers += StudentQuestionAnswer.objects.filter(question=q, ticked__isnull=False, student__present=True).exclude(ticked__exact='').count()
                                question.upper_correct += StudentQuestionAnswer.objects.filter(question=q, ticked=q.correct_answer, student__in=list(student_upper_list), student__present=True).count()
                                question.lower_correct += StudentQuestionAnswer.objects.filter(question=q, ticked=q.correct_answer, student__in=list(student_lower_list), student__present=True).count()

                    else:
                        question.tot_answers = StudentQuestionAnswer.objects.filter(question=question, ticked__isnull=False).exclude(ticked__exact='').count()
                        question.upper_correct = StudentQuestionAnswer.objects.filter(question=question, ticked=question.correct_answer, student__in=list(student_upper_list), student__present=True).count()
                        question.lower_correct = StudentQuestionAnswer.objects.filter(question=question, ticked=question.correct_answer, student__in=list(student_lower_list), student__present=True).count()
                    # logger.info(exam)
                    # logger.info(discriminatory_count)
                    question.di_calculation = math.ceil((question.upper_correct-question.lower_correct)/discriminatory_count*100000)/100000

                question.discriminatory_factor = 27

                #Statistics on answers
                answers_stats = []
                if exam.overall:
                    q_list = []
                    for comex in exam.common_exams.all():
                        if comex.questions.all():
                            q = Question.objects.get(code=question.code,exam=comex)
                            q_list.append(q)
                    if q_list[0].question_type.id == 4:
                        answers_stats.extend(StudentQuestionAnswer.objects.filter(question__in=q_list, student__present=True).values('ticked', 'points').annotate(qty=Count('ticked')))
                    else:
                        answers_stats.extend(StudentQuestionAnswer.objects.filter(question__in=q_list, student__present=True).values('ticked').annotate(qty=Count('ticked'), points=Sum('points')))
                else:
                    if question.question_type.id == 4:
                        answers_stats = StudentQuestionAnswer.objects.filter(question=question, student__present=True).values('ticked', 'points').annotate(qty=Count('ticked'))
                    else:
                        answers_stats = StudentQuestionAnswer.objects.filter(question=question, student__present=True).values('ticked').annotate(qty=Count('ticked'), points=Sum('points'))


                for values in answers_stats:
                    #print(values)
                    answer_stat = AnswerStatistic()
                    if question.question_type.id == 4:
                        if not values['ticked']:
                            answer_stat.answer = 'NONE'
                        else:
                            answer_stat.answer = math.ceil(values['points']*1000)/1000
                    else:
                        answer_stat.answer = values['ticked']
                    #logger.info(answer_stat.answer)
                    answer_stat.quantity = values['qty']
                    answer_stat.rate = math.ceil( (answer_stat.quantity / exam.present_students * 100) * 1000) / 1000
                    answer_stat.question = question
                    answer_statistic_list.append(answer_stat)

                AnswerStatistic.objects.bulk_create(answer_statistic_list)
                question.remark = get_answer_remark_html(question, discriminatory_count)
                question.save()

            # specific common exam (by section, com VS ind)
            process_number += 1
            progress_recorder.set_progress(process_number, process_count,
                                           description='Generating stats for exam : ' + exam.code + '(overall stats)')
            if exam.overall:
                create_dist_stats_by_section(exam)
                create_stats_comVsInd(exam)

    except IntegrityError as e:
        print("error :"+e.message)

def get_answer_remark_html(question, di_ref):
    upp_percent = 0;
    di = (question.upper_correct - question.lower_correct) / di_ref
    if question.question_type.id == 4:
        max_answer_stat = AnswerStatistic.objects.filter(question=question).exclude(answer__exact='NONE').aggregate(max=Max('answer'))['max']
        if max_answer_stat is not None:
            max_answer_stat = float(max_answer_stat)
            #print(max_answer_stat)
            if max_answer_stat>0:
                upp_percent = 100 / Decimal(max_answer_stat) * Decimal(question.upper_avg)
            else:
                upp_percent = 0
    else:
        upp_percent = 100 / di_ref * question.upper_correct

    return_html = ''

    if upp_percent < 60:
        return_html += '<i class="fas fa-circle" style="font-size:18px;color:orange"></i>'
    elif question.lower_correct > question.upper_correct:
        return_html += '<i class="fas fa-circle" style="font-size:18px;color:red"></i>'
    elif question.di_calculation > 0.5:
        return_html += '<i class="fas fa-circle" style="font-size:18px;color:green"></i>'

    return return_html


def reset_statistics(exam):

    StudentScaleGrade.objects.filter(student__exam=exam).delete()
    AnswerStatistic.objects.filter(question__exam=exam).delete()
    ScaleStatistic.objects.filter(exam=exam).delete()
    ScaleDistribution.objects.filter(scale_statistic__exam=exam).delete()

    for question in exam.questions.all():
        question.discriminatory_factor = 0
        question.upper_correct = 0
        question.lower_correct = 0
        question.di_calculation = 0.0
        question.tot_answers =0
        question.remark = ''
        question.upper_avg = 0.0
        question.lower_avg = 0.0
        question.save()

    return True

def create_dist_stats_by_section(exam):
    grade_list = [Decimal(i) for i in [1, 1.25, 1.5, 1.75, 2, 2.25, 2.5, 2.75, 3, 3.25, 3.5, 3.75, 4, 4.25, 4.5, 4.75, 5, 5.25, 5.5, 5.75, 6]]

    dist_stats = []

    sections = Student.objects.filter(present=True,exam__in=exam.common_exams.all()).order_by().values('section').distinct()

    for scale in exam.scales.all():
        for section in sections:
            scale_stat, created = ScaleStatistic.objects.get_or_create(exam = exam, scale = scale, section = section.get('section'))

            # grades dist
            section_grades = StudentScaleGrade.objects.filter(scale__name=scale.name,student__present=True,student__section=section.get('section'),student__exam__in=exam.common_exams.all()).values('grade').order_by('grade').annotate(quantity=Count('grade'))
            section_grades_full = []
            for g in grade_list:
                scale_dist, created = ScaleDistribution.objects.get_or_create(scale_statistic=scale_stat, grade=g)
                g_value = 0
                for sg in section_grades:
                    if sg.get('grade') == Decimal(g):
                        g_value=sg.get('quantity')
                        break

                scale_dist.quantity = g_value;
                scale_dist.save()

            all_grades = StudentScaleGrade.objects.filter(scale__name=scale.name,student__present=True,student__section=section.get('section'),student__exam__in=exam.common_exams.all()).values_list('grade', flat=True).order_by('grade')
            #print(exam)
            #print(all_grades)

            if all_grades.count() > 1:
                # Average
                scale_stat.average = round(mean(all_grades),5)
                # Stddev
                scale_stat.stddev = round(median(all_grades),5)
                # Median
                scale_stat.median = round(stdev(all_grades),5)
            else:
                scale_stat.median = 0;
                # Average
                scale_stat.average = 0;
                # Stddev,
                scale_stat.stddev = 0;
                # Median

            # nb students
            scale_stat.section_nb_students = Student.objects.filter(section=section.get('section'),exam__in=exam.common_exams.all()).count()

            # presents and absents
            scale_stat.section_presents = Student.objects.filter(present=True,section=section.get('section'),exam__in=exam.common_exams.all()).count()
            scale_stat.save()

    return True

def create_stats_comVsInd(exam):

    sections = Student.objects.filter(present=True,exam__in=exam.common_exams.all()).order_by().values('section').distinct()

    for scale in exam.scales.all():
        com_rate = 0

        # stats by teacher
        for comex in exam.common_exams.all():

            stat, created = ComVsIndStatistic.objects.get_or_create(exam = comex, scale = scale, section ='')

            #common = 0
            #indiv = 0
            com_pts = 0
            ind_pts = 0
            com_pts = StudentQuestionAnswer.objects.values('student').order_by('student').annotate(sum_pts=Sum('points')).filter(student__present=True, student__exam=comex, question__common=True, sum_pts__gt=0).aggregate(sum_all=Sum('sum_pts')).get('sum_all')

            if not comex.indiv_formula:
                ind_pts = StudentQuestionAnswer.objects.values('student').order_by('student').annotate(sum_pts=Sum('points')).filter(student__present=True, student__exam=comex, question__common=False, sum_pts__gt=0).aggregate(sum_all=Sum('sum_pts')).get('sum_all')
            else:
                ind_pts = 0
                for s in comex.students.all():
                    stud_ind_points = 0
                    for sd in s.data.all():
                        if not sd.question.common:
                            stud_ind_points += sd.points

                    formula_arr = comex.indiv_formula.split(";")
                    ind_max_points = Decimal(formula_arr[0])
                    com_max_points = Decimal(formula_arr[1])
                    indiv_formula = formula_arr[2].replace("SIP",str(stud_ind_points)).replace("SCP",str(com_pts)).replace("IP",str(ind_max_points)).replace("CP",str(com_max_points))
                    stud_ind_points = Decimal(eval(indiv_formula))
                    if stud_ind_points>ind_max_points:
                        stud_ind_points=ind_max_points

                    ind_pts += stud_ind_points;

            com_rate = 0
            stat.global_avg_grade = 0
            stat.com_rate = 0
            stat.com_avg_pts = 0
            stat.com_avg_grade = 0

            if comex.present_students > 0 and com_pts and com_pts > 0:

                com_pts=Decimal(com_pts or 0)
                ind_pts=Decimal(ind_pts or 0)
                com_rate = Decimal(100/comex.get_max_points()*comex.get_common_points())

                stat.glob_avg_grade = round(clamp(((com_pts+ind_pts)/comex.present_students+scale.points_to_add)/scale.total_points*5+1,1,6),5)

                stat.com_rate = com_rate
                stat.com_avg_pts = round(com_pts/comex.present_students,5)
                stat.com_avg_grade = round(clamp((com_pts/comex.present_students+scale.points_to_add*com_rate/100)/(scale.total_points*com_rate/100)*5+1,1,6),5)
                if com_rate < 100:
                    stat.ind_avg_pts = round(ind_pts/comex.present_students,5)
                    stat.ind_avg_grade = round(clamp((ind_pts/comex.present_students+scale.points_to_add*(100-com_rate)/100)/(scale.total_points*(100-com_rate)/100)*5+1,1,6),5)
                else:
                    stat.ind_avg_pts = 0
                    stat.ind_avg_grade = 0

            stat.save()

        # stats by section
        for section in sections:

            stat, created = ComVsIndStatistic.objects.get_or_create(exam = exam, scale = scale, section = section.get('section'))

            common = 0
            indiv = 0
            com_pts = 0
            ind_pts = 0

            question_list = Question.objects.filter(exam__in=exam.common_exams.all()).distinct()

            section_presents = Student.objects.filter(exam__in=exam.common_exams.all(),section=section.get('section'),present=True).values('pk').aggregate(Count('pk')).get('pk__count')

            com_pts = StudentQuestionAnswer.objects.values('student').order_by('student').annotate(sum_pts=Sum('points')).filter(student__section=section.get('section'), student__present=True, student__exam__in=exam.common_exams.all(), question__common=True, sum_pts__gt=0).aggregate(sum_all=Sum('sum_pts')).get('sum_all')
            ind_pts = StudentQuestionAnswer.objects.values('student').order_by('student').annotate(sum_pts=Sum('points')).filter(student__section=section.get('section'), student__present=True, student__exam__in=exam.common_exams.all(), question__common=False, sum_pts__gt=0).aggregate(sum_all=Sum('sum_pts')).get('sum_all')
            com_pts=Decimal(com_pts or 0)
            ind_pts=Decimal(ind_pts or 0)
            #print(section)
            #print(com_pts)
            #print(ind_pts)

            stat.global_avg_grade = 0
            stat.com_rate = 0
            stat.com_avg_pts = 0
            stat.com_avg_grade = 0

            if com_pts and com_pts > 0 and com_rate > 0:
                stat.glob_avg_grade = round(clamp(((com_pts+ind_pts)/section_presents+scale.points_to_add)/scale.total_points*5+1,1,6),5)
                stat.com_rate = com_rate
                stat.com_avg_pts = round(com_pts/section_presents,5)
                stat.com_avg_grade = round(clamp(com_pts/(section_presents+scale.points_to_add)/(scale.total_points*com_rate/100)*5+1,1,6),5)

                if com_rate < 100 and com_rate > 0:
                    stat.ind_avg_pts = round(ind_pts/section_presents,5)
                    stat.ind_avg_grade = round(clamp(ind_pts/(section_presents+scale.points_to_add)/(scale.total_points*(100-com_rate)/100)*5+1,1,6),5)

            stat.save()

    return True

def get_comVsInd_correlation(exam):
    correlation_list = []

    for comex in exam.common_exams.all():
        #.values_list('points', flat=True)
        common_pts_list = StudentQuestionAnswer.objects.values('student').filter(student__in=comex.students.all(), student__present=True, question__common=True).order_by('student').annotate(sum=Sum('points', output_field=FloatField())).values_list('sum', flat=True)
        indiv_pts_list = StudentQuestionAnswer.objects.values('student').filter(student__in=comex.students.all(), student__present=True, question__common=False).order_by('student').annotate(sum=Sum('points', output_field=FloatField())).values_list('sum', flat=True)
        common_pts_list = list(common_pts_list)
        indiv_pts_list = list(indiv_pts_list)

        if len(common_pts_list)==len(indiv_pts_list):
            graph_data = []
            for i in range(len(common_pts_list)):
                graph_data.append([common_pts_list[i], indiv_pts_list[i]])

            r = np.corrcoef(common_pts_list, indiv_pts_list)[0,1]
            sample_size = len(common_pts_list)
            df = 2*sample_size-2
            tscore = r*np.sqrt(288)/np.sqrt(1-r**2)
            pvalue = stats.t.sf(abs(tscore), df=df)*2
            correlation_list.append([comex,r,tscore,"{0:.10E}".format(pvalue),graph_data])

    return correlation_list
