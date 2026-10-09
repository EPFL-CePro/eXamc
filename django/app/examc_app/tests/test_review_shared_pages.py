import json
import sqlite3
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse
from PIL import Image

from examc_app.models import AcademicYear, Exam, PageMarkers, PagesGroup, Semester
from examc_app.signing import make_token_for
from examc_app.utils.amc_db_queries import select_marks_positions
from examc_app.utils.marker_rendering import build_marked_scan_path, render_marked_scan
from examc_app.utils.review_functions import get_exam_scans_dir


def write_amc_data(data_dir):
    """An AMC project whose page 2 of copy 1 holds the boxes of OPEN-Q1 (question 1) and OPEN-Q2 (question 2)."""
    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / "scoring.sqlite").write_bytes(b"")
    with sqlite3.connect(data_dir / "layout.sqlite") as layout:
        layout.execute("CREATE TABLE layout_question (question INTEGER, name TEXT)")
        layout.executemany("INSERT INTO layout_question VALUES (?, ?)", [(1, "OPEN-Q1"), (2, "OPEN-Q2")])
    with sqlite3.connect(data_dir / "capture.sqlite") as capture:
        capture.execute("CREATE TABLE capture_zone (zoneid INTEGER, student INTEGER, page INTEGER, copy INTEGER, "
                        "type INTEGER, id_a INTEGER, id_b INTEGER, total INTEGER, black INTEGER, manual REAL)")
        capture.execute("CREATE TABLE capture_position (zoneid INTEGER, corner INTEGER, x REAL, y REAL, type INTEGER)")
        for zoneid, question, answer in ((1, 1, 1), (2, 1, 2), (3, 2, 1), (4, 2, 2), (5, 2, 3)):
            capture.execute("INSERT INTO capture_zone VALUES (?, 1, 2, 0, 4, ?, ?, 100, 0, -1)", (zoneid, question, answer))
            for corner in range(1, 5):
                capture.execute("INSERT INTO capture_position VALUES (?, ?, ?, ?, 1)",
                                (zoneid, corner, 10.0 * zoneid + corner, 20.0 * corner))


def marker_state(left, top):
    return json.dumps({"width": 100, "height": 100, "markers": [{
        "typeName": "HighlightMarker", "left": left, "top": top, "width": 10, "height": 10,
        "fillColor": "black", "opacity": 1, "rotationAngle": 0, "strokeColor": "transparent", "strokeWidth": 0,
    }]})


class CorrectorBoxesOfTheQuestionTestCase(TestCase):
    def test_boxes_filtered_by_question(self):
        with TemporaryDirectory() as data_dir:
            write_amc_data(Path(data_dir))
            path = f"{data_dir}/"

            self.assertEqual(len(select_marks_positions(path, 1, 2, None)), 20)
            self.assertEqual({p["zoneid"] for p in select_marks_positions(path, 1, 2, None, "OPEN-Q1")}, {1, 2})
            self.assertEqual({p["zoneid"] for p in select_marks_positions(path, 1, 2, None, "OPEN-Q2")}, {3, 4, 5})


class SharedPageTestCase(TestCase):
    """Copy 0001, page 02 holds the questions of the groups OPEN-Q1 and OPEN-Q2."""

    def setUp(self):
        media = TemporaryDirectory()
        self.addCleanup(media.cleanup)
        # The signed URLs name the root of a file by its last folder ("scans", "marked_scans")
        self.scans_root = Path(media.name) / "scans"
        self.marked_root = Path(media.name) / "marked_scans"
        settings_override = override_settings(SCANS_ROOT=self.scans_root, MARKED_SCANS_ROOT=self.marked_root)
        settings_override.enable()
        self.addCleanup(settings_override.disable)

        self.exam = Exam.objects.create(code="CS-119(d)", name="Exam", date=date(2026, 10, 30),
                                        semester=Semester.objects.create(code=1, name="Autumn"),
                                        year=AcademicYear.objects.create(code="2026-2027", name="2026-2027"))
        self.q1 = PagesGroup.objects.create(exam=self.exam, group_name="OPEN-Q1", nb_pages=1)
        self.q2 = PagesGroup.objects.create(exam=self.exam, group_name="OPEN-Q2", nb_pages=1)
        copy_dir = get_exam_scans_dir(self.exam) / "0001"
        copy_dir.mkdir(parents=True)
        self.scan_path = copy_dir / "copy_0001_02.jpg"
        Image.new("RGB", (100, 100), "white").save(self.scan_path, format="JPEG")

        self.user = User.objects.create_superuser(username="admin", password="x")
        self.client.force_login(self.user, backend="django.contrib.auth.backends.ModelBackend")

    def page_markers(self, group, left, top):
        return PageMarkers.objects.create(exam=self.exam, pages_group=group, copie_no="0001", page_no="02",
                                          filename=str(self.scan_path), markers=marker_state(left, top))

    @staticmethod
    def is_dark(image, x, y):
        return sum(image.getpixel((x, y))[:3]) < 200

    def test_markers_saved_in_the_reviewed_group(self):
        self.page_markers(self.q1, 10, 10)
        scan_url = make_token_for(
            self.scan_path.relative_to(self.scans_root).as_posix(), str(self.scans_root))

        response = self.client.post(reverse("save_markers", args=[self.exam.pk]), {
            "reviewGroup_pk": self.q2.pk, "curr_row": 0, "copy_no": "0001", "page_no": "02",
            "markers": marker_state(70, 70), "filename": scan_url.split("?token=")[1],
        })

        self.assertEqual(response.status_code, 200)
        q1, q2 = (PageMarkers.objects.get(pages_group=group) for group in (self.q1, self.q2))
        self.assertEqual(json.loads(q1.markers)["markers"][0]["left"], 10)
        self.assertEqual(json.loads(q2.markers)["markers"][0]["left"], 70)
        self.assertTrue(q2.correctorBoxMarked)

    @patch("examc_app.views.review_views.get_amc_marks_positions_data", return_value=[])
    @patch("examc_app.views.review_views.get_amc_project_path", return_value="/nowhere")
    def test_markers_of_the_group_and_others_shown_read_only(self, _project_path, positions):
        self.page_markers(self.q1, 10, 10)
        self.page_markers(self.q2, 70, 70)

        data = json.loads(self.client.post(reverse("get_markers_and_comments", args=[self.exam.pk]), {
            "copy_no": "0001", "page_no": "02", "group_id": self.q2.pk,
        }).content)

        # Own markers only, to edit
        self.assertEqual(json.loads(data["markers"])["markers"][0]["left"], 70)
        # The corrector boxes of the question of the group only
        self.assertEqual(positions.call_args.args[3], "OPEN-Q2")
        # The page is shown with the markers of OPEN-Q1 burnt in
        self.assertIn("copy_0001_02", data["copyPageUrl"])
        background = next((self.marked_root / "_review_backgrounds").rglob("copy_0001_02.jpg"))
        with Image.open(background) as image:
            self.assertTrue(self.is_dark(image, 15, 15))
            self.assertFalse(self.is_dark(image, 75, 75))

    def test_marked_scan_holds_the_markers_of_every_group(self):
        q1 = self.page_markers(self.q1, 10, 10)
        q2 = self.page_markers(self.q2, 70, 70)

        for page_markers in (q1, q2):
            render_marked_scan(page_markers)

            with Image.open(build_marked_scan_path(page_markers)) as image:
                self.assertTrue(self.is_dark(image, 15, 15))
                self.assertTrue(self.is_dark(image, 75, 75))
