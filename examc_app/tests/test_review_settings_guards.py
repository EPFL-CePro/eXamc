from datetime import date
from decimal import Decimal

from django.test import TestCase

from examc_app.models import (
    AcademicYear,
    Exam,
    PageMarkers,
    PagesGroup,
    PagesGroupGradingSchemeCheckedBox,
    QuestionGradingScheme,
    QuestionGradingSchemeCheckBox,
    Semester,
)
from examc_app.utils.review_settings_guards import (
    decimal_value_changed,
    grading_scheme_checkbox_has_usage,
    grading_scheme_has_usage,
    pages_group_has_review_activity,
    pages_group_name_available,
    pages_group_settings_changed,
)


class ReviewSettingsGuardsTestCase(TestCase):
    def setUp(self):
        self.year = AcademicYear.objects.create(code="2025-2026", name="2025-2026")
        self.semester = Semester.objects.create(code=1, name="Autumn")
        self.exam = Exam.objects.create(
            code="TEST-EXAM",
            name="Test Exam",
            semester=self.semester,
            year=self.year,
            date=date(2026, 1, 20),
        )
        self.pages_group = PagesGroup.objects.create(
            exam=self.exam,
            group_name="Q1",
            nb_pages=2,
            use_grading_scheme=True,
        )

    def test_pages_group_has_no_activity_initially(self):
        self.assertFalse(pages_group_has_review_activity(self.pages_group))

    def test_pages_group_activity_ignores_corr_box_marker(self):
        PageMarkers.objects.create(
            copie_no="CORR-BOX",
            page_no="0",
            pages_group=self.pages_group,
            filename="dummy.jpg",
            markers='{"markers":[{"typeName":"HighlightMarker"}]}',
            exam=self.exam,
            correctorBoxMarked=True,
        )
        self.assertFalse(pages_group_has_review_activity(self.pages_group))

    def test_pages_group_activity_detects_real_marker(self):
        PageMarkers.objects.create(
            copie_no="0001",
            page_no="02",
            pages_group=self.pages_group,
            filename="dummy.jpg",
            markers='{"markers":[{"typeName":"FrameMarker"}]}',
            exam=self.exam,
            correctorBoxMarked=True,
        )
        self.assertTrue(pages_group_has_review_activity(self.pages_group))

    def test_grading_scheme_usage_detection(self):
        grading_scheme = QuestionGradingScheme.objects.create(
            pages_group=self.pages_group,
            name="Scheme A",
            max_points=Decimal("5.0"),
        )
        checkbox = QuestionGradingSchemeCheckBox.objects.create(
            questionGradingScheme=grading_scheme,
            name="C1",
            points=Decimal("2.0"),
            position=0,
        )
        self.assertFalse(grading_scheme_has_usage(grading_scheme))
        self.assertFalse(grading_scheme_checkbox_has_usage(checkbox))

        PagesGroupGradingSchemeCheckedBox.objects.create(
            pages_group=self.pages_group,
            gradingSchemeCheckBox=checkbox,
            copy_nr="0001",
            adjustment=0,
        )
        self.assertTrue(grading_scheme_has_usage(grading_scheme))
        self.assertTrue(grading_scheme_checkbox_has_usage(checkbox))
        self.assertTrue(pages_group_has_review_activity(self.pages_group))

    def test_pages_group_settings_changed_detection(self):
        updated = PagesGroup(
            pk=self.pages_group.pk,
            exam=self.exam,
            group_name=self.pages_group.group_name,
            nb_pages=self.pages_group.nb_pages + 1,
            use_grading_scheme=self.pages_group.use_grading_scheme,
        )
        self.assertTrue(pages_group_settings_changed(self.pages_group, updated))

    def test_pages_group_name_availability(self):
        self.assertFalse(pages_group_name_available(self.exam, "Q1"))
        self.assertTrue(
            pages_group_name_available(
                self.exam,
                "Q1",
                exclude_pages_group_id=self.pages_group.pk,
            )
        )
        self.assertTrue(pages_group_name_available(self.exam, "Q2"))

    def test_decimal_value_changed(self):
        self.assertFalse(decimal_value_changed(Decimal("4.00"), "4"))
        self.assertTrue(decimal_value_changed(Decimal("4.00"), "4.25"))
        self.assertTrue(decimal_value_changed(Decimal("4.00"), "not-a-number"))
