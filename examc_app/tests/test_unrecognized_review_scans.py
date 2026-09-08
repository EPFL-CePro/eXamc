from datetime import date
from pathlib import Path
from types import SimpleNamespace
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.contrib.auth.models import Group, User
from django.contrib.messages import get_messages
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from examc_app.models import AcademicYear, Exam, ExamUser, Semester, UnrecognizedReviewScan
from examc_app.utils.review_functions import (
    assign_unrecognized_review_scan_file,
    delete_unrecognized_review_scan_file,
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

    def test_delete_removes_file_and_keeps_resolution_record(self):
        scan = self.create_unrecognized_scan()
        copy_path = self.create_copy_file("0001", "01")

        deleted_scan = delete_unrecognized_review_scan_file(scan, resolved_by=self.user)

        deleted_scan.refresh_from_db()
        self.assertFalse((Path(self.scans_root.name) / scan.relative_path).exists())
        self.assertFalse((get_exam_scans_dir(self.exam) / "unrecognized").exists())
        self.assertTrue(copy_path.exists())
        self.assertTrue(deleted_scan.resolved)
        self.assertEqual(deleted_scan.resolved_by, self.user)
        self.assertIsNotNone(deleted_scan.deleted_at)
        self.assertEqual(deleted_scan.deleted_at, deleted_scan.resolved_at)
        self.assertEqual(deleted_scan.assigned_mode, "")
        self.assertEqual(deleted_scan.filename, scan.filename)
        self.assertEqual(_build_unrecognized_review_scan_context(self.exam), [])

    def test_delete_leaves_other_unrecognized_files(self):
        scan = self.create_unrecognized_scan()
        other_scan = self.create_unrecognized_scan("unrecognized_000002.jpg")

        delete_unrecognized_review_scan_file(scan, resolved_by=self.user)

        self.assertTrue((Path(self.scans_root.name) / other_scan.relative_path).exists())
        self.assertEqual([row["id"] for row in _build_unrecognized_review_scan_context(self.exam)], [other_scan.pk])

    def test_delete_can_resolve_an_already_missing_file(self):
        scan = self.create_unrecognized_scan()
        (Path(self.scans_root.name) / scan.relative_path).unlink()

        delete_unrecognized_review_scan_file(scan, resolved_by=self.user)

        scan.refresh_from_db()
        self.assertTrue(scan.resolved)
        self.assertIsNotNone(scan.deleted_at)

    def test_delete_rechecks_resolution_after_assignment(self):
        scan = self.create_unrecognized_scan()
        self.create_copy_file("0001", "01")
        assigned_scan = assign_unrecognized_review_scan_file(scan, "1", "2", "normal", self.user)

        with self.assertRaisesMessage(ValueError, "already been assigned or deleted"):
            delete_unrecognized_review_scan_file(scan, resolved_by=self.user)

        self.assertTrue((Path(self.scans_root.name) / assigned_scan.assigned_relative_path).exists())
        scan.refresh_from_db()
        self.assertIsNone(scan.deleted_at)

    def test_delete_rejects_paths_outside_exam_unrecognized_directory(self):
        scan = self.create_unrecognized_scan()
        copy_path = self.create_copy_file("0001", "01")
        outside_path = self.write_upload_file("unrelated.jpg")
        other_exam_path = Path(self.scans_root.name) / "other-exam" / "unrecognized" / "scan.jpg"
        other_exam_path.parent.mkdir(parents=True)
        other_exam_path.write_bytes(b"other exam scan")

        for path in (copy_path, outside_path, other_exam_path):
            with self.subTest(path=path):
                scan.relative_path = str(path)
                scan.save(update_fields=["relative_path"])
                with self.assertRaisesMessage(ValueError, "outside this exam's unrecognized directory"):
                    delete_unrecognized_review_scan_file(scan, resolved_by=self.user)
                self.assertTrue(path.exists())
                scan.refresh_from_db()
                self.assertFalse(scan.resolved)

    def test_delete_rejects_symlink(self):
        scan = self.create_unrecognized_scan()
        source_path = Path(self.scans_root.name) / scan.relative_path
        other_scan = self.create_unrecognized_scan("unrecognized_000002.jpg")
        target_path = Path(self.scans_root.name) / other_scan.relative_path
        source_path.unlink()
        source_path.symlink_to(target_path)

        with self.assertRaisesMessage(ValueError, "outside this exam's unrecognized directory"):
            delete_unrecognized_review_scan_file(scan, resolved_by=self.user)

        self.assertTrue(target_path.exists())

    def test_delete_file_error_preserves_unresolved_record(self):
        scan = self.create_unrecognized_scan()

        with patch.object(Path, "unlink", side_effect=PermissionError("Access denied")):
            with self.assertRaises(PermissionError):
                delete_unrecognized_review_scan_file(scan, resolved_by=self.user)

        scan.refresh_from_db()
        self.assertFalse(scan.resolved)
        self.assertIsNone(scan.deleted_at)
        self.assertIsNone(scan.resolved_by)
        self.assertTrue((Path(self.scans_root.name) / scan.relative_path).exists())

    def login_manager(self):
        group, _ = Group.objects.get_or_create(name="scan-managers")
        ExamUser.objects.create(exam=self.exam, user=self.user, group=group)
        self.client.force_login(self.user, backend="django.contrib.auth.backends.ModelBackend")

    @override_settings(EXAM_PERMISSION_GROUP_NAMES={"manage": ["scan-managers"]})
    def test_delete_view_starts_amc_after_last_scan_without_assignment_fields(self):
        self.login_manager()
        scan = self.create_unrecognized_scan()

        response = self.client.post(
            reverse("delete_unrecognized_review_scan", args=[self.exam.pk]), {"scan_id": scan.pk},
        )

        self.assertRedirects(response, reverse("upload_scans", args=[self.exam.pk]) + "?start_amc_import=1", fetch_redirect_response=False)
        scan.refresh_from_db()
        self.assertEqual(scan.resolved_by, self.user)
        self.assertIsNotNone(scan.deleted_at)

    @override_settings(EXAM_PERMISSION_GROUP_NAMES={"manage": ["scan-managers"]})
    def test_delete_view_waits_for_remaining_scans(self):
        self.login_manager()
        scan = self.create_unrecognized_scan()
        self.create_unrecognized_scan("unrecognized_000002.jpg")

        response = self.client.post(
            reverse("delete_unrecognized_review_scan", args=[self.exam.pk]), {"scan_id": scan.pk},
        )

        self.assertRedirects(response, reverse("upload_scans", args=[self.exam.pk]), fetch_redirect_response=False)

    @override_settings(EXAM_PERMISSION_GROUP_NAMES={"manage": ["scan-managers"]})
    def test_amc_import_is_unblocked_after_deletion(self):
        self.login_manager()
        scan = self.create_unrecognized_scan()
        import_url = reverse("import_scans_from_review", args=[self.exam.pk])

        with patch("examc_app.views.amc_views.amc_import_from_review_task.delay", return_value=SimpleNamespace(id="test-job")) as delay:
            self.assertEqual(self.client.post(import_url).status_code, 409)
            delay.assert_not_called()

            self.client.post(reverse("delete_unrecognized_review_scan", args=[self.exam.pk]), {"scan_id": scan.pk})
            self.assertEqual(self.client.post(import_url).status_code, 202)
            delay.assert_called_once_with(self.exam.pk)

    @override_settings(EXAM_PERMISSION_GROUP_NAMES={"manage": ["scan-managers"]})
    def test_assignment_still_starts_amc_after_last_scan(self):
        self.login_manager()
        scan = self.create_unrecognized_scan()
        self.create_copy_file("0001", "01")

        response = self.client.post(
            reverse("assign_unrecognized_review_scan", args=[self.exam.pk]),
            {"scan_id": scan.pk, "copy_no": "1", "page_no": "2", "assignment_mode": "normal"},
        )

        self.assertRedirects(response, reverse("upload_scans", args=[self.exam.pk]) + "?start_amc_import=1", fetch_redirect_response=False)
        scan.refresh_from_db()
        self.assertTrue(scan.resolved)
        self.assertIsNone(scan.deleted_at)

    @override_settings(EXAM_PERMISSION_GROUP_NAMES={"manage": ["scan-managers"]})
    def test_delete_view_rejects_other_exam_and_resolved_scan(self):
        self.login_manager()
        scan = self.create_unrecognized_scan()
        other_exam = Exam.objects.create(
            code="OTHER", name="Other exam", semester=self.semester, year=self.year, date=date(2026, 1, 21),
        )
        scan.exam = other_exam
        scan.save(update_fields=["exam"])
        url = reverse("delete_unrecognized_review_scan", args=[self.exam.pk])
        self.assertEqual(self.client.post(url, {"scan_id": scan.pk}).status_code, 404)

        scan.exam = self.exam
        scan.resolved = True
        scan.save(update_fields=["exam", "resolved"])
        self.assertEqual(self.client.post(url, {"scan_id": scan.pk}).status_code, 404)
        self.assertTrue((Path(self.scans_root.name) / scan.relative_path).exists())

    @override_settings(EXAM_PERMISSION_GROUP_NAMES={"manage": ["scan-managers"]})
    def test_delete_view_requires_manage_post_and_csrf(self):
        scan = self.create_unrecognized_scan()
        url = reverse("delete_unrecognized_review_scan", args=[self.exam.pk])
        self.client.force_login(self.user, backend="django.contrib.auth.backends.ModelBackend")
        self.assertEqual(self.client.post(url, {"scan_id": scan.pk}).status_code, 403)

        self.login_manager()
        self.assertEqual(self.client.get(url).status_code, 405)
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.user, backend="django.contrib.auth.backends.ModelBackend")
        self.assertEqual(csrf_client.post(url, {"scan_id": scan.pk}).status_code, 403)
        self.assertTrue((Path(self.scans_root.name) / scan.relative_path).exists())
        scan.refresh_from_db()
        self.assertFalse(scan.resolved)

    @override_settings(EXAM_PERMISSION_GROUP_NAMES={"manage": ["scan-managers"]})
    def test_delete_view_reports_file_error_without_starting_amc(self):
        self.login_manager()
        scan = self.create_unrecognized_scan()

        with patch.object(Path, "unlink", side_effect=PermissionError("Access denied")):
            with self.assertLogs("examc_app.views.review_views", level="ERROR"):
                response = self.client.post(
                    reverse("delete_unrecognized_review_scan", args=[self.exam.pk]), {"scan_id": scan.pk},
                )

        self.assertRedirects(response, reverse("upload_scans", args=[self.exam.pk]), fetch_redirect_response=False)
        self.assertIn("Unable to delete this scan file", str(list(get_messages(response.wsgi_request))[0]))
        scan.refresh_from_db()
        self.assertFalse(scan.resolved)

    @override_settings(EXAM_PERMISSION_GROUP_NAMES={"manage": ["scan-managers"]})
    def test_refreshed_table_contains_separate_delete_form(self):
        self.login_manager()
        self.create_unrecognized_scan()

        response = self.client.get(reverse("unrecognized_review_scans_table", args=[self.exam.pk]))

        self.assertContains(response, reverse("delete_unrecognized_review_scan", args=[self.exam.pk]))
        self.assertContains(response, "js-delete-unrecognized-scan")
        self.assertContains(response, "Delete scan")

    @override_settings(EXAM_PERMISSION_GROUP_NAMES={"manage": ["scan-managers"]})
    def test_bulk_delete_removes_only_selected_scans_and_keeps_audit(self):
        self.login_manager()
        scans = [self.create_unrecognized_scan(f"scan_{index}.jpg") for index in range(3)]
        response = self.client.post(
            reverse("delete_unrecognized_review_scans", args=[self.exam.pk]),
            {"scan_ids": [scans[0].pk, scans[2].pk]},
        )

        self.assertRedirects(response, reverse("upload_scans", args=[self.exam.pk]), fetch_redirect_response=False)
        for index, scan in enumerate(scans):
            scan.refresh_from_db()
            self.assertEqual(scan.resolved, index != 1)
            self.assertEqual((Path(self.scans_root.name) / scan.relative_path).exists(), index == 1)
            if index != 1:
                self.assertEqual(scan.resolved_by, self.user)
                self.assertIsNotNone(scan.deleted_at)
        self.assertIn("Deleted 2 selected scan(s).", [str(message) for message in get_messages(response.wsgi_request)])

    @override_settings(EXAM_PERMISSION_GROUP_NAMES={"manage": ["scan-managers"]})
    def test_bulk_delete_last_scans_starts_amc_and_deduplicates_selection(self):
        self.login_manager()
        first = self.create_unrecognized_scan()
        second = self.create_unrecognized_scan("second.jpg")

        response = self.client.post(
            reverse("delete_unrecognized_review_scans", args=[self.exam.pk]),
            {"scan_ids": [first.pk, second.pk, first.pk]},
        )

        self.assertRedirects(response, reverse("upload_scans", args=[self.exam.pk]) + "?start_amc_import=1", fetch_redirect_response=False)
        self.assertFalse(UnrecognizedReviewScan.objects.filter(exam=self.exam, resolved=False).exists())
        self.assertIn("Deleted 2 selected scan(s).", [str(message) for message in get_messages(response.wsgi_request)])

    @override_settings(EXAM_PERMISSION_GROUP_NAMES={"manage": ["scan-managers"]})
    def test_bulk_delete_rejects_entire_invalid_selection(self):
        self.login_manager()
        scan = self.create_unrecognized_scan()
        resolved_scan = self.create_unrecognized_scan("resolved.jpg")
        resolved_scan.resolved = True
        resolved_scan.save(update_fields=["resolved"])
        foreign_scan = self.create_unrecognized_scan("foreign.jpg")
        foreign_scan.exam = Exam.objects.create(
            code="OTHER", name="Other exam", semester=self.semester, year=self.year, date=date(2026, 1, 21),
        )
        foreign_scan.save(update_fields=["exam"])

        selections = [[], [scan.pk, "invalid"], [scan.pk, 999999], [scan.pk, resolved_scan.pk], [scan.pk, foreign_scan.pk]]
        for selection in selections:
            with self.subTest(selection=selection):
                response = self.client.post(
                    reverse("delete_unrecognized_review_scans", args=[self.exam.pk]), {"scan_ids": selection},
                )
                self.assertRedirects(response, reverse("upload_scans", args=[self.exam.pk]), fetch_redirect_response=False)
                self.assertTrue(any(message.level_tag == "error" for message in get_messages(response.wsgi_request)))
                scan.refresh_from_db()
                self.assertFalse(scan.resolved)
                for protected_scan in (scan, resolved_scan, foreign_scan):
                    self.assertTrue((Path(self.scans_root.name) / protected_scan.relative_path).exists())

    @override_settings(EXAM_PERMISSION_GROUP_NAMES={"manage": ["scan-managers"]})
    def test_bulk_delete_file_failure_keeps_successful_deletions_and_continues(self):
        self.login_manager()
        scans = [self.create_unrecognized_scan(f"scan_{index}.jpg") for index in range(3)]
        failed_path = Path(self.scans_root.name) / scans[1].relative_path
        original_unlink = Path.unlink

        def unlink(path, *args, **kwargs):
            if path == failed_path:
                raise PermissionError("Access denied")
            return original_unlink(path, *args, **kwargs)

        with patch.object(Path, "unlink", new=unlink):
            with self.assertLogs("examc_app.views.review_views", level="ERROR"):
                response = self.client.post(
                    reverse("delete_unrecognized_review_scans", args=[self.exam.pk]),
                    {"scan_ids": [scan.pk for scan in scans]},
                )

        self.assertRedirects(response, reverse("upload_scans", args=[self.exam.pk]), fetch_redirect_response=False)
        for index, scan in enumerate(scans):
            scan.refresh_from_db()
            self.assertEqual(scan.resolved, index != 1)
            self.assertEqual(scan.deleted_at is None, index == 1)
            self.assertEqual((Path(self.scans_root.name) / scan.relative_path).exists(), index == 1)
        messages = [str(message) for message in get_messages(response.wsgi_request)]
        self.assertIn("Deleted 2 selected scan(s).", messages)
        self.assertIn("Unable to delete scan_1.jpg. Please try again.", messages)

    @override_settings(EXAM_PERMISSION_GROUP_NAMES={"manage": ["scan-managers"]})
    def test_bulk_delete_requires_manage_post_and_csrf(self):
        scan = self.create_unrecognized_scan()
        url = reverse("delete_unrecognized_review_scans", args=[self.exam.pk])
        self.client.force_login(self.user, backend="django.contrib.auth.backends.ModelBackend")
        self.assertEqual(self.client.post(url, {"scan_ids": [scan.pk]}).status_code, 403)

        self.login_manager()
        self.assertEqual(self.client.get(url).status_code, 405)
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.user, backend="django.contrib.auth.backends.ModelBackend")
        self.assertEqual(csrf_client.post(url, {"scan_ids": [scan.pk]}).status_code, 403)
        self.assertTrue((Path(self.scans_root.name) / scan.relative_path).exists())
        scan.refresh_from_db()
        self.assertFalse(scan.resolved)

    @override_settings(EXAM_PERMISSION_GROUP_NAMES={"manage": ["scan-managers"]})
    def test_refreshed_table_contains_bulk_form_and_associated_checkboxes(self):
        self.login_manager()
        for index in range(2):
            self.create_unrecognized_scan(f"scan_{index}.jpg")

        response = self.client.get(reverse("unrecognized_review_scans_table", args=[self.exam.pk]))

        self.assertContains(response, reverse("delete_unrecognized_review_scans", args=[self.exam.pk]))
        self.assertContains(response, 'form="deleteSelectedUnrecognizedScansForm"', count=2)
        self.assertContains(response, 'name="scan_ids"', count=2)
        self.assertContains(response, "js-select-all-unrecognized-scans", count=1)
