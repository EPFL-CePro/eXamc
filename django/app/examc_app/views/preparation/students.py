"""Students of the exam: page, import (Excel file, IS-Academia), template, export, order and seats."""

import logging
import re

from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_POST

from examc_app.decorators import exam_permission_required
from examc_app.models import Exam
from examc_app.services.oasis import OasisError
from examc_app.services.person_directory import PersonDirectoryError
from examc_app.services.student.prep_import import (
    StudentsFileError,
    build_students_export,
    build_students_template,
    load_students_file,
    load_students_from_oasis,
    replace_prep_students,
)
from examc_app.services.student.prep_order import (
    StudentsOrderError,
    reorder_prep_students,
)
from examc_app.services.student.prep_seats import (
    SeatsAssignmentError,
    assign_rooms_and_seats,
)
from examc_app.utils.preparation_functions import (
    ensure_exam_not_finalized,
    is_exam_locked,
)

logger = logging.getLogger(__name__)


@exam_permission_required(["manage"])
def exam_preparation_students_view(request, exam_pk):
    exam = get_object_or_404(Exam, pk=exam_pk)

    return render(
        request,
        "exam/preparation/exam_preparation_students.html",
        {
            "exam": exam,
            "exam_selected": exam,
            "nav_url": "exam_preparation_students",
            "is_exam_finalized": exam.is_finalized,
            "is_exam_locked": is_exam_locked(exam),
        },
    )


@exam_permission_required(["manage"])
def download_prep_students_template(request, exam_pk):
    response = HttpResponse(
        build_students_template(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    response["Content-Disposition"] = 'attachment; filename="students_template.xlsx"'
    return response


@exam_permission_required(["manage"])
def download_prep_students_export(request, exam_pk):
    """The exam students as an Excel file to rearrange and import back (see build_students_export)."""
    exam = get_object_or_404(Exam, pk=exam_pk)
    response = HttpResponse(
        build_students_export(exam),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    file_name = re.sub(r"[^A-Za-z0-9_.-]+", "_", f"students_{exam.code}_{exam.year.code}") + ".xlsx"
    response["Content-Disposition"] = f'attachment; filename="{file_name}"'
    return response


@exam_permission_required(["manage"])
@require_POST
def import_prep_students_xlsx(request, exam_pk):
    """Replaces the exam students by those of an uploaded .xlsx file (see services.student.prep_import)."""
    exam = get_object_or_404(Exam, pk=exam_pk)

    locked = ensure_exam_not_finalized(exam)
    if locked:
        return locked

    uploaded_file = request.FILES.get("students_file")
    if not uploaded_file:
        return JsonResponse({"errors": ["No file selected."]}, status=400)

    # The file is only read: nothing is saved on disk
    try:
        students, warnings = load_students_file(uploaded_file.name, uploaded_file.read())
    except StudentsFileError as error:
        return JsonResponse({"errors": error.errors}, status=400)
    except PersonDirectoryError:
        logger.exception("EPFL directory unavailable during the students import of exam %s", exam.pk)
        return JsonResponse({"errors": ["The EPFL directory could not be reached: please try again later."]},
                            status=503)

    result = replace_prep_students(exam, students, warnings)
    return JsonResponse({"imported": result.imported, "replaced": result.replaced, "warnings": list(result.warnings)})


@exam_permission_required(["manage"])
@require_POST
def import_prep_students_api(request, exam_pk):
    """Replaces the exam students by those enrolled in the course in IS-Academia (see services.student.prep_import)."""
    exam = get_object_or_404(Exam, pk=exam_pk)

    locked = ensure_exam_not_finalized(exam)
    if locked:
        return locked

    try:
        students, warnings = load_students_from_oasis(exam)
    except StudentsFileError as error:
        return JsonResponse({"errors": error.errors}, status=400)
    except OasisError:
        logger.exception("OASIS unavailable during the students import of exam %s", exam.pk)
        return JsonResponse({"errors": ["IS-Academia (OASIS) could not be reached: please try again later."]},
                            status=503)
    except PersonDirectoryError:
        logger.exception("EPFL directory unavailable during the students import of exam %s", exam.pk)
        return JsonResponse({"errors": ["The EPFL directory could not be reached: please try again later."]},
                            status=503)

    result = replace_prep_students(exam, students, warnings)
    return JsonResponse({"imported": result.imported, "replaced": result.replaced, "warnings": list(result.warnings)})


@exam_permission_required(["manage"])
@require_POST
def reorder_prep_students_view(request, exam_pk):
    """Renumbers the exam students in the chosen order (see services.student.prep_order)."""
    exam = get_object_or_404(Exam, pk=exam_pk)

    locked = ensure_exam_not_finalized(exam)
    if locked:
        return locked

    try:
        reordered = reorder_prep_students(exam, request.POST.get("order", ""))
    except StudentsOrderError as error:
        return JsonResponse({"errors": error.errors}, status=400)

    return JsonResponse({"reordered": reordered})


@exam_permission_required(["manage"])
@require_POST
def assign_prep_students_seats(request, exam_pk):
    """Gives a room and numbered seats to a range of exam students (see services.student.prep_seats)."""
    exam = get_object_or_404(Exam, pk=exam_pk)

    locked = ensure_exam_not_finalized(exam)
    if locked:
        return locked

    try:
        first_id, last_id, first_number = (int(request.POST.get(name, "")) for name in
                                           ("first_id", "last_id", "first_number"))
    except ValueError:
        return JsonResponse({"errors": ["The IDs and the first seat number must be whole numbers."]}, status=400)

    try:
        result = assign_rooms_and_seats(exam, first_id, last_id, request.POST.get("room", ""),
                                        request.POST.get("seat_pattern", ""), first_number)
    except SeatsAssignmentError as error:
        return JsonResponse({"errors": error.errors}, status=400)

    return JsonResponse({"updated": result.updated, "first_seat": result.first_seat, "last_seat": result.last_seat})
