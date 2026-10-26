import logging
import sqlite3
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from typing import Any

Params = Sequence[Any] | Mapping[str, Any]

logger = logging.getLogger(__name__)


class AmcDb:
    def __init__(self, db_path: str):
        self.db_path: str = db_path
        self.conn: sqlite3.Connection | None = None
        self._explicit_transaction = False

        try:
            self.conn = sqlite3.connect(self.db_path)
            self.conn.row_factory = sqlite3.Row
        except sqlite3.Error:
            logger.exception(f"Error connecting to database {self.db_path}")

    def close(self) -> None:
        if self.conn is not None:
            self.conn.close()
            self.conn = None

    def execute_query(self, query: str, params: Params = ()) -> sqlite3.Cursor | None:
        """
        Execute a query on a fresh cursor. Writes are committed immediately,
        unless inside transaction().
        :return: The cursor, or None if the query failed (the error is logged).
        """
        if self.conn is None:
            return None
        try:
            cursor = self.conn.execute(query, params)
            if self.conn.in_transaction and not self._explicit_transaction:
                self.conn.commit()
            return cursor
        except sqlite3.Error:
            logger.exception(f"SQLite error on {self.db_path} when running {query}")
            return None

    @contextmanager
    def transaction(self) -> Iterator[None]:
        """
        Run several statements atomically: all committed at the end, or all rolled back on error.
        Nested calls join the outer transaction.
        """
        if self.conn is None: raise sqlite3.ProgrammingError(f"No open connection to {self.db_path}")

        # Already in a transaction: the outer one commits or rolls back.
        if self._explicit_transaction:
            yield
            return

        # IMMEDIATE locks the database for writing right away, so nobody else
        # can write between our reads and writes.
        self.conn.execute("BEGIN IMMEDIATE")
        self._explicit_transaction = True

        try:
            yield
            self.conn.commit()
        except BaseException:
            self.conn.rollback()
            raise
        finally:
            self._explicit_transaction = False