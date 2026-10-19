"""Views of the exam preparation module."""

from .answers import add_prep_answer, delete_prep_answer, prep_answer_panel, reorder_prep_answers
from .final_generation import cancel_final_exam_files, generate_final_exam_files_start
from .latex import edit_latex_file, edit_latex_packages, save_latex_edited_file, save_latex_edited_packages
from .preview import exam_preview_pdf_file, exam_preview_start, exam_preview_status
from .project import (
    create_exam_project,
    exam_preparation_view,
    prep_first_page_panel,
    prep_print_settings,
    unlock_exam_editing,
)
from .questions import (
    add_prep_question,
    delete_prep_question,
    download_prep_questions_template,
    import_prep_questions,
    prep_question_panel,
    reorder_prep_questions,
)
from .scoring import delete_scoring_formula, scoring_formulas_modal, scoring_infos, scoring_update_status
from .sections import add_prep_section, delete_prep_section, prep_section_panel, reorder_prep_sections
from .students import (
    assign_prep_students_seats,
    download_prep_students_export,
    download_prep_students_template,
    exam_preparation_students_view,
    import_prep_students_api,
    import_prep_students_xlsx,
    reorder_prep_students_view,
)

__all__ = [
    "add_prep_answer",
    "add_prep_question",
    "add_prep_section",
    "assign_prep_students_seats",
    "cancel_final_exam_files",
    "create_exam_project",
    "delete_prep_answer",
    "delete_prep_question",
    "delete_prep_section",
    "delete_scoring_formula",
    "download_prep_questions_template",
    "download_prep_students_export",
    "download_prep_students_template",
    "edit_latex_file",
    "edit_latex_packages",
    "exam_preparation_students_view",
    "exam_preparation_view",
    "exam_preview_pdf_file",
    "exam_preview_start",
    "exam_preview_status",
    "generate_final_exam_files_start",
    "import_prep_questions",
    "import_prep_students_api",
    "import_prep_students_xlsx",
    "prep_answer_panel",
    "prep_first_page_panel",
    "prep_print_settings",
    "prep_question_panel",
    "prep_section_panel",
    "reorder_prep_answers",
    "reorder_prep_questions",
    "reorder_prep_sections",
    "reorder_prep_students_view",
    "save_latex_edited_file",
    "save_latex_edited_packages",
    "scoring_formulas_modal",
    "scoring_infos",
    "scoring_update_status",
    "unlock_exam_editing",
]
