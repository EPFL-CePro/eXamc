#!/usr/bin/env python3
"""Fail when hardening-critical mutation views are missing @require_POST.

Views are tracked by their Django URL name (the `name=` kwarg in urls.py)
instead of a hardcoded (file, function name) pair. For each tracked URL
name, the current view function is looked up dynamically:
  1. resolve the URL name to a view reference in urls.py (`views.<func>`)
  2. find whichever file under examc_app/views/ currently defines that
     function

This survives the view being renamed or moved to a different file under
examc_app/views/, since nothing here hardcodes where a given view lives.
If a tracked URL name is removed from urls.py, or its view function can no
longer be found, the check fails loudly instead of silently losing
coverage - update TARGET_URL_NAMES below once that removal is confirmed
intentional.

A couple of hardening-critical views are not wired to any URL at all
(dead code, kept here for the record) - they are tracked directly by
function name in ORPHANED_VIEWS since there is no URL name to key off.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

# URL names (see examc_app/urls.py `name=`) of hardened mutation views.
TARGET_URL_NAMES = {
    # review_views.py
    "add_new_pages_group",
    "delete_pages_group",
    "edit_pages_group_grading_help",
    "get_pages_group_grading_help",
    "save_markers",
    "get_markers_and_comments",
    "save_comment",
    "update_page_group_markers",
    "review_student_pages_group_is_locked",
    "remove_review_user_locks",
    "get_copy_page",
    "add_new_grading_scheme_checkbox",
    "delete_grading_scheme_checkbox",
    "add_new_grading_scheme",
    "delete_grading_scheme",
    "save_pages_group_student_report_note",
    "update_pages_group_check_box",
    # exam_views.py
    "ldap_search_exam_user_by_email",
    "update_exam_users",
    "update_exam_info",
    "delete_exam_scale",
    "set_final_scale",
    "update_exam_options",
    "update_questions",
    "set_common_exam",
    "validate_common_exams_settings",
    # results_statistics_views.py
    "update_student_present",
    "upload_amc_csv",
    "upload_catalog_pdf",
    # preparation_views.py
    "exam_add_section",
    "exam_update_section",
    "get_header_section_txt",
    "exam_update_question",
    "exam_update_answers",
    "exam_add_answer",
    "exam_remove_answer",
    "exam_remove_question",
    "exam_remove_section",
    "exam_update_first_page",
    # amc_views.py
    "get_amc_marks_positions",
    "update_amc_mark_zone",
    "edit_amc_file",
    "save_amc_edited_file",
    "call_amc_update_documents",
    "call_amc_layout_detection",
    "call_amc_automatic_data_capture",
    "import_scans_from_review_pages",
    "import_scans_from_review",
    "view_amc_log_file",
    "get_amc_zooms",
    "add_unrecognized_page",
    "call_amc_mark",
    "call_amc_automatic_association",
    "amc_update_students_file",
    "call_amc_annotate",
    "call_amc_generate_results",
    "amc_manual_association_data",
    "amc_set_manual_association",
    "amc_send_annotated_papers_data",
    "call_amc_send_annotated_papers",
    "get_amc_scan_url",
    "get_unrecognized_pages",
}

# Hardening-critical views with no urls.py entry (dead code, not reachable
# via HTTP) - tracked by function name directly since there is no URL name.
ORPHANED_VIEWS = {
    "update_exam",  # exam_views.py - superseded, no longer routed
    "old_call_amc_annotate",  # amc_views.py - superseded by call_amc_annotate
}

URLS_FILE = "app/examc_app/urls.py"
VIEWS_DIR = "app/examc_app/views"


def _call_target_name(call: ast.Call) -> str | None:
    if isinstance(call.func, ast.Name):
        return call.func.id
    if isinstance(call.func, ast.Attribute):
        return call.func.attr
    return None


def _view_func_name(call: ast.Call) -> str | None:
    """Second positional arg of path()/re_path(): the view reference."""
    if len(call.args) < 2:
        return None
    view_arg = call.args[1]
    if isinstance(view_arg, ast.Attribute):
        return view_arg.attr
    if isinstance(view_arg, ast.Name):
        return view_arg.id
    return None


def _name_kwarg(call: ast.Call) -> str | None:
    for kw in call.keywords:
        if kw.arg == "name" and isinstance(kw.value, ast.Constant):
            return kw.value.value
    return None


def build_url_name_to_func_name(urls_path: Path) -> dict[str, str]:
    tree = ast.parse(urls_path.read_text(encoding="utf-8"), filename=str(urls_path))
    mapping: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and _call_target_name(node) in ("path", "re_path"):
            url_name = _name_kwarg(node)
            func_name = _view_func_name(node)
            if url_name and func_name:
                mapping[url_name] = func_name
    return mapping


def find_function(views_dir: Path, func_name: str) -> list[tuple[Path, ast.FunctionDef]]:
    matches = []
    for py_file in sorted(views_dir.glob("*.py")):
        tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
        for node in tree.body:
            if isinstance(node, ast.FunctionDef) and node.name == func_name:
                matches.append((py_file, node))
    return matches


def has_require_post(node: ast.FunctionDef) -> bool:
    for dec in node.decorator_list:
        if isinstance(dec, ast.Name) and dec.id == "require_POST":
            return True
        if isinstance(dec, ast.Call) and isinstance(dec.func, ast.Name) and dec.func.id == "require_POST":
            return True
    return False


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    views_dir = repo_root / VIEWS_DIR
    url_name_to_func = build_url_name_to_func_name(repo_root / URLS_FILE)

    stale_urls = []
    ambiguous = []
    not_found = []
    missing_decorator = []

    for url_name in sorted(TARGET_URL_NAMES):
        func_name = url_name_to_func.get(url_name)
        if func_name is None:
            stale_urls.append(url_name)
            continue
        matches = find_function(views_dir, func_name)
        if not matches:
            not_found.append(f"{url_name} -> {func_name} (not found under {VIEWS_DIR})")
            continue
        if len(matches) > 1:
            locations = ", ".join(str(path.relative_to(repo_root)) for path, _ in matches)
            ambiguous.append(f"{url_name} -> {func_name} (defined in multiple files: {locations})")
            continue
        py_file, node = matches[0]
        if not has_require_post(node):
            missing_decorator.append(f"{url_name} -> {py_file.relative_to(repo_root)}:{func_name}")

    for func_name in sorted(ORPHANED_VIEWS):
        matches = find_function(views_dir, func_name)
        if not matches:
            not_found.append(f"{func_name} (orphaned view, not found under {VIEWS_DIR})")
            continue
        if len(matches) > 1:
            locations = ", ".join(str(path.relative_to(repo_root)) for path, _ in matches)
            ambiguous.append(f"{func_name} (orphaned view, defined in multiple files: {locations})")
            continue
        py_file, node = matches[0]
        if not has_require_post(node):
            missing_decorator.append(f"{func_name} -> {py_file.relative_to(repo_root)} (orphaned view)")

    if stale_urls:
        print(f"ERROR: tracked URL names no longer registered in {URLS_FILE} (update TARGET_URL_NAMES):")
        for item in stale_urls:
            print(f"  - {item}")

    if ambiguous:
        print("ERROR: view function name is ambiguous across the views package:")
        for item in ambiguous:
            print(f"  - {item}")

    if not_found:
        print("ERROR: view function not found:")
        for item in not_found:
            print(f"  - {item}")

    if missing_decorator:
        print("ERROR: missing @require_POST on hardened mutation views:")
        for item in missing_decorator:
            print(f"  - {item}")

    if stale_urls or ambiguous or not_found or missing_decorator:
        return 1

    print(f"OK: all {len(TARGET_URL_NAMES) + len(ORPHANED_VIEWS)} tracked mutation views include @require_POST")
    return 0


if __name__ == "__main__":
    sys.exit(main())
