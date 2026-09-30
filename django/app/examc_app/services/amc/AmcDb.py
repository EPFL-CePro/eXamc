import logging
import sqlite3
import sys
import traceback
from typing import Sequence, Any, Mapping

Params = Sequence[Any] | Mapping[str, Any]

logger = logging.getLogger(__name__)

class AmcDb:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.conn = None
        self.cur = None
        self.connect()

    def connect(self) -> bool:
        try:
            self.conn = sqlite3.connect(self.db_path)
            self.conn.row_factory = sqlite3.Row
            self.cur = self.conn.cursor()
            return True
        except sqlite3.Error as e:
            print(f"Error connecting to database: {e}")
            return False

    def close(self):
        self.conn.close()

    def execute_query(self, query: str, params: Params = ()) -> sqlite3.Cursor | None:
        if not self.conn or not self.cur:
            return None
        try:
            result = self.cur.execute(query, params)
            if self.conn.in_transaction:  # only after INSERT/UPDATE/DELETE, not SELECT
                self.conn.commit()
            return result
        except sqlite3.Error as er:
            logger.exception('SQLite error: %s' % (' '.join(er.args)))
            logger.exception("Exception class is: ", er.__class__)
            logger.exception('SQLite traceback: ')
            exc_type, exc_value, exc_tb = sys.exc_info()
            logger.exception(traceback.format_exception(exc_type, exc_value, exc_tb))