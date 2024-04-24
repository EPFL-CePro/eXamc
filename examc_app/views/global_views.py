from django.contrib import messages
from django.conf import settings
from django.contrib.auth import authenticate, login
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db.models import Q
from django.http import HttpResponseRedirect, HttpResponseForbidden
from django.shortcuts import render, redirect
from django.utils.decorators import method_decorator
from django.views.generic import DetailView
from django_tables2 import SingleTableView
from django_tequila.django_backend import User

from examc_app.forms import LoginForm
from examc_app.models import Exam
from examc_app.tables import ExamSelectTable
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

        global EXAM
        EXAM = Exam.objects.get(pk=context.get("object").id)

        if user_allowed(EXAM,self.request.user.id):
            context['user_allowed'] = True
            context['common_list'] = None
            context['current_url'] = "examInfo"
            context['exam'] = EXAM
            return context
        else:
            context['user_allowed'] = False
            return context


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