import logging
import os
import sqlite3
from abc import ABC
from collections.abc import Callable
from enum import StrEnum
from typing import TypeVar

from examc_app.exceptions.amc import AmcDbManagerError
from examc_app.services.amc.AmcDb import AmcDb

logger = logging.getLogger(__name__)

T = TypeVar("T")


# Value AMC stores to mark a sheet as explicitly not associated.
NO_STUDENT = "NONE"


class AmcDbFile(StrEnum):
    ASSOCIATION = "association.sqlite"
    CAPTURE = "capture.sqlite"
    LAYOUT = "layout.sqlite"
    REPORT = "report.sqlite"
    SCORING = "scoring.sqlite"


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
        Attach another AMC database of the same data folder to the connection, unless it's already attached.
        :param amc_db_file: The database to attach, e.g., AmcDbFile.SCORING.
        :param alias: Schema name to use in queries. Defaults to the file name without extension
            (e.g. "scoring" for AmcDbFile.SCORING).
        :raise AmcDbManagerError: If the connection isn't open or the database file doesn't exist
        """
        alias = alias or os.path.splitext(amc_db_file.value)[0]
        database = os.path.join(self._amc_data_path, amc_db_file.value)

        conn = self._amc_db.conn
        if conn is None:
            raise AmcDbManagerError(f"No open connection to attach '{database}' to")

        check_query_str = "SELECT 1 FROM pragma_database_list WHERE name = :alias"
        check_query_params = {"alias": alias}

        already_attached = conn.execute(check_query_str, check_query_params).fetchone()
        if already_attached: return

        # Make sure ATTACH doesn't silently create an empty file for a missing path.
        if not os.path.isfile(database):
            raise AmcDbManagerError(f"AMC database not found: {database}")

        attach_query_str = f"ATTACH DATABASE '{database}' AS :alias"
        attach_query_params = {"alias": alias}

        logger.debug("Attaching database '%s' as '%s'", database, alias)
        conn.execute(attach_query_str, attach_query_params)


    def _has_db(self, amc_db_file: AmcDbFile) -> bool:
        """True if the given AMC database exists in the data folder and is not empty."""
        path = os.path.join(self._amc_data_path, amc_db_file.value)
        return os.path.isfile(path) and os.path.getsize(path) > 0

