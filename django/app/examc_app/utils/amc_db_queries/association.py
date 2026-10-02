import logging
from typing import Any

from examc_app.utils.amc_db_queries.AbstractAmcDbManager import AbstractAmcDbManager

logger = logging.getLogger(__name__)

ASSOC_TABLE = "association_association"

#: Value AMC stores in `manual` to mark a sheet as explicitly not associated, overriding `auto`.
NO_STUDENT = "NONE"


class AmcAssociationError(RuntimeError):
    """An association query failed."""


class AmcAssociationDbManager(AbstractAmcDbManager):
    """Access to AMC's association.sqlite.

    In the association table, (student, copy) identify an answer sheet: `student` is the sheet
    number and `copy` the copy number (0 unless sheets were photocopied). `auto` and `manual` hold
    student codes from the students list, as TEXT. A sheet's effective association is
    coalesce(manual, auto), where manual = 'NONE' means "no student".
    """

    def __init__(self, amc_data_path: str):
        super().__init__(amc_data_path, amc_table_file="association.sqlite")

    @staticmethod
    def _code(code) -> str:
        """Student codes are text: never go through int, which would drop leading zeros."""
        text = str(code).strip()
        if not text:
            raise ValueError("A student code is required")
        return text

    def _execute(self, query: str, params: dict, error: str):
        cursor = self._db.execute_query(query, params)
        if cursor is None:
            raise AmcAssociationError(error)
        return cursor

    def sheets_of(self, code) -> list[tuple[Any]]:
        """(student, copy) of the sheets currently associated with a student code.

        Port of AMC::DataModule::association realBack.
        """
        code = self._code(code)
        cursor = self._execute(
            f"""
            SELECT student, copy FROM {ASSOC_TABLE}
            WHERE coalesce(manual, auto) = :code || ''
            """,
            {"code": code},
            f"Could not read the sheets associated with {code}",
        )
        return [tuple(row) for row in cursor.fetchall()]

    def delete_target(self, code) -> list[tuple[Any]]:
        """Unlink a student code from every sheet. Port of AMC::DataModule::association::delete_target.

        Manual links to the code are cleared, falling back to `auto`; where `auto` is the code too,
        or the sheet only had the automatic link, manual becomes 'NONE' to override it.

        :return: The (student, copy) sheets that were associated with the code before.
        """
        code = self._code(code)
        previous = self.sheets_of(code)

        self._execute(
            f"""
            UPDATE {ASSOC_TABLE}
            SET manual = CASE WHEN manual IS NULL OR auto = :code || '' THEN '{NO_STUDENT}' ELSE NULL END
            WHERE manual = :code || '' OR (auto = :code || '' AND manual IS NULL)
            """,
            {"code": code},
            f"Could not unlink the sheets associated with {code}",
        )

        return previous

    def set_manual(self, sheet: int, copy: int, manual: str | None) -> None:
        """Set a sheet's manual association. Port of AMC::DataModule::association::set_manual.

        :param sheet: The sheet number (the table's `student` column).
        :param copy: The copy number.
        :param manual: A student code, 'NONE' for no student, or None to fall back to `auto`.
        """
        params = {"sheet": sheet, "copy": copy, "manual": manual}

        cursor = self._execute(
            f"UPDATE {ASSOC_TABLE} SET manual = :manual WHERE student = :sheet AND copy = :copy",
            params,
            f"Could not update the association of sheet {sheet}/{copy}",
        )
        if cursor.rowcount > 0:
            return

        # No row yet for this sheet (never auto-associated): create it.
        self._execute(
            f"INSERT INTO {ASSOC_TABLE} (student, copy, manual, auto) VALUES (:sheet, :copy, :manual, NULL)",
            params,
            f"Could not create the association of sheet {sheet}/{copy}",
        )

    def associate_manually(self, code, sheet: int, copy: int = 0) -> list[tuple[int, int]]:
        """Associate a student code with a sheet, unlinking it from any other sheet first.

        :return: The sheets the code was associated with before.
        """
        code = self._code(code)
        previous = self.delete_target(code)
        if previous:
            logger.info("Unlinking student %s from sheets %s", code, previous)

        self.set_manual(sheet, copy, code)
        return previous

    def unlink(self, sheet: int, copy: int = 0) -> None:
        """Mark a sheet as associated with no student, overriding any automatic association."""
        self.set_manual(sheet, copy, NO_STUDENT)