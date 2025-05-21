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

from examc_app.decorators import exam_permission_required
from examc_app.forms import ExportResultsForm
from examc_app.signing import make_token_for
from examc_app.utils.amc_functions import get_amc_catalog_pdf_path
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
#@login_required
@exam_permission_required(['manage','see_results'])
def update_student_present(request,exam_pk,student_pk,value):

    student = Student.objects.get(pk=student_pk)

    logger.info(value)

    if value == 1:
        student.present = True
        student.exam.present_students += 1
    else:
        student.present = False
        student.exam.present_students -= 1

    student.save()
    student.exam.save()

    exam = Exam.objects.get(pk=exam_pk)

    task = generate_statistics.delay(exam_pk)
    task_id = task.task_id

    return students_results_view(request,exam_pk=exam_pk,task_id=task_id)

    # generate_statistics(student.exam)
    #
    # return HttpResponse(1)

#@login_required
@exam_permission_required(['manage'])
def import_data_4_stats(request,exam_pk,task_id=None):
    exam = Exam.objects.get(pk=exam_pk)
    exam_selected = exam

    common_list = get_common_list(exam)

    if exam.is_overall():
        exam_selected = common_list[1]
        common_list.remove(exam)
    elif common_list:
        exam_selected = exam
        exam = common_list[0]
        if len(common_list) > 1:
            common_list.remove(exam)

    return render(request, 'res_and_stats/import_data.html',
                  {"user_allowed": user_allowed(exam,request.user.id),
                   "exam":exam,
                   "exam_selected":exam_selected,
                   "common_list":common_list,
                   "nav_url":'import_data_4_stats',
                   "task_id":task_id})

#@login_required
@exam_permission_required(['manage'])
def upload_amc_csv(request, exam_pk):
    csv_file = request.FILES["amc_csv_file"]
    temp_csv_file_name = "tmp_upload_amc_csv_"+datetime.datetime.now().strftime("%Y%m%d%H%M%S")+".csv"
    temp_csv_file_path = os.path.join(settings.AUTOUPLOAD_ROOT, temp_csv_file_name)

    os.makedirs(os.path.dirname(temp_csv_file_path), exist_ok=True)

    with open(temp_csv_file_path, 'wb') as temp_file:
        for chunk in csv_file.chunks():
            temp_file.write(chunk)

    task = import_csv_data.delay(temp_csv_file_path, exam_pk)
    task_id = task.task_id

    return import_data_4_stats(request,exam_pk,task_id)#redirect('../import_data_4_stats/' + str(exam.pk))

#@login_required
@exam_permission_required(['manage'])
def upload_catalog_pdf(request, exam_pk):
    exam = Exam.objects.get(pk=exam_pk)
    catalog = request.FILES["catalog_pdf_file"]

    filename = exam.code+'_'+str(exam.year.code)+'_'+str(exam.semester.code)+'_catalog.pdf'
    dest = str(settings.CATALOG_ROOT)+'/'+str(exam.year.code)+"/"+str(exam.semester.code)+'/'+exam.code+'_'+exam.date.strftime("%Y%m%d") +'/'
    dest += filename
    default_storage.delete(dest)
    default_storage.save(dest,ContentFile(catalog.read()))
    exam.pdf_catalog_name = filename
    exam.save()

    return redirect('../import_data_4_stats/' + str(exam.pk))

#@login_required
@exam_permission_required(['manage','see_results'])
def export_data(request,exam_pk):
    exam = Exam.objects.get(pk=exam_pk)
    exam_selected = exam
    common_list = get_common_list(exam)
    if exam.is_overall():
        exam_selected = common_list[1]
        common_list.remove(exam)
    elif common_list:
        exam_selected = exam
        exam = common_list[0]
        if len(common_list) > 1:
            common_list.remove(exam)

    if user_allowed(exam,request.user.id):

        if request.method == 'POST':

            if exam and exam.scaleStatistics:

                # delete old tmp folders and zips
                for filename in os.listdir(str(settings.EXPORT_TMP_ROOT)):
                    file_path = os.path.join(str(settings.EXPORT_TMP_ROOT), filename)
                    try:
                        if os.path.isfile(file_path) or os.path.islink(file_path):
                            os.unlink(file_path)
                        elif os.path.isdir(file_path):
                            shutil.rmtree(file_path)
                    except Exception as e:
                        print('Failed to delete %s. Reason: %s' % (file_path, e))

                form = ExportResultsForm(request.POST,exam=exam)
                logger.info(form)
                if form.is_valid():


                    scale_pk = form.cleaned_data['scale']
                    scale = Scale.objects.get(pk=scale_pk)

                    common_exams = []
                    if exam.overall:
                        common_exams = form.cleaned_data['common_exams']
                    else:
                        common_exams.append(exam.pk)

                    isaCsv = form.cleaned_data['exportIsaCsv']
                    scalePdf = form.cleaned_data['exportExamScalePdf']
                    studentDataCsv = form.cleaned_data['exportStudentsDataCsv']

                    # create tmp folder
                    export_folder_name = "export_"+str(datetime.datetime.now().strftime("%d%m%y_%H%M%S"))
                    export_path = str(settings.EXPORT_TMP_ROOT)+"/"+export_folder_name
                    os.makedirs(export_path, exist_ok=True)
                    logger.info(os.path.dirname(export_path))

                    for exam_id in common_exams:
                        exam = Exam.objects.get(pk=exam_id)
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
                    #return HttpResponseRedirect(request.path_info)
                else:
                    logger.info("INVALID")
                    logger.info(form.errors)
                    return HttpResponseRedirect(request.path_info)

        # if a GET (or any other method) we'll create a blank form
        else:
            if exam and exam.scaleStatistics:
                form = ExportResultsForm(exam=exam)
            else:
                form = ExportResultsForm()

            return render(request, 'res_and_stats/export_results.html', {"user_allowed":True,
                                                          "form": form,
                                                          "exam" : exam,
                                                         "exam_selected" : exam_selected,
                                                          "common_list":common_list,
                                                          "nav_url": "export_data"})
    else:
        return render(request, 'res_and_stats/export_results.html', {"user_allowed":False,
                                                      "form": None,
                                                      "exam" : exam,
                                                         "exam_selected" : exam_selected,
                                                      "common_list":None,
                                                      "nav_url": "export_data"})

    return HttpResponse(None)

# STATISTICS
# ------------------------------------------
#@login_required
@exam_permission_required(['manage','see_results'])
def generate_stats(request, exam_pk):
    exam = Exam.objects.get(pk=exam_pk)
    #generate_statistics(exam)

    task = generate_statistics.delay(exam.pk)
    task_id = task.task_id

    # if not result == True:
    #     messages.error(request, "Unable to upload file. " + result)

    return HttpResponseRedirect(reverse('examInfo', kwargs={'pk': exam_pk, 'task_id': task_id}))
    #return redirect('../examInfo/' + str(exam.pk))

#@login_required
@exam_permission_required(['manage','see_results'])
def general_statistics_view(request,exam_pk):
    exam = Exam.objects.get(pk=exam_pk)
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
                           "exam_selected": currexam,
                           "grade_list": grade_list,
                           "absent": sum_all_students - currexam.present_students,
                           "common_list": common_list,
                           "correlation_list":correlation_list,
                           "nav_url": "generalStats"})
        else:
            return render(request, "res_and_stats/general_statistics.html",
                          {"user_allowed":True,"exam": exam, "grade_list": None, "absent": 0,"nav_url": "generalStats"})

    else:
        return render(request, "res_and_stats/general_statistics.html",
                      {"user_allowed":False,"scaleStatistics": None, "grade_list": None, "absent": 0,"nav_url": "generalStats"})


#@login_required
@exam_permission_required(['manage','see_results'])
def students_results_view(request, exam_pk, task_id=None):
    exam = Exam.objects.get(pk=exam_pk)
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
                           "exam_selected" : currexam,
                           "nav_url": "studentsResults",
                           "task_id":task_id})
        else:
            return render(request, "res_and_stats/students_results.html", {"user_allowed":True, "scales": None, "students": None,"nav_url": "studentsResults"})
    else:
        return render(request, "res_and_stats/students_results.html", {"user_allowed":False, "scales": None, "students": None,"nav_url": "studentsResults"})


#@login_required
@exam_permission_required(['manage','see_results'])
def questions_statistics_view(request,exam_pk):
    exam = Exam.objects.get(pk=exam_pk)
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
                           "exam_selected" : currexam,
                           "discriminatory_factor": discriminatory_factor, "discriminatory_qty": discriminatory_qty,
                           "mcq_questions": mcq_questions,
                           "open_questions": open_questions,
                           "questionsStatsByTeacher": question_stat_by_teacher_list,
                           "common_list" : common_list,
                           "nav_url": "questionsStats"})
        else:
            return render(request, "res_and_stats/questions_statistics.html",
                          {"user_allowed":True,"exam": exam,"discriminatory_factor": None, "discriminatory_qty": None, "questions": None,"nav_url": "questionsStats"})
    else:
        return render(request, "res_and_stats/questions_statistics.html",
                      {"user_allowed":False,"exam": exam,"discriminatory_factor": None, "discriminatory_qty": None, "questions": None,"nav_url": "questionsStats"})


# PDF
# ------------------------------------------
@xframe_options_exempt
#@login_required
@exam_permission_required(['manage','see_results'])
def display_catalog(request, exam_pk):
    exam = Exam.objects.get(pk=exam_pk)
    if exam.is_overall():
        exam = exam.common_exams.all().first()
    cat_name = exam.code + '_' + str(exam.year.code) + '_' + str(exam.semester.code) + '_catalog.pdf'
    cat_url = str(exam.year.code)+"/"+str(exam.semester.code)+'/'+exam.code+'_'+exam.date.strftime("%Y%m%d") +'/'+cat_name
    cat_path = str(settings.CATALOG_ROOT)+'/'+cat_url
    if not os.path.exists(cat_path):
      #try to find it in amc dir
      cat_path = get_amc_catalog_pdf_path(exam)
    try:
        response = FileResponse(open(cat_path, 'rb'), content_type='application/pdf')
        return response
    except FileNotFoundError:
        raise HttpResponse("No catalog found !")

## TESTING
