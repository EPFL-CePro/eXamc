"""
AMC helper utilities.

This module contains small shared helpers used by the AMC integration layer.
Its responsibilities are intentionally narrow:

- expose the canonical AMC question and answer identifiers used by Django
- give the main LaTeX file of an AMC project folder

Important:
    The identifier helpers in this module are part of the contract between
    Django-side data and the generated LaTeX/AMC output. If the LaTeX naming
    convention changes, these helpers must be updated at the same time.
"""

from pathlib import Path

from examc_app.models import PrepQuestion, PrepQuestionAnswer

# ---------------------------------------------------------------------------
# AMC ID HELPERS (SINGLE SOURCE OF TRUTH)
# ---------------------------------------------------------------------------

def get_amc_question_id(question: PrepQuestion) -> str:
    """
    Build the canonical AMC question identifier for a preparation question.

    This identifier is the one written in the LaTeX of the question (see
    render_question_tex_from_html): it must stay aligned with it.

    Example:
        SECTION-1-SCQ-3
    """
    return (
        f"SECTION-{question.prep_section.position}-"
        f"{question.question_type.code}-{question.position}"
    )



def get_amc_answer_code(
    question: PrepQuestion,
    answer: PrepQuestionAnswer,
) -> str:
    """
    Build the canonical Django-side answer identifier for an answer choice.

    AMC itself relies on the order of the answers: this identifier is only the
    readable name of an answer, used in the hash of the preparation content.

    Example:
        SECTION-1-SCQ-3-A2
    """
    return f"{get_amc_question_id(question)}-A{answer.position}"


# ---------------------------------------------------------------------------
# BUILD / PATH HELPERS
# ---------------------------------------------------------------------------


def get_exam_latex_main_file(build_path: Path) -> Path:
    """
    Return the main LaTeX file for an AMC build/project folder.
    """
    return build_path / "exam.tex"
