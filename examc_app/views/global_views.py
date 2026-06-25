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
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_GET, require_POST

from examc_app.forms import LoginForm
from examc_app.middleware.impersonation import (
    IMPERSONATED_SESSION_KEY,
    IMPERSONATOR_SESSION_KEY,
    clear_impersonation_session,
)
from examc_app.models import Exam, ExamUser, PageMarkers, PagesGroupGradingSchemeCheckedBox, ReviewLock
from examc_app.permissions import exam_group_names_allow
from examc_app.signing import verify_and_get_path
from examc_app.utils.results_statistics_functions import update_common_exams

logger = logging.getLogger(__name__)

DASHBOARD_EXAM_LIMIT = 8
DASHBOARD_TODO_LIMIT = 8


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


def _normalize_group_names(group_names):
    return {
        group_name.strip().casefold()
        for group_name in group_names
        if group_name and group_name.strip()
    }


def _get_reviewer_group_names():
    return _normalize_group_names(getattr(settings, "EXAM_REVIEWER_GROUP_NAMES", ()))


def _get_exam_user_group_names(exam_users):
    return [
        exam_user.group.name
        for exam_user in exam_users
        if exam_user.group
    ]


def _exam_users_allow(exam_users, permission_codenames):
    return exam_group_names_allow(
        _get_exam_user_group_names(exam_users),
        permission_codenames,
    )


def _exam_user_allows(exam_user, permission_codenames):
    if not exam_user.group:
        return False
    return exam_group_names_allow([exam_user.group.name], permission_codenames)


def _is_reviewer_exam_user(exam_user):
    if not exam_user.group:
        return False
    return exam_user.group.name.strip().casefold() in _get_reviewer_group_names()


def _exam_has_reviewer(exam):
    reviewer_group_names = _get_reviewer_group_names()
    exam_group_names = ExamUser.objects.filter(
        exam=exam,
        group__isnull=False,
    ).values_list("group__name", flat=True)
    return bool(_normalize_group_names(exam_group_names) & reviewer_group_names)


def _get_user_exam_users(exam, user):
    if user.is_superuser:
        return []
    return [exam_user for exam_user in exam.exam_users.all() if exam_user.user_id == user.id]


def _get_role_label(user, exam_users):
    if user.is_superuser:
        return "Superuser"

    role_names = sorted({
        exam_user.group.name
        for exam_user in exam_users
        if exam_user.group
    })
    return ", ".join(role_names) if role_names else "User"


def _get_dashboard_type(user, exam_users):
    if user.is_superuser:
        return "Superuser dashboard"

    group_names = _get_exam_user_group_names(exam_users)
    if exam_group_names_allow(group_names, ["manage"]):
        return "Teacher dashboard"
    if _normalize_group_names(group_names) & _get_reviewer_group_names():
        return "Reviewer dashboard"
    if exam_group_names_allow(group_names, ["see_results"]):
        return "Results dashboard"
    return "User dashboard"


def _get_exam_capabilities(user, exam_users):
    return {
        "manage": user.is_superuser or _exam_users_allow(exam_users, ["manage"]),
        "review": user.is_superuser or _exam_users_allow(exam_users, ["review"]),
        "results": user.is_superuser or _exam_users_allow(exam_users, ["see_results"]),
    }


def _get_review_progress(exam):
    markers = PageMarkers.objects.filter(exam=exam).exclude(copie_no="CORR-BOX")
    total = markers.count()
    if not total:
        return None

    graded = markers.filter(correctorBoxMarked=True).count()
    return {
        "graded": graded,
        "total": total,
        "percent": round(100 / total * graded),
    }


def _get_pages_group_progress(pages_group, user_id=None):
    markers = PageMarkers.objects.filter(pages_group=pages_group).exclude(copie_no="CORR-BOX")
    if pages_group.use_grading_scheme:
        total = markers.values("copie_no").distinct().count()
        graded = PagesGroupGradingSchemeCheckedBox.objects.filter(pages_group=pages_group)
        if user_id:
            graded = graded.filter(user_id=user_id)
        graded_count = graded.values("copy_nr").distinct().count()
    else:
        total = markers.count()
        graded = markers.filter(correctorBoxMarked=True)
        if user_id:
            graded = graded.filter(pageMarkers_users__user_id=user_id).distinct()
        graded_count = graded.count()

    return {
        "graded": graded_count,
        "total": total,
        "percent": round(100 / total * graded_count) if total else None,
    }


def _build_exam_card(user, exam):
    exam_users = _get_user_exam_users(exam, user)
    capabilities = _get_exam_capabilities(user, exam_users)
    module_badges = []
    actions = []

    if exam.prep_option:
        module_badges.append("Preparation")
    if exam.review_option:
        module_badges.append("Review")
    if exam.amc_option:
        module_badges.append("AMC")
    if exam.res_and_stats_option:
        module_badges.append("Results")

    if capabilities["manage"]:
        actions.append({
            "label": "Info",
            "url": reverse("examInfo", kwargs={"exam_pk": exam.pk}),
            "icon": "fa-book-open",
        })
        if exam.prep_option:
            actions.append({
                "label": "Prepare",
                "url": reverse("exam_preparation", kwargs={"exam_pk": exam.pk}),
                "icon": "fa-edit",
            })
        if exam.amc_option:
            actions.append({
                "label": "AMC",
                "url": reverse("amc_view", kwargs={"exam_pk": exam.pk}),
                "icon": "fa-file-import",
            })
    if exam.review_option and capabilities["review"]:
        actions.append({
            "label": "Review",
            "url": reverse("reviewView", kwargs={"exam_pk": exam.pk}),
            "icon": "fa-glasses",
        })
    if exam.res_and_stats_option and capabilities["results"]:
        actions.append({
            "label": "Results",
            "url": reverse("studentsResults", kwargs={"exam_pk": exam.pk}),
            "icon": "fa-th-list",
        })

    return {
        "exam": exam,
        "role": _get_role_label(user, exam_users),
        "module_badges": module_badges,
        "actions": actions,
        "review_progress": _get_review_progress(exam) if exam.review_option else None,
    }


def _add_todo(todos, title, description, url=None, icon="fa-circle-info"):
    if len(todos) >= DASHBOARD_TODO_LIMIT:
        return
    todos.append({
        "title": title,
        "description": description,
        "url": url,
        "icon": icon,
    })


def _add_manage_todos(todos, exam):
    if exam.review_option:
        if not exam.pagesGroup.exists():
            _add_todo(
                todos,
                f"{exam.code}: configure review groups",
                "No page group exists for online review.",
                reverse("reviewSettingsView", kwargs={"exam_pk": exam.pk, "curr_tab": "groups"}),
                "fa-cogs",
            )
        else:
            if not _exam_has_reviewer(exam):
                _add_todo(
                    todos,
                    f"{exam.code}: assign reviewers",
                    "No dedicated reviewer is assigned to this exam.",
                    reverse("reviewSettingsView", kwargs={"exam_pk": exam.pk, "curr_tab": "reviewers"}),
                    "fa-user-plus",
                )
            if not PageMarkers.objects.filter(exam=exam).exclude(copie_no="CORR-BOX").exists():
                _add_todo(
                    todos,
                    f"{exam.code}: upload scans",
                    "Review is enabled but no scanned page is available yet.",
                    reverse("upload_scans", kwargs={"exam_pk": exam.pk}),
                    "fa-cloud-upload-alt",
                )

    if exam.res_and_stats_option:
        if not exam.scales.exists():
            _add_todo(
                todos,
                f"{exam.code}: create a scale",
                "Results are enabled but no scale exists yet.",
                reverse("examInfo", kwargs={"exam_pk": exam.pk}),
                "fa-sliders",
            )
        elif exam.students.exists() and not exam.scaleStatistics.exists():
            _add_todo(
                todos,
                f"{exam.code}: generate statistics",
                "Student data exists but statistics have not been generated.",
                reverse("generate_stats", kwargs={"exam_pk": exam.pk}),
                "fa-chart-line",
            )
        elif not exam.students.exists():
            _add_todo(
                todos,
                f"{exam.code}: import result data",
                "Results are enabled but no student data is available.",
                reverse("import_data_4_stats", kwargs={"exam_pk": exam.pk}),
                "fa-cloud-upload-alt",
            )


def _add_review_todos(todos, user, exam, exam_users):
    if not exam.review_option:
        return

    review_exam_users = [
        exam_user
        for exam_user in exam_users
        if _exam_user_allows(exam_user, ["review"])
    ]
    for exam_user in review_exam_users:
        if exam_user.review_blocked:
            _add_todo(
                todos,
                f"{exam.code}: review blocked",
                "Your review access is currently blocked for this exam.",
                reverse("reviewView", kwargs={"exam_pk": exam.pk}),
                "fa-lock",
            )
            continue

        pages_groups = list(exam_user.pages_groups.all())
        if not pages_groups and _is_reviewer_exam_user(exam_user):
            _add_todo(
                todos,
                f"{exam.code}: no assigned page group",
                "You are reviewer on this exam but no page group is assigned to you.",
                reverse("reviewView", kwargs={"exam_pk": exam.pk}),
                "fa-triangle-exclamation",
            )
            continue

        for pages_group in pages_groups:
            progress = _get_pages_group_progress(pages_group, user.id)
            if progress["total"] and progress["graded"] < progress["total"]:
                _add_todo(
                    todos,
                    f"{exam.code}: continue {pages_group.group_name}",
                    f"{progress['graded']} / {progress['total']} pages reviewed.",
                    reverse(
                        "reviewGroup",
                        kwargs={
                            "exam_pk": exam.pk,
                            "group_pk": pages_group.pk,
                            "currpage": "0",
                            "current_grading_scheme": 0,
                        },
                    ),
                    "fa-glasses",
                )


def _get_dashboard_context(user):
    if user.is_superuser:
        exams = Exam.objects.filter(overall=False)
    else:
        exams = Exam.objects.filter(overall=False, exam_users__user=user).distinct()

    exams = exams.select_related("year", "semester").prefetch_related(
        "exam_users__group",
        "exam_users__user",
        "pagesGroup",
        "scales",
        "scaleStatistics",
    ).order_by("-date", "code")

    all_exam_users = list(ExamUser.objects.filter(user=user).select_related("group"))
    visible_exams = list(exams[:DASHBOARD_EXAM_LIMIT])
    todos = []

    for exam in visible_exams:
        exam_users = _get_user_exam_users(exam, user)
        capabilities = _get_exam_capabilities(user, exam_users)
        if capabilities["manage"]:
            _add_manage_todos(todos, exam)
        if capabilities["review"]:
            _add_review_todos(todos, user, exam, exam_users)

    shortcuts = [
        {
            "label": "Open exam",
            "description": "Browse all exams available to you.",
            "url": reverse("examSelect"),
            "icon": "fa-folder-open",
        },
        {
            "label": "Documentation",
            "description": "Open the eXamc user documentation.",
            "url": f"{settings.DOCUMENTATION_URL}index.html",
            "icon": "fa-circle-question",
        },
    ]
    if user.is_superuser:
        shortcuts.append({
            "label": "Admin",
            "description": "Open Django administration.",
            "url": reverse("admin:index"),
            "icon": "fa-screwdriver-wrench",
        })

    return {
        "dashboard_type": _get_dashboard_type(user, all_exam_users),
        "dashboard_exam_count": exams.count(),
        "dashboard_exam_limit": DASHBOARD_EXAM_LIMIT,
        "dashboard_exams": [_build_exam_card(user, exam) for exam in visible_exams],
        "dashboard_todos": todos,
        "dashboard_shortcuts": shortcuts,
    }
### admin views ###
def getCommonExams(request, pk):
    update_common_exams(pk)

    return HttpResponseRedirect("../admin/examc_app/exam/")

def home(request):
    user_info = request.user.__dict__
    user_info.update(request.user.__dict__)
    print("XXXXXXXXXXXXXX "+str(settings.BASE_DIR))
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
        context.update(_get_dashboard_context(request.user))

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
