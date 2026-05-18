"""Server-side rendering helpers for PageMarkers markerjs3 JSON.

This module turns persisted marker state stored in ``PageMarkers.markers``
into rendered images written under ``MARKED_SCANS_ROOT``.

Current renderer coverage:
- ``FreehandMarker`` via embedded PNG data URLs
- ``HighlightMarker`` as a filled rectangle
- ``FrameMarker`` as a stroked rectangle
- ``TextMarker`` with approximate Pillow text rendering

The intended source of truth is:
- original scan image from ``SCANS_ROOT``
- marker JSON from the database

Rendered marked scan files are treated as derived artifacts that can be
regenerated on demand.
"""

import base64
import io
import json
import shutil
from pathlib import Path
from typing import Callable

from django.conf import settings
from PIL import Image, ImageColor, ImageDraw, ImageFont

from examc_app.models import PageMarkers, PagesGroupGradingSchemeCheckedBox
from examc_app.utils.amc_db_queries import get_question_max_points, select_copy_question_page
from examc_app.utils.amc_functions import get_amc_project_path, get_amc_marks_positions_data
from examc_app.utils.review_functions import get_question_points


DEFAULT_FONT_PATHS = (
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/TTF/DejaVuSans.ttf",
)


def resolve_scan_path(page_markers) -> Path:
    """Resolve the original scan file path for a ``PageMarkers`` row.

    The stored filename is currently expected to be either:
    - an absolute filesystem path, or
    - a path relative to ``settings.BASE_DIR``

    As a fallback, this function also reconstructs the path from exam metadata
    and the copy folder under ``SCANS_ROOT``.
    """
    raw_path = Path(page_markers.filename)
    if raw_path.is_absolute():
        return raw_path

    # Review currently stores scan filenames as paths relative to BASE_DIR.
    resolved = (Path(settings.BASE_DIR) / raw_path).resolve()
    if resolved.exists():
        return resolved

    project_subdir = (
        f"{page_markers.exam.year.code}/"
        f"{page_markers.exam.semester.code}/"
        f"{page_markers.exam.code}_{page_markers.exam.date.strftime('%Y%m%d')}"
    )
    fallback = (
        Path(settings.SCANS_ROOT)
        / project_subdir
        / str(page_markers.copie_no)
        / raw_path.name
    ).resolve()
    return fallback


def build_marked_scan_path(page_markers) -> Path:
    """Build the destination path for the derived marked scan image."""
    original_path = resolve_scan_path(page_markers)
    project_subdir = (
        f"{page_markers.exam.year.code}/"
        f"{page_markers.exam.semester.code}/"
        f"{page_markers.exam.code}_{page_markers.exam.date.strftime('%Y%m%d')}"
    )
    return (
        Path(settings.MARKED_SCANS_ROOT)
        / project_subdir
        / str(page_markers.copie_no)
        / f"marked_{original_path.stem}.png"
    )


def get_exam_marked_scans_dir(exam) -> Path:
    """Return the root marked_scans directory for one exam."""
    project_subdir = (
        f"{exam.year.code}/"
        f"{exam.semester.code}/"
        f"{exam.code}_{exam.date.strftime('%Y%m%d')}"
    )
    return Path(settings.MARKED_SCANS_ROOT) / project_subdir


def parse_rgba(color: str, opacity: float = 1.0) -> tuple[int, int, int, int]:
    """Convert a CSS-like color string and opacity into an RGBA tuple."""
    rgb = ImageColor.getrgb(color or "#000000")
    alpha = max(0, min(255, round(float(opacity) * 255)))
    return rgb[0], rgb[1], rgb[2], alpha


def image_from_data_url(data_url: str) -> Image.Image:
    """Decode a ``data:image/...;base64,...`` URL into a Pillow RGBA image."""
    _, payload = data_url.split(",", 1)
    return Image.open(io.BytesIO(base64.b64decode(payload))).convert("RGBA")


def load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """Load a server-side font with fallback to Pillow's default font."""
    for font_path in DEFAULT_FONT_PATHS:
        font_file = Path(font_path)
        if font_file.exists():
            return ImageFont.truetype(str(font_file), size)
    return ImageFont.load_default()


def scaled_rect(marker: dict, scale_x: float, scale_y: float) -> tuple[int, int, int, int]:
    """Scale marker geometry from markerjs canvas coordinates to image pixels."""
    left = round(float(marker.get("left", 0)) * scale_x)
    top = round(float(marker.get("top", 0)) * scale_y)
    width = max(1, round(float(marker.get("width", 0)) * scale_x))
    height = max(1, round(float(marker.get("height", 0)) * scale_y))
    return left, top, width, height


def render_freehand_marker(base_img: Image.Image, marker: dict, scale_x: float, scale_y: float) -> None:
    """Render a ``FreehandMarker`` from either embedded PNG data or point paths."""
    drawing = marker.get("drawingImgUrl")
    if drawing:
        overlay = image_from_data_url(drawing)
        left, top, width, height = scaled_rect(marker, scale_x, scale_y)
        overlay = overlay.resize((width, height), Image.LANCZOS)
        base_img.alpha_composite(overlay, (left, top))
        return

    points = marker.get("points") or []
    if not points:
        return

    stroke = parse_rgba(marker.get("strokeColor", "#000000"), marker.get("opacity", 1))
    avg_scale = max(0.1, (scale_x + scale_y) / 2)
    stroke_width = max(1, round(float(marker.get("strokeWidth", 1)) * avg_scale))

    scaled_points = [
        (float(point.get("x", 0)) * scale_x, float(point.get("y", 0)) * scale_y)
        for point in points
    ]

    overlay = Image.new("RGBA", base_img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    if len(scaled_points) == 1:
        x, y = scaled_points[0]
        radius = max(1, stroke_width // 2)
        draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=stroke)
    else:
        draw.line(scaled_points, fill=stroke, width=stroke_width, joint="curve")

    base_img.alpha_composite(overlay)


def render_highlight_marker(base_img: Image.Image, marker: dict, scale_x: float, scale_y: float) -> None:
    """Render a ``HighlightMarker`` as a filled rectangle overlay."""
    left, top, width, height = scaled_rect(marker, scale_x, scale_y)
    fill = parse_rgba(marker.get("fillColor", "#000000"), marker.get("opacity", 1))

    overlay = Image.new("RGBA", base_img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    draw.rectangle((left, top, left + width, top + height), fill=fill)
    base_img.alpha_composite(overlay)


def render_frame_marker(base_img: Image.Image, marker: dict, scale_x: float, scale_y: float) -> None:
    """Render a ``FrameMarker`` as a rectangle stroke."""
    left, top, width, height = scaled_rect(marker, scale_x, scale_y)
    stroke = parse_rgba(marker.get("strokeColor", "#000000"), marker.get("opacity", 1))
    avg_scale = max(0.1, (scale_x + scale_y) / 2)
    stroke_width = max(1, round(float(marker.get("strokeWidth", 1)) * avg_scale))

    overlay = Image.new("RGBA", base_img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    draw.rectangle((left, top, left + width, top + height), outline=stroke, width=stroke_width)
    base_img.alpha_composite(overlay)


def fit_single_line_font(draw: ImageDraw.ImageDraw, text: str, max_width: int, max_height: int):
    """Find the largest font size that fits one line inside the target box."""
    max_size = max(8, min(max_height, 80))
    for size in range(max_size, 7, -1):
        font = load_font(size)
        bbox = draw.textbbox((0, 0), text, font=font)
        width = bbox[2] - bbox[0]
        height = bbox[3] - bbox[1]
        if width <= max_width and height <= max_height:
            return font
    return load_font(8)


def grow_font(font, delta: int):
    """Return a slightly larger variant when using a truetype font."""
    if delta <= 0:
        return font
    font_path = getattr(font, "path", None)
    font_size = getattr(font, "size", None)
    if font_path and font_size:
        try:
            return ImageFont.truetype(font_path, font_size + delta)
        except OSError:
            return font
    return font


def wrap_text(draw: ImageDraw.ImageDraw, text: str, font, max_width: int) -> list[str]:
    """Wrap text greedily so each line fits within ``max_width``."""
    words = text.split()
    if not words:
        return [""]

    lines = []
    current = words[0]
    for word in words[1:]:
        candidate = f"{current} {word}"
        bbox = draw.textbbox((0, 0), candidate, font=font)
        if bbox[2] - bbox[0] <= max_width:
            current = candidate
        else:
            lines.append(current)
            current = word
    lines.append(current)
    return lines


def fit_wrapped_font(draw: ImageDraw.ImageDraw, text: str, max_width: int, max_height: int):
    """Find the largest wrapped font/layout that fits inside the target box."""
    max_size = max(8, min(max_height, 80))
    for size in range(max_size, 7, -1):
        font = load_font(size)
        lines = wrap_text(draw, text, font, max_width)
        spacing = max(2, round(size * 0.2))
        line_boxes = [draw.textbbox((0, 0), line, font=font) for line in lines]
        width = max((bbox[2] - bbox[0]) for bbox in line_boxes) if line_boxes else 0
        height = sum((bbox[3] - bbox[1]) for bbox in line_boxes) + spacing * max(0, len(lines) - 1)
        if width <= max_width and height <= max_height:
            return font, lines, spacing
    font = load_font(8)
    return font, wrap_text(draw, text, font, max_width), 2


def line_metrics(draw: ImageDraw.ImageDraw, line: str, font) -> tuple[int, int, int, int]:
    """Return Pillow text bbox metrics for one line."""
    return draw.textbbox((0, 0), line or " ", font=font)


def render_text_marker(base_img: Image.Image, marker: dict, scale_x: float, scale_y: float) -> None:
    """Render a ``TextMarker`` using approximate server-side text layout."""
    left, top, width, height = scaled_rect(marker, scale_x, scale_y)
    avg_scale = max(0.1, (scale_x + scale_y) / 2)
    padding = max(0, round(float(marker.get("padding", 0)) * avg_scale))
    text = str(marker.get("text", ""))
    fill = parse_rgba(marker.get("color", "#000000"), 1)
    has_explicit_line_breaks = "\n" in text
    use_multiline_layout = bool(marker.get("wrapText")) or has_explicit_line_breaks

    overlay = Image.new("RGBA", base_img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    inner_left = left + padding
    inner_top = top + padding
    inner_width = max(1, width - 2 * padding)
    inner_height = max(1, height - 2 * padding)
    text_box_inset_x = max(1, round(inner_width * 0.04))
    text_box_inset_y = max(1, round(inner_height * 0.03))
    text_left = inner_left + text_box_inset_x
    text_top = inner_top + text_box_inset_y
    text_width = max(1, inner_width - 2 * text_box_inset_x)
    text_height = max(1, inner_height - 2 * text_box_inset_y)

    if use_multiline_layout:
        if has_explicit_line_breaks:
            font = fit_single_line_font(
                draw,
                max(text.splitlines(), key=len, default=""),
                text_width,
                max(1, text_height),
            )
            font = grow_font(font, 1)
            lines = text.splitlines() or [""]
            spacing = 0
        else:
            font, lines, spacing = fit_wrapped_font(draw, text, text_width, text_height)
            font = grow_font(font, 1)
        line_boxes = [line_metrics(draw, line, font) for line in lines]
        line_heights = [bbox[3] - bbox[1] for bbox in line_boxes]
        total_height = sum(line_heights) + spacing * max(0, len(lines) - 1)
        current_y = text_top + max(0, (text_height - total_height) / 2)

        for line, bbox, line_height in zip(lines, line_boxes, line_heights):
            center_x = text_left + text_width / 2
            center_y = current_y + line_height / 2

            draw.text(
                (center_x, center_y),
                line,
                fill=fill,
                font=font,
                anchor="mm"  # middle-middle
            )

            current_y += line_height + spacing
    else:
        font = fit_single_line_font(draw, text, text_width, text_height)
        font = grow_font(font, 1)
        bbox = line_metrics(draw, text, font)
        rendered_text_width = bbox[2] - bbox[0]
        rendered_text_height = bbox[3] - bbox[1]
        text_x = text_left + max(0, (text_width - rendered_text_width) / 2) - bbox[0]
        text_y = text_top + max(0, (text_height - rendered_text_height) / 2) - bbox[1]
        draw.text((text_x, text_y), text, fill=fill, font=font)

    base_img.alpha_composite(overlay)


def render_marker(base_img: Image.Image, marker: dict, scale_x: float, scale_y: float) -> None:
    """Dispatch rendering based on markerjs3 ``typeName``."""
    marker_type = marker.get("typeName")
    renderer_map: dict[str, Callable[[Image.Image, dict, float, float], None]] = {
        "FreehandMarker": render_freehand_marker,
        "HighlightMarker": render_highlight_marker,
        "FrameMarker": render_frame_marker,
        "TextMarker": render_text_marker,
    }
    renderer = renderer_map.get(marker_type)
    if renderer:
        renderer(base_img, marker, scale_x, scale_y)


def get_active_grading_scheme(page_markers):
    """Return the grading scheme currently applied to this copy/pages_group, if any."""
    checked_box = (
        PagesGroupGradingSchemeCheckedBox.objects
        .filter(
            pages_group=page_markers.pages_group,
            copy_nr=str(page_markers.copie_no),
        )
        .select_related("gradingSchemeCheckBox__questionGradingScheme")
        .first()
    )
    if not checked_box or not checked_box.gradingSchemeCheckBox:
        return None
    return checked_box.gradingSchemeCheckBox.questionGradingScheme


def get_review_corr_box_index_for_page(page_markers):
    """Recompute the active corr-box index from grading DB state for this page."""
    grading_scheme = get_active_grading_scheme(page_markers)
    if not grading_scheme:
        return -1

    copy_nr = str(page_markers.copie_no)
    pages_group = grading_scheme.pages_group
    points = float(get_question_points(grading_scheme, copy_nr))

    if points > float(grading_scheme.max_points):
        points = float(grading_scheme.max_points)

    if points > 0:
        amc_data_path = get_amc_project_path(pages_group.exam, True) + "/data/"
        question_page = select_copy_question_page(amc_data_path, copy_nr, pages_group.group_name)

        # Only the page that owns the corr boxes should render the grading overlay.
        if str(page_markers.page_no) != str(question_page):
            return -1

        max_points = float(get_question_max_points(amc_data_path, pages_group.group_name, copy_nr))
        amc_corr_boxes = get_amc_marks_positions_data(pages_group.exam, copy_nr.lstrip("0"), float(question_page)) or []
        nb_boxes = len(amc_corr_boxes) / 4 - 1
        if nb_boxes <= 0 or max_points <= 0:
            return -1

        points_per_box = max_points / nb_boxes
        round_value = 1 / points_per_box
        points_rnd = round(points * round_value) / round_value
        return round(points_rnd / (max_points / nb_boxes))

    zero_checked = PagesGroupGradingSchemeCheckedBox.objects.filter(
        pages_group=pages_group,
        copy_nr=copy_nr,
        gradingSchemeCheckBox__name="ZERO",
    ).exists()
    return 0 if zero_checked else -1


def build_grading_corr_box_marker(page_markers, state: dict, image_width: int, image_height: int) -> dict | None:
    """Build a derived HighlightMarker from grading-scheme DB state for export."""
    if not getattr(page_markers.pages_group, "use_grading_scheme", False):
        return None

    corr_box_index = get_review_corr_box_index_for_page(page_markers)
    if corr_box_index < 0:
        return None

    page_no = float(str(page_markers.page_no))
    corr_boxes = get_amc_marks_positions_data(page_markers.exam, str(page_markers.copie_no).lstrip("0"), page_no) or []
    start = corr_box_index * 4
    selected_box = corr_boxes[start:start + 4]
    if len(selected_box) != 4:
        return None

    xs = [float(item["x"]) for item in selected_box]
    ys = [float(item["y"]) for item in selected_box]
    canvas_width = max(1.0, float(state.get("width", image_width)))
    canvas_height = max(1.0, float(state.get("height", image_height)))

    return {
        "typeName": "HighlightMarker",
        "left": min(xs) * canvas_width / image_width,
        "top": min(ys) * canvas_height / image_height,
        "width": (max(xs) - min(xs)) * canvas_width / image_width,
        "height": (max(ys) - min(ys)) * canvas_height / image_height,
        "fillColor": "black",
        "opacity": 1,
        "rotationAngle": 0,
        "strokeColor": "transparent",
        "strokeWidth": 0,
        "strokeDasharray": "",
    }


def render_marked_scan(page_markers, extra_markers: list[dict] | None = None) -> Path:
    """Render one marked scan image from a ``PageMarkers`` database row.

    Args:
        page_markers: ``PageMarkers`` instance containing persisted marker JSON.
        extra_markers: Optional additional marker definitions rendered on top of
            the persisted state. This is intended for future derived overlays,
            such as grading-driven correction box highlights.

    Returns:
        Filesystem path to the generated PNG file under ``MARKED_SCANS_ROOT``.
    """
    if not page_markers.markers:
        raise ValueError("Page markers do not contain marker state")

    original_path = resolve_scan_path(page_markers)
    if not original_path.exists():
        raise FileNotFoundError(f"Original scan not found: {original_path}")

    state = json.loads(page_markers.markers)
    base_img = Image.open(original_path).convert("RGBA")
    canvas_width = max(1, float(state.get("width", base_img.width)))
    canvas_height = max(1, float(state.get("height", base_img.height)))
    scale_x = base_img.width / canvas_width
    scale_y = base_img.height / canvas_height

    markers_to_render = state.get("markers", [])
    derived_grading_marker = None
    if getattr(page_markers.pages_group, "use_grading_scheme", False):
        markers_to_render = [marker for marker in markers_to_render if marker.get("typeName") != "HighlightMarker"]
        derived_grading_marker = build_grading_corr_box_marker(page_markers, state, base_img.width, base_img.height)

    for marker in markers_to_render:
        render_marker(base_img, marker, scale_x, scale_y)

    if extra_markers:
        for marker in extra_markers:
            render_marker(base_img, marker, scale_x, scale_y)

    if derived_grading_marker:
        render_marker(base_img, derived_grading_marker, scale_x, scale_y)

    output_path = build_marked_scan_path(page_markers)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    base_img.save(output_path, format="PNG")
    return output_path


def regenerate_marked_scans_for_exam(exam, progress_callback: Callable[[int, int], None] | None = None) -> int:
    """Regenerate all derived marked scan images for an exam from DB marker state."""
    marked_dir = get_exam_marked_scans_dir(exam)
    if marked_dir.exists():
        shutil.rmtree(marked_dir)

    page_markers_qs = PageMarkers.objects.filter(exam=exam).exclude(markers__isnull=True).exclude(markers="")
    total = page_markers_qs.count()

    for index, page_markers in enumerate(page_markers_qs.iterator(), start=1):
        if progress_callback:
            progress_callback(index, max(1, total))
        render_marked_scan(page_markers)

    return total


def regenerate_marked_scans_for_page_markers(page_markers_qs) -> int:
    """Regenerate marked scans for a specific queryset/iterable of PageMarkers rows."""
    if hasattr(page_markers_qs, "iterator") and hasattr(page_markers_qs, "count"):
        total = page_markers_qs.count()
        page_markers_iterable = page_markers_qs.iterator()
    else:
        page_markers_iterable = list(page_markers_qs)
        total = len(page_markers_iterable)

    for page_markers in page_markers_iterable:
        render_marked_scan(page_markers)
    return total
