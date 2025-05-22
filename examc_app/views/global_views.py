import os

import pytz
import requests
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import User
from django.core.signing import BadSignature, SignatureExpired
from django.db.models import Q
from django.http import HttpResponseRedirect, HttpResponseForbidden, Http404, HttpResponse, FileResponse
from django.shortcuts import render, redirect
from django.urls import reverse
from django.views.decorators.http import require_GET

from examc_app.forms import LoginForm
from examc_app.signing import verify_and_get_path
from examc_app.utils.amc.detect_layout import detect_layout
from examc_app.utils.results_statistics_functions import update_common_exams

### admin views ###
def getCommonExams(request, pk):
    update_common_exams(pk)

    return HttpResponseRedirect("../admin/examc_app/exam/")

def home(request):
    user_info = request.user.__dict__
    user_info.update(request.user.__dict__)

    last_connection_users = []
    if request.user.is_superuser:
        for u in User.objects.all().order_by('-last_login'):
            if u.last_login:
                datetime_zone = u.last_login.astimezone(pytz.timezone(settings.TIME_ZONE))
                last_connection_users.append({"username":u.get_username(),"last_login" : datetime_zone.strftime('%Y-%m-%d %H:%M:%S')})
    return render(request, 'home.html', {
        'user': request.user,
        'user_info': user_info,
        'last_connection_users': last_connection_users,
    })


def select_exam(request, pk, nav_url=None):
    url_string = '../'
    if nav_url is None:
        return HttpResponseRedirect(reverse('examInfo', kwargs={'pk': str(pk)}))
    else:
        return HttpResponseRedirect(reverse(nav_url, kwargs={'pk': str(pk)}))


### global views ###
# def menu_access_required(view_func):
#     def wrapped_view(request, *args, **kwargs):
#         if not request.user.is_authenticated or not (request.user.is_superuser or request.user.is_staff):
#             return HttpResponseForbidden("You don't have permission to access this page.")
#         return view_func(request, *args, **kwargs)
#     return wrapped_view

def log_in(request):
    ok = 2
    if request.method == 'POST':
        form = LoginForm(request.POST)
        if form.is_valid():
            user = authenticate(
                request,
                username=form.cleaned_data['username'],
                password=form.cleaned_data['password']
            )
            if user is not None:
                login(request, user)
                return redirect('home')
            else:
                messages.error(request, "Invalid username or password")
    else:
        form = LoginForm()

    return render(request, 'login_form.html', {'form': form})

# @login_required
# def logout(request):
#     response = requests.get("https://tequila.epfl.ch/logout")
#     django.contrib.auth.logout(request)
#     return redirect(settings.LOGIN_URL)
#
# @login_required
# def logout_view(request):
#     if request.user.is_authenticated == True:
#         response = requests.get("https://tequila.epfl.ch/logout")
#         logout(request)
#         return redirect(settings.LOGIN_URL)

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

@require_GET
def serve_signed_file(request, token):
    try:
        full_path = verify_and_get_path(
            token,
            max_age=settings.SIGNED_FILES_EXPIRATION_TIMEOUT
        )
    except (BadSignature, SignatureExpired, FileNotFoundError):
        raise Http404("Link invalid or expired")

    return FileResponse(open(full_path, "rb"), as_attachment=False)

def test(request):
    detect_layout()
    return render(request,'index.html')

