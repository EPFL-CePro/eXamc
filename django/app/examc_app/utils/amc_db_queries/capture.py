import time
from typing import Any, TypedDict

from examc_app.utils.amc_db_queries import (
    AbstractAmcDbManager,
    AmcDbFile,
    AmcDbManagerError,
)


class CapturePage(TypedDict):
    student: str
    page: str
    src: str


class AmcCaptureDbManager(AbstractAmcDbManager):
    """Access to AMC's capture.sqlite"""

    def __init__(self, amc_data_path: str):
        super().__init__(amc_data_path, amc_db_file=AmcDbFile.CAPTURE)

    # ------------------------------------------------------------------
    # capture_page
    # ------------------------------------------------------------------

    def select_capture_pages(self) -> list[CapturePage]:
        """
        Select all rows from the capture_page table ordered by student, page
        :return: list of dictionaries with keys student, page, src
        """
        query_str = "SELECT student, page, src FROM capture_page ORDER BY student, page"
        cursor = self._execute(
            query_str,
            error="Couldn't select capture pages"
        )

        return [
            CapturePage(student=student, page=page, src=src)
            for student, page, src in cursor.fetchall()
        ]


    def update_capture_page_src(self, student: str, page, new_filename: str) -> int:
        """
        Update capture_page table with new_filename where student = :student and page = :page
        :param student: student id
        :param page: page number
        :param new_filename: new filename
        :return: number of rows updated (0 if no matching row)
        :raise AmcDbManagerError: if the query could not be executed
        """
        query_str = "UPDATE capture_page SET src = :new_filename WHERE student = :student AND page = :page"
        query_params = {"new_filename": new_filename, "student": student, "page": page}

        cursor = self._execute(
            query_str, query_params,
            error=f"Failed to update capture_page src (student={student}, page={page})"
        )

        return cursor.rowcount

    def select_amc_scan_path(self, copy_no: str, page_no: str) -> str:
        """
        Select the scan path of a page of a copy.
        :param copy_no: The copy (student) identifier.
        :param page_no: The page number.
        :return: The source path of the scan, or "" if the page was not captured.
        """
        query_str = "SELECT src FROM capture_page WHERE page = :page_no AND student = :student"
        query_params = {"page_no": page_no, "student": copy_no}

        cursor = self._execute(
            query_str, query_params,
            error=f"Failed to select capture_page src (student={copy_no}, page={page_no})"
        )

        row = cursor.fetchone()

        return row["src"] if row else ""

    def select_nb_copies(self) -> int:
        """
        Count the copies with at least one captured page.
        :return: Number of (student, copy) pairs captured automatically or manually.
        """
        query_str = (
            "SELECT COUNT(*) "
            "FROM (SELECT student, copy "
            "      FROM capture_page "
            "      WHERE timestamp_auto > 0 OR timestamp_manual > 0) "
            "GROUP BY student, copy"
        )

        cursor = self._execute(
            query_str,
            error="Failed to select number of copies with captured pages"
        )
        
        return len(cursor.fetchall())

    def select_missing_pages(self) -> list[dict[str, Any]]:
        """
        Select the pages expected by the layout but not captured, for the copies that have captured pages.
        :return: Dicts with keys student, page, copy.
        """
        query_str = (
            "SELECT enter.student AS student, enter.page AS page, capture_page.copy AS copy "
            "FROM (SELECT student, page "
            "      FROM layout_box "
            "      WHERE role = 1 "
            "      UNION "
            "      SELECT student, page "
            "      FROM layout_zone) AS enter "
            "JOIN capture_page ON enter.student = capture_page.student "
            "EXCEPT SELECT student, page, copy FROM capture_page "
            "ORDER BY student, copy, page"
        )

        self._attach(AmcDbFile.LAYOUT)

        cursor = self._execute(
            query_str,
            error="Failed to select pages expected by layout but not captured"
        )

        return self._rows_as_dicts(cursor)

    def select_overwritten_pages(self) -> list[dict[str, Any]]:
        """
        Select the captured pages that were overwritten by a later scan.
        :return: Dicts with keys student, page, copy, overwritten, timestamp_auto.
        """
        query_str = (
            "SELECT student, page, copy, overwritten, timestamp_auto "
            "FROM capture_page WHERE overwritten > 0 "
            "ORDER BY student, page, copy, timestamp_auto DESC"
        )

        cursor = self._execute(
            query_str,
            error="Failed to select overwritten pages"
        )

        return self._rows_as_dicts(cursor)

    def get_count_missing_associations(self) -> int:
        """
        Count the captured copies not associated with a student, automatically or manually.
        :return: Number of copies without association.
        """
        query_str = (
            "SELECT COUNT(*) AS count FROM "
            "(SELECT student FROM capture_page "
            " EXCEPT SELECT student FROM association_association "
            " WHERE manual IS NOT NULL OR auto IS NOT NULL)"
        )

        self._attach(AmcDbFile.ASSOCIATION)

        cursor = self._execute(
            query_str,
            error="Failed to select copies without association"
        )

        row = cursor.fetchone()

        return row["count"] if row and row["count"] else 0

    # ------------------------------------------------------------------
    # capture_zone / capture_position
    # ------------------------------------------------------------------
    def select_manual_datacapture_questions(self, copy: int, page: int) -> list[dict[str, Any]] | None:
        """
        Select the questions of a page of a copy, with the scoring explanation when available.
        Falls back to the layout when no capture zone exists for the page.
        :return: Dicts with keys question_id, why ('' if unavailable). None if the page has no question.
        """

        zone_box = 4

        if self._has_db(AmcDbFile.SCORING):
            self._attach(AmcDbFile.SCORING)
            query_str = (
                "SELECT cz.id_a AS question_id, COALESCE(MAX(sc.why), '') AS why "
                "FROM capture_zone cz "
                "LEFT JOIN scoring.scoring_score sc ON sc.student = cz.student AND sc.question = cz.id_a "
                "WHERE cz.type = :zone_type AND cz.student = :copy AND cz.page = :page "
                "GROUP BY cz.id_a ORDER BY cz.id_a"
            )
        else:
            query_str = (
                "SELECT DISTINCT cz.id_a AS question_id, '' AS why "
                "FROM capture_zone cz "
                "WHERE cz.type = :zone_type AND cz.student = :copy AND cz.page = :page "
                "ORDER BY cz.id_a"
            )

        query_params = {"copy": copy, "page": page, "zone_type": zone_box}

        cursor = self._execute(
            query_str, query_params,
            error=f"Failed to query capture zones (copy={copy}, page={page})"
        )


        questions = self._rows_as_dicts(cursor)

        cursor.close()

        if questions:
            return questions

        # No capture zone for this page: take its questions from the layout
        self._attach(AmcDbFile.LAYOUT)
        query_str_layout = (
            "SELECT DISTINCT question AS question_id, '' AS why FROM layout.layout_box "
            "WHERE student = :copy AND page = :page ORDER BY question"
        )

        cursor = self._execute(
            query_str_layout, query_params,
            error=f"Failed to query layout (copy={copy}, page={page})",
        )

        return self._rows_as_dicts(cursor)

    def select_marks_positions(self, copy, page) -> list[dict[str, Any]]:
        """
        Select the corner positions of the answer boxes of a page of a copy, with their darkness.
        :param copy: The copy (student) identifier.
        :param page: The page number.
        :return: Dicts with keys zoneid, bvalue, corner, x, y, manual, black, and why when the marks are computed.
        """
        query_params = {"copy": str(copy), "page": str(page)}
        scoring_exists = self._has_db(AmcDbFile.SCORING)

        query_str = (
            "SELECT cp.zoneid, "
            "       CAST(cz.black AS REAL) / cz.total AS bvalue, "
            "       cp.corner, cp.x, cp.y, cz.manual, cz.black"
            + (", sc.why " if scoring_exists else " ")
            + "FROM capture_position cp "
              "INNER JOIN capture_zone cz ON cz.zoneid = cp.zoneid "
            + ("LEFT OUTER JOIN scoring.scoring_score sc ON sc.student = :copy AND sc.question = cz.id_a "
               if scoring_exists else "")
            + "WHERE cp.zoneid IN "
              "      (SELECT cz2.zoneid FROM capture_zone cz2 WHERE cz2.student = :copy AND cz2.page = :page) "
              "  AND cp.type = 1 "
              "  AND cz.type = 4 "
              "ORDER BY cz.id_b"
        )

        if scoring_exists:
            self._attach(AmcDbFile.SCORING)

        cursor = self._execute(
            query_str, query_params,
            error=f"Couldn't query data zones (copy={query_params['copy']}, page={query_params['page']})"
        )

        return self._rows_as_dicts(cursor)

    def select_data_zones(self, zoneid: int) -> list[dict[str, float | int]]:
        """
        Select a capture zone's manual value and darkness ratio.
        :param zoneid: The zone id.
        :return: Dicts with the keys "manual" and "bvalue".
        """
        query_str = (
            "SELECT manual, "
            "CASE WHEN total > 0 THEN CAST(black AS REAL) / total ELSE 0.0 END AS bvalue "
            "FROM capture_zone WHERE zoneid = :zoneid"
        )

        cursor = self._execute(
            query_str, {"zoneid": zoneid},
            error=f"Couldn't query data zone (zoneid={zoneid})",
        )

        rows = [
            {
                "manual": manual,
                "bvalue": bvalue
            } for manual, bvalue in cursor.fetchall()
        ]

        for row in rows:
            for key, value in row.items():
                if type(value) is not float:
                    raise AmcDbManagerError(
                        f"zone {zoneid}: {key} expected float, got {type(value).__name__} ({value!r})"
                    )

        return rows


    def update_data_zone(self, manual, zoneid, copy, page):
        """
        Set the manual value of a capture zone, and mark its page as manually edited unless the value is reset.
        :param manual: Manual value, -1 to reset it to the automatic detection.
        :param zoneid: The zone id.
        :param copy: The copy (student) identifier.
        :param page: The page number.
        :return: The number of rows affected.
        """
        update_manual_query_str = "UPDATE capture_zone SET manual = :manual WHERE zoneid = :zoneid"
        update_manual_query_params = {"manual": manual, "zoneid": zoneid}

        update_timestamp_query_str = "UPDATE capture_page SET timestamp_manual = :timestamp WHERE student = :copy AND page = :page"
        update_timestamp_query_params = {"timestamp": int(time.time()), "copy": copy, "page": page}

        update_count = 0

        cursor = self._execute(
            update_manual_query_str, update_manual_query_params,
            error=f"Couldn't update manual value (zoneid={zoneid})"
        )

        update_count += cursor.rowcount

        if float(manual) != -1.0:
            cursor = self._execute(
                update_timestamp_query_str, update_timestamp_query_params,
                error=f"Couldn't update timestamp (copy={copy}, page={page})"
            )
            update_count += cursor.rowcount

        return update_count

    def select_copy_page_zooms(self, copy, page) -> list[dict[str, Any]]:
        """
        Select the answer box zones of a page of a copy, with their images.
        :param copy: The copy (student) identifier.
        :param page: The page number.
        :return: Dicts with keys zoneid, bvalue, imagedata, black, manual.
        """
        query_str = (
            "SELECT zoneid, "
            "       CAST(black AS REAL) / total AS bvalue, "
            "       imagedata, black, manual "
            "FROM capture_zone "
            "WHERE student = :copy AND page = :page AND type = 4"
        )
        query_params = {"copy": copy, "page": page}

        cursor = self._execute(
            query_str, query_params,
            error=f"Couldn't select zooms (copy={copy}, page={page})"
        )

        return self._rows_as_dicts(cursor)

    # ------------------------------------------------------------------
    # capture_failed
    # ------------------------------------------------------------------

    def count_unrecognized_pages(self) -> int:
        """
        Count the scans that AMC could not recognize.
        :return: Number of unrecognized scans.
        """
        query_str = "SELECT COUNT(*) AS count FROM capture_failed"

        cursor = self._execute(
            query_str,
            error="Couldn't count unrecognized pages"
        )

        row = cursor.fetchone()

        return row["count"] if row and row["count"] else 0

    def select_unrecognized_pages(self) -> list[dict[str, str]]:
        """
        Select the scans that AMC could not recognize.
        :return: Dicts with keys filename (base name) and filepath (as stored by AMC).
        """
        query_str = "SELECT filename FROM capture_failed"
        cursor = self._execute(
            query_str,
            error="Couldn't select unrecognized pages"
        )

        return [
            {
                "filename": row["filename"].split("/")[-1],
                "filepath": row["filename"]
            } for row in cursor.fetchall()
        ]

    def delete_unrecognized_page(self, img_filename: str) -> int:
        """
        Delete all rows from capture_failed table where filename LIKE :img_filename
        :param img_filename: filename to delete
        :return: number of rows deleted
        """
        query_str = "DELETE FROM capture_failed WHERE filename LIKE :img_filename"
        query_params = {"img_filename": f"%{img_filename}"}

        cursor = self._execute(
            query_str, query_params,
            error=f"Couldn't delete unrecognized page for image '{img_filename}'"
        )

        return cursor.rowcount
