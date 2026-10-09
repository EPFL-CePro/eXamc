import cv2
from pyzbar import pyzbar

from examc_app.utils.amc_db_queries.layout import AmcLayoutDbManager
from examc_app.utils.amc_functions import get_amc_project_path
from examc_app.utils.review_functions import get_expected_review_qr_data


def get_scan_qrcode_data(file_path):
    # read qrcode (see parse_scan_qr)
    image = cv2.imread(file_path)
    return get_expected_review_qr_data(pyzbar.decode(image))

def analyze_scan(file_path,exam,student=None,page_nr=None):
    if not student or not page_nr:
        data = get_scan_qrcode_data(file_path)
        student = data.copy_no
        page_nr = data.page_no

    amc_project_path = get_amc_project_path(exam, True)

    with AmcLayoutDbManager(amc_data_path=f"{amc_project_path}/data/") as amc_layout_db_manager:
        amc_layout_db_manager.get_page_layout_boxes(student, page_nr)

