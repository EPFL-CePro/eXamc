import re
from dataclasses import dataclass

from examc_app.models import Exam

# QR code printed on each page of a copy (\examcQRCode in exam_template.tex):
#   eXamcQRC2,<exam pk>,<exam code>,<exam date YYYYMMDD>,<copy number>,<page>
# The exam pk is empty when the project was compiled outside eXamc (the AMC models of CePro): the scans are then
# checked against the exam code and date.
QR_PREFIX = "eXamcQRC2"
# Without exam: "<prefix>,<copy number>,<page>", accepted without check
LEGACY_QR_PREFIXES = ("CePROExamsQRC", "eXamcQRC")


def qr_exam_code(code) -> str:
    """The exam code as written in the QR codes: upper case, any run of other characters than A-Z 0-9 . - as '-'."""
    return re.sub(r"[^A-Z0-9.-]+", "-", str(code or "").strip().upper())


def qr_exam_date(exam: Exam) -> str:
    return exam.date.strftime("%Y%m%d") if exam.date else ""


def qr_exam_fields(exam: Exam) -> str:
    """'<prefix>,<pk>,<code>,<date>': the start of the QR codes of the exam, before the copy and page numbers."""
    return f"{QR_PREFIX},{exam.pk},{qr_exam_code(exam.code)},{qr_exam_date(exam)}"


@dataclass(frozen=True)
class ScanQr:
    """The content of the QR code of a scanned page. The exam fields are None for the legacy QR codes."""
    copy_no: str
    page_no: str
    exam_pk: str | None = None
    exam_code: str | None = None
    exam_date: str | None = None


def parse_scan_qr(text: str) -> ScanQr | None:
    """The QR code of an eXamc copy page, None for another QR code (one printed in a question...)."""
    fields = text.split(",")
    if fields[0] == QR_PREFIX and len(fields) == 6:
        _, exam_pk, exam_code, exam_date, copy_no, page_no = fields
        if not exam_pk and not exam_code:
            return None
        qr = ScanQr(copy_no, page_no, exam_pk, exam_code, exam_date)
    elif fields[0] in LEGACY_QR_PREFIXES and len(fields) >= 3:
        qr = ScanQr(fields[1], fields[2])
    else:
        return None
    return qr if qr.copy_no and qr.page_no else None


def scan_exams(exam: Exam) -> list[Exam]:
    """The exams whose pages may be in the scans of `exam`: itself and its common exams."""
    return [exam, *exam.common_exams.all()]


def scan_qr_exam_problem(qr: ScanQr, exams: list[Exam]) -> str | None:
    """
    Why the page of `qr` does not belong to one of `exams` (see scan_exams), None when it does or when the QR code
    has no exam (legacy).
    """
    if qr.exam_pk is None:
        return None
    if qr.exam_pk:
        if qr.exam_pk in {str(e.pk) for e in exams}:
            return None
    # Compiled outside eXamc: same code, and same date when both are known
    elif any(qr.exam_code == qr_exam_code(e.code) and (not qr.exam_date or not e.date or qr.exam_date == qr_exam_date(e))
             for e in exams):
        return None
    date = f" of {qr.exam_date}" if qr.exam_date else ""
    return f"page of another exam ({qr.exam_code}{date})"
