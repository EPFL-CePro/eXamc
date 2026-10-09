import logging
from typing import TypedDict

from examc_app.utils.amc_db_queries import NO_STUDENT, AbstractAmcDbManager, AmcDbFile

logger = logging.getLogger(__name__)

ASSOC_TABLE = "association_association"

#: capture_zone.type of the zone where the student writes their name (AMC's ZONE_NAME).
ZONE_NAME = 2


class AssociationWithImage(TypedDict):
    """An association row, with the path of the scanned name zone of its sheet."""
    student: int
    copy: int
    manual: str | None
    auto: str | None
    image_path: str


class SheetAssociation(TypedDict):
    """The student code a sheet is effectively associated with, None if there is none."""
    amc_copy: int
    associated_student: str | None


class AmcAssociationDbManager(AbstractAmcDbManager):
    """
    Access to AMC's association.sqlite.

    In the association table, (student, copy) identify an answer sheet: `student` is the sheet
    number and `copy` the copy number (0 unless sheets were photocopied). `auto` and `manual` hold
    student codes from the students list, as TEXT. A sheet's effective association is
    coalesce(manual, auto), where manual = 'NONE' means "no student".
    """

    def __init__(self, amc_data_path: str):
        super().__init__(amc_data_path, amc_db_file=AmcDbFile.ASSOCIATION)

    def sheets_of(self, code: str) -> list[tuple[int, int]]:
        """
        (student, copy) of the sheets currently associated with a student code.

        Port of AMC::DataModule::association realBack.
        """
        query_str = f"SELECT student, copy FROM {ASSOC_TABLE} WHERE coalesce(manual, auto) = :code || ''"
        query_params = {"code": code}

        cursor = self._execute(
            query_str, query_params,
            error=f"Could not read the sheets associated with {code}"
        )

        return [(student, copy) for student, copy in cursor.fetchall()]

    def delete_target(self, code) -> list[tuple[int, int]]:
        """
        Unlink a student code from every sheet. Port of AMC::DataModule::association::delete_target.

        Manual links to the code are cleared, falling back to `auto`; where `auto` is the code too,
        or the sheet only had the automatic link, manual becomes 'NONE' to override it.

        :return: The (student, copy) sheets that were associated with the code before.
        """
        query_str = f"""
            UPDATE {ASSOC_TABLE}
                SET manual = CASE WHEN manual IS NULL OR auto = :code || '' THEN :no_student END
                WHERE manual = :code || '' OR (auto = :code || '' AND manual IS NULL)
        """
        query_params = {"code": code, "no_student": NO_STUDENT}

        # One transaction: the sheets returned are exactly the ones unlinked.
        with self._amc_db.transaction():
            previous = self.sheets_of(code)

            self._execute(
                query_str,
                query_params,
                error=f"Could not unlink the sheets associated with {code}",
            )

        return previous

    def set_manual(self, sheet: int, copy: int, manual: str | None) -> int:
        """
        Set a sheet's manual association. Port of AMC::DataModule::association::set_manual.

        :param sheet: The sheet number (the table's `student` column).
        :param copy: The copy number.
        :param manual: A student code, 'NONE' for no student, or None to fall back to `auto`.
        :return: The number of rows affected by the update.
        """
        update_query_str = f"UPDATE {ASSOC_TABLE} SET manual = :manual WHERE student = :sheet AND copy = :copy"
        update_query_params = {"sheet": sheet, "copy": copy, "manual": manual}

        insert_query_str = f"INSERT INTO {ASSOC_TABLE} (student, copy, manual, auto) VALUES (:sheet, :copy, :manual, NULL)"
        insert_query_params = {"sheet": sheet, "copy": copy, "manual": manual}

        # One transaction: no other writer can create the row between the UPDATE and the INSERT.
        with self._amc_db.transaction():
            cursor = self._execute(
                update_query_str,
                update_query_params,
                error=f"Could not update the association of sheet {sheet}/{copy}",
            )

            if cursor.rowcount == 0:
                # No row yet for this sheet (never auto-associated): create it.
                cursor = self._execute(
                    insert_query_str,
                    insert_query_params,
                    error=f"Could not create the association of sheet {sheet}/{copy}",
                )

        return cursor.rowcount

    def associate_manually(self, code, sheet: int, copy: int = 0) -> list[tuple[int, int]]:
        """
        Associate a student code with a sheet, unlinking it from any other sheet first.

        :return: The sheets the code was associated with before.
        """
        # One transaction: if set_manual fails, delete_target is rolled back too.
        with self._amc_db.transaction():
            previous = self.delete_target(code)  # a code can only be on one sheet
            self.set_manual(sheet, copy, code)   # manual overrides AMC's auto association

        # Logged after commit, so only actual changes are reported.
        if previous:
            logger.info("Unlinked student %s from sheets %s", code, previous)

        return previous

    def unlink(self, sheet: int, copy: int = 0) -> None:
        """Mark a sheet as associated with no student, overriding any automatic association."""
        self.set_manual(sheet, copy, NO_STUDENT)

    def get_assoc_details_with_images(self, amc_assoc_img_path: str) -> list[AssociationWithImage]:
        """
        All the association rows, each with the scan of its sheet's name zone.

        :param amc_assoc_img_path: Folder (or URL prefix) of the name zone images, prepended to the
            image file names stored by AMC.
        :return: One entry per sheet that has a scanned name zone.
        """
        query_str = f"""
            SELECT aa.student, aa.copy, aa.manual, aa.auto, :img_path || cz.image AS image_path
                FROM {ASSOC_TABLE} aa
                INNER JOIN capture.capture_zone cz ON cz.student = aa.student AND cz.copy = aa.copy
                WHERE cz.type = :zone_name AND cz.image IS NOT NULL
                ORDER BY aa.student, aa.copy
        """
        query_params = {"img_path": amc_assoc_img_path, "zone_name": ZONE_NAME}

        self._attach(AmcDbFile.CAPTURE)

        cursor = self._execute(
            query_str, query_params,
            error="Could not read the associations with their name zone images",
        )

        return [
            AssociationWithImage(student=student, copy=copy, manual=manual, auto=auto, image_path=image_path)
            for student, copy, manual, auto, image_path in cursor.fetchall()
        ]

    def select_student_association_data(self) -> list[SheetAssociation]:
        """
        The student code each sheet is effectively associated with: manual first, then auto.
        Empty values and the 'NONE' marker give None.

        :return: One entry per association row.
        """
        query_str = f"""
            SELECT student AS amc_copy,
                   NULLIF(COALESCE(NULLIF(manual, ''), NULLIF(auto, '')), :no_student) AS associated_student
                FROM {ASSOC_TABLE}
        """
        query_params = {"no_student": NO_STUDENT}

        cursor = self._execute(
            query_str, query_params,
            error="Could not read the sheets associations",
        )

        return [
            SheetAssociation(amc_copy=amc_copy, associated_student=associated_student)
            for amc_copy, associated_student in cursor.fetchall()
        ]
