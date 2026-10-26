import tempfile

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from examc_app.models import QuestionType
from examc_app.services.preparation.questions_import import (
    TEMPLATE_PATH,
    QuestionsImportError,
    parse_questions_tex,
)
from examc_app.tests.helpers.models import create_mock_exam, create_mock_user
from examc_app.utils.preparation_functions import (
    create_prep_question,
    create_prep_section,
)

AMC_QUESTION = r"""
\begin{Question}{SCQ-01-2025}%
The system of linear equations
\mathcenter{%
	\SYSTEM{%
	\EQUATION{}{+}{+}{+}{10}\CR}}
has a unique solution which satisfies
\begin{choices}{4}
	\correctchoice{$x^{}_4=4$}
	\wrongchoice{$x^{}_4=1$}
	\wrongchoice{$x^{}_4=2$}
\end{choices}
\end{Question}
"""


class ParseQuestionsTestCase(SimpleTestCase):
    def test_template_has_one_example_of_each_type(self):
        questions = parse_questions_tex(TEMPLATE_PATH.read_text(encoding="utf-8"))

        self.assertEqual([question.type_code for question in questions], ["SCQ", "MCQ", "TF", "OPEN"])
        self.assertEqual(questions[3].open_options["points"], "4")
        self.assertTrue(questions[2].tf_correct)

    def test_amc_question_keeps_its_latex_and_gets_its_type_from_the_correct_choices(self):
        question, = parse_questions_tex(AMC_QUESTION)

        self.assertEqual(question.type_code, "SCQ")
        self.assertEqual(question.title, "SCQ-01-2025")
        self.assertTrue(question.text.startswith("The system of linear equations\n\\mathcenter{%"))
        self.assertTrue(question.text.endswith("has a unique solution which satisfies"))
        self.assertEqual([(c.text, c.is_correct) for c in question.choices],
                         [("$x^{}_4=4$", True), ("$x^{}_4=1$", False), ("$x^{}_4=2$", False)])

    def test_several_correct_choices_make_an_mcq_for_an_amc_question(self):
        question, = parse_questions_tex(AMC_QUESTION.replace(r"\wrongchoice{$x^{}_4=1$}", r"\correctchoice{$x^{}_4=1$}"))

        self.assertEqual(question.type_code, "MCQ")

    def test_all_the_problems_are_reported(self):
        with self.assertRaises(QuestionsImportError) as context:
            parse_questions_tex(
                "\\begin{scq}{A}\nText\n\\begin{choices}\n\\correctchoice{1}\n\\correctchoice{2}\n\\end{choices}\n\\end{scq}\n"
                "\\begin{tf}{B}\nText\n\\end{tf}\n"
                "\\begin{open}{C}[points=3, increment=2]\nText\n\\end{open}\n"
            )

        errors = context.exception.errors
        self.assertEqual(len(errors), 3)
        self.assertIn("Line 1, scq \"A\"", errors[0])
        self.assertIn("exactly one", errors[0])
        self.assertIn("\\answer", errors[1])
        self.assertIn("increment", errors[2])

    def test_a_file_without_question_is_refused(self):
        with self.assertRaises(QuestionsImportError):
            parse_questions_tex("% nothing here\n")

    def test_commented_questions_are_ignored(self):
        self.assertEqual(len(parse_questions_tex("% " + AMC_QUESTION.strip().replace("\n", "\n% ") + "\n" + AMC_QUESTION)), 1)


class ImportQuestionsViewTestCase(TestCase):
    def setUp(self):
        projects_root = tempfile.TemporaryDirectory()
        self.addCleanup(projects_root.cleanup)
        override = override_settings(AMC_PROJECTS_ROOT=projects_root.name)
        override.enable()
        self.addCleanup(override.disable)

        self.types = {code: QuestionType.objects.create(code=code, name=code) for code in ("SCQ", "MCQ", "TF", "OPEN")}
        self.exam = create_mock_exam()
        self.section = create_prep_section(self.exam)
        create_prep_question(self.section, self.types["OPEN"], title="Existing")
        user = create_mock_user()
        user.is_superuser = True
        user.save()
        self.client.force_login(user)
        self.url = reverse("import_prep_questions", kwargs={"exam_pk": self.exam.pk, "section_id": self.section.pk})

    def upload(self, content: bytes):
        return self.client.post(self.url, {"questions_file": SimpleUploadedFile("questions.tex", content)})

    def test_template_download(self):
        response = self.client.get(reverse("download_prep_questions_template", kwargs={"exam_pk": self.exam.pk}))

        self.assertEqual(response.status_code, 200)
        self.assertIn("attachment", response["Content-Disposition"])
        self.assertIn(b"\\begin{tf}", response.content)

    def test_template_import_adds_the_questions_after_the_existing_ones(self):
        response = self.upload(TEMPLATE_PATH.read_bytes())

        self.assertEqual(response.status_code, 200)
        questions = list(self.section.prepQuestions.order_by("position"))
        self.assertEqual([q.title for q in questions], ["Existing", "Example single choice", "Example multiple choice",
                                                        "Example true or false", "Example open question"])
        self.assertEqual([q.position for q in questions], [1, 2, 3, 4, 5])

        scq, mcq, tf, open_question = questions[1:]
        self.assertEqual([a.is_correct for a in scq.prepAnswers.order_by("position")], [False, True, False, False])
        self.assertEqual(sum(a.is_correct for a in mcq.prepAnswers.all()), 2)
        self.assertEqual({a.title: a.is_correct for a in tf.prepAnswers.all()}, {"TRUE": True, "FALSE": False})
        self.assertEqual(float(open_question.max_points), 4.0)
        self.assertEqual(open_question.point_increment, "0.5")
        zone, = open_question.prepAnswers.filter(box_type__isnull=False)
        self.assertEqual((zone.box_type, zone.box_height_mm), ("grid", 60))
        # exam.tex is regenerated with the new questions
        self.assertTrue(self.section.prepQuestions.count() == 5)

    def test_nothing_is_created_when_the_file_has_a_problem(self):
        response = self.upload(b"\\begin{tf}{A}\nText\n\\end{tf}\n" + TEMPLATE_PATH.read_bytes())

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["HX-Retarget"], "#modalImportQuestionsBody")
        self.assertEqual(self.section.prepQuestions.count(), 1)

    def test_finalized_exam_is_refused(self):
        self.exam.is_finalized = True
        self.exam.save()

        response = self.upload(TEMPLATE_PATH.read_bytes())

        self.assertEqual(response.status_code, 403)
        self.assertEqual(self.section.prepQuestions.count(), 1)
