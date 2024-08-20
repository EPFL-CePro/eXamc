import shutil
from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Q
from django.http import HttpResponse
from django.shortcuts import render, redirect
from django.utils.decorators import method_decorator
from django.views.generic import CreateView, DetailView
from django_tables2 import SingleTableView

from examc import settings
from examc_app.forms import CreateExamProjectForm, CreateQuestionForm, ckeditorForm
from examc_app.models import *
from examc_app.models import Semester, AcademicYear, Course, Exam
from examc_app.tables import ExamSelectTable
from examc_app.utils.generate_statistics_functions import generate_statistics
from examc_app.utils.global_functions import get_course_teachers_string, add_course_teachers_ldap, user_allowed, convert_html_to_latex, exam_generate_preview
from examc_app.views.global_views import menu_access_required


@login_required
def create_exam_project(request):

    if request.method == 'POST':
        form = CreateExamProjectForm(request.POST)
        if form.is_valid():
            course_id = form.cleaned_data['course']
            date = form.cleaned_data['date']
            year_id = form.cleaned_data['year']
            semester_id = form.cleaned_data['semester']
            date_text = date.strftime('%d.%m.%Y')
            duration_text = form.cleaned_data['durationText']
            language = form.cleaned_data['language']

            semester = Semester.objects.get(pk=semester_id)
            year = AcademicYear.objects.get(pk=year_id)
            course = Course.objects.get(pk=course_id)
            exam_text = course.code+" - "+course.name
            teachers_text = get_course_teachers_string(course.teachers)
            teachers = add_course_teachers_ldap(course.teachers)

            user = request.user
            if not user in teachers:
                teachers.append(user)

            exam = Exam()
            exam.code = course.code
            exam.name = course.name
            exam.semester = semester
            exam.year = year
            exam.date = date
            exam.amc_option = True
            exam.save()
            for teacher in teachers:
                exam.users.add(teacher)
            exam.save()

            #copy template to new amc_project directory
            amc_project_template_path = str(settings.AMC_PROJECTS_ROOT)+"/templates/"+language+"/base"
            new_project_path = str(settings.AMC_PROJECTS_ROOT)+"/"+year.code+"/"+str(semester.code)+"/"+exam.code+"_"+date.strftime("%Y%m%d")
            shutil.copytree(amc_project_template_path,new_project_path)

            #update exam-info.tex
            exam_info_path = new_project_path+"/exam-info.tex"
            with open(exam_info_path, 'r') as file:
                file_contents = file.read()
                updated_contents = file_contents.replace("<TEACHER>", teachers_text).replace("<PAGES>", "8").replace("<DURATION>", duration_text).replace("<DATE>", date_text).replace("<EXAM>", exam_text)


            with open(exam_info_path, 'w') as file:
                file.write(updated_contents)

            return redirect('examInfo',pk=exam.pk)
        else:
            logger.info("INVALID")
            logger.info(form.errors)
            return render(request, 'exam/create_exam_project.html', {"user_allowed": True,
                                                                   "form": form,
                                                                   "current_url": "create_exam_project"})

    # if a GET (or any other method) we'll create a blank form
    else:
        form = CreateExamProjectForm(request.POST)

        return render(request, 'exam/create_exam_project.html', {"user_allowed": True,
                                                               "form": form,
                                                               "current_url": "create_exam_project"})


@method_decorator(login_required(login_url='/'), name='dispatch')
class ExamSelectView(SingleTableView):
    model = Exam
    template_name = 'exam/exam_select.html'
    table_class = ExamSelectTable
    table_pagination = False

    def get_queryset(self):
        qs = Exam.objects.all()
        if not self.request.user.is_superuser:
            qs = qs.filter(Q(users__id=self.request.user.id) | Q(reviewers__user=self.request.user))
        return qs

@method_decorator(login_required(login_url='/'), name='dispatch')
class ExamInfoView(DetailView):
    model = Exam
    template_name = 'exam/exam_info.html'

    def get_context_data(self, **kwargs):
        context = super(ExamInfoView, self).get_context_data(**kwargs)

        exam = Exam.objects.get(pk=context.get("object").id)

        if user_allowed(exam,self.request.user.id):
            context['user_allowed'] = True
            context['common_list'] = None
            context['current_url'] = "examInfo"
            context['exam'] = exam
            context['question_types'] = QuestionType.objects.all()
            context['sum_questions_points'] = exam.questions.all().aggregate(Sum('max_points'))
            return context
        else:
            context['user_allowed'] = False
            return context


@method_decorator(login_required, name='dispatch')
class ScaleCreateView(CreateView):
    template_name = 'exam/scale_create.html'
    model = Scale
    fields = ['name', 'total_points', 'points_to_add', 'min_grade','max_grade','rounding']#,'formula']

    def form_valid(self, form):
        scale = form.save(commit=False)
        scale.save()
        exam = Exam.objects.get(pk=self.kwargs['pk'])
        exam.scales.add(scale)
        exam.save()

        for comex in exam.common_exams.all():
            scale_comex, created = Scale.objects.get_or_create(exam=comex,name = scale.name,total_points=scale.total_points)
            if created:
                scale_comex.total_points = scale.total_points
                scale_comex.points_to_add = scale.points_to_add
                scale_comex.min_grade = scale.min_grade
                scale_comex.max_grade = scale.max_grade
                scale_comex.rounding = scale.rounding
                scale_comex.formula = scale.formula
                scale_comex.save()

        generate_statistics(exam)
        return redirect('../examInfo/' + str(exam.pk))

    def get_context_data(self, **kwargs):
        context = super(ScaleCreateView, self).get_context_data(**kwargs)
        context['pk'] = self.kwargs['pk']
        return context
@login_required
def delete_exam_scale(request, scale_pk, exam_pk):
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

    generate_statistics(exam_to_manage)

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

@login_required
def set_final_scale(request, pk):
    final_scale = Scale.objects.get(id=pk)

    for scale in final_scale.exam.scales.all():
        if scale == final_scale:
            scale.final = True
        else:
            scale.final = False
        scale.save()

    for comex in final_scale.exam.common_exams.all():
        for comex_scale in comex.scales.all():
            if comex_scale.name == scale.name:
                comex_scale.final = True
            else:
                comex_scale.final = False
            comex_scale.save()

    return redirect('../examInfo/' + str(scale.exam.pk))


@login_required
def update_exam_options(request,pk):
    if request.method == 'POST':
        exam = Exam.objects.get(pk=pk)
        exam.review_option = False
        exam.amc_option = False
        exam.res_and_stats_option = False
        exam.prep_option = False
        if 'review_option' in request.POST:
            exam.review_option = True
        if 'amc_option' in request.POST:
            exam.amc_option = True
        if 'res_and_stats_option' in request.POST:
            exam.res_and_stats_option = True
        if 'prep_option' in request.POST:
            exam.prep_option = True

        exam.save()
        return HttpResponse('ok')

@login_required
def exam_preparation_view(request,pk):
    exam = Exam.objects.get(pk=pk)

    first_page_text_form = ckeditorForm()
    first_page_text_form.initial['ckeditor_txt'] = exam.first_page_text

    section_txt_frm_list = {}
    question_txt_frm_list = {}
    answer_txt_frm_list = {}
    for section in exam.sections.all() :
        frm = ckeditorForm(auto_id="%s_section_"+str(section.id))
        frm.initial['ckeditor_txt'] = section.header_text
        section_txt_frm_list[section.id] = frm

        for question in section.questions.all() :
            frm_q = ckeditorForm(auto_id="%s_question_"+str(question.id))
            frm_q.initial['ckeditor_txt'] = question.question_text
            question_txt_frm_list[question.id] = frm_q
            
            if question.question_type.code in ["SCQ","MCQ"]:
                for answer in question.answers.all() :
                    frm_a = ckeditorForm(auto_id="%s_answer_"+str(answer.id))
                    frm_a.initial['ckeditor_txt'] = answer.answer_text
                    answer_txt_frm_list[answer.id] = frm_a



    return render(request, 'exam/exam_preparation.html',
            {"user_allowed": True,
                    "exam":exam,
                    "fp_txt_form":first_page_text_form,
                    "sh_txt_frm_list":section_txt_frm_list,
                    "qu_txt_frm_list":question_txt_frm_list,
                    "an_txt_frm_list":answer_txt_frm_list})

@login_required
def exam_add_section(request,exam_pk):
    exam = Exam.objects.get(pk=exam_pk)
    section_num = 1
    if exam.sections.all():
        section_num += len(exam.sections.all())
    section = ExamSection()
    section.title = "Section "+str(section_num)
    section.section_number = section_num
    section.exam = exam
    section.save()

    return exam_preparation_view

    #return render(request, 'exam/exam_preparation.html', {"user_allowed": True,"exam":exam})

@login_required
def exam_add_section_question(request):
    if request.method == 'POST':
        form = CreateQuestionForm(request.POST)
        if form.is_valid():
            section_pk = form.cleaned_data['section_pk']
            question_type_pk = form.cleaned_data['question_type']
            nb_answers = form.cleaned_data['nb_answers']

            section = ExamSection.objects.get(pk=section_pk)
            exam = Exam.objects.get(pk=section.exam.pk)
            question_type = QuestionType.objects.get(pk=question_type_pk)

            # get new question code
            last_question = Question.objects.filter(section=section, question_type=question_type).order_by(
                'code').all().last()
            if last_question:
                last_number = int(last_question.code.split('-')[1]) + 1
            else:
                last_number = 1
            last_number = str(last_number).zfill(2)

            # create question
            question = Question()
            question.exam = exam
            question.section = section
            question.code = question_type.code+"-"+last_number
            question.question_type = question_type
            question.save()

            # create answers
            if question_type.code in ['SCQ','MCQ']:
                for i in range(nb_answers):
                    answer = QuestionAnswer()
                    answer.code = chr(ord('@')+(i+1))
                    answer.question = question
                    answer.save()
            elif question_type.code == 'TF':
                answer = QuestionAnswer()
                answer.code = 'TRUE'
                answer.question = question
                answer.answer_text = 'TRUE'
                answer.save()
                answer = QuestionAnswer()
                answer.code = 'FALSE'
                answer.question = question
                answer.answer_text = 'FALSE'
                answer.save()
            else:
                open_max_points = form.cleaned_data['open_max_points']
                open_points_increment = Decimal(form.cleaned_data['open_points_increment'])
                answers_range = int(open_max_points / open_points_increment) + 1
                for i in range(answers_range):
                    answer = QuestionAnswer()
                    answer.code = i
                    answer.question = question
                    answer.answer_text = str(i)
                    answer.save()

            return redirect('exam_preparation', pk=exam.pk)

        else:
            logger.info("INVALID")
            logger.info(form.errors)
            return render(request, 'exam/create_exam_project.html', {"user_allowed": True,
                                                                     "form": form,
                                                                     "current_url": "create_exam_project"})

    # if a GET (or any other method) we'll create a blank form
    elif request.method == 'GET':
        form = CreateQuestionForm(section_pk=request.GET.get('section_pk'))

        return HttpResponse(form.as_p())

@login_required
def exam_update_section(request):
    section = ExamSection.objects.get(pk=request.POST.get('section_pk'))

    section.header_text = request.POST.get('header_text')
    section.title = request.POST.get('section_title')
    section.save()

    return HttpResponse('ok')

@login_required
@menu_access_required
def get_header_section_txt(request):
    """
      Get the section header text.

      This view function retrieves the header section text identified by its primary key. It returns
      the text as an HTTP response.

      Args:
          request: The HTTP request object containing the primary key 'section_pk' of the section.

      Returns:
          HttpResponse: An HTTP response containing the text for the section.
      """

    section = ExamSection.objects.get(pk=request.POST['section_pk'])
    section_txt_frm = ckeditorForm()
    section_txt_frm.initial['ckeditor_txt'] = section.header_text
    return HttpResponse(section.header_text)

@login_required
def exam_update_question(request):
    question = Question.objects.get(pk=request.POST.get('question_pk'))

    question.question_text = request.POST.get('question_text')
    if question.question_type.code == 'OPEN':
        answer, created = QuestionAnswer.objects.get_or_create(question=question, code='BOX')
        answer_box_dict = {"box_type":request.POST.get('open_question_box_type'),"box_size":request.POST.get('open_question_box_size')}
        answer.answer_text = json.dumps(answer_box_dict)
        answer.question = question
        answer.save()
    else:
        question.formula = request.POST.get('question_formula')
    question.save()

    return HttpResponse('ok')

@login_required
def exam_update_answers(request):

    answers = json.loads(request.POST.get('answers'))
    for a in answers:
        answer = QuestionAnswer.objects.get(pk=a['answer_pk'])
        answer.answer_text = a['answer_text']
        answer.is_correct = a['is_correct']
        answer.formula = a['answer_formula']
        answer.save()

    return HttpResponse('ok')

@login_required
def exam_add_answer(request):
    if request.method == 'POST':
        question = Question.objects.get(pk=request.POST.get('question_pk'))
        nb_answers = question.answers.all().count()

        answer = QuestionAnswer()
        answer.code = chr(ord('@') + (nb_answers + 1))
        answer.question = question
        answer.save()

        exam = question.exam

    return HttpResponse('ok')

@login_required
def exam_remove_answer(request):
    answer = QuestionAnswer.objects.get(pk=request.POST.get('answer_pk'))
    exam = answer.question.exam
    answer.delete()
    # redo codes
    answers = QuestionAnswer.objects.filter(question__pk=answer.question.pk).order_by('code')
    i = 1
    for a in answers.all():
        a.code = chr(ord('@') + (i))
        a.save()
        i+=1
    return HttpResponse('ok')

@login_required
def exam_remove_question(request):
    question = Question.objects.get(pk=request.POST.get('question_pk'))
    question.delete()
    return HttpResponse('ok')

@login_required
def exam_remove_section(request):
    section = ExamSection.objects.get(pk=request.POST.get('section_pk'))
    section.delete()
    # redo numbering
    sections = ExamSection.objects.filter(exam__pk=section.exam.id).order_by('section_number')
    i = 1
    for s in sections.all():
        if s.title == 'Section '+str(s.section_number):
            s.title = 'Section '+str(i)
        s.section_number = i
        s.save()
        i += 1
    return HttpResponse('ok')

@login_required
def exam_update_first_page(request):
    exam = Exam.objects.get(pk=request.POST.get('exam_pk'))
    exam.first_page_text = request.POST.get('first_page_text')

    output = convert_html_to_latex(exam.first_page_text)
    print(output)

    exam.save()
    return HttpResponse('ok')

@login_required
def exam_preview_pdf(request,exam_pk):
    exam = Exam.objects.get(pk=exam_pk)
    result = exam_generate_preview(exam)
    return HttpResponse(result)