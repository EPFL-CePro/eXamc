import logging
import sqlite3
from typing import Any

from examc_app.exceptions.amc import AmcDbManagerError
from examc_app.utils.amc_db_queries import (
    NO_STUDENT,
    AbstractAmcDbManager,
    AmcDbFile,
)

logger = logging.getLogger(__name__)


class AmcReportDbManager(AbstractAmcDbManager):
    """
    Access to AMC's report.sqlite.

    In report_student, (student, copy) identify an answer sheet: `student` is the sheet number
    and `copy` the copy number (0 unless sheets were photocopied). `file` is the generated report
    (e.g. the annotated PDF) and the mail_* columns track the sending of that report.
    """

    def __init__(self, amc_data_path: str):
        super().__init__(amc_data_path, amc_db_file=AmcDbFile.REPORT)

    def select_students_report(self) -> list[dict[str, Any]]:
        """
        Mail status of every associated sheet.
        :return: Dicts with keys id (sheet number), copy (associated student code),
            status, error, date.
        """
        query_str = (
            "SELECT rs.student, "
            "       NULLIF(COALESCE(NULLIF(aa.manual, ''), NULLIF(aa.auto, '')), :no_student), "
            "       rs.mail_status, rs.mail_message, rs.mail_timestamp "
            "FROM report_student rs "
            "INNER JOIN association.association_association aa "
            "        ON aa.student = rs.student AND aa.copy = rs.copy "
            "ORDER BY rs.student, rs.copy"
        )
        query_params = {"no_student": NO_STUDENT}

        self._attach(AmcDbFile.ASSOCIATION)

        cursor = self._execute(
            query_str, query_params,
            error="Could not read the students reports",
        )

        return [
            {"id": sheet, "copy": code, "status": status, "error": error, "date": date}
            for sheet, code, status, error, date in cursor.fetchall()
        ]

    def get_annotated_pdf_path(self, student_id: int) -> str | None:
        """File of a sheet's report, or None if it has none."""
        query_str = "SELECT file FROM report_student WHERE student = :student ORDER BY copy LIMIT 1"
        query_params = {"student": student_id}

        cursor = self._execute(
            query_str, query_params,
            error=f"Could not read the report file of sheet {student_id}",
        )

        row = cursor.fetchone()
        return row[0] if row else None

    def get_student_report_data(self) -> list[dict[str, Any]]:
        """
        Every report row with its sheet number (amc_copy) and associated student code
        (associated_student, None if not associated). If association.sqlite is missing,
        associated_student is None for every row.
        """
        with_association_query_str = (
            "SELECT rs.*, "
            "       rs.student AS amc_copy, "
            "       NULLIF(COALESCE(NULLIF(aa.manual, ''), NULLIF(aa.auto, '')), :no_student) "
            "           AS associated_student "
            "FROM report_student rs "
            "LEFT JOIN association.association_association aa "
            "       ON aa.student = rs.student AND aa.copy = rs.copy "
            "ORDER BY rs.student, rs.copy"
        )
        with_association_query_params = {"no_student": NO_STUDENT}

        without_association_query_str = (
            "SELECT rs.*, rs.student AS amc_copy, NULL AS associated_student "
            "FROM report_student rs "
            "ORDER BY rs.student, rs.copy"
        )
        without_association_query_params = {}

        try:
            self._attach(AmcDbFile.ASSOCIATION)
            query_str, query_params = with_association_query_str, with_association_query_params
        except (AmcDbManagerError, sqlite3.Error) as e:
            logger.warning("Association database unavailable, reports without association: %s", e)
            query_str, query_params = without_association_query_str, without_association_query_params

        cursor = self._execute(
            query_str, query_params,
            error="Could not read the students report data",
        )

        return self._rows_as_dicts(cursor)

    def update_report_student(
            self, student: int, mail_timestamp: float, mail_status: int, mail_message: str = ""
    ) -> int:
        """
        Record the result of mailing a sheet's report.
        :return: The number of rows updated (0 if the sheet has no report).
        """
        query_str = (
            "UPDATE report_student "
            "SET mail_status = :status, mail_timestamp = :timestamp, mail_message = :message "
            "WHERE student = :student"
        )
        query_params = {
            "status": int(mail_status),
            "timestamp": int(mail_timestamp),
            "message": mail_message,
            "student": student,
        }

        cursor = self._execute(
            query_str, query_params,
            error=f"Could not update the mail status of sheet {student}",
        )

        return cursor.rowcount