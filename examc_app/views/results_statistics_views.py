import zipfile
from pathlib import Path

import requests
import shutil

from datetime import datetime
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, Http404, FileResponse, HttpResponseRedirect
from django.contrib import messages
from django.shortcuts import render
from django.shortcuts import redirect

from examc_app.forms import ExportResultsForm

from django.db.models.functions import Cast

from examc_app.utils.generate_statistics_functions import *
from examc_app.utils.global_functions import user_allowed
from examc_app.utils.results_statistics_functions import *
from userprofile.models import *

# Get an instance of a logger
logger = logging.getLogger(__name__)


# QUESTIONS MANAGEMENT
# ------------------------------------------
@login_required
def update_question(request):
    question = Question.objects.get(pk=request.POST['pk'])
    field_name = request.POST['field']
    value = request.POST['value']

    setattr(question, field_name, value)
    question.save()

    return HttpResponse(1)

# STUDENTS MANAGEMENT
@login_required
def update_student_present(request):

    student = Student.objects.get(pk=request.POST['pk'])
    value = request.POST['value']

    logger.info(value)

    if value == "1":
        student.present = True
        student.exam.present_students += 1
    else:
        student.present = False
        student.exam.present_students -= 1

    student.save()
    student.exam.save()

    EXAM = Exam.objects.get(pk=student.exam.pk)

    generate_statistics(student.exam)

    return HttpResponse(1)
@login_required
def import_data_4_stats(request,pk):
    exam = Exam.objects.get(pk=pk)
    return render(request, 'res_and_stats/import_data.html',
                  {"user_allowed": user_allowed(exam,request.user.id),"exam":exam })

@login_required
def upload_amc_csv(request, pk):
    exam = Exam.objects.get(pk=pk)
    result = import_csv_data(request.FILES["amc_csv_file"], exam)

    if not result == True:
        messages.error(request, "Unable to upload file. " + result)

    return redirect('../examInfo/' + str(exam.pk))

@login_required
def upload_catalog_pdf(request, pk):
    exam = Exam.objects.get(pk=pk)
    catalog = request.FILES["catalog_pdf_file"]

    filename = exam.code+'_'+str(exam.year)+'_'+str(exam.semester)+'_catalog.pdf'
    dest = str(settings.CATALOG_ROOT)+'/'+str(exam.year)+"/"+str(exam.semester)+'/'+exam.code+'/'
    dest += filename
    default_storage.delete(dest)
    default_storage.save(dest,ContentFile(catalog.read()))
    exam.pdf_catalog_name = filename
    exam.save()

    return redirect('../examInfo/' + str(exam.pk))

@login_required
def export_data(request,pk):
    EXAM = Exam.objects.get(pk=pk)

    if user_allowed(EXAM,request.user.id):

        if request.method == 'POST':

            if EXAM and EXAM.scaleStatistics:

                # delete old tmp folders and zips
                for filename in os.listdir(str(settings.EXPORT_FOLDER)):
                    file_path = os.path.join(str(settings.EXPORT_FOLDER), filename)
                    try:
                        if os.path.isfile(file_path) or os.path.islink(file_path):
                            os.unlink(file_path)
                        elif os.path.isdir(file_path):
                            shutil.rmtree(file_path)
                    except Exception as e:
                        print('Failed to delete %s. Reason: %s' % (file_path, e))

                form = ExportResultsForm(request.POST,exam=EXAM)
                logger.info(form)
                if form.is_valid():


                    scale_pk = form.cleaned_data['scale']
                    scale = Scale.objects.get(pk=scale_pk)

                    common_exams = []
                    if EXAM.overall:
                        common_exams = form.cleaned_data['common_exams']
                    else:
                        common_exams.append(EXAM.pk)

                    isaCsv = form.cleaned_data['exportIsaCsv']
                    scalePdf = form.cleaned_data['exportExamScalePdf']
                    studentDataCsv = form.cleaned_data['exportStudentsDataCsv']

                    # create tmp folder
                    export_folder_name = "export_"+str(datetime.datetime.now().strftime("%d%m%y_%H%M%S"))
                    export_path = str(settings.EXPORT_FOLDER)+"/"+export_folder_name
                    os.makedirs(export_path, exist_ok=True)
                    logger.info(os.path.dirname(export_path))

                    for exam_pk in common_exams:
                        exam = Exam.objects.get(pk=exam_pk)
                        if isaCsv:
                            generate_isa_csv(exam,scale,export_path)
                        if scalePdf:
                            generate_scale_pdf(exam,scale,export_path)
                        if studentDataCsv:
                            generate_students_data_csv(exam,export_path)

                    # zip folder
                    zipf = zipfile.ZipFile(export_path+".zip", 'w', zipfile.ZIP_DEFLATED)
                    zipdir(export_path, zipf)
                    zipf.close()

                    zip_file = open(export_path+".zip", 'rb')
                    return FileResponse(zip_file)

                    # process the data in form.cleaned_data as required
                    # ...
                    # redirect to a new URL:
                    return HttpResponseRedirect(request.path_info)
                else:
                    logger.info("INVALID")
                    logger.info(form.errors)
                    return HttpResponseRedirect(request.path_info)

        # if a GET (or any other method) we'll create a blank form
        else:
            common_list = get_common_list(EXAM)
            if EXAM and EXAM.scaleStatistics:
                form = ExportResultsForm(exam=EXAM)
            else:
                form = ExportResultsForm()

            return render(request, 'res_and_stats/export_results.html', {"user_allowed":True,
                                                          "form": form,
                                                          "exam" : EXAM,
                                                          "common_list":common_list,
                                                          "current_url": "export_data"})
    else:
        return render(request, 'res_and_stats/export_results.html', {"user_allowed":False,
                                                      "form": None,
                                                      "exam" : EXAM,
                                                      "common_list":None,
                                                      "current_url": "export_data"})

# STATISTICS
# ------------------------------------------
@login_required
def generate_stats(request, pk):
    exam = Exam.objects.get(pk=pk)
    generate_statistics(exam)

    return redirect('../examInfo/' + str(exam.pk))

@login_required
def general_statistics_view(request,pk):
    exam = Exam.objects.get(pk=pk)

    if user_allowed(exam,request.user.id):

        if exam and exam.scaleStatistics:
            grade_list = [1, 1.25, 1.5, 1.75, 2, 2.25, 2.5, 2.75, 3, 3.25, 3.5, 3.75, 4, 4.25, 4.5, 4.75, 5, 5.25, 5.5,
                          5.75, 6]

            common_list = get_common_list(exam)

            sum_all_students = len(exam.students.all())
            correlation_list = []

            if exam.overall:
                sum_all_students = exam.get_sum_common_students()
                correlation_list = get_comVsInd_correlation(exam)

            return render(request, "res_and_stats/general_statistics.html",
                          {"user_allowed":True,
                           "exam" : exam,
                           "grade_list": grade_list,
                           "absent": sum_all_students - exam.present_students,
                           "common_list": common_list,
                           "correlation_list":correlation_list,
                           "current_url": "generalStats"})
        else:
            return render(request, "res_and_stats/general_statistics.html",
                          {"user_allowed":True,"exam": exam, "grade_list": None, "absent": 0})

    else:
        return render(request, "res_and_stats/general_statistics.html",
                      {"user_allowed":False,"scaleStatistics": None, "grade_list": None, "absent": 0})


@login_required
def students_statistics_view(request,pk):
    EXAM = Exam.objects.get(pk=pk)

    if user_allowed(EXAM,request.user.id):
        if EXAM and EXAM.scaleStatistics:

            common_list = get_common_list(EXAM)
            students = Exam.objects.none()

            if EXAM.overall:
                for com_exam in EXAM.common_exams.all():

                    students = students | com_exam.students.all()

                students = sorted(students, key=operator.attrgetter('name'))
            else:
                students = EXAM.students.all()

            return render(request, "res_and_stats/students_statistics.html",
                          {"user_allowed":True,
                           "exam" : EXAM,
                           "students" : students,
                           "common_list": common_list,
                           "current_url": "studentsStats"})
        else:
            return render(request, "res_and_stats/students_statistics.html", {"user_allowed":True,"scales": None, "students": None})
    else:
        return render(request, "res_and_stats/students_statistics.html", {"user_allowed":False,"scales": None, "students": None})


@login_required
def questions_statistics_view(request,pk):
    EXAM = Exam.objects.get(pk=pk)

    if user_allowed(EXAM,request.user.id):

        if EXAM and EXAM.scaleStatistics.all() and EXAM.questions.all():
            discriminatory_factor = Question.objects.filter(exam=EXAM)[0].discriminatory_factor
            discriminatory_qty = round(EXAM.present_students * discriminatory_factor / 100)

            question_stat_by_teacher_list = []

            if EXAM.overall:
                question_stat_by_teacher_list = get_questions_stats_by_teacher(EXAM)

            return render(request, "res_and_stats/questions_statistics.html",
                          {"user_allowed":True,"exam": EXAM,"discriminatory_factor": discriminatory_factor, "discriminatory_qty": discriminatory_qty,
                           "mcq_questions": Question.objects.filter(exam=EXAM).exclude(qtype=4),
                           "open_questions": Question.objects.filter(exam=EXAM,qtype=4),
                           "questionsStatsByTeacher": question_stat_by_teacher_list,
                           "common_list" : get_common_list(EXAM),
                           "current_url": "questionsStats"})
        else:
            return render(request, "res_and_stats/questions_statistics.html",
                          {"user_allowed":True,"exam": EXAM,"discriminatory_factor": None, "discriminatory_qty": None, "questions": None})
    else:
        return render(request, "res_and_stats/questions_statistics.html",
                      {"user_allowed":False,"exam": EXAM,"discriminatory_factor": None, "discriminatory_qty": None, "questions": None})


# PDF
# ------------------------------------------
@login_required
def display_catalog(request, pk):
    exam = Exam.objects.get(pk=pk)
    cat_name = exam.code + '_' + str(exam.year) + '_' + str(exam.semester) + '_catalog.pdf'
    cat_path = str(settings.CATALOG_ROOT)+'/'+str(exam.year)+"/"+str(exam.semester)+'/'+exam.code+'/'+cat_name
    try:
        return FileResponse(open(cat_path, 'rb'), content_type='application/pdf')
    except FileNotFoundError:
        raise Http404('not found')

# other
# -----------------------------------------
#@login_required
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

    com_questions = Question.objects.filter(common=True,exam=exam)

    for question in com_questions:
        question_stat = {'question':question}
        teacher_list = []

        for comex in exam.common_exams.all():
            teacher = {'teacher':comex.primary_user.last_name.replace("-","_")}

            section_list = Student.objects.filter(present=True,exam=comex).values_list('section', flat=True).order_by().distinct()
            teacher.update({'sections':section_list})

            answer_list = StudentQuestionAnswer.objects.filter(student__exam=comex, student__present=True, question__code=question.code).values('ticked').order_by('ticked').annotate(percent=Cast(100 / comex.present_students * Count('ticked'), FloatField()))

            na_answers = 0
            new_answer_list = []
            for answer in answer_list.iterator():
                if answer.get('ticked') == '' or (question.qtype == 1 and len(answer.get('ticked')) > 1):
                    na_answers += comex.present_students*answer.get('percent')/100
                else:
                    new_answer_list.append({'ticked':answer.get('ticked'),'percent':answer.get('percent')})

            new_answer_list.append({'ticked':'NA','percent':100/comex.present_students*na_answers})


            teacher.update({'answers':new_answer_list})

            teacher_list.append(teacher)

        question_stat.update({'teachers':teacher_list})
        question_stat_list.append(question_stat)

    return question_stat_list
