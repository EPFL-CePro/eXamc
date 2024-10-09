
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Q
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.views.generic import CreateView, DetailView
from django_tables2 import SingleTableView
from examc_app.models import *
from examc_app.tables import ExamSelectTable
from examc_app.utils.epflldap import ldap_search
from examc_app.utils.global_functions import get_course_teachers_string, add_course_teachers_ldap, user_allowed, convert_html_to_latex, exam_generate_preview
from examc_app.views.global_views import menu_access_required
from examc_app.tasks import generate_statistics


@method_decorator(login_required(login_url='/'), name='dispatch')
class ExamSelectView(SingleTableView):
    model = Exam
    template_name = 'exam/exam_select.html'
    table_class = ExamSelectTable
    table_pagination = False

    def get_queryset(self):
        qs = Exam.objects.filter(overall=False).all()
        if not self.request.user.is_superuser:
            qs = qs.filter(Q(exam_users__user_id=self.request.user.id) )#| Q(reviewers__user=self.request.user))
        return qs

@method_decorator(login_required(login_url='/'), name='dispatch')
class ExamInfoView(DetailView):
    model = Exam
    template_name = 'exam/exam_info.html'
    #slug_url_kwarg = 'task_id'

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        context = self.get_context_data(object=self.object)
        exam = Exam.objects.get(pk=context.get("object").id)
        exam_user = ExamUser.objects.filter(exam=exam, user=self.request.user).first()

        # redirect to review if reviewer
        if not self.request.user.is_superuser and exam_user.group.pk == 3:
            return redirect(reverse('reviewView', kwargs={'pk': exam.pk}))

        return self.render_to_response(context)

    def get_context_data(self, **kwargs):
        context = super(ExamInfoView, self).get_context_data(**kwargs)
        task_id = None
        if 'task_id' in self.kwargs:
            task_id = self.kwargs['task_id']
        exam = Exam.objects.get(pk=context.get("object").id)

        users_groups_add = Group.objects.filter(pk__in=[2,3,4])

        if exam.common_exams:
            for common_exam in exam.common_exams.all():
                if common_exam.is_overall():
                    exam = common_exam
                    break

        if user_allowed(exam,self.request.user.id):
            context['user_allowed'] = True
            context['common_list'] = None
            context['current_url'] = "examInfo"
            context['exam'] = exam
            context['question_types'] = QuestionType.objects.all()
            context['sum_questions_points'] = exam.questions.all().aggregate(Sum('max_points'))
            context['users_groups_add'] = users_groups_add
            context['task_id'] = task_id
            return context
        else:
            context['user_allowed'] = False
            return context

@login_required
@menu_access_required
def ldap_search_exam_user_by_email(request):
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
    user = ExamUser.objects.filter(user__email=email, exam__id=request.POST['pk']).all()
    if user:
        return HttpResponse("exist")

    django_user = User.objects.filter(email=email).first()
    if django_user:
        entry_str = f"{django_user.username};{django_user.first_name};{django_user.last_name};{email}"
        return HttpResponse(entry_str)

    user_entry = ldap_search.get_entry(email, 'mail')
    entry_str = user_entry['uniqueidentifier'][0] + ";" + user_entry['givenName'][0] + ";" + user_entry['sn'][
        0] + ";" + email

    return HttpResponse(entry_str)

@login_required
@menu_access_required
def update_exam_users(request):
    """
           Add new users to exam.

           This function is used to add a new users to exam

           :param request: The HTTP request object.

               Args:
                    request: The HTTP request object.
           """
    exam = Exam.objects.get(pk=request.POST.get('pk'))
    users_list = request.POST.getlist('users_list[]')
    #reviewer_group, created = Group.objects.get_or_create(name='Reviewer')
    for user_in in users_list:
        user_list = user_in.split(";")
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

    return redirect('examInfo', pk=exam.pk)

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

        task = generate_statistics.delay(exam.pk)
        task_id = task.task_id

        return HttpResponseRedirect(reverse('examInfo', kwargs={'pk': exam.pk, 'task_id': task_id}))
        # generate_statistics(exam)
        # return redirect('../examInfo/' + str(exam.pk))

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

    task = generate_statistics.delay(exam_pk)
    task_id = task.task_id

    return HttpResponseRedirect(reverse('examInfo', kwargs={'pk': exam_pk, 'task_id': task_id}))
    # generate_statistics(exam_to_manage)    #
    # return redirect('../../examInfo/' + str(exam_pk))


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