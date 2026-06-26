import os
import logging
from datetime import datetime
from pathlib import Path

import pytz
import requests
from celery import shared_task
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import User
from django.contrib.sessions.models import Session
from django.core.signing import BadSignature, SignatureExpired
from django.db.models import Q
from django.http import HttpResponseRedirect, HttpResponseForbidden, Http404, HttpResponse, FileResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.templatetags.static import static
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_GET, require_POST

from examc_app.forms import LoginForm
from examc_app.middleware.impersonation import (
    IMPERSONATED_SESSION_KEY,
    IMPERSONATOR_SESSION_KEY,
    clear_impersonation_session,
)
from examc_app.models import ReviewLock
from examc_app.signing import verify_and_get_path
from examc_app.utils.dashboard import get_dashboard_context
from examc_app.utils.results_statistics_functions import update_common_exams

logger = logging.getLogger(__name__)


def _get_real_user(request):
    return getattr(request, "impersonator", None) or request.user


def _is_impersonation_admin(user):
    return user.is_authenticated and user.is_superuser


def _get_safe_next_url(request):
    next_url = request.POST.get("next") or request.GET.get("next")
    if next_url and url_has_allowed_host_and_scheme(
        next_url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return next_url
    return reverse("home")


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
    context = {
        'user': request.user,
        'user_info': user_info,
        'last_connection_users': last_connection_users,
    }
    if request.user.is_authenticated:
        context.update(get_dashboard_context(request.user))

    return render(request, 'home.html', context)


def select_exam(request, pk, nav_url=None):
    url_string = '../'
    if nav_url is None:
        return HttpResponseRedirect(reverse('examInfo', kwargs={'pk': str(pk)}))
    else:
        return HttpResponseRedirect(reverse(nav_url, kwargs={'pk': str(pk)}))


@login_required
def impersonate_user_select(request):
    real_user = _get_real_user(request)
    if not _is_impersonation_admin(real_user):
        return HttpResponseForbidden("Only superusers can impersonate users.")

    users = User.objects.filter(is_active=True).exclude(
        pk=real_user.pk
    ).exclude(
        is_superuser=True
    ).order_by("last_name", "first_name", "username")

    return render(request, "impersonation/select_user.html", {
        "impersonation_users": users,
        "real_user": real_user,
    })


@login_required
@require_POST
def impersonate_start(request, user_pk):
    real_user = _get_real_user(request)
    if not _is_impersonation_admin(real_user):
        return HttpResponseForbidden("Only superusers can impersonate users.")

    target_user = get_object_or_404(User, pk=user_pk, is_active=True)
    if target_user.is_superuser:
        return HttpResponseForbidden("Superuser accounts cannot be impersonated.")
    if target_user.pk == real_user.pk:
        return HttpResponseForbidden("You cannot impersonate your own account.")

    request.session[IMPERSONATOR_SESSION_KEY] = real_user.pk
    request.session[IMPERSONATED_SESSION_KEY] = target_user.pk
    logger.info(
        "User %s started impersonating user %s",
        real_user.username,
        target_user.username,
    )

    return redirect("home")


@login_required
@require_POST
def impersonate_stop(request):
    impersonator = getattr(request, "impersonator", None)
    impersonated = request.user if impersonator else None
    clear_impersonation_session(request.session)

    if impersonator and impersonated:
        logger.info(
            "User %s stopped impersonating user %s",
            impersonator.username,
            impersonated.username,
        )

    return redirect(_get_safe_next_url(request))


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
    return redirect(static("docs/html/index.html"))

def user_allowed(exam, user_id):
    exam_users = User.objects.filter(Q(exam=exam) | Q(exam__in=exam.common_exams.all()))
    user = User.objects.get(pk=user_id)
    if user in exam_users or user.is_superuser:
        return True
    else:
        return False

@require_GET
def serve_signed_file(request, file_hint=None):
    token = request.GET.get("token")
    if not token:
        rooms_plans = request.GET.get("rooms_plans")
        if rooms_plans:
            relative_rooms_plan = rooms_plans.lstrip("/")
            if not (relative_rooms_plan.startswith("export/") or relative_rooms_plan.startswith("map/")):
                raise Http404("Invalid room plan path")

            rooms_root = Path(settings.ROOMS_PLANS_ROOT).resolve()
            folder_root = (rooms_root / rooms_plans.split("/")[0]).resolve()
            full_path = (rooms_root / relative_rooms_plan).resolve()
            try:
                full_path.relative_to(folder_root)
            except ValueError:
                raise Http404("Invalid room plan path")
            if not full_path.is_file():
                raise Http404("Room plan file not found")
            return FileResponse(open(full_path, "rb"), as_attachment=False)
        else:
            raise Http404("Missing token")
    try:
        full_path = verify_and_get_path(
            token,
            max_age=settings.SIGNED_FILES_EXPIRATION_TIMEOUT
        )
    except (BadSignature, SignatureExpired, FileNotFoundError):
        raise Http404("Link invalid or expired")

    return FileResponse(open(full_path, "rb"), as_attachment=False)

def force_oidc_logout(request):
    if request.user.is_authenticated:
        logout(request)
    return render(request, 'oidc_auto_logout.html')

def test(request):
    #detect_layout()
    return render(request,'index.html')
