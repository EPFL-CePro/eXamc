import cv2
from pyzbar import pyzbar

from examc_app.utils.amc_db_queries.layout import AmcLayoutDbManager, get_amc_copy_nr
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

    amc_data_path = f"{amc_project_path}/data/"
    # The QR code holds the ID of the students list, not the AMC copy number
    with AmcLayoutDbManager(amc_data_path=amc_data_path) as amc_layout_db_manager:
        amc_layout_db_manager.get_page_layout_boxes(get_amc_copy_nr(amc_data_path, student), page_nr)

