import os.path

import cv2
from pyzbar import pyzbar

from examc_app.utils.amc_db_queries import get_page_layout_boxes
from examc_app.utils.amc_functions import get_amc_project_path


def get_scan_qrcode_data(file_path):
    # read qrcode
    image = cv2.imread(file_path)
    decodeObjects = pyzbar.decode(image)
    data = None
    if len(decodeObjects) > 0:
        for obj in decodeObjects:
            if str(obj.type) == 'QRCODE' and 'CePROExamsQRC' in str(obj.data):
                data = obj.data.decode("utf-8").split(',')
    return data

def analyze_scan(file_path,exam,student=None,page_nr=None):

    if not student or not page_nr:
        data = get_scan_qrcode_data(file_path)
        student = data[1]
        page_nr = data[2]

    layout_boxes = get_page_layout_boxes(get_amc_project_path(exam, True) + "/data/",student, page_nr)






