import os
import sqlite3
from abc import ABC
from pathlib import Path
from typing import Any

from examc_app.services.amc.AmcDb import AmcDb
from examc_app.utils.amc_db_queries.AmcDbFiles import AmcDbFile


class AmcDbManagerError(Exception):
    """Raised when reading or writing the AMC association database fails."""


class AbstractAmcDbManager(ABC):
    """
    Abstract base class for managing AMC database queries.
    """
    def __init__(self, amc_data_path: str, amc_db_file: AmcDbFile):
        self._amc_data_path = amc_data_path
        self._amc_table_file = amc_db_file.value
        self._db = self._open_db()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _rows_as_dicts(cursor) -> list[dict[str, Any]]:
        """Convert all the rows of a cursor to dicts keyed by column's name."""
        columns = [d[0] for d in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]


    # ------------------------------------------------------------------
    # DB operations
    # ------------------------------------------------------------------

    def _open_db(self) -> AmcDb:
        db_path = os.path.join(self._amc_data_path, self._amc_table_file)

        # sqlite silently creates an empty file for a missing path, so check first.
        if not os.path.isfile(db_path):
            raise AmcDbManagerError(f"AMC database not found: {db_path}")

        db = AmcDb(db_path)

        if db.conn is None:  # AmcDb.connect() logs instead of raising
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
        if params is None: params = dict()

        cursor = self._db.execute_query(query, params)

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

        if self._db.cursor is None:
            raise AmcDbManagerError(f"SQLite cursor is None for file '{self._amc_data_path}/{self._amc_table_file}'")

        self._db.cursor.execute(
            "ATTACH DATABASE :db AS :alias",
            {"db": self._amc_data_path + amc_db_file.value, "alias": alias}
        )


    def _has_db(self, amc_db_file: AmcDbFile) -> bool:
        """
        True if a given db file name such as "scoring.sqlite" exists in the same amc_data_path and is not empty.
        :rtype: bool
        """
        return Path(self._amc_data_path + amc_db_file.value).stat().st_size > 0