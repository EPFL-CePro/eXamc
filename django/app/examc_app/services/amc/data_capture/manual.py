from collections import defaultdict
from pathlib import Path
from typing import Any, TypedDict

from examc_app.models import Exam
from examc_app.services.amc.AmcDb import AmcDb
from examc_app.utils.amc_db_queries import select_questions
from examc_app.utils.amc_functions import (
    get_amc_option_by_key, get_amc_project_path, get_amc_project_url, get_extra_pages,
)

# AMC "why" codes -> marker appended after the question id
_WHY_STATES = {"E": "invalid", "V": "empty"}

PageKey = tuple[int, int]  # (copy, page)
QuestionRow = dict[str, Any]


class AmcDataCaptureManualData(TypedDict):
    pages: list[dict[str, Any]]
    questions: list[dict[str, Any]]
    copies: list[Any]


# ---------------------------------------------------------------------------
# Queries
# ---------------------------------------------------------------------------

def _fetch_dicts(db: AmcDb, query: str, params: Any = ()) -> list[dict[str, Any]]:
    """Run a query and return its rows as dicts (empty list on error)."""
    response = db.execute_query(query, params)
    if not response:
        return []
    columns = [d[0] for d in response.description]
    return [dict(zip(columns, row)) for row in response.fetchall()]


def select_manual_data_capture_pages(amc_data_path: str, amc_threshold: str) -> list[dict[str, Any]]:
    """Every captured page, with its sensitivity to the black threshold."""
    query = """
        SELECT
            cp.student          AS copy,
            cp.page             AS page,
            cp.mse              AS mse,
            cp.timestamp_auto   AS timestamp_auto,
            cp.timestamp_manual AS timestamp_manual,
            ROUND(10 * (:t - MIN(ABS(1.0 * cz.black / cz.total - :t))) / :t, 2) AS sensitivity
        FROM capture_page cp
        LEFT JOIN capture_zone cz
            ON  cz.student = cp.student
            AND cz.page    = cp.page
            AND cz.type    = 4
            AND cz.total   > 0
        GROUP BY cp.student, cp.page, cp.copy
        ORDER BY cp.student, cp.page
    """
    db = AmcDb(amc_data_path + "capture.sqlite")
    try:
        return _fetch_dicts(db, query, {"t": float(amc_threshold)})
    finally:
        db.close()


def _page_key(copy: Any, page: Any) -> PageKey:
    return int(float(copy)), int(float(page))


def _group_by_page(rows: list[dict[str, Any]]) -> dict[PageKey, list[QuestionRow]]:
    grouped: dict[PageKey, list[QuestionRow]] = defaultdict(list)
    for row in rows:
        grouped[_page_key(row["student"], row["page"])].append(
            {"question_id": row["question_id"], "why": row["why"]}
        )
    return grouped


def select_manual_data_capture_questions_by_page(amc_data_path: str) -> dict[PageKey, list[QuestionRow]]:
    """Questions of every page, from capture (+ scoring) data, falling back to the layout."""
    scoring_path = Path(amc_data_path) / "scoring.sqlite"
    has_scoring = scoring_path.is_file() and scoring_path.stat().st_size > 0

    db = AmcDb(amc_data_path + "capture.sqlite")
    try:
        if has_scoring:
            db.execute_query("ATTACH DATABASE ? AS scoring", (str(scoring_path),))
            query = """
                SELECT DISTINCT cz.student, cz.page, cz.id_a AS question_id, sc.why AS why
                FROM capture_zone cz
                JOIN scoring.scoring_score sc
                    ON sc.student = cz.student AND sc.question = cz.id_a
                WHERE cz.type = 4
                ORDER BY cz.student, cz.page, cz.id_a
            """
        else:
            query = """
                SELECT DISTINCT student, page, id_a AS question_id, NULL AS why
                FROM capture_zone
                WHERE type = 4
                ORDER BY student, page, id_a
            """
        captured = _group_by_page(_fetch_dicts(db, query))
    finally:
        db.close()

    db = AmcDb(amc_data_path + "layout.sqlite")
    try:
        layout = _group_by_page(_fetch_dicts(db, """
            SELECT DISTINCT student, page, question AS question_id, '' AS why
            FROM layout_box
            ORDER BY student, page, question
        """))
    finally:
        db.close()

    # Capture data wins; the layout is only used for pages with no captured questions.
    return {**layout, **captured}


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------

def _build_questions_ids(question_rows: list[QuestionRow] | None) -> str:
    """Encode a page's questions as '%12%|INV|%13%...%'."""
    parts: list[str] = []
    for row in question_rows or []:
        parts.append(f"%{row['question_id']}%")
        if flag := _WHY_STATES.get(row.get("why")):
            parts.append(flag)
    return "".join(parts) + "%"


def _page_questions(question_rows: list[QuestionRow] | None, names: dict[int, str]) -> list[dict[str, Any]]:
    """A page's questions as [{id, name, state}], state being 'invalid', 'empty' or None."""
    return [
        {
            "id": row["question_id"],
            "name": names.get(row["question_id"], str(row["question_id"])),
            "state": _WHY_STATES.get(row.get("why")),
        }
        for row in question_rows or []
    ]



def get_amc_data_capture_manual_data(exam: Exam) -> AmcDataCaptureManualData | None:
    """Pages, questions, and copies needing manual capture; None if the exam has no AMC project."""
    amc_project_path = get_amc_project_path(exam, False)
    if not amc_project_path:
        return None

    amc_data_path = f"{amc_project_path}/data/"
    amc_project_url = get_amc_project_url(exam)
    amc_threshold = get_amc_option_by_key(exam, "seuil")

    pages = select_manual_data_capture_pages(amc_data_path=amc_data_path, amc_threshold=amc_threshold)
    pages += get_extra_pages(f"{amc_project_path}/scans/extra/", f"{amc_project_url}/scans/extra/")
    pages.sort(key=lambda p: (float(p["copy"]), float(p["page"])))

    questions = select_questions(amc_data_path)
    question_names = {q["question"]: q["name"] for q in questions}

    questions_by_page = select_manual_data_capture_questions_by_page(amc_data_path)

    for page in pages:
        page_questions = _page_questions(
            questions_by_page.get(_page_key(page["copy"], page["page"])),
            question_names,
        )
        page["page_questions"] = page_questions
        page["states"] = [s for s in ("invalid", "empty") if any(q["state"] == s for q in page_questions)]

    return AmcDataCaptureManualData(
        pages=pages,
        questions=questions,
        copies=list(dict.fromkeys(p["copy"] for p in pages)),  # unique, first-seen order
    )