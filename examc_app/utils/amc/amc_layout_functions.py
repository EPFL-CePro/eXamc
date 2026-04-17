"""
AMC layout extraction and page-population helpers.

This module is responsible for converting AMC layout output (mainly the
``calage.xy`` file and the compiled subject PDF) into normalized Django models.

It performs two distinct jobs that must stay separate:

1. Determine subject copy/page structure and populate ``LayoutPage`` rows.
2. Parse XY geometry and insert per-page objects such as boxes, zones, digits,
   and corner marks.

Important invariants:
- Only SUBJECT artifacts should be used for database layout extraction.
- ``LayoutPage`` rows should exist before geometry objects are attached.
- Object cleanup must not delete the page rows themselves.
- Numeric checksums must fit inside a signed MySQL ``BIGINT``.
"""

import re
from _sha2 import sha256
from dataclasses import dataclass, field
from pathlib import Path

from PyPDF2 import PdfReader
from django.db import transaction

from examc_app.models import (
    ExamBuild,
    ExamBuildQuestion,
    LayoutBox,
    LayoutDigit,
    LayoutMark,
    LayoutPage,
    LayoutZone,
)

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

ZONE_FLAGS_ID = 0x1

BOX_ROLE_ANSWER = "answer"
BOX_ROLE_QUESTIONONLY = "question_only"
BOX_ROLE_SCORE = "score"
BOX_ROLE_SCOREQUESTION = "score_question"
BOX_ROLE_QUESTIONTEXT = "question_text"
BOX_ROLE_ANSWERTEXT = "answer_text"

AMC_TYPE_TO_ROLE = {
    "case": BOX_ROLE_ANSWER,
    "casequestion": BOX_ROLE_QUESTIONONLY,
    "score": BOX_ROLE_SCORE,
    "scorequestion": BOX_ROLE_SCOREQUESTION,
    "qtext": BOX_ROLE_QUESTIONTEXT,
    "atext": BOX_ROLE_ANSWERTEXT,
}

DEFAULT_LAYOUT_DPI = 300.0
DEFAULT_MARK_DIAMETER = 42.519511994409
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



def _safe_int(value):
    """
    Best-effort integer conversion used by parsing helpers.
    """
    if value in (None, ""):
        return None
    try:
        return int(value)
    except ValueError:
        return None



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



def build_question_maps(
    build: ExamBuild,
) -> tuple[dict[str, ExamBuildQuestion], dict[int, ExamBuildQuestion]]:
    """
    Preload build questions and expose lookup maps by rendered id and AMC number.
    """
    questions = list(
        ExamBuildQuestion.objects.filter(build=build).prefetch_related("build_answers")
    )

    by_rendered_id: dict[str, ExamBuildQuestion] = {}
    by_amc_question_number: dict[int, ExamBuildQuestion] = {}

    for question in questions:
        by_rendered_id[question.rendered_id] = question

        if question.amc_question_number is not None:
            by_amc_question_number[question.amc_question_number] = question

    return by_rendered_id, by_amc_question_number



def build_answer_maps(build_question):
    """
    Build answer lookup maps by rendered code and rendered answer number.
    """
    by_code = {}
    by_number = {}

    for answer in build_question.build_answers.all():
        if answer.rendered_code:
            by_code[answer.rendered_code] = answer
        if answer.rendered_answer_number is not None:
            by_number[answer.rendered_answer_number] = answer

    return by_code, by_number



def find_build_answer_for_amc(build_question, answer_number: int):
    """
    Resolve an AMC answer number to the matching frozen build-answer row.

    The preferred lookup is via rendered code (for example ``A4``), with a
    fallback to the numeric rendered answer number.
    """
    by_code, by_number = build_answer_maps(build_question)

    answer = by_code.get(f"A{answer_number}")
    if answer is not None:
        return answer

    return by_number.get(answer_number)



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



def bbox_from_case(case: CaseData, page_y_in: float, dpi: float) -> tuple[float, float, float, float]:
    """
    Convert one parsed XY case into the AMC bounding-box convention in pixels.
    """
    if len(case.bx) != 2 or len(case.by) != 2:
        raise LayoutExtractionError(f"Incomplete case bounds for key: {case.raw_key or case.normalized_key}")

    bx0 = case.bx[0] * dpi
    bx1 = case.bx[1] * dpi
    by0 = dpi * (page_y_in - case.by[0])
    by1 = dpi * (page_y_in - case.by[1])

    # AMC bbox order: xmin, xmax, ymin, ymax = bx_min, bx_max, by_max, by_min
    return bx0, bx1, by1, by0



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



def get_or_create_layout_page(build, copy_number, page_number):
    """
    Fetch or create one ``LayoutPage`` row for a build/copy/page triple.
    """
    page, _ = LayoutPage.objects.get_or_create(
        build=build,
        copy_number=copy_number,
        page_number=page_number,
        defaults={},
    )
    return page


@transaction.atomic
def clear_build_layout_objects(build):
    """
    Delete extracted layout objects for a build without deleting page rows.

    This is important because page metadata may already have been populated and
    should survive re-extraction.
    """
    LayoutBox.objects.filter(page__build=build).delete()
    LayoutMark.objects.filter(page__build=build).delete()
    LayoutZone.objects.filter(page__build=build).delete()
    LayoutDigit.objects.filter(page__build=build).delete()


@transaction.atomic
def extract_layout_from_xy(build: ExamBuild, xy_path=None, clear_existing=True, strict=False):
    """
    Parse a subject XY file and persist geometry-driven layout objects.

    Flow:
    1. Parse the full source file, including pages, trace positions, chars, and
       question-level flags.
    2. Create or reuse ``LayoutPage`` rows.
    3. Insert geometry-based boxes, zones, digits, and corner marks.
    4. Apply AMC question-level flags to answer-role boxes.

    Args:
        build: Frozen exam build snapshot.
        xy_path: Optional override path. Defaults to ``build.xy_path``.
        clear_existing: Whether existing layout objects should be deleted first.
        strict: Whether unknown question references should raise errors.

    Returns:
        dict: Counts of inserted objects and samples of unknown payloads.
    """
    xy_path = xy_path or build.xy_path
    if not xy_path:
        raise LayoutExtractionError("No xy_path provided and build.xy_path is empty")

    if clear_existing:
        clear_build_layout_objects(build)

    pages, question_flags = parse_amc_layout_source(xy_path)
    _, build_questions_by_number = build_question_maps(build)

    counts = {
        "pages": 0,
        "boxes": 0,
        "marks": 0,
        "zones": 0,
        "digits": 0,
        "unknown_payloads": 0,
    }
    unknown_payloads: list[str] = []

    # Key = (copy_number, amc_question_number), value = inserted answer-box ids
    inserted_answer_box_ids: dict[tuple[int | None, int], list[int]] = {}

    for parsed_page in pages:
        copy_number, page_number = get_epc_from_page_or_cases(parsed_page)

        layout_page = get_or_create_layout_page(
            build=build,
            copy_number=copy_number,
            page_number=page_number,
        )
        counts["pages"] += 1

        dpi = layout_page.dpi or DEFAULT_LAYOUT_DPI

        # AMC-like mark diameter from position boxes.
        mark_diameter = 0.0
        dmn = 0
        for case in parsed_page.cases.values():
            key = case.normalized_key
            if re.search(r"position[HB][GD]$", key):
                if len(case.bx) == 2:
                    mark_diameter += abs(case.bx[1] - case.bx[0]) * dpi
                    dmn += 1
                if len(case.by) == 2:
                    mark_diameter += abs(case.by[1] - case.by[0]) * dpi
                    dmn += 1

        if dmn:
            layout_page.mark_diameter = mark_diameter / dmn
            layout_page.save(update_fields=["mark_diameter"])

        # Regular objects.
        for case in sorted(parsed_page.cases.values(), key=lambda c: c.normalized_key):
            raw_key = case.normalized_key

            # Corner positions are converted to LayoutMark later.
            if re.search(r"position[HB][GD]$", raw_key):
                continue

            xmin, xmax, ymin, ymax = bbox_from_case(case, parsed_page.page_y_in, dpi)

            match = re.search(r"chiffre:([0-9]+),([0-9]+)$", raw_key)
            if match:
                LayoutDigit.objects.update_or_create(
                    page=layout_page,
                    number_id=int(match.group(1)),
                    digit_id=int(match.group(2)),
                    defaults={
                        "xmin": xmin,
                        "xmax": xmax,
                        "ymin": ymin,
                        "ymax": ymax,
                    },
                )
                counts["digits"] += 1
                continue

            match = re.search(r"__zone:(.*):(.*)$", raw_key)
            if match:
                flags_str, zone = match.groups()
                zone_flags = 0
                for flag_name in re.split(r"\s*,\s*", flags_str):
                    if flag_name == "id":
                        zone_flags |= ZONE_FLAGS_ID

                LayoutZone.objects.create(
                    page=layout_page,
                    zone_type="idzone" if zone == "id" else "custom",
                    zone_code=zone,
                    flags=zone_flags,
                    xmin=xmin,
                    xmax=xmax,
                    ymin=ymin,
                    ymax=ymax,
                )
                counts["zones"] += 1
                continue

            match = re.search(
                r"(case|casequestion|score|scorequestion|qtext|atext):(.+?):([0-9]+),(-?[0-9]+)$",
                raw_key,
            )
            if match:
                box_type, _name, q_num, a_num = match.groups()
                q_num = int(q_num)
                a_num = int(a_num)

                build_question = build_questions_by_number.get(q_num)
                if build_question is None:
                    if strict:
                        raise LayoutExtractionError(f"Question number not found for {raw_key}")
                    unknown_payloads.append(raw_key)
                    continue

                build_answer = None
                if box_type == "case" and a_num > 0:
                    build_answer = find_build_answer_for_amc(build_question, a_num)

                box = LayoutBox.objects.create(
                    page=layout_page,
                    build_question=build_question,
                    build_answer=build_answer,
                    role=AMC_TYPE_TO_ROLE[box_type],
                    answer_number=a_num,
                    flags=case.flags,
                    char=case.char or "",
                    xmin=xmin,
                    xmax=xmax,
                    ymin=ymin,
                    ymax=ymax,
                )
                counts["boxes"] += 1

                # Keep exact AMC numeric question mapping for phase-2 flag application.
                if box_type == "case":
                    inserted_answer_box_ids.setdefault((copy_number, q_num), []).append(box.id)

                continue

            unknown_payloads.append(raw_key)

        # Corner marks.
        corner_map = ["HG", "HD", "BD", "BG"]
        for idx, pos in enumerate(corner_map, start=1):
            target = f"position{pos}"
            case = next(
                (c for c in parsed_page.cases.values() if c.normalized_key == target),
                None,
            )
            if not case:
                continue

            xmin, xmax, ymin, ymax = bbox_from_case(case, parsed_page.page_y_in, dpi)
            LayoutMark.objects.update_or_create(
                page=layout_page,
                corner=idx,
                defaults={
                    "x": (xmin + xmax) / 2,
                    "y": (ymin + ymax) / 2,
                },
            )
            counts["marks"] += 1

    # Phase 2: apply AMC question-level flags to answer boxes only.
    for key, flags in question_flags.items():
        box_ids = inserted_answer_box_ids.get(key, [])
        if not box_ids:
            continue

        for box in LayoutBox.objects.filter(id__in=box_ids):
            box.flags |= flags
            box.save(update_fields=["flags"])

    deduped_unknown_payloads = sorted(set(unknown_payloads))
    counts["unknown_payloads"] = len(deduped_unknown_payloads)

    return {
        **counts,
        "unknown_payload_samples": deduped_unknown_payloads[:50],
    }



def _compute_layout_page_checksum(build_id: int, copy_number: int, page_number: int, source_page_number: int) -> int:
    """
    Compute a deterministic page checksum that fits in signed MySQL ``BIGINT``.
    """
    payload = f"{build_id}:{copy_number}:{page_number}:{source_page_number}"
    digest = sha256(payload.encode("utf-8")).digest()
    return int.from_bytes(digest[:8], byteorder="big", signed=False) & 0x7FFFFFFFFFFFFFFF


@transaction.atomic
def populate_subject_layout_pages(
    build,
    *,
    total_copies: int,
    pages_per_copy: int,
    dpi: float = DEFAULT_LAYOUT_DPI,
    width: float | None = None,
    height: float | None = None,
    mark_diameter: float = DEFAULT_MARK_DIAMETER,
):
    """
    Populate or update ``LayoutPage`` rows for the canonical subject build.

    The generated page metadata is later reused by XY geometry extraction and by
    downstream scan/scoring logic.

    Returns:
        dict: Number of created/updated pages and total expected pages.
    """
    created = 0
    updated = 0
    source_page_number = 1

    for copy_number in range(1, total_copies + 1):
        for page_number in range(1, pages_per_copy + 1):
            checksum = _compute_layout_page_checksum(
                build_id=build.pk,
                copy_number=copy_number,
                page_number=page_number,
                source_page_number=source_page_number,
            )

            page, was_created = LayoutPage.objects.update_or_create(
                build=build,
                copy_number=copy_number,
                page_number=page_number,
                defaults={
                    "checksum": checksum,
                    "source_page_number": source_page_number,
                    "dpi": dpi,
                    "width": width,
                    "height": height,
                    "mark_diameter": mark_diameter,
                },
            )

            if was_created:
                created += 1
            else:
                updated += 1

            source_page_number += 1

    return {
        "created_pages": created,
        "updated_pages": updated,
        "total_pages": total_copies * pages_per_copy,
    }



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
