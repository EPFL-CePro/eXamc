from typing import TypedDict

from examc_app.utils.amc_db_queries.AbstractAmcDbManager import AbstractAmcDbManager


class CapturePage(TypedDict):
    student: str
    page: str
    src: str


class AmcCaptureDbManager(AbstractAmcDbManager):
    """Access to AMC's capture.sqlite"""

    def __init__(self, amc_data_path: str):
        super().__init__(amc_data_path, amc_table_file="capture.sqlite")

    def delete_unrecognized_page(self, img_filename: str) -> int:
        """
        Delete all rows from capture_failed table where filename LIKE :img_filename
        :param img_filename: filename to delete
        :return: number of rows deleted
        """
        query_str = "DELETE FROM capture_failed WHERE filename LIKE :img_filename"
        query_params = {"img_filename": f"%{img_filename}"}

        try:
            cursor = self._db.execute_query(query_str, query_params)
            rowcount = cursor.rowcount

            return rowcount
        finally:
            self._db.close()

    def select_capture_pages(self) -> list[CapturePage]:
        """
        Select all rows from the capture_page table ordered by student, page
        :return: list of dictionaries with keys student, page, src
        """
        query_str = "SELECT student, page, src FROM capture_page ORDER BY student, page"

        try:
            cursor = self._execute(query=query_str, error="Couldn't select capture pages")

            return [
                CapturePage(student=student, page=page, src=src)
                for student, page, src in cursor.fetchall()
            ]
        finally:
            self._db.close()

    def update_capture_page_src(self, student: str, page, new_filename: str) -> int:
        """
        Update capture_page table with new_filename where student = :student and page = :page
        :param student: student id
        :param page: page number
        :param new_filename: new filename
        :raise AmcDbManagerError: if the update fails
        :return: number of rows updated
        """
        query_str = "UPDATE capture_page SET src = :new_filename WHERE student = :student AND page = :page"
        query_params = {"new_filename": new_filename, "student": student, "page": page}

        try:
            cursor = self._execute(
                query_str, query_params,
                f"Couldn't update capture_page with src={new_filename}, student={student} and page={page}"
            )

            return cursor.rowcount
        finally:
            self._db.close()

    def select_amc_scan_path(self, copy_no: str, page_no: str) -> str:
        """
        Selects the scan path for a given copy number and page number.

        This method interacts with the database to fetch the source path
        of a scanned document based on the provided copy number and page
        number. An internal query is executed and returns the scan path
        associated with the given parameters.

        :param copy_no: The unique identifier for the copy (student).
        :type copy_no: str
        :param page_no: The page number to locate the scan path.
        :type page_no: str
        :return: The source path of the scanned document.
        :rtype: str
        """
        query_str = "SELECT src FROM capture_page cp WHERE page = :page_no AND student = :student"
        query_params = {"page": page_no, "student": copy_no}

        try:
            scan_path = ""

            cursor = self._db.execute_query(query_str, query_params)

            if cursor:
                scan_path = cursor.fetchall()[0]['src']

            return scan_path
        finally:
            self._db.close()