import re
from _sha2 import sha256
from dataclasses import dataclass
from pathlib import Path

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


TRACEPOS_RE = re.compile(
    r"^\\tracepos\{([^}]*)\}\{([+-]?[0-9.]+[a-z]*)\}\{([+-]?[0-9.]+[a-z]*)\}(?:\{([a-zA-Z]*)\})?$"
)
DIM_RE = re.compile(r"^([+-]?[0-9.]+)([a-z]*)$")
QUESTION_ID_RE = re.compile(r"^SECTION-(\d+)-([A-Z]+)-(\d+)$")
ANSWER_CODE_RE = re.compile(r"^A(\d+)$")
PAGE_TOKEN_RE = re.compile(r"^(\d+)/(\d+)$")
CASE_COORD_RE = re.compile(r"^(\d+),(\d+)$")

A4_WIDTH_AT_300_DPI = 2480.31494396015
A4_HEIGHT_AT_300_DPI = 3507.87397260274
DEFAULT_LAYOUT_DPI = 300.0
DEFAULT_MARK_DIAMETER = 42.519511994409


class LayoutExtractionError(Exception):
    pass


@dataclass
class TracePosEntry:
    raw_payload: str
    x: float
    y: float
    unit: str
    shape: str
    tokens: tuple


@dataclass
class BoxBounds:
    xmin: float
    xmax: float
    ymin: float
    ymax: float


@dataclass
class DecodedPayload:
    kind: str
    copy_number: int | None
    page_number: int | None
    question_id: str | None = None
    answer_number: int | None = None
    zone_type: str | None = None
    corner: int | None = None
    number_id: int | None = None
    digit_id: int | None = None
    raw_tokens: tuple = ()


def _safe_int(value):
    if value in (None, ""):
        return None
    try:
        return int(value)
    except ValueError:
        return None


def _parse_dimension(value: str):
    match = DIM_RE.match(value.strip())
    if not match:
        raise LayoutExtractionError(f"Invalid dimension: {value}")
    number, unit = match.groups()
    return float(number), unit or ""


def parse_tracepos_line(line: str):
    match = TRACEPOS_RE.match(line.strip())
    if not match:
        return None

    raw_payload, x_raw, y_raw, shape = match.groups()
    x, unit_x = _parse_dimension(x_raw)
    y, unit_y = _parse_dimension(y_raw)

    if unit_x != unit_y:
        raise LayoutExtractionError(f"Inconsistent units in tracepos line: {line}")

    return TracePosEntry(
        raw_payload=raw_payload,
        x=x,
        y=y,
        unit=unit_x,
        shape=shape or "",
        tokens=tuple(raw_payload.split(":")),
    )


def load_tracepos_entries(xy_path):
    xy_file = Path(xy_path)
    if not xy_file.exists():
        raise LayoutExtractionError(f"calage.xy not found: {xy_file}")

    entries = []
    for line in xy_file.read_text(encoding="utf-8", errors="replace").splitlines():
        entry = parse_tracepos_line(line)
        if entry is not None:
            entries.append(entry)
    return entries


def group_entries_by_payload(entries):
    grouped = {}
    for entry in entries:
        grouped.setdefault(entry.raw_payload, []).append(entry)
    return grouped


def entries_to_bounds(entries):
    if not entries:
        raise LayoutExtractionError("Cannot compute bounds from empty entry list")

    xs = [entry.x for entry in entries]
    ys = [entry.y for entry in entries]

    return BoxBounds(
        xmin=min(xs),
        xmax=max(xs),
        ymin=min(ys),
        ymax=max(ys),
    )


def decode_payload(tokens):
    lowered = {token.lower() for token in tokens}

    # Parse AMC page token like "1/2" -> copy 1, page 2
    copy_number = None
    page_number = None
    if tokens:
        page_match = PAGE_TOKEN_RE.match(tokens[0])
        if page_match:
            copy_number = int(page_match.group(1))
            page_number = int(page_match.group(2))

    question_id = next((token for token in tokens if QUESTION_ID_RE.match(token)), None)

    # Old/custom answer token style: "A4"
    answer_number = None
    answer_token = next((token for token in tokens if ANSWER_CODE_RE.match(token)), None)
    if answer_token:
        match = ANSWER_CODE_RE.match(answer_token)
        if match:
            answer_number = int(match.group(1))

    # AMC native case payload style: "...:case:SECTION-...:1,4"
    # In your XY file, the second number is the answer number.
    if answer_number is None and "case" in lowered and tokens:
        case_match = CASE_COORD_RE.match(tokens[-1])
        if case_match:
            answer_number = int(case_match.group(2))

    # Keep a fallback pool of plain ints for legacy/custom payloads
    ints = [value for value in (_safe_int(t) for t in tokens) if value is not None]

    if question_id and "case" in lowered and answer_number is not None:
        return DecodedPayload(
            kind="answer_box",
            copy_number=copy_number,
            page_number=page_number,
            question_id=question_id,
            answer_number=answer_number,
            raw_tokens=tokens,
        )

    if question_id and "score" in lowered:
        return DecodedPayload(
            kind="score_box",
            copy_number=copy_number,
            page_number=page_number,
            question_id=question_id,
            raw_tokens=tokens,
        )

    if any(token.lower() in {"coin", "mark"} for token in tokens):
        corner = ints[-1] if ints else None
        return DecodedPayload(
            kind="mark",
            copy_number=copy_number,
            page_number=page_number,
            corner=corner,
            raw_tokens=tokens,
        )

    if any(token.lower() in {"nom", "namefield", "name"} for token in tokens):
        return DecodedPayload(
            kind="zone",
            copy_number=copy_number,
            page_number=page_number,
            zone_type="namefield",
            raw_tokens=tokens,
        )

    if any(token.lower() in {"idzone", "id"} for token in tokens) and not question_id:
        return DecodedPayload(
            kind="zone",
            copy_number=copy_number,
            page_number=page_number,
            zone_type="idzone",
            raw_tokens=tokens,
        )

    if any(token.lower() in {"digit", "chiffre"} for token in tokens):
        digit_pairs = []
        for token in tokens:
            m = CASE_COORD_RE.match(token)
            if m:
                digit_pairs.append((int(m.group(1)), int(m.group(2))))

        if digit_pairs:
            number_id, digit_id = digit_pairs[-1]
        else:
            number_id = ints[-2] if len(ints) >= 2 else None
            digit_id = ints[-1] if len(ints) >= 1 else None

        return DecodedPayload(
            kind="digit",
            copy_number=copy_number,
            page_number=page_number,
            number_id=number_id,
            digit_id=digit_id,
            raw_tokens=tokens,
        )

    return DecodedPayload(
        kind="unknown",
        copy_number=copy_number,
        page_number=page_number,
        raw_tokens=tokens,
    )


def get_or_create_layout_page(build, copy_number, page_number):
    page, _ = LayoutPage.objects.get_or_create(
        build=build,
        copy_number=copy_number,
        page_number=page_number,
        defaults={},
    )
    return page


@transaction.atomic
def clear_build_layout_objects(build):
    LayoutBox.objects.filter(page__build=build).delete()
    LayoutMark.objects.filter(page__build=build).delete()
    LayoutZone.objects.filter(page__build=build).delete()
    LayoutDigit.objects.filter(page__build=build).delete()


@transaction.atomic
def extract_layout_from_xy(build: ExamBuild, xy_path=None, clear_existing=True, strict=False):
    """
    Parse build.xy_path (or explicit xy_path) and fill:
      - LayoutPage
      - LayoutBox
      - LayoutMark
      - LayoutZone
      - LayoutDigit

    Returns a summary dict with counters + unknown payload samples.
    """
    xy_path = xy_path or build.xy_path
    if not xy_path:
        raise LayoutExtractionError("No xy_path provided and build.xy_path is empty")

    if clear_existing:
        clear_build_layout_objects(build)

    entries = load_tracepos_entries(xy_path)
    grouped = group_entries_by_payload(entries)

    build_questions = {
        build_question.rendered_id: build_question
        for build_question in ExamBuildQuestion.objects.filter(build=build).prefetch_related("build_answers")
    }

    unknown_payloads = []
    seen_pages = set()

    counts = {
        "pages": 0,
        "boxes": 0,
        "marks": 0,
        "zones": 0,
        "digits": 0,
        "unknown_payloads": 0,
    }

    for raw_payload, payload_entries in grouped.items():
        decoded = decode_payload(payload_entries[0].tokens)
        bounds = entries_to_bounds(payload_entries)

        if decoded.page_number is None:
            if strict:
                raise LayoutExtractionError(f"Could not decode page number from payload: {raw_payload}")
            unknown_payloads.append(raw_payload)
            continue

        page_number = decoded.page_number or 1
        layout_page = get_or_create_layout_page(
            build=build,
            copy_number=decoded.copy_number,
            page_number=page_number,
        )

        page_key = (decoded.copy_number, page_number)
        if page_key not in seen_pages:
            seen_pages.add(page_key)
            counts["pages"] += 1

        if decoded.kind == "answer_box":
            build_question = build_questions.get(decoded.question_id or "")
            if build_question is None:
                if strict:
                    raise LayoutExtractionError(
                        f"Question id not found in build snapshot: {decoded.question_id}"
                    )
                unknown_payloads.append(raw_payload)
                continue

            build_answer = build_question.build_answers.filter(
                rendered_answer_number=decoded.answer_number
            ).first()

            LayoutBox.objects.create(
                page=layout_page,
                build_question=build_question,
                build_answer=build_answer,
                role="answer",
                answer_number=decoded.answer_number or 0,
                flags=0,
                char="",
                xmin=bounds.xmin,
                xmax=bounds.xmax,
                ymin=bounds.ymin,
                ymax=bounds.ymax,
            )
            counts["boxes"] += 1
            continue

        if decoded.kind == "score_box":
            build_question = build_questions.get(decoded.question_id or "")
            if build_question is None:
                if strict:
                    raise LayoutExtractionError(
                        f"Score box question id not found in build snapshot: {decoded.question_id}"
                    )
                unknown_payloads.append(raw_payload)
                continue

            LayoutBox.objects.create(
                page=layout_page,
                build_question=build_question,
                build_answer=None,
                role="score",
                answer_number=0,
                flags=0,
                char="",
                xmin=bounds.xmin,
                xmax=bounds.xmax,
                ymin=bounds.ymin,
                ymax=bounds.ymax,
            )
            counts["boxes"] += 1
            continue

        if decoded.kind == "mark":
            if decoded.corner is None:
                unknown_payloads.append(raw_payload)
                continue

            LayoutMark.objects.update_or_create(
                page=layout_page,
                corner=decoded.corner,
                defaults={
                    "x": payload_entries[0].x,
                    "y": payload_entries[0].y,
                },
            )
            counts["marks"] += 1
            continue

        if decoded.kind == "zone":
            LayoutZone.objects.create(
                page=layout_page,
                zone_type=decoded.zone_type or "custom",
                zone_code=raw_payload,
                flags=0,
                xmin=bounds.xmin,
                xmax=bounds.xmax,
                ymin=bounds.ymin,
                ymax=bounds.ymax,
            )
            counts["zones"] += 1
            continue

        if decoded.kind == "digit":
            if decoded.number_id is None or decoded.digit_id is None:
                unknown_payloads.append(raw_payload)
                continue

            LayoutDigit.objects.update_or_create(
                page=layout_page,
                number_id=decoded.number_id,
                digit_id=decoded.digit_id,
                defaults={
                    "xmin": bounds.xmin,
                    "xmax": bounds.xmax,
                    "ymin": bounds.ymin,
                    "ymax": bounds.ymax,
                },
            )
            counts["digits"] += 1
            continue

        unknown_payloads.append(raw_payload)

    deduped_unknown_payloads = sorted(set(unknown_payloads))
    counts["unknown_payloads"] = len(deduped_unknown_payloads)

    return {
        **counts,
        "unknown_payload_samples": deduped_unknown_payloads[:50],
    }

def _compute_layout_page_checksum(build_id: int, copy_number: int, page_number: int, source_page_number: int) -> int:
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
    width: float = A4_WIDTH_AT_300_DPI,
    height: float = A4_HEIGHT_AT_300_DPI,
    mark_diameter: float = DEFAULT_MARK_DIAMETER,
):
    """
    Create or update LayoutPage rows for the SUBJECT build only.

    source_page_number is the physical page sequence in the compiled subject PDF:
      copy 1/page 1 -> 1
      copy 1/page 2 -> 2
      ...
      copy 2/page 1 -> pages_per_copy + 1
      etc.
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
    entries = load_tracepos_entries(xy_path)

    max_copy = 0
    max_page = 0

    for entry in entries:
        tokens = entry.tokens
        if not tokens:
            continue

        page_token = tokens[0]
        match = PAGE_TOKEN_RE.match(page_token)
        if not match:
            continue

        copy_number = int(match.group(1))
        page_number = int(match.group(2))

        if copy_number > max_copy:
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