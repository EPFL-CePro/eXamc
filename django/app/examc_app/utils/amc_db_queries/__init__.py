import logging
import os
import sqlite3
from abc import ABC
from collections.abc import Callable
from enum import StrEnum
from pathlib import Path
from typing import TypeVar

from examc_app.services.amc.AmcDb import AmcDb

logger = logging.getLogger(__name__)

T = TypeVar("T")


class AmcDbManagerError(Exception):
    """Raised when reading or writing the AMC association database fails."""



class AmcDbFile(StrEnum):
    ASSOCIATION = "association.sqlite"
    SCORING = "scoring.sqlite"
    CAPTURE = "capture.sqlite"
    LAYOUT = "layout.sqlite"


class AbstractAmcDbManager(ABC):
    """
    Abstract base class for managing AMC database queries.
    """
    def __init__(self, amc_data_path: str, amc_db_file: AmcDbFile):
        self._amc_data_path: str = amc_data_path
        self._amc_table_file: str = amc_db_file.value
        self._amc_db: AmcDb = self.open_db()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        """Always close the database connection."""
        self.close_db()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _rows_as_dicts(cursor: sqlite3.Cursor, row_type: Callable[..., T] = dict) -> list[T]:
        """Convert all the rows of a cursor to dicts keyed by column's name."""
        columns = [d[0] for d in cursor.description]
        return [row_type(**dict(zip(columns, row))) for row in cursor.fetchall()]

    # ------------------------------------------------------------------
    # DB operations
    # ------------------------------------------------------------------
    def close_db(self):
        """Close the database connection."""
        self._amc_db.close()

    def open_db(self) -> AmcDb:
        db_path = os.path.join(self._amc_data_path, self._amc_table_file)

        # sqlite silently creates an empty file for a missing path, so check first.
        if not os.path.isfile(db_path):
            raise AmcDbManagerError(f"AMC database not found: {db_path}")

        db = AmcDb(db_path)

        if db.conn is None:
            raise AmcDbManagerError(f"Could not open AMC database {db_path}")

        return db

    def _execute(self, query: str, params: dict | None = None, error: str = "") -> sqlite3.Cursor:
        """
        Helper method to execute a query and raise an error if the cursor is None.
        :param query: The SQL query to execute.
        :param params: The parameters to pass to the query.
        :param error: The error message to raise if the cursor is None.
        :return: The cursor object.
        :raise AmcDbManagerError: if the cursor is None
        """
        # Default error message
        if error == "":
            error = f"Could not execute the following query: {query}"
            if params is not None:
                error += f"\nwith parameters {params}"

        # Default parameters
        if params is None: params = {}

        cursor = self._amc_db.execute_query(query, params)

        if cursor is None: raise AmcDbManagerError(error)

        return cursor

    def _attach(self, amc_db_file: AmcDbFile, alias: str = "") -> None:
        """
        Attach another AMC database of the same data folder to the connection using ATTACH DATABASE {db_file} AS {alias}.
        :param amc_db_file: File name of the database, e.g. "scoring.sqlite".
        :type amc_db_file: AmcDbFile
        :param alias: Schema name to use in queries. If unspecified, the amc DB file name without extension is used.
        """
        # Default alias value
        if alias == "":
            alias = amc_db_file.value.split(".")[0]

        database = self._amc_data_path + amc_db_file.value
        logger.critical(f"Attaching database '{database}' as '{alias}'")
        query_str = f"ATTACH DATABASE '{database}' AS :alias"
        query_params = {"alias": alias}

        if self._amc_db.cursor is None or not self._amc_db.cursor:
            raise AmcDbManagerError(f"SQLite cursor is None for file '{self._amc_data_path}/{self._amc_table_file}'")

        self._amc_db.cursor.execute(query_str, query_params)


    def _has_db(self, amc_db_file: AmcDbFile) -> bool:
        """
        True if a given db file name such as "scoring.sqlite" exists in the same amc_data_path and is not empty.
        :rtype: bool
        """
        return Path(self._amc_data_path + amc_db_file.value).stat().st_size > 0











################################################
# SCORING
################################################


def get_mean(amc_data_path: str):
    db = AmcDb(amc_data_path + "scoring.sqlite")

    query_str = "SELECT AVG(mark) as mean FROM scoring_mark"

    response = db.execute_query(query_str)
    row = response.fetchone() if response else None
    mean = 0
    if row and row['mean'] is not None:
        mean = round(row['mean'], 4)

    db.close()

    return mean


def get_marks(amc_data_path):
    db = AmcDb(amc_data_path + "scoring.sqlite")

    query_str = "SELECT student, total, max, mark FROM scoring_mark"

    response = db.execute_query(query_str)
    colname_marks = [d[0] for d in response.description]
    data_marks = [dict(zip(colname_marks, r)) for r in response.fetchall()]

    db.close()

    return data_marks


def get_questions_scoring_details(amc_data_path):
    db = AmcDb(amc_data_path + "scoring.sqlite")
    # Attach layout db
    db.cursor.execute("ATTACH DATABASE '" + amc_data_path + "layout.sqlite' as layout")

    query_str = (
        "SELECT sm.student as copy,sm.total, sm.max as max_total, mark, lq.name as question, ss.score, ss.max as max_question "
        "FROM scoring_score ss "
        "INNER JOIN layout_question lq ON lq.question = ss.question "
        "INNER JOIN scoring_mark sm ON sm.student = ss.student "
        "ORDER BY sm.student, lq.name")

    response = db.execute_query(query_str)
    marking_details = []
    if response:
        colname_marking = [d[0] for d in response.description]
        marking_details = [dict(zip(colname_marking, r)) for r in response.fetchall()]

    db.close()

    return marking_details



def get_question_max_points(amc_data_path, question_name, copy_nr):
    db = AmcDb(amc_data_path + "scoring.sqlite")
    db.cursor.execute("ATTACH DATABASE '" + amc_data_path + "layout.sqlite' as layout")
    query_str = ("SELECT strategy FROM scoring_question sc"
                 " INNER JOIN layout_question lq ON lq.question = sc.question"
                 " WHERE lq.name = '" + str(question_name) + "'")

    if copy_nr:
        query_str += " AND sc.student = " + str(copy_nr)

    response = db.execute_query(query_str)
    strategy = response.fetchall()[0]['strategy']
    max_points = strategy.split("=")[1]
    return max_points




################################################
# REPORT
################################################

def select_students_report(amc_data_path):
    db = AmcDb(amc_data_path + "report.sqlite")
    db.cursor.execute("ATTACH DATABASE '" + amc_data_path + "association.sqlite' as association")
    query_str = ("SELECT rs.student as id, coalesce(aa.auto,aa.manual) as copy, "
                 "rs.mail_status as status, rs.mail_message as error, rs.mail_timestamp as date "
                 "FROM report_student rs "
                 "INNER JOIN association_association aa "
                 "WHERE rs.student = aa.student")

    response = db.execute_query(query_str)
    colname_rep = [d[0] for d in response.description]
    rep_details = [dict(zip(colname_rep, r)) for r in response.fetchall()]

    db.close()

    return rep_details


def get_annotated_pdf_path(amc_data_path, student_id):
    db = AmcDb(amc_data_path + "report.sqlite")
    query_str = ("SELECT file FROM report_student WHERE student = " + student_id)

    response = db.execute_query(query_str)
    file = None
    if response:
        file = response.fetchall()[0]['file']

    db.close()

    return file


def get_student_report_data(amc_data_path):
    db = AmcDb(amc_data_path + "report.sqlite")
    try:
        db.cursor.execute("ATTACH DATABASE '" + amc_data_path + "association.sqlite' as association")
        query_str = (
            "SELECT rs.*, "
            "aa.student AS amc_copy, "
            "COALESCE(NULLIF(aa.manual, ''), NULLIF(aa.auto, '')) AS associated_student "
            "FROM report_student rs "
            "LEFT JOIN association.association_association aa ON aa.student = rs.student"
        )
        response = db.execute_query(query_str)
    except sqlite3.Error:
        response = None

    if not response:
        query_str = "SELECT rs.*, rs.student AS amc_copy, NULL AS associated_student FROM report_student rs"
        response = db.execute_query(query_str)

    colname_rep = [d[0] for d in response.description]
    rep_details = [dict(zip(colname_rep, r)) for r in response.fetchall()]

    db.close()

    return rep_details


def update_report_student(amc_data_path, student, mail_timestamp, mail_status, mail_message=''):
    db = AmcDb(amc_data_path + "report.sqlite")
    query_str = ("UPDATE report_student "
                 "SET mail_status = " + str(mail_status) + ", "
                                                           "mail_timestamp = " + str(int(mail_timestamp)) + ", "
                                                                                                            "mail_message = '" + mail_message.replace(
        "'", "''") + "' "
                     "WHERE student = " + student)

    response = db.execute_query(query_str)

    db.close()

    return response


