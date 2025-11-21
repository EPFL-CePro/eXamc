from datetime import datetime

from dateutil.utils import today
from django.conf import settings
from django.db.models import Sum, Q
from django.http import HttpResponse, HttpResponseRedirect, JsonResponse
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.views.generic import CreateView, DetailView
from django_tables2 import SingleTableView, LazyPaginator

from examc_app.decorators import exam_permission_required
from examc_app.mixins import ExamPermissionAndRedirectMixin
from examc_app.models import *
from examc_app.tables import ExamSelectTable
from examc_app.utils.epflldap import ldap_search
from examc_app.utils.global_functions import get_course_teachers_string, add_course_teachers_ldap, user_allowed, \
    convert_html_to_latex, exam_generate_preview, update_folders_paths
from examc_app.utils.results_statistics_functions import update_common_exams
from examc_app.tasks import generate_statistics


#@method_decorator(login_required(login_url='/'), name='dispatch')
class ExamSelectView(SingleTableView):
    model = Exam
    template_name = 'exam/exam_select.html'
    table_class = ExamSelectTable
    #table_pagination = False

    def get_queryset(self):
        qs = Exam.objects.filter(overall=False).all()
        if not self.request.user.is_superuser:
            qs = qs.filter(Q(exam_users__user_id=self.request.user.id) )#| Q(reviewers__user=self.request.user))
        return qs

#@method_decorator(login_required(login_url='/'), name='dispatch')
class ExamInfoView(ExamPermissionAndRedirectMixin,DetailView):
    model = Exam
    template_name = 'exam/exam_info.html'
    perm_codenames = ['manage']
    pk_url_kwarg = 'exam_pk'
    redirect_enabled = True

    #slug_url_kwarg = 'task_id'

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        context = self.get_context_data(object=self.object)
        exam = Exam.objects.get(pk=context.get("object").id)
        exam_user = ExamUser.objects.filter(exam=exam, user=self.request.user).first()

        if not exam_user and exam.common_exams:
            for comex in exam.common_exams.all():
                exam_user = ExamUser.objects.filter(exam=comex,user=self.request.user).first()
                if exam_user:
                    break

        # redirect to review if reviewer
        if exam_user and not self.request.user.is_superuser and exam_user.group.pk == 3:
            return redirect(reverse('reviewView', kwargs={'exam_pk': exam.pk}))

        return self.render_to_response(context)

    def get_context_data(self, **kwargs):
        context = super(ExamInfoView, self).get_context_data(**kwargs)
        task_id = None
        if 'task_id' in self.kwargs:
            task_id = self.kwargs['task_id']
        exam = Exam.objects.get(pk=context.get("object").id)

        users_groups_add = Group.objects.filter(pk__in=[2,3,4])
        semesters = Semester.objects.all()
        years = AcademicYear.objects.all()

        exam_selected = exam
        if exam.common_exams:
            for common_exam in exam.common_exams.all():
                if common_exam.is_overall():
                    exam = common_exam
                    break

        if user_allowed(exam,self.request.user.id):
            context['user_allowed'] = True
            context['common_list'] = None
            context['nav_url'] = "examInfo"
            context['exam'] = exam
            context['exam_selected'] = exam_selected
            context['question_types'] = QuestionType.objects.all()
            context['sum_questions_points'] = exam.questions.all().aggregate(Sum('max_points'))
            context['users_groups_add'] = users_groups_add
            context['semesters'] = semesters
            context['years'] = years
            context['task_id'] = task_id
            return context
        else:
            context['user_allowed'] = False
            return context

#@login_required
@exam_permission_required(['manage'])
def ldap_search_exam_user_by_email(request,exam_pk):
    """
    Search in LDAP by email.

    This function is used to search a new reviewer in the ldap database. The email of the reviewer will
    give the complete name of the user and his email.

    Args:
        request: The HTTP request object containing the email address ('email') and the exam ID ('pk').

    Returns:
        HttpResponse: A response string containing user information or an indication of existence.
    """
    email = request.POST['email']
    user = ExamUser.objects.filter(user__email=email, exam__id=exam_pk).all()
    if user:
        return HttpResponse("exist")

    django_user = User.objects.filter(email=email).first()
    if django_user:
        entry_str = f"{django_user.username};{django_user.first_name};{django_user.last_name};{email}"
        return HttpResponse(entry_str)

    user_entry = ldap_search.get_entry(email, 'mail')
    if user_entry:
        entry_str = user_entry['uniqueidentifier'][0] + ";"  + user_entry['givenName'][0] + ";" + user_entry['sn'][
            0] + ";" + email
        return HttpResponse(entry_str)
    else:
        return JsonResponse(
            {"error": "not_found"},
            status=400
        )

#@login_required
@exam_permission_required(['manage'])
def update_exam_users(request,exam_pk):
    """
           Add new users to exam.

           This function is used to add a new users to exam

           :param request: The HTTP request object.

               Args:
                    request: The HTTP request object.
           """
    exam = Exam.objects.get(pk=exam_pk)
    users_list = request.POST.getlist('users_list[]')

    #reviewer_group, created = Group.objects.get_or_create(name='Reviewer')
    for user_in in users_list:
        user_list = user_in.split(";")

        if user_list[0].startswith('delete_'):
            user_to_delete = User.objects.filter(email=user_list[3]).first()
            exam_user = ExamUser.objects.get(user=user_to_delete,exam=exam)
            exam_user.delete()
        else:
            users = User.objects.filter(email=user_list[3]).all()
            if users:
                user = users.first()
            else:
                user = User()
                user.username = user_list[0]
                user.first_name = user_list[1]
                user.last_name = user_list[2]
                user.email = user_list[3]
                user.save()

            exam_user, created = ExamUser.objects.get_or_create(user=user, exam=exam)
            exam_user.group = Group.objects.get(pk=user_list[4])
            if exam_user.group.id in [2,3,4] and not exam_user.pages_groups:
                exam_user.pages_groups.set(PagesGroup.objects.filter(exam=exam).all())
            exam_user.save()

    return redirect('examInfo', exam_pk=exam.pk)

#@login_required
@exam_permission_required(['manage'])
def update_exam_info(request,exam_pk):
    """
           Update exam info.

           This function is used to update exam info

           :param request: The HTTP request object.

               Args:
                    request: The HTTP request object.
           """

    exam = Exam.objects.get(pk=exam_pk)

    if exam.date :
        old_exam_date = exam.date.strftime("%Y-%m-%d")
    else:
        old_exam_date = today().strftime("%Y-%m-%d")
    old_folder_path = "/" + str(exam.year.code) + "/" + str(exam.semester.code) + "/" + exam.code + "_" + old_exam_date#.replace("-","")
    exam.date = datetime.strptime(request.POST.get('date'),"%Y-%m-%d")
    exam.code = request.POST.get('code')
    exam.name = request.POST.get('name')
    exam.semester_id = request.POST.get('semester_id')
    exam.year_id = request.POST.get('year_id')
    exam.save()

    new_folder_path = "/" + str(exam.year.code) + "/" + str(exam.semester.code) + "/" + exam.code + "_" + exam.date.replace("-","")

    if old_folder_path != new_folder_path:
        update_folders_paths(old_folder_path, new_folder_path)

    return redirect('examInfo', exam_pk=exam.pk)

#@method_decorator(login_required, name='dispatch')
class ScaleCreateView(ExamPermissionAndRedirectMixin,CreateView):
    template_name = 'exam/scale_create.html'
    model = Scale
    fields = ['name', 'total_points', 'points_to_add', 'min_grade','max_grade','rounding']#,'formula']
    perm_codenames = ['manage']
    pk_url_kwarg = 'exam_pk'

    def form_valid(self, form):
        scale = form.save(commit=False)
        scale.save()
        exam = Exam.objects.get(pk=self.kwargs['exam_pk'])
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

        task = generate_statistics.delay(exam.pk)
        task_id = task.task_id

        return HttpResponseRedirect(reverse('examInfo', kwargs={'exam_pk': exam.pk, 'task_id': task_id}))

    def get_context_data(self, **kwargs):
        context = super(ScaleCreateView, self).get_context_data(**kwargs)
        context['exam_pk'] = self.kwargs['exam_pk']
        return context

#@login_required
@exam_permission_required(['manage'])
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

    task = generate_statistics.delay(exam_pk)
    task_id = task.task_id

    return HttpResponseRedirect(reverse('examInfo', kwargs={'exam_pk': exam_pk, 'task_id': task_id}))


#@login_required
@exam_permission_required(['manage'])
def update_exam(request,exam_pk):
    exam = Exam.objects.get(pk=exam_pk)
    field_name = request.POST['field']
    value = request.POST['value']

    setattr(exam, field_name, value)
    exam.save()

    global DATA_UPDATED
    DATA_UPDATED = True

    return HttpResponse(1)

#@login_required
@exam_permission_required(['manage'])
def set_final_scale(request, scale_pk, exam_pk,all_common=0):
    final_scale = Scale.objects.get(id=scale_pk)

    for scale in final_scale.exam.scales.all():
        if scale == final_scale:
            scale.final = True
        else:
            scale.final = False
        scale.save()

    if all_common == 1:
        for comex in final_scale.exam.common_exams.all():
            for comex_scale in comex.scales.all():
                if comex_scale.name == final_scale.name:
                    comex_scale.final = True
                else:
                    comex_scale.final = False
                comex_scale.save()

    return redirect(reverse('examInfo', kwargs={'exam_pk': str(final_scale.exam.pk)}))


#@login_required
@exam_permission_required(['manage'])
def update_exam_options(request,exam_pk):
    if request.method == 'POST':
        exam = Exam.objects.get(pk=exam_pk)
        exam.review_option = False
        exam.amc_option = False
        exam.res_and_stats_option = False
        exam.prep_option = False
        if 'review_option_'+str(exam_pk) in request.POST:
            exam.review_option = True
        if 'amc_option_'+str(exam_pk) in request.POST:
            exam.amc_option = True
        if 'res_and_stats_option_'+str(exam_pk) in request.POST:
            exam.res_and_stats_option = True
        if 'prep_option_'+str(exam_pk) in request.POST:
            exam.prep_option = True

        exam.save()
        return HttpResponse('ok')


# QUESTIONS MANAGEMENT
# ------------------------------------------
# #@login_required
# @exam_permission_required(['manage'])
# def update_question(request,exam_pk):
#     question = Question.objects.get(pk=request.POST['question_pk'])
#     field_name = request.POST['field']
#     value = request.POST['value']
#     setattr(question, field_name, value)
#     question.save()
#
#     return HttpResponse(1)


#@login_required
@exam_permission_required(['manage'])
def update_questions(request,exam_pk):
    data = json.loads(request.POST.get('data'))
    for question in data:
        quest = Question.objects.get(pk=question['QUESTION'])
        if 'ANSWERS' in question:
            quest.nb_answers = question['ANSWERS']
        quest.max_points = question['MAX POINTS']
        if quest.question_type_id != question['TYPE']:
            old_qtype = quest.question_type_id
            quest.question_type_id = question['TYPE']
            if quest.question_type_id in (1,2) and quest.nb_answers == 0 or old_qtype == 3:
                quest.nb_answers = 4
            elif quest.question_type_id == 3:
                quest.nb_answers = 2
            else:
                quest.nb_answers = 0
        if 'COMMON' in question:
            quest.common = True if question['COMMON'] else False
        quest.save()

    return HttpResponse(1)

#@login_required
@exam_permission_required(['manage'])
def validate_common_exams_settings(request,exam_pk):
    exam = Exam.objects.get(pk=exam_pk)
    common_exams_ids = request.POST.getlist(str(exam_pk)+'_common_to[]')
    if common_exams_ids:
        common_exams = Exam.objects.filter(id__in=common_exams_ids)
        exam.common_exams.set(common_exams)


        #get or create overall exam if not from overall exam
        if not exam.is_overall():
            overall_exam, created = Exam.objects.get_or_create( code='000-' + exam.name + '-' + exam.year.code + '-' + str(exam.semester.code),
                                                                year = exam.year, semester = exam.semester)
            if created:
                overall_exam.name = exam.name
                overall_exam.pdf_catalog_name = exam.pdf_catalog_name
                overall_exam = exam.date
                overall_exam.overall = True
                overall_exam.save()

            exam.common_exams.add(overall_exam)
        else:
            overall_exam = exam

        exam.save()
        update_common_exams(exam_pk)

        # if common exam, update overall exam users
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


    return redirect('../examInfo/' + str(exam.pk))
