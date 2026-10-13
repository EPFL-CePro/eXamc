import re

from examc_app.models import Exam

OVERALL_CODE_PREXIX = "000"

def build_overall_exam_code(exam: Exam):
    # Sample 000_Code_11-2026
    clean_code = re.sub(r"\(.*?\)", "", exam.code).strip()
    return f"000_{clean_code}_{exam.date.strftime('%m-%Y')}"