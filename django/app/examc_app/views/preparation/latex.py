"""Edition of the LaTeX files and packages of the exam."""

import json
import os
from pathlib import Path

from django.http import HttpRequest, HttpResponse, JsonResponse
from django.views.decorators.http import require_POST

from examc_app.decorators import exam_permission_required
from examc_app.models import Exam
from examc_app.utils.amc_functions import ensure_amc_project
from examc_app.utils.preparation_functions import ensure_exam_not_finalized
from examc_app.utils.preparation_latex_functions import extract_used_packages, list_available_latex_packages


@exam_permission_required(['manage'])
def edit_latex_file(request: HttpRequest, exam_pk: int):
    exam = Exam.objects.get(pk=exam_pk)

    locked = ensure_exam_not_finalized(exam)
    if locked:
        return locked

    file_type = request.GET.get('type')
    amc_project_path = ensure_amc_project(exam)
    if file_type == 'packages':
        filepath = Path(amc_project_path) / "packages.tex"
    else:
        filepath = Path(amc_project_path) / "commands.tex"

    with open(filepath, 'r') as f:
        file_contents = f.read()
        f.close()

    return HttpResponse(json.dumps([os.path.relpath(filepath, amc_project_path), file_contents]))


@exam_permission_required(['manage'])
def edit_latex_packages(request,exam_pk):
    exam = Exam.objects.get(pk=exam_pk)

    locked = ensure_exam_not_finalized(exam)
    if locked:
        return locked

    amc_project_path = ensure_amc_project(exam)
    filepath= Path(amc_project_path) / "packages.tex"

    with open(filepath, 'r') as f:
        file_contents = f.read()

    latex_packages_available = list_available_latex_packages()
    used_packages = extract_used_packages(file_contents)

    return JsonResponse({
        "latex_available_packages": sorted({pkg["name"] for pkg in latex_packages_available}),
        "used_packages": sorted(set(used_packages)),
    })


@exam_permission_required(['manage'])
@require_POST
def save_latex_edited_file(request,exam_pk):
    data = request.POST['source']
    exam = Exam.objects.get(pk=exam_pk)

    locked = ensure_exam_not_finalized(exam)
    if locked:
        return locked

    file_type = request.POST['type']
    amc_project_path = ensure_amc_project(exam)
    if file_type == 'packages':
        filepath = Path(amc_project_path) / "packages.tex"
    else:
        filepath = Path(amc_project_path) / "commands.tex"

    with open(filepath, 'r+', encoding="utf-8") as f:
        f.truncate(0)
        f.write(data)

    return HttpResponse('ok')


@exam_permission_required(['manage'])
@require_POST
def save_latex_edited_packages(request,exam_pk):
    exam = Exam.objects.get(pk=exam_pk)
    locked = ensure_exam_not_finalized(exam)
    if locked:
        return locked

    new_used_packages = request.POST.getlist("new_used_packages[]")

    cleaned_packages = []
    seen = set()

    for pkg in new_used_packages:
        if isinstance(pkg, str):
            pkg = pkg.strip()
            if pkg and pkg not in seen:
                seen.add(pkg)
                cleaned_packages.append(pkg)

    exam = Exam.objects.get(pk=exam_pk)
    amc_project_path = ensure_amc_project(exam)
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
