import operator
import shutil
import zipfile
from datetime import datetime

from django.contrib.auth.decorators import login_required
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.db.models.functions import Cast
from django.http import HttpResponse, Http404, FileResponse, HttpResponseRedirect, JsonResponse
from django.shortcuts import redirect
from django.shortcuts import render
from django.urls import reverse
from django.views.decorators.clickjacking import xframe_options_exempt

from examc_app.forms import ExportResultsForm
from examc_app.utils.generate_statistics_functions import *
from examc_app.utils.global_functions import user_allowed
from examc_app.utils.results_statistics_functions import *
from examc_app.views import ExamInfoView
from userprofile.models import *

## testing
from examc_app.tasks import import_csv_data, generate_statistics

# Get an instance of a logger
logger = logging.getLogger(__name__)


# STUDENTS MANAGEMENT
@login_required
def update_student_present(request,pk,value):

    student = Student.objects.get(pk=pk)

    logger.info(value)

    if value == 1:
        student.present = True
        student.exam.present_students += 1
    else:
        student.present = False
        student.exam.present_students -= 1

    student.save()
    student.exam.save()

    exam = Exam.objects.get(pk=student.exam.pk)

    task = generate_statistics.delay(student.exam.pk)
    task_id = task.task_id

    return students_results_view(request,student.exam.pk,task_id)

    # generate_statistics(student.exam)
    #
    # return HttpResponse(1)

@login_required
def import_data_4_stats(request,pk,task_id=None):
    exam = Exam.objects.get(pk=pk)
    currexam = exam

    common_list = get_common_list(exam)

    if exam.is_overall():
        currexam = common_list[1]
        common_list.remove(exam)
    elif common_list:
        currexam = exam
        exam = common_list[0]
        if len(common_list) > 1:
            common_list.remove(exam)

    return render(request, 'res_and_stats/import_data.html',
                  {"user_allowed": user_allowed(exam,request.user.id),
                   "exam":exam,
                   "currselected_exam":currexam,
                   "common_list":common_list,
                   "task_id":task_id})

@login_required
def upload_amc_csv(request, pk):
    csv_file = request.FILES["amc_csv_file"]
    temp_csv_file_name = "tmp_upload_amc_csv_"+datetime.datetime.now().strftime("%Y%m%d%H%M%S")+".csv"
    temp_csv_file_path = os.path.join(settings.AUTOUPLOAD_ROOT, temp_csv_file_name)

    os.makedirs(os.path.dirname(temp_csv_file_path), exist_ok=True)

    with open(temp_csv_file_path, 'wb') as temp_file:
        for chunk in csv_file.chunks():
            temp_file.write(chunk)

    task = import_csv_data.delay(temp_csv_file_path, pk)
    task_id = task.task_id

    # if not result == True:
    #     messages.error(request, "Unable to upload file. " + result)

    return import_data_4_stats(request,pk,task_id)#redirect('../import_data_4_stats/' + str(exam.pk))

@login_required
def upload_catalog_pdf(request, pk):
    exam = Exam.objects.get(pk=pk)
    catalog = request.FILES["catalog_pdf_file"]

    filename = exam.code+'_'+str(exam.year.code)+'_'+str(exam.semester.code)+'_catalog.pdf'
    dest = str(settings.CATALOG_ROOT)+'/'+str(exam.year.code)+"/"+str(exam.semester.code)+'/'+exam.code+'/'
    dest += filename
    default_storage.delete(dest)
    default_storage.save(dest,ContentFile(catalog.read()))
    exam.pdf_catalog_name = filename
    exam.save()

    return redirect('../import_data_4_stats/' + str(exam.pk))

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
    #generate_statistics(exam)

    task = generate_statistics.delay(exam.pk)
    task_id = task.task_id

    # if not result == True:
    #     messages.error(request, "Unable to upload file. " + result)

    return HttpResponseRedirect(reverse('examInfo', kwargs={'pk': pk, 'task_id': task_id}))
    #return redirect('../examInfo/' + str(exam.pk))

@login_required
def general_statistics_view(request,pk):
    exam = Exam.objects.get(pk=pk)
    currexam = exam

    if user_allowed(exam,request.user.id):

        if exam and exam.scaleStatistics:
            grade_list = [1, 1.25, 1.5, 1.75, 2, 2.25, 2.5, 2.75, 3, 3.25, 3.5, 3.75, 4, 4.25, 4.5, 4.75, 5, 5.25, 5.5,
                          5.75, 6]

            common_list = get_common_list(exam)

            if common_list:
                currexam = exam
                exam = common_list[0]

            sum_all_students = len(currexam.students.all())
            correlation_list = []

            if currexam.overall:
                sum_all_students = currexam.get_sum_common_students()
                correlation_list = get_comVsInd_correlation(currexam)

            return render(request, "res_and_stats/general_statistics.html",
                          {"user_allowed":True,
                           "exam" : exam,
                           "currselected_exam": currexam,
                           "grade_list": grade_list,
                           "absent": sum_all_students - currexam.present_students,
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
def students_results_view(request, pk, task_id=None):
    exam = Exam.objects.get(pk=pk)
    currexam = exam

    if user_allowed(exam,request.user.id):
        if exam and exam.scaleStatistics:
            common_list = get_common_list(exam)

            if exam.is_overall():
                currexam = common_list[1]
                common_list.remove(exam)
            elif common_list:
                currexam = exam
                exam = common_list[0]
                if len(common_list) > 1:
                    common_list.remove(exam)

            return render(request, "res_and_stats/students_results.html",
                          {"user_allowed":True,
                           "exam" : exam,
                           "common_list": common_list,
                           "currselected_exam" : currexam,
                           "current_url": "studentsResults",
                           "task_id":task_id})
        else:
            return render(request, "res_and_stats/students_results.html", {"user_allowed":True, "scales": None, "students": None})
    else:
        return render(request, "res_and_stats/students_results.html", {"user_allowed":False, "scales": None, "students": None})


@login_required
def questions_statistics_view(request,pk):
    exam = Exam.objects.get(pk=pk)
    currexam = exam

    if user_allowed(exam,request.user.id):

        if exam and exam.scaleStatistics.all() and exam.questions.all():

            common_list = get_common_list(exam)

            if common_list:
                currexam = exam
                exam = common_list[0]

            discriminatory_factor = Question.objects.filter(exam=currexam)[0].discriminatory_factor
            discriminatory_qty = round(currexam.present_students * discriminatory_factor / 100)

            question_stat_by_teacher_list = []

            if currexam.overall:
                question_stat_by_teacher_list = get_questions_stats_by_teacher(currexam)

            mcq_questions = Question.objects.filter(exam=currexam).exclude(question_type__id=4)
            open_questions = Question.objects.filter(exam=currexam,question_type__id=4)

            for question in open_questions.all():
                print(question)

            return render(request, "res_and_stats/questions_statistics.html",
                          {"user_allowed":True,
                           "exam": exam,
                           "currselected_exam" : currexam,
                           "discriminatory_factor": discriminatory_factor, "discriminatory_qty": discriminatory_qty,
                           "mcq_questions": mcq_questions,
                           "open_questions": open_questions,
                           "questionsStatsByTeacher": question_stat_by_teacher_list,
                           "common_list" : common_list,
                           "current_url": "questionsStats"})
        else:
            return render(request, "res_and_stats/questions_statistics.html",
                          {"user_allowed":True,"exam": exam,"discriminatory_factor": None, "discriminatory_qty": None, "questions": None})
    else:
        return render(request, "res_and_stats/questions_statistics.html",
                      {"user_allowed":False,"exam": exam,"discriminatory_factor": None, "discriminatory_qty": None, "questions": None})


# PDF
# ------------------------------------------
@xframe_options_exempt
@login_required
def display_catalog(request, pk):
    exam = Exam.objects.get(pk=pk)
    cat_name = exam.code + '_' + str(exam.year.code) + '_' + str(exam.semester.code) + '_catalog.pdf'
    cat_path = str(settings.CATALOG_ROOT)+'/'+str(exam.year.code)+"/"+str(exam.semester.code)+'/'+exam.code+'/'+cat_name
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



## TESTING
