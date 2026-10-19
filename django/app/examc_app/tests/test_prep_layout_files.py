import tempfile
from pathlib import Path

from django.test import SimpleTestCase
from pypdf import PdfWriter

from examc_app.utils.amc.amc_layout_functions import (
    LayoutExtractionError,
    get_pages_by_copy_from_xy,
    get_pdf_page_metrics,
    get_subject_copy_and_page_counts_from_xy,
    parse_amc_layout_source,
)


def xy_text(*copy_pages: tuple[int, int]) -> str:
    """The shape of the XY file AMC reads: a \\page line then positions, for each (copy, page) given."""
    lines = ["\\version{2023/02/06 v1.6.0}", "\\with{lang=FR}"]
    for copy, page in copy_pages:
        lines.append(f"\\page{{{copy}/{page}/60}}{{597.50787pt}}{{845.04684pt}}{{597.50787pt}}{{845.04684pt}}")
        lines += [f"\\tracepos{{{copy}/{page}:positionHG}}{{0sp}}{{52412938sp}}{{square}}",
                  f"\\tracepos{{{copy}/{page}:positionHG}}{{3263190sp}}{{0sp}}{{square}}"]
    return "\n".join(lines) + "\n"


def all_pages(copies: int, pages: int) -> list[tuple[int, int]]:
    return [(copy, page) for copy in range(1, copies + 1) for page in range(1, pages + 1)]


class XyFileTestCase(SimpleTestCase):
    def write(self, text: str) -> str:
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        path = Path(folder.name) / "exam-calage.xy"
        path.write_text(text, encoding="utf-8")
        return str(path)

    def test_copies_and_pages_are_counted(self):
        path = self.write(xy_text(*all_pages(copies=3, pages=2)))

        self.assertEqual(get_subject_copy_and_page_counts_from_xy(path),
                         {"total_copies": 3, "pages_per_copy": 2, "total_pages": 6})
        self.assertEqual(get_pages_by_copy_from_xy(path), {1: 2, 2: 2, 3: 2})

    def test_pages_are_parsed_with_their_size_in_inches(self):
        pages, flags = parse_amc_layout_source(self.write(xy_text((1, 1))))

        self.assertEqual(len(pages), 1)
        self.assertAlmostEqual(pages[0].dim_x_in, 597.50787 / 72.27, places=4)
        self.assertAlmostEqual(pages[0].dim_y_in, 845.04684 / 72.27, places=4)
        self.assertEqual(flags, {})

    def test_copies_of_different_lengths_give_the_longest(self):
        path = self.write(xy_text((1, 1), (1, 2), (2, 1), (2, 2), (2, 3)))

        self.assertEqual(get_pages_by_copy_from_xy(path), {1: 2, 2: 3})
        self.assertEqual(get_subject_copy_and_page_counts_from_xy(path)["pages_per_copy"], 3)

    def test_a_file_without_pages_is_refused(self):
        with self.assertRaisesMessage(LayoutExtractionError, "Could not determine copy/page counts"):
            get_subject_copy_and_page_counts_from_xy(self.write("\\version{2023/02/06}\n"))

    def test_a_missing_file_is_refused(self):
        with self.assertRaisesMessage(LayoutExtractionError, "AMC layout source not found"):
            get_subject_copy_and_page_counts_from_xy("/nowhere/exam-calage.xy")


class PdfMetricsTestCase(SimpleTestCase):
    def test_pages_and_size_at_300_dpi(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        path = Path(folder.name) / "subject.pdf"
        writer = PdfWriter()
        for _ in range(3):
            writer.add_blank_page(width=595, height=842)
        with open(path, "wb") as handle:
            writer.write(handle)

        metrics = get_pdf_page_metrics(str(path))

        self.assertEqual(metrics["page_count"], 3)
        self.assertAlmostEqual(metrics["width"], 595 / 72 * 300)
        self.assertAlmostEqual(metrics["height"], 842 / 72 * 300)
