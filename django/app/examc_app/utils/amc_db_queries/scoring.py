import logging
from typing import Any

from examc_app.utils.amc_db_queries import (
    AbstractAmcDbManager,
    AmcDbFile,
    AmcDbManagerError,
)

logger = logging.getLogger(__name__)


class AmcScoringDbManager(AbstractAmcDbManager):
    """
    Access to AMC's scoring.sqlite.

    In the scoring tables, (student, copy) identify an answer sheet: `student` is the sheet
    number and `copy` the copy number (0 unless sheets were photocopied).
    """

    def __init__(self, amc_data_path: str):
        super().__init__(amc_data_path, amc_db_file=AmcDbFile.SCORING)

    # ------------------------------------------------------------------
    # scoring_mark
    # ------------------------------------------------------------------
    def get_mean(self) -> float:
        """Mean mark over all sheets, rounded to 4 decimals. 0.0 if there are no marks."""
        query_str = "SELECT AVG(mark) FROM scoring_mark"

        cursor = self._execute(query_str, error="Could not compute the mean mark")

        row = cursor.fetchone()

        return round(row[0], 4) if row and row[0] is not None else 0.0

    def get_marks(self) -> list[dict[str, Any]]:
        """The mark of every sheet: dicts with keys student, total, max, mark."""
        query_str = "SELECT student, total, max, mark FROM scoring_mark ORDER BY student, copy"

        cursor = self._execute(query_str, error="Could not read the marks")

        return [
            {"student": student, "total": total, "max": max_, "mark": mark}
            for student, total, max_, mark in cursor.fetchall()
        ]

    # ------------------------------------------------------------------
    # scoring_score / scoring_question (with layout)
    # ------------------------------------------------------------------
    def get_questions_scoring_details(self) -> list[dict[str, Any]]:
        """
        The score of every question of every sheet, with the sheet's totals.
        :return: Dicts with keys copy, total, max_total, mark, question, score, max_question.
        """
        self._attach(AmcDbFile.LAYOUT)

        query_str = (
            "SELECT sm.student, sm.total, sm.max, sm.mark, lq.name, ss.score, ss.max "
            "FROM scoring_score ss "
            "INNER JOIN layout.layout_question lq ON lq.question = ss.question "
            "INNER JOIN scoring_mark sm ON sm.student = ss.student AND sm.copy = ss.copy "
            "ORDER BY sm.student, sm.copy, lq.name"
        )

        cursor = self._execute(query_str, error="Could not read the questions scoring details")

        return [
            {"copy": copy, "total": total, "max_total": max_total, "mark": mark,
             "question": question, "score": score, "max_question": max_question}
            for copy, total, max_total, mark, question, score, max_question in cursor.fetchall()
        ]

    def get_question_max_points(self, question_name: str, copy_nr = None) -> str:
        """
        Points of a question, read from the first key=value of its scoring strategy
        (e.g. 'b=2,m=-1' gives '2').
        :param question_name: The question name
        :param copy_nr: The sheet number. None or 0: any sheet.
        :raise AmcDbManagerError: if the question or its points can't be found
        """
        self._attach(AmcDbFile.LAYOUT)

        query_str = (
            "SELECT sq.strategy "
            "FROM scoring_question sq "
            "INNER JOIN layout.layout_question lq ON lq.question = sq.question "
            "WHERE lq.name = :name AND (:copy IS NULL OR sq.student = :copy) "
            "ORDER BY sq.student "
            "LIMIT 1"
        )

        cursor = self._execute(
            query_str, {"name": question_name, "copy": copy_nr or None},
            error=f"Could not read the strategy of question {question_name!r} (copy={copy_nr})",
        )

        row = cursor.fetchone()
        
        if row is None or not row[0]:
            raise AmcDbManagerError(f"No scoring strategy for question {question_name!r} (copy={copy_nr})")

        for part in row[0].split(","):
            _key, sep, value = part.partition("=")
            if sep and value.strip():
                return value.strip()

        raise AmcDbManagerError(f"No points in strategy {row[0]!r} of question {question_name!r}")