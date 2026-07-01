from datetime import date
from pathlib import Path
from types import SimpleNamespace
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase, override_settings

from examc_app.models import AcademicYear, Exam, Semester, UnrecognizedReviewScan
from examc_app.utils.review_functions import (
    assign_unrecognized_review_scan_file,
    get_exam_scans_dir,
    get_scan_relative_path,
    split_scans_by_copy,
)
from examc_app.views.review_views import _build_unrecognized_review_scan_context


class DummyProgressRecorder:
    def set_progress(self, *args, **kwargs):
        return None


def qr_payload(payload):
    return SimpleNamespace(type="QRCODE", data=payload.encode("utf-8"))


class UnrecognizedReviewScansTestCase(TestCase):
    def setUp(self):
        self.scans_root = TemporaryDirectory()
        self.extract_root = TemporaryDirectory()
        self.addCleanup(self.scans_root.cleanup)
        self.addCleanup(self.extract_root.cleanup)

        self.settings_override = override_settings(SCANS_ROOT=self.scans_root.name)
        self.settings_override.enable()
        self.addCleanup(self.settings_override.disable)

        self.year = AcademicYear.objects.create(code="2025-2026", name="2025-2026")
        self.semester = Semester.objects.create(code=1, name="Autumn")
        self.exam = Exam.objects.create(
            code="TEST-EXAM",
            name="Test Exam",
            semester=self.semester,
            year=self.year,
            date=date(2026, 1, 20),
        )
        self.user = User.objects.create_user(username="manager")

    def write_upload_file(self, filename):
        path = Path(self.extract_root.name) / filename
        path.write_bytes(b"scan")
        return path

    def create_unrecognized_scan(self, filename="unrecognized_000001.jpg"):
        unrecognized_dir = get_exam_scans_dir(self.exam) / "unrecognized"
        unrecognized_dir.mkdir(parents=True, exist_ok=True)
        scan_path = unrecognized_dir / filename
        scan_path.write_bytes(b"scan")
        return UnrecognizedReviewScan.objects.create(
            exam=self.exam,
            relative_path=get_scan_relative_path(scan_path),
            filename=filename,
            original_filename="upload.jpg",
            upload_order=1,
        )

    def create_copy_file(self, copy_no, page_token):
        copy_dir = get_exam_scans_dir(self.exam) / copy_no
        copy_dir.mkdir(parents=True, exist_ok=True)
        scan_path = copy_dir / f"copy_{copy_no}_{page_token}.jpg"
        scan_path.write_bytes(b"scan")
        return scan_path

    def run_split_with_decode_results(self, decode_results):
        for filename in ("page_001.jpg", "page_002.jpg", "page_003.jpg"):
            self.write_upload_file(filename)
        with (
            patch("examc_app.utils.review_functions.imghdr.what", return_value="jpeg"),
            patch("examc_app.utils.review_functions.cv2.imread", return_value=object()),
            patch("examc_app.utils.review_functions.pyzbar.decode", side_effect=decode_results),
        ):
            return split_scans_by_copy(
                self.exam,
                self.extract_root.name,
                DummyProgressRecorder(),
                process_count=3,
                process_number=0,
            )

    def test_missing_qr_creates_unrecognized_scan_with_previous_and_next_context(self):
        self.run_split_with_decode_results([
            [qr_payload("eXamcQRC,2,012")],
            [],
            [qr_payload("eXamcQRC,2,013")],
        ])

        scan = UnrecognizedReviewScan.objects.get(exam=self.exam)
        self.assertEqual(scan.previous_copy_no, "0002")
        self.assertEqual(scan.previous_page_no, "012")
        self.assertTrue(scan.previous_relative_path.endswith("/0002/copy_0002_012.jpg"))
        self.assertEqual(scan.next_copy_no, "0002")
        self.assertEqual(scan.next_page_no, "013")
        self.assertTrue(scan.next_relative_path.endswith("/0002/copy_0002_013.jpg"))
        self.assertTrue(scan.relative_path.endswith("/unrecognized/unrecognized_000002.jpg"))

    def test_invalid_qr_is_treated_as_unrecognized_scan(self):
        self.run_split_with_decode_results([
            [qr_payload("OtherQRCode,2,012")],
            [qr_payload("eXamcQRC,2,012")],
            [qr_payload("eXamcQRC,2,013")],
        ])

        scan = UnrecognizedReviewScan.objects.get(exam=self.exam)
        self.assertEqual(scan.previous_copy_no, "")
        self.assertEqual(scan.next_copy_no, "0002")
        self.assertEqual(scan.next_page_no, "012")

    def test_unrecognized_scan_context_uses_canonical_protected_url(self):
        scan = self.create_unrecognized_scan()

        rows = _build_unrecognized_review_scan_context(self.exam)

        self.assertEqual(rows[0]["id"], scan.pk)
        self.assertTrue(rows[0]["scan_url"].startswith("/protected/?token="))

    def test_normal_assignment_moves_scan_to_missing_page(self):
        self.create_copy_file("0052", "012")
        self.create_copy_file("0052", "014")
        scan = self.create_unrecognized_scan()

        assigned_scan = assign_unrecognized_review_scan_file(
            scan,
            copy_no="52",
            page_no="13",
            assignment_mode=UnrecognizedReviewScan.ASSIGNMENT_MODE_NORMAL,
            resolved_by=self.user,
        )

        destination = get_exam_scans_dir(self.exam) / "0052" / "copy_0052_013.jpg"
        self.assertTrue(destination.exists())
        self.assertFalse((get_exam_scans_dir(self.exam) / "unrecognized").exists())
        assigned_scan.refresh_from_db()
        self.assertTrue(assigned_scan.resolved)
        self.assertEqual(assigned_scan.resolved_by, self.user)
        self.assertEqual(assigned_scan.assigned_copy_no, "0052")
        self.assertEqual(assigned_scan.assigned_page_no, "013")
        self.assertEqual(assigned_scan.assigned_mode, UnrecognizedReviewScan.ASSIGNMENT_MODE_NORMAL)
        self.assertTrue(assigned_scan.assigned_relative_path.endswith("/0052/copy_0052_013.jpg"))

    def test_extra_assignment_uses_next_available_suffix(self):
        self.create_copy_file("0075", "016")
        self.create_copy_file("0075", "016.1")
        scan = self.create_unrecognized_scan()

        assigned_scan = assign_unrecognized_review_scan_file(
            scan,
            copy_no="75",
            page_no="16",
            assignment_mode=UnrecognizedReviewScan.ASSIGNMENT_MODE_EXTRA,
            resolved_by=self.user,
        )

        destination = get_exam_scans_dir(self.exam) / "0075" / "copy_0075_016.2.jpg"
        self.assertTrue(destination.exists())
        assigned_scan.refresh_from_db()
        self.assertTrue(assigned_scan.resolved)
        self.assertEqual(assigned_scan.assigned_copy_no, "0075")
        self.assertEqual(assigned_scan.assigned_page_no, "016")
        self.assertEqual(assigned_scan.assigned_mode, UnrecognizedReviewScan.ASSIGNMENT_MODE_EXTRA)
        self.assertTrue(assigned_scan.assigned_relative_path.endswith("/0075/copy_0075_016.2.jpg"))

    def test_normal_assignment_does_not_overwrite_existing_page(self):
        self.create_copy_file("0052", "013")
        scan = self.create_unrecognized_scan()

        with self.assertRaisesMessage(ValueError, "already exists"):
            assign_unrecognized_review_scan_file(
                scan,
                copy_no="52",
                page_no="13",
                assignment_mode=UnrecognizedReviewScan.ASSIGNMENT_MODE_NORMAL,
                resolved_by=self.user,
            )

        scan.refresh_from_db()
        self.assertFalse(scan.resolved)
