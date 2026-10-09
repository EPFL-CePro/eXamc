import cv2
from pyzbar import pyzbar

from examc_app.utils.amc_db_queries.layout import AmcLayoutDbManager
from examc_app.utils.amc_functions import get_amc_project_path


def get_scan_qrcode_data(file_path):
    # read qrcode
    image = cv2.imread(file_path)
    decode_objects = pyzbar.decode(image)
    data = None
    if len(decode_objects) > 0:
        for obj in decode_objects:
            if str(obj.type) == 'QRCODE' and 'CePROExamsQRC' in str(obj.data):
                data = obj.data.decode("utf-8").split(',')
    return data

def analyze_scan(file_path,exam,student=None,page_nr=None):
    if not student or not page_nr:
        data = get_scan_qrcode_data(file_path)
        student = data[1]
        page_nr = data[2]

    amc_project_path = get_amc_project_path(exam, True)

    with AmcLayoutDbManager(amc_data_path=f"{amc_project_path}/data/") as amc_layout_db_manager:
        amc_layout_db_manager.get_page_layout_boxes(student, page_nr)

