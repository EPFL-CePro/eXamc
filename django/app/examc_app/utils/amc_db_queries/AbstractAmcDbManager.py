import os
from abc import ABC

from examc_app.services.amc.AmcDb import AmcDb

class AmcDbManagerError(Exception):
    """Raised when reading or writing the AMC association database fails."""


class AbstractAmcDbManager(ABC):
    """
    Abstract base class for managing AMC database queries.
    """
    def __init__(self, amc_data_path: str, amc_table_file: str):
        self._amc_data_path = amc_data_path
        self._amc_table_file = amc_table_file
        self._db = self._open_db()

    def _open_db(self) -> AmcDb:
        db_path = os.path.join(self._amc_data_path, self._amc_table_file)

        # sqlite silently creates an empty file for a missing path, so check first.
        if not os.path.isfile(db_path):
            raise AmcDbManagerError(f"AMC database not found: {db_path}")

        db = AmcDb(db_path)

        if db.conn is None:  # AmcDb.connect() logs instead of raising
            raise AmcDbManagerError(f"Could not open AMC database {db_path}")

        return db

    def _execute(self, query: str, params: dict | None = None, error: str = ""):
        """
        Helper method to execute a query and raise an error if the cursor is None.
        :param query: The SQL query to execute.
        :param params: The parameters to pass to the query.
        :param error: The error message to raise if the cursor is None.
        :return: The cursor object.
        :raise AmcDbManagerError: if the cursor is None
        """
        if params is None: params = dict()
        cursor = self._db.execute_query(query, params)

        if cursor is None: raise AmcDbManagerError(error)

        return cursor
