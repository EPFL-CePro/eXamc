import json
import os
from pathlib import Path

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import HttpResponseBadRequest, JsonResponse, Http404, FileResponse, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from examc_app.signing import make_token_for
from examc_app.tasks import compile_exam_preview_task, generate_final_exam_files_task
from examc_app.decorators import exam_permission_required
from examc_app.forms import (
    CreateExamProjectForm,
    CreatePrepQuestionForm,
    ExamFirstPageForm,
    PrepScoringFormulaFormSet,
)
from examc_app.models import (
    AcademicYear,
    Course,
    Exam,
    ExamUser,
    PrepQuestion,
    PrepQuestionAnswer,
    PrepScoringFormula,
    PrepSection,
    Semester, ExamAMCJob
)
from examc_app.utils.amc_functions import get_amc_project_path
from examc_app.utils.global_functions import add_course_teachers_ldap
from examc_app.utils.preparation_functions import build_sections_list_context, build_section_form, get_questions, \
    renumber_sections, build_question_form, get_answers, renumber_questions, build_answer_form, renumber_answers, \
    get_scoring_formula_scope, get_scoring_formula_queryset, create_prep_section, create_prep_question, \
    create_prep_answer, compile_exam_preview, save_scoring_formulas, \
    delete_exam_preview_job_files, ensure_exam_not_finalized, update_open_answers
from examc_app.utils.preparation_latex_functions import (
    render_first_page_tex_from_html,
    update_exam_latex, list_available_latex_packages, extract_used_packages,
)
from examc_app.views import logger




# -------------------------
# Create exam project
# -------------------------

@login_required
def create_exam_project(request):
    if request.method == "POST":
        form = CreateExamProjectForm(request.POST)
        if form.is_valid():
            course_id = form.cleaned_data["course"]
            date = form.cleaned_data["date"]
            year_id = form.cleaned_data["year"]
            semester_id = form.cleaned_data["semester"]

            semester = Semester.objects.get(pk=semester_id)
            year = AcademicYear.objects.get(pk=year_id)
            course = Course.objects.get(pk=course_id)
            teachers = add_course_teachers_ldap(course.teachers)

            exam = Exam.objects.create(
                code=course.code,
                name=course.name,
                semester=semester,
                year=year,
                date=date,
            )

            for teacher in teachers:
                ExamUser.objects.create(
                    user=teacher,
                    exam=exam,
                    group_id=2,
                )

            return redirect("examInfo", exam_pk=exam.pk)

        logger.info("INVALID")
        logger.info(form.errors)
        return render(
            request,
            "exam/create_exam_project.html",
            {
                "user_allowed": True,
                "form": form,
                "nav_url": "create_exam_project",
            },
        )

    form = CreateExamProjectForm()
    return render(
        request,
        "exam/create_exam_project.html",
        {
            "user_allowed": True,
            "form": form,
            "nav_url": "create_exam_project",
        },
    )


# -------------------------
# Main page
# -------------------------

@exam_permission_required(["manage"])
def exam_preparation_view(request, exam_pk):
    exam = get_object_or_404(Exam, pk=exam_pk)
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

    return render(
        request,
        "exam/preparation/exam_preparation.html",
        {
            "exam_selected": exam,
            "fp_txt_form": first_page_form,
            "nav_url": "exam_preparation",
            "is_exam_finalized": exam.is_finalized,
            "final_subject_pdf": final_subject_pdf,
            "final_catalog_pdf": final_catalog_pdf,
            **build_sections_list_context(exam),
        },
    )

@exam_permission_required(["manage"])
def unlock_exam_editing(request, exam_pk):
    if request.method != "POST":
        return HttpResponseBadRequest("Invalid method")

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


# -------------------------
# First page
# -------------------------

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

            amc_project_path = get_amc_project_path(exam, False)
            amc_project_template_path = f"{settings.AMC_PROJECTS_ROOT}/templates/base"
            template_first_page_latex_path = f"{amc_project_template_path}/first_page_template.tex"
            first_page_latex_path_output = f"{amc_project_path}/first_page.tex"

            render_first_page_tex_from_html(
                exam,
                exam.first_page_text,
                template_first_page_latex_path,
                first_page_latex_path_output,
            )
    else:
        form = ExamFirstPageForm(instance=exam)
        saved = False

    return render(
        request,
        "exam/preparation/_prep_first_page_card.html",
        {
            "exam_selected": exam,
            "fp_txt_form": form,
            "saved": saved,
            "is_exam_finalized": exam.is_finalized,
        },
    )


# -------------------------
# Sections
# -------------------------

@exam_permission_required(["manage"])
def prep_sections_list(request, exam_pk):
    exam = get_object_or_404(Exam, pk=exam_pk)

    return render(
        request,
        "exam/preparation/_prep_sections_list.html",
        {
            "exam_selected": exam,
            **build_sections_list_context(exam),
        },
    )


@exam_permission_required(["manage"])
def prep_section_panel(request, exam_pk, section_id):
    section = get_object_or_404(PrepSection, pk=section_id, exam_id=exam_pk)

    if request.method == "POST":
        locked = ensure_exam_not_finalized(section.exam)
        if locked:
            return locked
        form = build_section_form(section, data=request.POST)
        saved = form.is_valid()

        if saved:
            form.save()
            section.refresh_from_db()
            update_exam_latex(section.exam)
    else:
        form = build_section_form(section)
        saved = False

    questions = get_questions(section)

    return render(
        request,
        "exam/preparation/_prep_section_card.html",
        {
            "exam_selected": section.exam,
            "section": section,
            "section_form": form,
            "questions": questions,
            "expanded": True,
            "saved": saved,
            "is_exam_finalized": section.exam.is_finalized,
        },
    )


@exam_permission_required(["manage"])
def reorder_prep_sections(request, exam_pk):
    if request.method != "POST":
        return HttpResponseBadRequest("Invalid method")

    exam = get_object_or_404(Exam, pk=exam_pk)

    locked = ensure_exam_not_finalized(exam)
    if locked:
        return locked

    try:
        payload = json.loads(request.body)
        sections_data = payload.get("sections", [])
    except (json.JSONDecodeError, TypeError):
        return HttpResponseBadRequest("Invalid JSON")

    section_map = {section.id: section for section in exam.prepSections.all()}

    for item in sections_data:
        try:
            section_id = int(item["id"])
            position = int(item["position"])
        except (KeyError, TypeError, ValueError):
            continue

        section = section_map.get(section_id)
        if section and section.position != position:
            section.position = position
            section.save(update_fields=["position"])

    return render(
        request,
        "exam/preparation/_prep_sections_list.html",
        {
            "exam_selected": exam,
            **build_sections_list_context(exam),
        },
    )

@exam_permission_required(["manage"])
def reorder_prep_questions(request, exam_pk, section_id):
    if request.method != "POST":
        return HttpResponseBadRequest("Invalid method")

    section = get_object_or_404(PrepSection, pk=section_id, exam_id=exam_pk)

    if section.exam.is_finalized:
        return HttpResponseBadRequest("Exam is finalized")

    try:
        payload = json.loads(request.body)
        questions_data = payload.get("questions", [])
    except (json.JSONDecodeError, TypeError):
        return HttpResponseBadRequest("Invalid JSON")

    question_map = {question.id: question for question in section.prepQuestions.all()}

    for item in questions_data:
        try:
            question_id = int(item["id"])
            position = int(item["position"])
        except (KeyError, TypeError, ValueError):
            continue

        question = question_map.get(question_id)
        if question and question.position != position:
            question.position = position
            question.save(update_fields=["position"])

    update_exam_latex(section.exam)

    return render(
        request,
        "exam/preparation/_prep_questions_list.html",
        {
            "exam_selected": section.exam,
            "section": section,
            "questions": get_questions(section),
            "is_exam_finalized": section.exam.is_finalized,
        },
    )


@exam_permission_required(["manage"])
def reorder_prep_answers(request, exam_pk, question_id):
    if request.method != "POST":
        return HttpResponseBadRequest("Invalid method")

    question = get_object_or_404(
        PrepQuestion,
        pk=question_id,
        prep_section__exam_id=exam_pk,
    )

    if question.prep_section.exam.is_finalized:
        return HttpResponseBadRequest("Exam is finalized")

    try:
        payload = json.loads(request.body)
        answers_data = payload.get("answers", [])
    except (json.JSONDecodeError, TypeError):
        return HttpResponseBadRequest("Invalid JSON")

    answer_map = {answer.id: answer for answer in question.prepAnswers.all()}

    for item in answers_data:
        try:
            answer_id = int(item["id"])
            position = int(item["position"])
        except (KeyError, TypeError, ValueError):
            continue

        answer = answer_map.get(answer_id)
        if answer and answer.position != position:
            answer.position = position
            answer.save(update_fields=["position"])

    update_exam_latex(question.prep_section.exam)

    return render(
        request,
        "exam/preparation/_prep_answers_block.html",
        {
            "exam_selected": question.prep_section.exam,
            "question": question,
            "answers": get_answers(question),
            "is_exam_finalized": question.prep_section.exam.is_finalized,
        },
    )


@exam_permission_required(["manage"])
def add_prep_section(request, exam_pk):
    exam = get_object_or_404(Exam, pk=exam_pk)

    locked = ensure_exam_not_finalized(exam)
    if locked:
        return locked

    section = create_prep_section(exam)

    return render(
        request,
        "exam/preparation/_prep_section_card.html",
        {
            "exam_selected": exam,
            "section": section,
            "section_form": build_section_form(section),
            "questions": get_questions(section),
            "expanded": True,
            "saved": False,
        },
    )


@exam_permission_required(["manage"])
def delete_prep_section(request, exam_pk, section_id):
    exam = get_object_or_404(Exam, pk=exam_pk)

    locked = ensure_exam_not_finalized(exam)
    if locked:
        return locked

    section = get_object_or_404(PrepSection, pk=section_id, exam=exam)

    section.delete()
    renumber_sections(exam)
    update_exam_latex(exam)

    return render(
        request,
        "exam/preparation/_prep_sections_list.html",
        {
            "exam_selected": exam,
            **build_sections_list_context(exam),
        },
    )


# -------------------------
# Questions
# -------------------------

@exam_permission_required(["manage"])
def prep_question_panel(request, exam_pk, question_id):
    question = get_object_or_404(
        PrepQuestion,
        pk=question_id,
        prep_section__exam_id=exam_pk,
    )

    if request.method == "POST":
        exam = Exam.objects.get(pk=exam_pk)
        locked = ensure_exam_not_finalized(exam)
        if locked:
            return locked

        form = build_question_form(question, data=request.POST)
        saved = form.is_valid()

        if saved:
            form.save()
            question.refresh_from_db()

            if question.question_type.code == 'OPEN':
                update_open_answers(question)

            update_exam_latex(question.prep_section.exam)
    else:
        form = build_question_form(question)
        saved = False

    answers = get_answers(question)

    return render(
        request,
        "exam/preparation/_prep_question_block.html",
        {
            "exam_selected": question.prep_section.exam,
            "section": question.prep_section,
            "question": question,
            "question_form": form,
            "answers": answers,
            "saved": saved,
            "is_exam_finalized": question.prep_section.exam.is_finalized,
        },
    )


@exam_permission_required(["manage"])
def add_prep_question(request, exam_pk, section_id):
    exam = get_object_or_404(Exam, pk=exam_pk)
    section = get_object_or_404(PrepSection, pk=section_id, exam=exam)

    if request.method == "POST":
        locked = ensure_exam_not_finalized(exam)
        if locked:
            return locked

        form = CreatePrepQuestionForm(request.POST)

        if form.is_valid():
            question_type = form.cleaned_data["question_type"]
            nb_answers = form.cleaned_data.get("nb_answers") or 0
            title = form.cleaned_data.get("title") or "New question"

            create_prep_question(
                section=section,
                question_type=question_type,
                title=title,
                nb_answers=nb_answers,
            )

            update_exam_latex(section.exam)

            return render(
                request,
                "exam/preparation/_prep_questions_list.html",
                {
                    "exam_selected": exam,
                    "section": section,
                    "questions": get_questions(section),
                },
            )

        return render(
            request,
            "exam/preparation/_prep_add_question_form.html",
            {
                "exam_selected": exam,
                "form": form,
                "section": section,
            },
        )

    form = CreatePrepQuestionForm(initial={"section_pk": section_id})

    return render(
        request,
        "exam/preparation/_prep_add_question_form.html",
        {
            "exam_selected": exam,
            "form": form,
            "section": section,
        },
    )


@exam_permission_required(["manage"])
def delete_prep_question(request, exam_pk, question_id):
    exam = Exam.objects.get(pk=exam_pk)

    locked = ensure_exam_not_finalized(exam)
    if locked:
        return locked

    question = get_object_or_404(
        PrepQuestion,
        pk=question_id,
        prep_section__exam_id=exam_pk,
    )
    section = question.prep_section

    question.delete()
    renumber_questions(section)
    update_exam_latex(section.exam)

    return render(
        request,
        "exam/preparation/_prep_questions_list.html",
        {
            "exam_selected": section.exam,
            "section": section,
            "questions": get_questions(section),
        },
    )


# -------------------------
# Answers
# -------------------------

@exam_permission_required(["manage"])
def prep_answers_block(request, exam_pk, question_id):
    question = get_object_or_404(
        PrepQuestion,
        pk=question_id,
        prep_section__exam_id=exam_pk,
    )

    return render(
        request,
        "exam/preparation/_prep_answers_block.html",
        {
            "exam_selected": question.prep_section.exam,
            "question": question,
            "answers": get_answers(question),
            "is_exam_finalized": question.prep_section.exam.is_finalized,
        },
    )


@exam_permission_required(["manage"])
def prep_answer_panel(request, exam_pk, answer_id):
    answer = get_object_or_404(
        PrepQuestionAnswer,
        pk=answer_id,
        prep_question__prep_section__exam_id=exam_pk,
    )

    if request.method == "POST":
        locked = ensure_exam_not_finalized(answer.prep_question.prep_section.exam)
        if locked:
            return locked

        form = build_answer_form(answer, data=request.POST)
        saved = form.is_valid()

        if saved:
            form.save()
            answer.refresh_from_db()
            update_exam_latex(answer.prep_question.prep_section.exam)
    else:
        form = build_answer_form(answer)
        saved = False

    return render(
        request,
        "exam/preparation/_prep_answer_row.html",
        {
            "exam_selected": answer.prep_question.prep_section.exam,
            "question": answer.prep_question,
            "answer": answer,
            "answer_form": form,
            "saved": saved,
            "is_exam_finalized": answer.prep_question.prep_section.exam.is_finalized,
        },
    )


@exam_permission_required(["manage"])
def add_prep_answer(request, exam_pk, question_id):
    exam = Exam.objects.get(pk=exam_pk)

    locked = ensure_exam_not_finalized(exam)
    if locked:
        return locked

    question = get_object_or_404(
        PrepQuestion,
        pk=question_id,
        prep_section__exam_id=exam_pk,
    )

    create_prep_answer(question)

    update_exam_latex(question.prep_section.exam)

    return render(
        request,
        "exam/preparation/_prep_answers_block.html",
        {
            "exam_selected": question.prep_section.exam,
            "question": question,
            "answers": get_answers(question),
        },
    )


@exam_permission_required(["manage"])
def delete_prep_answer(request, exam_pk, answer_id):
    exam = Exam.objects.get(pk=exam_pk)
    locked = ensure_exam_not_finalized(exam)
    if locked:
        return locked

    answer = get_object_or_404(
        PrepQuestionAnswer,
        pk=answer_id,
        prep_question__prep_section__exam_id=exam_pk,
    )
    question = answer.prep_question

    answer.delete()
    renumber_answers(question)
    update_exam_latex(question.prep_section.exam)

    return render(
        request,
        "exam/preparation/_prep_answers_block.html",
        {
            "exam_selected": question.prep_section.exam,
            "question": question,
            "answers": get_answers(question),
        },
    )


@exam_permission_required(["manage"])
def exam_preview_pdf(request, exam_pk):
    exam = get_object_or_404(Exam, pk=exam_pk)

    result = compile_exam_preview(exam)

    if not result["ok"]:
        return JsonResponse({"error": result["error"]}, status=result["status"])

    return JsonResponse({
        "pdf_url": reverse("exam_preview_pdf_file", kwargs={"exam_pk": exam.pk})
    })

@exam_permission_required(["manage"])
def exam_preview_pdf_file(request, exam_pk, job_pk):
    job = get_object_or_404(
        ExamAMCJob,
        pk=job_pk,
        exam_id=exam_pk,
        requested_by=request.user,
    )

    if job.status != "success" or not job.pdf_path:
        raise Http404("Preview PDF not ready")

    pdf_path = Path(job.pdf_path)
    if not pdf_path.exists():
        raise Http404("Preview PDF file missing")
    # else:
    #     rel_path = pdf_path.resolve().relative_to(Path(settings.AMC_PROJECTS_ROOT).resolve()).as_posix()
    #     preview_pdf_path = make_token_for(rel_path, settings.AMC_PROJECTS_ROOT, token_type="amc_document")

    return FileResponse(open(pdf_path, "rb"), content_type="application/pdf")

@exam_permission_required(["manage"])
def exam_preview_start(request, exam_pk):
    exam = get_object_or_404(Exam, pk=exam_pk)

    active_jobs = ExamAMCJob.objects.filter(
        exam=exam,
        requested_by=request.user,
        job_type="exam_preview",
        status__in=["pending", "running"],
    )

    for active_job in active_jobs:
        active_job.status = "error"
        active_job.error_message = "Replaced by a new preview request."
        active_job.save(update_fields=["status", "error_message", "updated_at"])

    old_jobs = ExamAMCJob.objects.filter(
        exam=exam,
        job_type="exam_preview",
        requested_by=request.user,
    )

    for old_job in old_jobs:
        delete_exam_preview_job_files(old_job)

    old_jobs.delete()

    job = ExamAMCJob.objects.create(
        exam=exam,
        requested_by=request.user,
        job_type="exam_preview",
        status="pending",
        pdf_path="",
        error_message="",
    )

    async_result = compile_exam_preview_task.apply_async(
        args=[job.pk],
        queue="celery",
        routing_key="celery",
    )

    job.celery_task_id = async_result.id
    job.save(update_fields=["celery_task_id", "updated_at"])

    return JsonResponse({
        "job_id": job.pk,
        "task_id": async_result.id,
        "status": job.status,
        "reused": False,
    })

@exam_permission_required(["manage"])
def exam_preview_status(request, exam_pk, job_pk):
    exam = get_object_or_404(Exam, pk=exam_pk)
    job = get_object_or_404(
        ExamAMCJob,
        pk=job_pk,
        exam=exam,
        requested_by=request.user,
    )

    data = {
        "status": job.status,
    }

    if job.status == "success":
        data["pdf_url"] = reverse(
            "exam_preview_pdf_file",
            kwargs={"exam_pk": exam.pk, "job_pk": job.pk},
        )
    elif job.status == "error":
        data["error"] = job.error_message

    return JsonResponse(data)

@exam_permission_required(["manage"])
def scoring_formulas_modal(request, exam_pk):
    if request.method == "GET":
        prep_section = request.GET.get("prep_section") or None
        prep_question = request.GET.get("prep_question") or None
        prep_answer = request.GET.get("prep_answer") or None

        scope = get_scoring_formula_scope(
            prep_section=prep_section,
            prep_question=prep_question,
            prep_answer=prep_answer,
        )

        queryset = get_scoring_formula_queryset(
            exam_pk=exam_pk,
            prep_section=prep_section,
            prep_question=prep_question,
            prep_answer=prep_answer,
        )

        formset = PrepScoringFormulaFormSet(
            queryset=queryset,
            form_kwargs={
                "scope": scope,
                "exam_pk": exam_pk,
                "prep_section": prep_section,
                "prep_question": prep_question,
                "prep_answer": prep_answer,
            },
        )

        return render(
            request,
            "exam/preparation/_prep_scoring_formulas_modal_body.html",
            {
                "formset": formset,
                "exam_pk": exam_pk,
                "prep_section": prep_section,
                "prep_question": prep_question,
                "prep_answer": prep_answer,
                "scope": scope,
            },
        )

    if request.method == "POST":
        prep_section = request.POST.get("prep_section") or None
        prep_question = request.POST.get("prep_question") or None
        prep_answer = request.POST.get("prep_answer") or None

        scope = get_scoring_formula_scope(
            prep_section=prep_section,
            prep_question=prep_question,
            prep_answer=prep_answer,
        )

        queryset = get_scoring_formula_queryset(
            exam_pk=exam_pk,
            prep_section=prep_section,
            prep_question=prep_question,
            prep_answer=prep_answer,
        )

        formset = PrepScoringFormulaFormSet(
            request.POST,
            queryset=queryset,
            form_kwargs={
                "scope": scope,
                "exam_pk": exam_pk,
                "prep_section": prep_section,
                "prep_question": prep_question,
                "prep_answer": prep_answer,
            },
        )

        if formset.is_valid():
            save_scoring_formulas(
                formset,
                exam_pk=exam_pk,
                scope=scope,
                prep_section=prep_section,
                prep_question=prep_question,
                prep_answer=prep_answer,
            )

            return JsonResponse(
                {
                    "success": True,
                    "message": "Formulas saved successfully.",
                }
            )

        html = render(
            request,
            "exam/preparation/_prep_scoring_formulas_modal_body.html",
            {
                "formset": formset,
                "exam_pk": exam_pk,
                "prep_section": prep_section,
                "prep_question": prep_question,
                "prep_answer": prep_answer,
                "scope": scope,
            },
        ).content.decode("utf-8")

        return JsonResponse(
            {
                "success": False,
                "html": html,
            }
        )

    return JsonResponse(
        {
            "success": False,
            "message": "Invalid request method.",
        },
        status=400,
    )


@exam_permission_required(["manage"])
def delete_scoring_formula(request, exam_pk, pk):
    if request.method != "POST":
        exam = Exam.objects.get(pk=exam_pk)

        locked = ensure_exam_not_finalized(exam)
        if locked:
            return locked

        return JsonResponse(
            {
                "success": False,
                "message": "Invalid request method.",
            },
            status=405,
        )

    obj = get_object_or_404(PrepScoringFormula, pk=pk, exam_id=exam_pk)
    obj.delete()

    return JsonResponse(
        {
            "success": True,
            "message": "Scoring formula deleted successfully.",
        }
    )

@exam_permission_required(['manage'])
def edit_latex_file(request,exam_pk):
    exam = Exam.objects.get(pk=exam_pk)

    locked = ensure_exam_not_finalized(exam)
    if locked:
        return locked

    file_type = request.GET.get('type')
    amc_project_path = get_amc_project_path(exam, False)
    if file_type == 'packages':
        filepath = Path(amc_project_path) / "packages.tex"
    else:
        filepath = Path(amc_project_path) / "commands.tex"

    f = open(filepath, 'r')
    file_contents = f.read()
    f.close()
    return HttpResponse(json.dumps([os.path.relpath(filepath, amc_project_path), file_contents]))

@exam_permission_required(['manage'])
def edit_latex_packages(request,exam_pk):
    exam = Exam.objects.get(pk=exam_pk)

    locked = ensure_exam_not_finalized(exam)
    if locked:
        return locked

    amc_project_path = get_amc_project_path(exam, False)
    filepath= Path(amc_project_path) / "packages.tex"
    f = open(filepath, 'r')
    file_contents = f.read()

    latex_packages_available = list_available_latex_packages()
    used_packages = extract_used_packages(file_contents)

    return JsonResponse({
        "latex_available_packages": sorted({pkg["name"] for pkg in latex_packages_available}),
        "used_packages": sorted(set(used_packages)),
    })


@exam_permission_required(['manage'])
def save_latex_edited_file(request,exam_pk):
    data = request.POST['source']
    exam = Exam.objects.get(pk=exam_pk)

    locked = ensure_exam_not_finalized(exam)
    if locked:
        return locked

    file_type = request.POST['type']
    amc_project_path = get_amc_project_path(exam, False)
    if file_type == 'packages':
        filepath = Path(amc_project_path) / "packages.tex"
    else:
        filepath = Path(amc_project_path) / "commands.tex"

    f = open(filepath, 'r+', encoding="utf-8")
    f.truncate(0)
    f.write(data)
    f.close()
    return HttpResponse('ok')


@exam_permission_required(['manage'])
def save_latex_edited_packages(request,exam_pk):
    if request.method != "POST":
        return JsonResponse({"error": "Invalid method"}, status=405)

    exam = Exam.objects.get(pk=exam_pk)
    locked = ensure_exam_not_finalized(exam)
    if locked:
        return locked

    new_used_packages = request.POST.getlist("new_used_packages[]", "[]")

    cleaned_packages = []
    seen = set()

    for pkg in new_used_packages:
        if isinstance(pkg, str):
            pkg = pkg.strip()
            if pkg and pkg not in seen:
                seen.add(pkg)
                cleaned_packages.append(pkg)

    exam = Exam.objects.get(pk=exam_pk)
    amc_project_path = get_amc_project_path(exam, False)
    filepath = Path(amc_project_path) / "packages.tex"

    lines = [
        f"\\usepackage{{{pkg}}}"
        for pkg in cleaned_packages
    ]

    content = "% Auto-generated package list\n"
    if lines:
        content += "\n".join(lines) + "\n"

    filepath.write_text(content, encoding="utf-8")

    return JsonResponse({
        "success": True,
        "used_packages": cleaned_packages,
    })

@exam_permission_required(["manage"])
def generate_final_exam_files_start(request, exam_pk):
    exam = get_object_or_404(Exam, pk=exam_pk)

    active_jobs = ExamAMCJob.objects.filter(
        exam=exam,
        requested_by=request.user,
        job_type="final_build",
        status__in=["pending", "running"],
    )

    for active_job in active_jobs:
        active_job.status = "error"
        active_job.error_message = "Replaced by a new final build request."
        active_job.save(update_fields=["status", "error_message", "updated_at"])

    old_jobs = ExamAMCJob.objects.filter(
        exam=exam,
        requested_by=request.user,
    )
    old_jobs.delete()

    job = ExamAMCJob.objects.create(
        exam=exam,
        requested_by=request.user,
        job_type="final_build",
        status="pending",
        pdf_path="",
        error_message="",
    )

    async_result = generate_final_exam_files_task.apply_async(
        args=[job.pk],
        queue="celery",
        routing_key="celery",
    )

    job.celery_task_id = async_result.id
    job.save(update_fields=["celery_task_id", "updated_at"])

    return JsonResponse({
        "job_id": job.pk,
        "task_id": async_result.id,
        "status": job.status,
        "reused": False,
    })