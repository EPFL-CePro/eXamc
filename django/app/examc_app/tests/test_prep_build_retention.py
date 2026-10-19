from django.test import TestCase

from examc_app.models import ExamBuild
from examc_app.tests.helpers.models import create_mock_exam
from examc_app.utils.amc.amc_build_retention import cleanup_exam_builds, get_exam_build_retention_decisions


class BuildRetentionTestCase(TestCase):
    def setUp(self):
        self.exam = create_mock_exam()

    def build(self, version, status="ready", locked=False):
        return ExamBuild.objects.create(exam=self.exam, version=version, status=status, is_locked=locked,
                                        source_hash=f"hash-{version}", latex_engine="pdflatex")

    def test_locked_and_recent_builds_are_kept_the_others_are_candidates(self):
        locked = self.build(1, locked=True)
        old = [self.build(version) for version in range(2, 6)]
        decisions = {decision.build_id: decision for decision in get_exam_build_retention_decisions(self.exam)}

        self.assertTrue(decisions[locked.pk].keep)
        self.assertIn("locked", decisions[locked.pk].reasons)
        # The 3 last ready builds are kept, the oldest unlocked one is not
        self.assertFalse(decisions[old[0].pk].keep)
        self.assertTrue(all(decisions[build.pk].keep for build in old[1:]))

    def test_dry_run_deletes_nothing(self):
        for version in range(1, 6):
            self.build(version)

        result = cleanup_exam_builds(self.exam, dry_run=True, delete_files=False)

        self.assertEqual(len(result["to_delete"]), 2)
        self.assertEqual(ExamBuild.objects.filter(exam=self.exam).count(), 5)
