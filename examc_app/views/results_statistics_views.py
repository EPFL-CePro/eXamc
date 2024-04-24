import zipfile
from pathlib import Path

import requests
import shutil

from datetime import datetime
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile

from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.urls import reverse
from django.http import HttpResponse, Http404, FileResponse, HttpRequest, HttpResponseRedirect
from django.contrib import messages
from django.shortcuts import render
from django.shortcuts import redirect
from django_tables2 import SingleTableView
from django.views.generic import DetailView
from django.views.generic.edit import CreateView

from examc_app.forms import ExportResultsForm
from examc_app.tables import ExamSelectTable

from django.db.models.functions import Cast

from examc_app.utils.generate_statistics_functions import *
from examc_app.utils.global_functions import user_allowed
from examc_app.utils.results_statistics_functions import *
from userprofile.models import *

# Get an instance of a logger
logger = logging.getLogger(__name__)

# GLOBAL VARIABLES
# ------------------------------------------
global EXAM
EXAM = None

global CATALOG_STORAGE
CATALOG_STORAGE = "examstats_app/pdfs/"

### admin views ###
@login_required
def getCommonExams(request, pk):
    update_common_exams(pk)

    return HttpResponseRedirect("../admin/examstats_app/exam/")

### app views ###

# to check to implement complete logout (like sesame.epfl)
@login_required
def logout(request):
    response = requests.get("https://tequila.epfl.ch/logout")
    return redirect(settings.LOGIN_URL)

#@login_required
def index(request):
    user_info = request.user.__dict__
    if request.user.is_authenticated:
        user_info.update(request.user.__dict__)
        return redirect('./home')
    else:
        return render(request, 'index.html')

@login_required
def home(request):
    user_info = request.user.__dict__
    if request.user.is_authenticated:
        user_info.update(request.user.__dict__)
        return render(request, 'home.html', {
            'user': request.user,
            'user_info': user_info,
        })

# CLASSES
# ------------------------------------------
@method_decorator(login_required, name='dispatch')
class ExamSelectView(SingleTableView):
    model = Exam
    template_name = 'exam/exam_select.html'
    table_class = ExamSelectTable
    table_pagination = False

    def get_queryset(self):
        qs = Exam.objects.filter(overall=False)
        if not self.request.user.is_superuser:
            qs = qs.filter(Q(users__id=self.request.user.id))
        return qs


@method_decorator(login_required, name='dispatch')
class ScaleCreateView(CreateView):
    template_name = 'scale/scale_create.html'
    model = Scale
    fields = ['name', 'total_points', 'points_to_add', 'min_grade','max_grade','rounding']#,'formula']

    def form_valid(self, form):
        scale = form.save(commit=False)
        scale.save()
        EXAM.scales.add(scale)
        EXAM.save()

        for comex in EXAM.common_exams.all():
            scale_comex, created = Scale.objects.get_or_create(exam=comex,name = scale.name,total_points=scale.total_points)
            if created:
                scale_comex.total_points = scale.total_points
                scale_comex.points_to_add = scale.points_to_add
                scale_comex.min_grade = scale.min_grade
                scale_comex.max_grade = scale.max_grade
                scale_comex.rounding = scale.rounding
                scale_comex.formula = scale.formula
                scale_comex.save()

        generate_statistics(EXAM)
        return redirect('./examInfo/' + str(EXAM.pk))


@method_decorator(login_required, name='dispatch')
class ExamInfoView(DetailView):
    model = Exam
    template_name = 'exam/exam_info.html'

    def get_context_data(self, **kwargs):
        context = super(ExamInfoView, self).get_context_data(**kwargs)

        global EXAM
        EXAM = Exam.objects.get(pk=context.get("object").id)

        if user_allowed(EXAM,self.request.user.id):
            context['user_allowed'] = True
            context['common_list'] = get_common_list(EXAM)
            context['current_url'] = "examInfo"
            context['sum_questions_points'] = EXAM.questions.all().aggregate(Sum('max_points'))
            return context
        else:
            context['user_allowed'] = False
            return context

# HOME
# ------------------------------------------
@login_required
def home_view(request):

    request.session['exam_pk'] = Exam.objects.first().pk

    return render(request, "home.html")


# EXAM MANAGEMENT
# ------------------------------------------
@login_required
def select_exam(request, pk, current_url=None):

    global EXAM
    EXAM = Exam.objects.get(pk=pk)
    # exam = Exam.objects.get(pk=pk)
    request.session['exam_pk'] = EXAM.pk


    # if len(EXAM.scalesStatistics.all()) == 0:
    #     generate_statistics(EXAM)

    url_string = '../'
    if current_url is None:
        return HttpResponseRedirect( reverse('examInfo', kwargs={'pk':str(pk)}))
    else:
        return HttpResponseRedirect( reverse(current_url, kwargs={'pk':str(pk)}) )

@login_required
def select_exam_scale(request, scale_pk):
    scale_to_add = Scale.objects.get(pk=scale_pk)
    exam_to_add_scale = Exam.objects.get(pk=EXAM.pk)

    exam_to_add_scale.scales.add(scale_to_add)
    generate_statistics(EXAM)

    return redirect('../examInfo/' + str(EXAM.pk))


@login_required
def delete_exam_scale(request, scale_pk, exam_pk):
    EXAM.pk

    scale_to_delete = Scale.objects.get(pk=scale_pk)
    exam_to_manage = Exam.objects.get(pk=exam_pk)

    exam_to_manage.scales.remove(scale_to_delete)
    exam_to_manage.save()

    scale_to_delete.delete()

    # delete scale in other commons
    for comex in exam_to_manage.common_exams.all():
        scale_to_del_comex = Scale.objects.filter(exam__pk=comex.pk, name=scale_to_delete.name).first()
        if scale_to_del_comex:
            comex.scales.remove(scale_to_del_comex)
            comex.save()
            scale_to_del_comex.delete()

    generate_statistics(EXAM)

    return redirect('../../examInfo/' + str(exam_pk))


@login_required
def update_exam(request):
    exam = Exam.objects.get(pk=request.POST['pk'])
    field_name = request.POST['field']
    value = request.POST['value']

    setattr(exam, field_name, value)
    exam.save()

    global DATA_UPDATED
    DATA_UPDATED = True

    return HttpResponse(1)


# SCALE MANAGEMENT
# ------------------------------------------
@login_required
def delete_scale(request, pk):
    scale = Scale.objects.get(id=pk)

    for comex in scale.exam.common_exams.all():
        for comex_scale in comex.scales.all():
            if comex_scale.name == scale.name:
                comex_scale.delete()

    scale.delete()

    generate_statistics(EXAM)

    return redirect('../examInfo/' + str(EXAM.pk))

@login_required
def set_final_scale(request, pk):
    scale = Scale.objects.get(id=pk)
    scale.final = True
    scale.save()

    for comex in scale.exam.common_exams.all():
        for comex_scale in comex.scales.all():
            if comex_scale.name == scale.name:
                comex_scale.final = False
                comex_scale.save()

    return redirect('../examInfo/' + str(scale.exam.pk))



# QUESTIONS MANAGEMENT
# ------------------------------------------
@login_required
def update_question(request):
    question = Question.objects.get(pk=request.POST['pk'])
    field_name = request.POST['field']
    value = request.POST['value']

    setattr(question, field_name, value)
    question.save()

    #generate_statistics(question.exam)

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

# DATA UPLOAD
# ------------------------------------------
# @login_required
# def upload_data(request):
#     result = import_data(request.FILES["zip_file"])
#
#     if not result == True:
#         messages.error(request, "Unable to upload file. " + result)
#
#     return redirect('/')

@login_required
def import_exams(request):
    result = import_exams_csv(request.FILES["exams_csv_file"])

    if not result == True:
        messages.error(request, "Unable to upload file. " + result)

    return redirect('/')

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
    # default_storage.delete(CATALOG_STORAGE + catalog.name)
    #file_name = default_storage.save(CATALOG_STORAGE + catalog.name, catalog)
    # exam.pdf_catalog_name = file_name
    # exam.save()

    dest = str(settings.PDF_FOLDER)+'/'
    teacher = UserProfile.objects.get(user=exam.primary_user)
    filename = exam.code+'_'+str(teacher.sciper)+'_'+str(exam.year)+'_'+str(exam.semester)+'.pdf'
    dest += filename
    logger.info(catalog)
    logger.info(dest)
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

            if EXAM and EXAM.scalesStatistics:

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
            if EXAM and EXAM.scalesStatistics:
                form = ExportResultsForm(exam=EXAM)
            else:
                form = ExportResultsForm()

            return render(request, 'export/export.html', {"user_allowed":True,
                                                          "form": form,
                                                          "exam" : EXAM,
                                                          "common_list":common_list,
                                                          "current_url": "export_data"})
    else:
        return render(request, 'export/export.html', {"user_allowed":False,
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
    EXAM = Exam.objects.get(pk=pk)

    if user_allowed(EXAM,request.user.id):

        if EXAM and EXAM.scalesStatistics:
            grade_list = [1, 1.25, 1.5, 1.75, 2, 2.25, 2.5, 2.75, 3, 3.25, 3.5, 3.75, 4, 4.25, 4.5, 4.75, 5, 5.25, 5.5,
                          5.75, 6]

            common_list = get_common_list(EXAM)

            sum_all_students = len(EXAM.students.all())

            # section_dist_stat_list = []
            comVsInd_stat_list = []
            correlation_list = []

            if EXAM.overall:
                sum_all_students = EXAM.get_sum_common_students()
                correlation_list = get_comVsInd_correlation(EXAM)

            return render(request, "statistics/general_statistics.html",
                          {"user_allowed":True,
                           "exam" : EXAM,
                           "grade_list": grade_list,
                           "absent": sum_all_students - EXAM.present_students,
                           "common_list": common_list,
                           "correlation_list":correlation_list,
                           "current_url": "generalStats"})
        else:
            return render(request, "statistics/general_statistics.html",
                          {"user_allowed":True,"exam": EXAM, "grade_list": None, "absent": 0})

    else:
        return render(request, "statistics/general_statistics.html",
                      {"user_allowed":False,"scalesStatistics": None, "grade_list": None, "absent": 0})


@login_required
def students_statistics_view(request,pk):
    EXAM = Exam.objects.get(pk=pk)

    if user_allowed(EXAM,request.user.id):
        if EXAM and EXAM.scalesStatistics:

            common_list = get_common_list(EXAM)
            students = Exam.objects.none()

            if EXAM.overall:
                sum_all_students = EXAM.get_sum_common_students()
                for com_exam in EXAM.common_exams.all():

                    students = students | com_exam.students.all()

                students = sorted(students, key=operator.attrgetter('name'))
            else:
                students = EXAM.students.all()

            return render(request, "statistics/students_statistics.html",
                          {"user_allowed":True,
                           "exam" : EXAM,
                           "students" : students,
                           "common_list": common_list,
                           "current_url": "studentsStats"})
        else:
            return render(request, "statistics/students_statistics.html", {"user_allowed":True,"scales": None, "students": None})
    else:
        return render(request, "statistics/students_statistics.html", {"user_allowed":False,"scales": None, "students": None})


@login_required
def questions_statistics_view(request,pk):
    EXAM = Exam.objects.get(pk=pk)

    if user_allowed(EXAM,request.user.id):

        if EXAM and EXAM.scalesStatistics.all() and EXAM.questions.all():
            discriminatory_factor = Question.objects.filter(exam=EXAM)[0].discriminatory_factor
            discriminatory_qty = round(EXAM.present_students * discriminatory_factor / 100)

            question_stat_by_teacher_list = []

            if EXAM.overall:
                question_stat_by_teacher_list = get_questions_stats_by_teacher(EXAM)

            return render(request, "statistics/questions_statistics.html",
                          {"user_allowed":True,"exam": EXAM,"discriminatory_factor": discriminatory_factor, "discriminatory_qty": discriminatory_qty,
                           "mcq_questions": Question.objects.filter(exam=EXAM).exclude(qtype=4),
                           "open_questions": Question.objects.filter(exam=EXAM,qtype=4),
                           "questionsStatsByTeacher": question_stat_by_teacher_list,
                           "common_list" : get_common_list(EXAM),
                           "current_url": "questionsStats"})
        else:
            return render(request, "statistics/questions_statistics.html",
                          {"user_allowed":True,"exam": EXAM,"discriminatory_factor": None, "discriminatory_qty": None, "questions": None})
    else:
        return render(request, "statistics/questions_statistics.html",
                      {"user_allowed":False,"exam": EXAM,"discriminatory_factor": None, "discriminatory_qty": None, "questions": None})


# PDF
# ------------------------------------------
@login_required
def display_catalog(request, pk):

    cat_name = Exam.objects.get(pk=pk).pdf_catalog_name
    cat_path = str(Path(os.path.dirname(os.path.realpath(__file__))))+'/pdfs/'+cat_name
    try:
        return FileResponse(open(cat_path, 'rb'), content_type='application/pdf')
    except FileNotFoundError:
        raise Http404('not found')
#     else:
#         return render(request, 'statistics/display_pdf.html', {"searchFor": searchFor})
#
#
# @login_required
# def display_pdf_view(request, searchFor):
#     return render(request, 'statistics/display_pdf.html', {"searchFor": searchFor})

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
