from pathlib import Path

from django.conf import settings
from django.urls import reverse

from examc_app.models import Exam, ExamUser, PageMarkers, PagesGroupGradingSchemeCheckedBox
from examc_app.permissions import exam_group_names_allow


DASHBOARD_EXAM_LIMIT = 20
DASHBOARD_TODO_LIMIT = 8


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
        return "Superuser overview"

    group_names = _get_exam_user_group_names(exam_users)
    if exam_group_names_allow(group_names, ["manage"]):
        return "Management access"
    if _normalize_group_names(group_names) & _get_reviewer_group_names():
        return "Review access"
    if exam_group_names_allow(group_names, ["see_results"]):
        return "Results access"
    return "Standard access"


def _get_exam_capabilities(user, exam_users):
    return {
        "manage": user.is_superuser or _exam_users_allow(exam_users, ["manage"]),
        "review": user.is_superuser or _exam_users_allow(exam_users, ["review"]),
        "results": user.is_superuser or _exam_users_allow(exam_users, ["see_results"]),
    }


def _get_review_progress(exam):
    total_copies = _get_exam_review_copy_count(exam)
    if not total_copies:
        return None

    pages_groups_progress = [
        progress
        for progress in (
            _get_pages_group_progress(pages_group, total_copies=total_copies)
            for pages_group in exam.pagesGroup.all()
        )
        if progress["percent"] is not None
    ]
    if not pages_groups_progress:
        return None

    average_graded = sum(progress["graded"] for progress in pages_groups_progress) / len(pages_groups_progress)
    return {
        "graded": _format_progress_count(average_graded),
        "total": total_copies,
        "percent": round(100 / total_copies * average_graded),
    }


def _format_progress_count(count):
    rounded_count = round(count, 1)
    if rounded_count == int(rounded_count):
        return int(rounded_count)
    return rounded_count


def _get_exam_review_scans_path(exam):
    if not exam.year_id or not exam.semester_id or not exam.date:
        return None

    scans_path = (
        Path(settings.SCANS_ROOT)
        / str(exam.year.code)
        / str(exam.semester.code)
        / f"{exam.code}_{exam.date:%Y%m%d}"
    )
    if not scans_path.is_dir():
        return None

    return scans_path


def _get_exam_review_copy_dirs(exam):
    scans_path = _get_exam_review_scans_path(exam)
    if not scans_path:
        return []

    return [
        scan_path
        for scan_path in scans_path.iterdir()
        if scan_path.is_dir() and scan_path.name != "0000"
    ]


def _get_exam_review_copy_count(exam):
    return len(_get_exam_review_copy_dirs(exam))


def _exam_has_review_scan_files(exam):
    for copy_path in _get_exam_review_copy_dirs(exam):
        if any(scan_path.is_file() for scan_path in copy_path.iterdir()):
            return True
    return False


def _get_pages_group_progress(pages_group, user_id=None, total_copies=None):
    total = total_copies if total_copies is not None else _get_exam_review_copy_count(pages_group.exam)
    markers = PageMarkers.objects.filter(pages_group=pages_group).exclude(copie_no="CORR-BOX")
    if pages_group.use_grading_scheme:
        graded = PagesGroupGradingSchemeCheckedBox.objects.filter(pages_group=pages_group)
        if user_id:
            graded = graded.filter(user_id=user_id)
        graded_count = graded.values("copy_nr").distinct().count()
    else:
        graded = markers.filter(correctorBoxMarked=True)
        if user_id:
            graded = graded.filter(pageMarkers_users__user_id=user_id).distinct()
        graded_count = graded.count()

    return {
        "graded": graded_count,
        "total": total,
        "percent": round(100 / total * graded_count) if total else None,
    }


def _get_filter_tags(exam, capabilities):
    filter_tags = []
    if capabilities["manage"]:
        filter_tags.append("manage")
    if exam.review_option and capabilities["review"]:
        filter_tags.append("review")
    if exam.res_and_stats_option and capabilities["results"]:
        filter_tags.append("results")
    return filter_tags


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

    role = _get_role_label(user, exam_users)
    return {
        "exam": exam,
        "role": role,
        "module_badges": module_badges,
        "actions": actions,
        "review_progress": _get_review_progress(exam) if exam.review_option else None,
        "filter_tags": _get_filter_tags(exam, capabilities),
        "search_text": " ".join([exam.code or "", exam.name or "", role, " ".join(module_badges)]).casefold(),
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
            if not _exam_has_review_scan_files(exam):
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


def _get_dashboard_exam_filters(exam_cards):
    filter_defs = [
        ("all", "All"),
        ("manage", "Manage"),
        ("review", "Review"),
        ("results", "Results"),
    ]
    filters = []
    for key, label in filter_defs:
        if key == "all":
            count = len(exam_cards)
        else:
            count = sum(1 for card in exam_cards if key in card["filter_tags"])
        filters.append({
            "key": key,
            "label": label,
            "count": count,
        })
    return filters


def get_dashboard_context(user):
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

    exam_cards = [_build_exam_card(user, exam) for exam in visible_exams]
    shortcuts = [
        {
            "label": "Open exam",
            "description": "Browse all exams available to you.",
            "url": reverse("examSelect"),
            "icon": "fa-folder-open",
        },
        {
            "label": "Room plan",
            "description": "Generate and export exam room plans.",
            "url": reverse("generate_room_plan"),
            "icon": "fa-meteor",
        },
        {
            "label": "Students CSV generator",
            "description": "Prepare student CSV files for exam workflows.",
            "url": reverse("csvgen"),
            "icon": "fa-file-excel",
        },
        {
            "label": "Documentation",
            "description": "Open the eXamc user documentation.",
            "url": reverse("documentation"),
            "icon": "fa-circle-question",
        },
    ]
    if user.is_superuser:
        shortcuts.append({
            "label": "Create exam",
            "description": "Create a new exam project.",
            "url": reverse("create_exam_project"),
            "icon": "fa-plus",
        })
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
        "dashboard_visible_exam_count": len(exam_cards),
        "dashboard_exam_filters": _get_dashboard_exam_filters(exam_cards),
        "dashboard_exams": exam_cards,
        "dashboard_todos": todos,
        "dashboard_shortcuts": shortcuts,
    }
