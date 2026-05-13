#!/usr/bin/env python3
"""Fail when hardening-critical mutation views are missing @require_POST."""

from __future__ import annotations

import ast
import sys
from pathlib import Path


TARGETS = {
    "examc_app/views/review_views.py": [
        "add_new_pages_group",
        "delete_pages_group",
        "edit_pages_group_grading_help",
        "get_pages_group_grading_help",
        "saveMarkers",
        "getMarkersAndComments",
        "saveComment",
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
    ],
    "examc_app/views/exam_views.py": [
        "ldap_search_exam_user_by_email",
        "update_exam_users",
        "update_exam_info",
        "delete_exam_scale",
        "update_exam",
        "set_final_scale",
        "update_exam_options",
        "update_questions",
        "set_common_exam",
        "validate_common_exams_settings",
    ],
    "examc_app/views/results_statistics_views.py": [
        "update_student_present",
        "upload_amc_csv",
        "upload_catalog_pdf",
    ],
    "examc_app/views/preparation_views.py": [
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
    ],
    "examc_app/views/amc_views.py": [
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
        "old_call_amc_annotate",
        "call_amc_annotate",
        "call_amc_generate_results",
        "amc_manual_association_data",
        "amc_set_manual_association",
        "amc_send_annotated_papers_data",
        "call_amc_send_annotated_papers",
        "get_amc_scan_url",
        "get_unrecognized_pages",
    ],
}


def has_require_post(node: ast.FunctionDef) -> bool:
    for dec in node.decorator_list:
        if isinstance(dec, ast.Name) and dec.id == "require_POST":
            return True
        if isinstance(dec, ast.Call) and isinstance(dec.func, ast.Name) and dec.func.id == "require_POST":
            return True
    return False


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    missing = []
    missing_defs = []

    for rel_file, func_names in TARGETS.items():
        file_path = repo_root / rel_file
        source = file_path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(file_path))
        func_nodes = {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)}

        for func_name in func_names:
            node = func_nodes.get(func_name)
            if node is None:
                missing_defs.append(f"{rel_file}:{func_name} (function not found)")
                continue
            if not has_require_post(node):
                missing.append(f"{rel_file}:{func_name}")

    if missing_defs:
        print("ERROR: expected functions not found:")
        for item in missing_defs:
            print(f"  - {item}")

    if missing:
        print("ERROR: missing @require_POST on hardened mutation views:")
        for item in missing:
            print(f"  - {item}")
        return 1

    print("OK: all targeted mutation views include @require_POST")
    return 0


if __name__ == "__main__":
    sys.exit(main())

