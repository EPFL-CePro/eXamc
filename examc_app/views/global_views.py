from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, login
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.sites import requests
from django.db.models import Q
from django.http import HttpResponseRedirect, HttpResponseForbidden
from django.shortcuts import render, redirect
from django.urls import reverse
from django_tequila.django_backend import User

from examc_app.forms import LoginForm
from examc_app.utils.results_statistics_functions import update_common_exams


### admin views ###
@login_required
def getCommonExams(request, pk):
    update_common_exams(pk)

    return HttpResponseRedirect("../admin/examc_app/exam/")

def home(request):
    user_info = request.user.__dict__
    user_info.update(request.user.__dict__)
    return render(request, 'home.html', {
        'user': request.user,
        'user_info': user_info,
    })


@login_required
def select_exam(request, pk, current_url=None):
    url_string = '../'
    if current_url is None:
        return HttpResponseRedirect(reverse('examInfo', kwargs={'pk': str(pk)}))
    else:
        return HttpResponseRedirect(reverse(current_url, kwargs={'pk': str(pk)}))


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

def log_in(request, my_task=None):
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

@login_required
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

