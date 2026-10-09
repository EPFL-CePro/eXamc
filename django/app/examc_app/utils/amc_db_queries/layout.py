import logging
from typing import Any

from examc_app.exceptions.amc import AmcDbManagerError
from examc_app.utils.amc_db_queries import AbstractAmcDbManager, AmcDbFile

logger = logging.getLogger(__name__)

#: layout_box.role of answer boxes (AMC's BOX_ROLE_ANSWER).
ROLE_ANSWER = 1


class AmcLayoutDbManager(AbstractAmcDbManager):
    """
    Access to AMC's layout.sqlite.

    In layout_box, `student` is the sheet number (the copy), and `question` references
    layout_question.question, whose `name` is the question's label in the LaTeX source.
    """

    def __init__(self, amc_data_path: str):
        super().__init__(amc_data_path, amc_db_file=AmcDbFile.LAYOUT)

    # ------------------------------------------------------------------
    # layout_page
    # ------------------------------------------------------------------
    def select_count_layout_pages(self) -> int:
        """Number of pages in the layout."""
        query_str = "SELECT COUNT(*) FROM layout_page"

        cursor = self._execute(query_str, error="Could not count the layout pages")

        row = cursor.fetchone()

        return row[0] if row else 0

    # ------------------------------------------------------------------
    # layout_question
    # ------------------------------------------------------------------
    def select_questions(self) -> list[dict[str, Any]]:
        """All the questions, with all their columns."""
        query_str = "SELECT * FROM layout_question ORDER BY question"

        cursor = self._execute(query_str, error="Could not read the questions")

        return self._rows_as_dicts(cursor)

    def get_question_number(self, copy_nr: int, question_name: str) -> int:
        """
        Position of a question in a copy, ordered by where its first answer box appears
        (page, then top to bottom, then left to right).
        :raise AmcDbManagerError: if the question isn't in this copy
        """
        query_str = """
            WITH firstpage AS (
              SELECT question, MIN(page) AS p
              FROM layout_box
              WHERE student = :copy AND role = :role
              GROUP BY question
            ),
            firstpos AS (
              SELECT b.question, f.p, MIN(b.ymin) AS y0, MIN(b.xmin) AS x0
              FROM layout_box b
              JOIN firstpage f ON f.question = b.question AND f.p = b.page
              WHERE b.student = :copy AND b.role = :role
              GROUP BY b.question, f.p
            ),
            ordered AS (
              SELECT question, ROW_NUMBER() OVER (ORDER BY p, y0, x0) AS qnum
              FROM firstpos
            )
            SELECT o.qnum
            FROM ordered o
            JOIN layout_question q ON q.question = o.question
            WHERE q.name = :name
        """
        query_params = {"copy": copy_nr, "role": ROLE_ANSWER, "name": question_name}

        cursor = self._execute(
            query_str, query_params,
            error=f"Could not compute the number of question {question_name!r} (copy={copy_nr})",
        )

        row = cursor.fetchone()

        if row is None:
            raise AmcDbManagerError(f"Question name {question_name!r} not found for copy {copy_nr}")

        return row[0]

    # ------------------------------------------------------------------
    # layout_box
    # ------------------------------------------------------------------
    def select_copy_question_page(self, copy, question: str) -> int | None:
        """First page of a copy on which a question appears, or None."""
        query_str = (
            "SELECT MIN(lb.page) "
            "FROM layout_box lb "
            "INNER JOIN layout_question lq ON lq.question = lb.question "
            "WHERE lb.student = :copy AND lq.name = :question"
        )
        query_params = {"copy": copy, "question": question}

        cursor = self._execute(
            query_str, query_params,
            error=f"Could not find the page of question {question!r} (copy={copy})",
        )

        row = cursor.fetchone()

        return row[0] if row else None

    def get_question_start_page_by_student(self, question_name: str, student_id: int) -> list[dict[str, Any]]:
        """Every page of a copy on which a question appears: dicts with keys student, question, name, page."""
        query_str = (
            "SELECT DISTINCT b.student, q.question, q.name, b.page "
            "FROM layout_box b "
            "INNER JOIN layout_question q ON q.question = b.question "
            "WHERE q.name = :question_name AND b.student = :student "
            "ORDER BY b.page"
        )
        query_params = {"question_name": question_name, "student": student_id}

        cursor = self._execute(
            query_str, query_params,
            error=f"Could not read the pages of question {question_name!r} (copy={student_id})",
        )

        return [
            {"student": student, "question": question, "name": name, "page": page}
            for student, question, name, page in cursor.fetchall()
        ]

    def get_question_name_by_student_page(self, student_id: int, page_no) -> str | None:
        """
        Name of a question on a page of a copy. If the page has no box, the question
        continuing from the closest previous page. None if there is none.
        """
        query_str = (
            "SELECT q.name "
            "FROM layout_box b "
            "INNER JOIN layout_question q ON q.question = b.question "
            "WHERE b.student = :student AND b.page <= :page "
            "ORDER BY b.page DESC, b.question "
            "LIMIT 1"
        )
        query_params = {"student": student_id, "page": page_no}

        cursor = self._execute(
            query_str, query_params,
            error=f"Could not find the question of page {page_no} (copy={student_id})",
        )

        row = cursor.fetchone()

        return row[0] if row else None

    def get_page_layout_boxes(self, student: int, page_nr) -> list[dict[str, Any]]:
        """All the boxes of a page of a copy, with all their columns."""
        query_str = (
            "SELECT * FROM layout_box "
            "WHERE student = :student AND page = :page "
            "ORDER BY question, answer"
        )
        query_params = {"student": student, "page": page_nr}

        cursor = self._execute(
            query_str, query_params,
            error=f"Could not read the layout boxes of page {page_nr} (copy={student})",
        )

        return self._rows_as_dicts(cursor)