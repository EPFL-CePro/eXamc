"""Sections of the exam: panel, add, delete and reorder."""

import json

from django.http import HttpResponseBadRequest
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_POST

from examc_app.decorators import exam_permission_required
from examc_app.models import Exam, PrepSection
from examc_app.utils.preparation_functions import (
    build_section_form,
    build_sections_list_context,
    create_prep_section,
    ensure_exam_not_finalized,
    is_exam_locked,
    get_questions,
    renumber_sections,
)
from examc_app.utils.preparation_latex_functions import update_exam_latex

from ._htmx import with_save_feedback


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

    response = render(
        request,
        "exam/preparation/_prep_section_card.html",
        {
            "exam_selected": section.exam,
            "section": section,
            "section_form": form,
            "questions": questions,
            "expanded": True,
            "saved": saved,
            "is_exam_locked": is_exam_locked(section.exam),
        },
    )
    return with_save_feedback(request, response, saved)


@exam_permission_required(["manage"])
@require_POST
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
@require_POST
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


@exam_permission_required(["manage"])
@require_POST
def reorder_prep_sections(request, exam_pk):
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

    update_exam_latex(exam)

    return render(
        request,
        "exam/preparation/_prep_sections_list.html",
        {
            "exam_selected": exam,
            **build_sections_list_context(exam),
        },
    )
