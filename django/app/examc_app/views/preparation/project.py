"""Exam preparation page: creation of the exam project, unlocking, print settings and first page."""

from pathlib import Path

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.models import User
from django.http import HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from examc_app.decorators import exam_permission_required
from examc_app.exceptions.exam import NoAcademicYearError
from examc_app.forms.preparation import CreateExamProjectForm, ExamFirstPageForm
from examc_app.models import AcademicYear, Exam, ExamUser, Semester
from examc_app.services.oasis import get_courses, get_teachers_names_by_course
from examc_app.signing import make_token_for
from examc_app.utils.global_functions import add_course_teachers_ldap
from examc_app.utils.preparation_functions import (
    build_sections_list_context,
    ensure_exam_not_finalized,
    get_active_final_build_job,
    is_exam_locked,
)
from examc_app.utils.preparation_latex_functions import (
    get_exam_katex_macros,
    update_exam_latex,
)

from ...utils.view_context_helpers import ViewContext, ViewTab
from ._htmx import with_save_feedback


@exam_permission_required(["manage"])
def preparation_view(request, exam_pk):
    exam = get_object_or_404(Exam, pk=exam_pk)
    user = get_object_or_404(User, pk=request.user.id)

    first_page_form = ExamFirstPageForm(instance=exam)

    final_subject_pdf = ""
    final_catalog_pdf = ""

    if exam.is_finalized and exam.finalized_build and exam.finalized_build.project_path:
        project_path = Path(exam.finalized_build.project_path)
        exam_prefix = exam.code or f"exam-{exam.pk}"

        subject_pdf = project_path / f"{exam_prefix}-sujet.pdf"
        catalog_pdf = project_path / f"{exam_prefix}-catalog.pdf"

        root = Path(settings.AMC_PROJECTS_ROOT).resolve()
        if subject_pdf.exists():
            rel_path = subject_pdf.resolve().relative_to(root).as_posix()
            final_subject_pdf = make_token_for(rel_path, settings.AMC_PROJECTS_ROOT,token_type="amc_document")
        if catalog_pdf.exists():
            rel_path = catalog_pdf.resolve().relative_to(root).as_posix()
            final_catalog_pdf = make_token_for(rel_path, settings.AMC_PROJECTS_ROOT,token_type="amc_document")

    view_context = ViewContext(
        exam_pk=exam.pk,
        user_id=user.id,
        tabs=[
            ViewTab(key="exam", label="Exam"),
            ViewTab(key="students", label="Students"),
        ],
        nav_url="exam_preparation",
    )
    
    view_context.update(
        fp_txt_form=first_page_form,
        is_exam_finalized=exam.is_finalized,
        is_exam_locked=is_exam_locked(exam),
        active_final_job=get_active_final_build_job(exam),
        final_subject_pdf=final_subject_pdf,
        final_catalog_pdf=final_catalog_pdf,
        katex_macros=get_exam_katex_macros(exam),
        **build_sections_list_context(exam)
    )

    return render(
        request,
        "exam/preparation.html",
        view_context.as_dict()
    )

def create_exam_project(request):
    # get the most current academic year
    year = AcademicYear.objects.order_by("-code").first()

    if year is None:
        raise NoAcademicYearError("No academic year in the database")

    teacher_names_by_course = get_teachers_names_by_course(year.code)
    courses = get_courses(year.code)

    form = CreateExamProjectForm(
        request.POST or None,
        courses=courses,
        teacher_names_by_course=teacher_names_by_course
    )

    if request.method == 'POST' and form.is_valid():
        course_code = form.cleaned_data['course']
        course_name = form.courses_by_code[course_code]["coursNomFr"]
        course_teachers = form.teachers_by_course.get(course_code, [])
        teacher_scipers = [t["sciper"] for t in course_teachers]

        date = form.cleaned_data['date']
        semester_id = form.cleaned_data['semester']

        semester = Semester.objects.get(pk=semester_id)
        teachers = add_course_teachers_ldap(teacher_scipers)

        exam = Exam()
        exam.code = course_code
        exam.name = course_name
        exam.semester = semester
        exam.year = year
        exam.date = date
        exam.save()

        for teacher in teachers:
            exam_user = ExamUser()
            exam_user.user = teacher
            exam_user.exam = exam
            exam_user.group_id = 2
            exam_user.save()

        # The AMC project (base files, exam.tex) exists from the creation of the exam
        update_exam_latex(exam)

        return redirect("exam_info", exam_pk=exam.pk)

    # if form is invalid or a GET (or any other method) is received, we'll create a blank form
    return render(
        request,
        "exam/create_exam_project.html",
        {
            "user_allowed": True,
            "form": form,
            "nav_url": "create_exam_project",
            "errors": form.errors_list,
        }
    )


@exam_permission_required(["manage"])
@require_POST
def unlock_exam_editing(request, exam_pk):
    exam = get_object_or_404(Exam, pk=exam_pk)

    exam.is_finalized = False
    exam.finalized_at = None
    exam.finalized_build = None
    exam.save(update_fields=["is_finalized", "finalized_at"])

    messages.warning(
        request,
        "Editing has been unlocked. Any previously generated final files may now be inconsistent. "
        "All printed documents should be destroyed and final files must be generated again before use."
    )

    return redirect("exam_preparation", exam_pk=exam.pk)


@exam_permission_required(["manage"])
def prep_print_settings(request, exam_pk):
    """Print format of the exam (standard or booklet), used by the final generation to pad the copies."""
    exam = get_object_or_404(Exam, pk=exam_pk)

    if request.method == "POST":
        locked = ensure_exam_not_finalized(exam)
        if locked:
            return locked
        print_format = request.POST.get("print_format")
        if print_format not in dict(Exam.PRINT_FORMAT_CHOICES):
            return HttpResponseBadRequest("Unknown print format.")
        exam.print_format = print_format
        exam.save(update_fields=["print_format"])
        # The preview compiles the files of the project: \ExamcBooklet is written in examc_generated_vars.tex
        update_exam_latex(exam)
        # The button of the page shows the format

        return render(
            request,
            "exam/preparation/partials/_prep_print_settings_form.html",
            {
                "exam_selected": exam,
                "oob": True
            })

    return render(
        request,
        "exam/preparation/partials/_prep_print_settings_form.html",
        {
            "exam_selected": exam
        }
    )


@exam_permission_required(["manage"])
def prep_first_page_panel(request, exam_pk):
    exam = get_object_or_404(Exam, pk=exam_pk)

    if request.method == "POST":
        locked = ensure_exam_not_finalized(exam)
        if locked:
            return locked
        form = ExamFirstPageForm(request.POST, instance=exam)
        saved = form.is_valid()

        if saved:
            form.save()
            exam.refresh_from_db()

            # Creates the AMC project if needed, and renders first_page.tex along with exam.tex
            update_exam_latex(exam)
    else:
        form = ExamFirstPageForm(instance=exam)
        saved = False

    response = render(
        request,
        "exam/preparation/partials/_prep_first_page_card.html",
        {
            "exam_selected": exam,
            "fp_txt_form": form,
            "saved": saved,
            "is_exam_locked": is_exam_locked(exam),
        },
    )
    return with_save_feedback(request, response, saved)
