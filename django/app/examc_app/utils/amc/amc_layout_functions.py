"""
Helpers reading the AMC layout output of the subject (the ``calage.xy`` file and the compiled PDF).

AMC itself stores the layout in the ``layout.sqlite`` of the project (``auto-multiple-choice meptex``), which is the
reference for the scans and the scoring: nothing of it is copied in the database of eXamc. This module only reads the
number of copies and pages of the XY file, to check them against the PDF.
"""

import re
from dataclasses import dataclass, field
from pathlib import Path

from pypdf import PdfReader

QUESTION_ID_RE = re.compile(r"^SECTION-(\d+)-([A-Z]+)-(\d+)$")

PAGE_RE = re.compile(
    r"\\page\{([^\}]+)\}\{([^\}]+)\}\{([^\}]+)\}(?:\{([^\}]+)\}\{([^\}]+)\})?"
)
TRACEPOS_RE = re.compile(
    r"\\tracepos\{(.+?)\}\{([+-]?[0-9.]+[a-z]*)\}\{([+-]?[0-9.]+[a-z]*)\}(?:\{([a-zA-Z]*)\})?$"
)
BOXCHAR_RE = re.compile(r"\\boxchar\{(.+)\}\{(.*)\}$")
DONTSCAN_RE = re.compile(r"\\dontscan\{(.*)\}")
DONTANNOTATE_RE = re.compile(r"\\dontannotate\{(.*)\}")
RETICK_RE = re.compile(r"\\retick\{(.*)\}")

BOX_FLAGS_DONTSCAN = 0x1
BOX_FLAGS_DONTANNOTATE = 0x2
BOX_FLAGS_RETICK = 0x4
BOX_FLAGS_SHAPE_OVAL = 0x10

DEFAULT_LAYOUT_DPI = 300.0
PDF_POINTS_PER_INCH = 72.0

UNIT_IN_ONE_INCH = {
    "in": 1.0,
    "cm": 2.54,
    "mm": 25.4,
    "pt": 72.27,
    "sp": 65536 * 72.27,
}


class LayoutExtractionError(Exception):
    """
    Raised when AMC layout extraction or page analysis cannot be completed.
    """
    pass


@dataclass
class CaseData:
    """
    Parsed raw XY object for one AMC case/trace entry.
    """
    raw_key: str = ""
    normalized_key: str = ""
    bx: list[float] = field(default_factory=list)
    by: list[float] = field(default_factory=list)
    flags: int = 0
    shape: str = ""
    char: str = ""


@dataclass
class ParsedPage:
    """
    Parsed representation of one AMC page section from the XY file.
    """
    page_id: str
    page_number: int
    dim_x_in: float
    dim_y_in: float
    page_x_in: float
    page_y_in: float
    cases: dict[str, CaseData] = field(default_factory=dict)



def read_inches(dim: str) -> float:
    """
    Convert an AMC/TeX dimension string to inches.

    Args:
        dim: Dimension such as ``12mm`` or ``8.5in``.

    Returns:
        float: Value converted to inches.
    """
    match = re.match(r"^\s*([+-]?[0-9]*\.?[0-9]*)\s*([a-zA-Z]+)\s*$", dim)
    if not match:
        raise LayoutExtractionError(f"Unknown dim: {dim}")

    value = float(match.group(1))
    unit = match.group(2)

    if unit not in UNIT_IN_ONE_INCH:
        raise LayoutExtractionError(f"Unknown unit: {unit}")

    return value / UNIT_IN_ONE_INCH[unit]


def _strip_student_page_prefix(payload: str) -> str:
    """
    Remove the leading ``copy/page:`` prefix from an AMC payload key.
    """
    return re.sub(r"^[0-9]+/[0-9]+:", "", payload)



def _add_span(bounds: list[float], value: float) -> None:
    """
    Expand a min/max bounds list with one additional coordinate value.
    """
    if bounds:
        if value and bounds[0] > value:
            bounds[0] = value
        if value and bounds[1] < value:
            bounds[1] = value
    else:
        if value:
            bounds[:] = [value, value]



def _add_question_flag(flag_map: dict[tuple[int, int], int], ref: str, flag: int) -> None:
    """
    Accumulate AMC question-level flags keyed by ``(copy_number, question_no)``.
    """
    match = re.match(r"^([0-9]+),([0-9]+)$", ref)
    if not match:
        return

    student = int(match.group(1))
    question = int(match.group(2))
    key = (student, question)
    flag_map[key] = flag_map.get(key, 0) | flag



def get_epc_from_page_or_cases(parsed_page: ParsedPage) -> tuple[int | None, int]:
    """
    Extract ``(copy_number, page_number)`` from the raw case keys of a page.

    AMC embeds the copy/page prefix in case payloads such as ``1/2:case:...``.
    This helper keeps the logic close to AMC's own notion of sheet/page origin.
    """
    for raw_key in parsed_page.cases.keys():
        match = re.match(r"^(\d+)/(\d+):", raw_key)
        if match:
            return int(match.group(1)), int(match.group(2))

    raise LayoutExtractionError(
        f"Could not extract copy/page from parsed page {parsed_page.page_id}"
    )



def parse_amc_layout_source(src_path: str) -> tuple[list[ParsedPage], dict[tuple[int, int], int]]:
    """
    Parse a full AMC XY source file.

    Returns:
        tuple:
            - list of parsed pages with their cases
            - question-level flag map keyed by ``(copy_number, question_number)``
    """
    pages: list[ParsedPage] = []
    question_flags: dict[tuple[int, int], int] = {}
    current_page: ParsedPage | None = None
    page_number = 0

    src_file = Path(src_path)
    if not src_file.exists():
        raise LayoutExtractionError(f"AMC layout source not found: {src_file}")

    with src_file.open("r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            match = PAGE_RE.search(line)
            if match:
                page_id, dx, dy, px, py = match.groups()
                px = dx if not px or not re.search(r"[1-9]", px) else px
                py = dy if not py or not re.search(r"[1-9]", py) else py

                page_number += 1
                current_page = ParsedPage(
                    page_id=page_id,
                    page_number=page_number,
                    dim_x_in=read_inches(dx),
                    dim_y_in=read_inches(dy),
                    page_x_in=read_inches(px),
                    page_y_in=read_inches(py),
                )
                pages.append(current_page)
                continue

            if current_page is None:
                continue

            match = TRACEPOS_RE.search(line)
            if match:
                raw_id, x_raw, y_raw, shape = match.groups()
                x = read_inches(x_raw)
                y = read_inches(y_raw)

                normalized_key = _strip_student_page_prefix(raw_id)
                case = current_page.cases.setdefault(
                    raw_id,
                    CaseData(raw_key=raw_id, normalized_key=normalized_key),
                )
                _add_span(case.bx, x)
                _add_span(case.by, y)

                shape = shape or ""
                if not case.shape or case.shape == shape:
                    case.shape = shape
                    if shape == "oval":
                        case.flags |= BOX_FLAGS_SHAPE_OVAL
                continue

            match = BOXCHAR_RE.search(line)
            if match:
                raw_id, char = match.groups()
                normalized_key = _strip_student_page_prefix(raw_id)
                case = current_page.cases.setdefault(
                    raw_id,
                    CaseData(raw_key=raw_id, normalized_key=normalized_key),
                )
                case.char = char
                continue

            match = DONTSCAN_RE.search(line)
            if match:
                _add_question_flag(question_flags, match.group(1), BOX_FLAGS_DONTSCAN)
                continue

            match = DONTANNOTATE_RE.search(line)
            if match:
                _add_question_flag(question_flags, match.group(1), BOX_FLAGS_DONTANNOTATE)
                continue

            match = RETICK_RE.search(line)
            if match:
                _add_question_flag(question_flags, match.group(1), BOX_FLAGS_RETICK)
                continue

    return pages, question_flags



def get_pdf_page_metrics(pdf_path: str, *, dpi: float = DEFAULT_LAYOUT_DPI) -> dict:
    """
    Read the compiled subject PDF and derive page metrics at the target DPI.

    Returns:
        dict: page count, DPI, width, and height expressed in output pixels.
    """
    reader = PdfReader(pdf_path)
    if not reader.pages:
        raise LayoutExtractionError(f"PDF has no pages: {pdf_path}")

    first_page = reader.pages[0]
    width_points = float(first_page.mediabox.width)
    height_points = float(first_page.mediabox.height)

    return {
        "page_count": len(reader.pages),
        "dpi": dpi,
        "width": width_points / PDF_POINTS_PER_INCH * dpi,
        "height": height_points / PDF_POINTS_PER_INCH * dpi,
    }



def get_pages_by_copy_from_xy(xy_path) -> dict[int, int]:
    """The number of pages of each copy of the subject XY file: {copy number: pages}."""
    pages, _ = parse_amc_layout_source(xy_path)

    pages_by_copy = {}
    for parsed_page in pages:
        copy_number, page_number = get_epc_from_page_or_cases(parsed_page)
        if copy_number:
            pages_by_copy[copy_number] = max(pages_by_copy.get(copy_number, 0), page_number)
    return pages_by_copy


def get_subject_copy_and_page_counts_from_xy(xy_path):
    """
    Derive subject copy and page counts from the subject XY file.

    Returns:
        dict: Total copies, pages per copy, and total pages.
    """
    pages, _ = parse_amc_layout_source(xy_path)

    max_copy = 0
    max_page = 0

    for parsed_page in pages:
        copy_number, page_number = get_epc_from_page_or_cases(parsed_page)

        if copy_number and copy_number > max_copy:
            max_copy = copy_number
        if page_number > max_page:
            max_page = page_number

    if max_copy == 0 or max_page == 0:
        raise LayoutExtractionError(f"Could not determine copy/page counts from XY file: {xy_path}")

    return {
        "total_copies": max_copy,
        "pages_per_copy": max_page,
        "total_pages": max_copy * max_page,
    }
