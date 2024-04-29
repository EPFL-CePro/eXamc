from django.contrib import messages
from django.conf import settings
from django.contrib.auth import authenticate, login
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.sites import requests
from django.db.models import Q, Sum
from django.http import HttpResponseRedirect, HttpResponseForbidden, HttpResponse
from django.shortcuts import render, redirect
from django.utils.decorators import method_decorator
from django.views.generic import DetailView, CreateView
from django_tables2 import SingleTableView
from django_tequila.django_backend import User

from examc_app.forms import LoginForm
from examc_app.models import Exam, Scale
from examc_app.tables import ExamSelectTable
from examc_app.utils.generate_statistics_functions import generate_statistics
from examc_app.utils.results_statistics_functions import update_common_exams


### admin views ###
@login_required
def getCommonExams(request, pk):
    update_common_exams(pk)

    return HttpResponseRedirect("../admin/examc_app/exam/")

### global views ###
def menu_access_required(view_func):
    def wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated or not (request.user.is_superuser or request.user.is_staff):
            return HttpResponseForbidden("You don't have permission to access this page.")
        return view_func(request, *args, **kwargs)
    return wrapped_view

def users_view(request):
    users = User.objects.all()
    return render(request, 'admin/users.html', {'users': users})

@user_passes_test(lambda u: u.is_superuser)
def staff_status(request, user_id):
    user = User.objects.get(pk=user_id)
    if request.POST.get('action') == 'add_staff':
        user.is_staff = True
    elif request.POST.get('action') == 'remove_staff':
        user.is_staff = False
    user.save()
    return redirect('users')

def log_in(request):
    if request.method == 'POST':
        form = LoginForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data['username']
            password = form.cleaned_data['password']
            user = authenticate(request, username=username, password=password)
            if user:
                login(request, user)
                return redirect('home')
            else:
                messages.error(request, "Invalid username or password")
    else:
        form = LoginForm()
    return render(request, 'login_form.html', {'form': form})

@login_required
def logout(request):
    response = requests.get("https://tequila.epfl.ch/logout")
    return redirect(settings.LOGIN_URL)

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
    scale = Scale.objects.get(id=pk)
    scale.final = True
    scale.save()

    for comex in scale.exam.common_exams.all():
        for comex_scale in comex.scales.all():
            if comex_scale.name == scale.name:
                comex_scale.final = False
                comex_scale.save()

    return redirect('../examInfo/' + str(scale.exam.pk))


def documentation_view(request):
    doc_index_content = open(str(settings.DOCUMENTATION_ROOT)+"/index.html")
    return render(request, 'index.html')

def user_allowed(exam, user_id):
    exam_users = User.objects.filter(Q(exam=exam) | Q(exam__in=exam.common_exams.all()))
    user = User.objects.get(pk=user_id)
    if user in exam_users or user.is_superuser:
        return True
    else:
        return False