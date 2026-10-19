import tempfile
from datetime import date
from pathlib import Path

from django.test import TestCase, override_settings
from django.urls import reverse

from examc_app.forms.preparation import PrepScoringFormulaForm
from examc_app.models import PrepQuestion, PrepQuestionAnswer, PrepScoringFormula, PrepSection, QuestionType
from examc_app.tests.helpers.models import create_mock_exam, create_mock_user
from examc_app.templatetags.prep_tags import prep_scoring_info
from examc_app.utils.preparation_functions import get_applied_scorings, scoring_info_text
from examc_app.utils.preparation_latex_functions import (
    question_scoring_tex, scoring_formulas_by_type, update_exam_latex, write_global_scoring_file,
)


class ScoringTestCase(TestCase):
    def setUp(self):
        self.exam = create_mock_exam()
        self.exam.date = date(2026, 1, 15)
        self.exam.save()
        self.types = {code: QuestionType.objects.create(code=code, name=code) for code in ("SCQ", "MCQ", "TF", "OPEN")}
        self.section = PrepSection.objects.create(exam=self.exam, title="Algebra", position=1)

    def question(self, code, position=1, section=None):
        question = PrepQuestion.objects.create(prep_section=section or self.section, question_type=self.types[code],
                                               title=f"Q{position}", question_text="Question?", position=position)
        for answer_position, correct in enumerate((True, False), start=1):
            PrepQuestionAnswer.objects.create(prep_question=question, title=f"A{answer_position}",
                                              answer_text=f"Answer {answer_position}", is_correct=correct,
                                              position=answer_position)
        return question

    def formula(self, formula, code=None, **level):
        return PrepScoringFormula.objects.create(exam=self.exam, formula=formula,
                                                 question_type=self.types[code] if code else None, **level)


class QuestionScoringTestCase(ScoringTestCase):
    def test_most_specific_level_wins(self):
        scq = self.question("SCQ")
        tf = self.question("TF", 2)
        mcq = self.question("MCQ", 3)
        self.formula("b=3", prep_question=scq)
        section_formulas = {"SCQ": "b=2", "TF": "b=1,m=-1"}

        self.assertEqual(question_scoring_tex(scq, section_formulas, exam_tf_formula=True), "\\bareme{b=3}")
        self.assertEqual(question_scoring_tex(tf, section_formulas, exam_tf_formula=True), "\\bareme{b=1,m=-1}")
        # No section formula: the exam default of AMC (\baremeDefautM)
        self.assertEqual(question_scoring_tex(mcq, section_formulas, exam_tf_formula=True), "")

    def test_exam_true_false_formula(self):
        tf = self.question("TF")

        self.assertEqual(question_scoring_tex(tf, {}, exam_tf_formula=True), "\\bareme{\\baremeDefautTF}")
        self.assertEqual(question_scoring_tex(tf, {}, exam_tf_formula=False), "")

    def test_answer_formula_is_not_the_question_one(self):
        scq = self.question("SCQ")
        self.formula("b=5", prep_answer=scq.prepAnswers.first())

        self.assertEqual(question_scoring_tex(scq), "")

    def test_formulas_by_type(self):
        self.formula("b=1", "SCQ")
        self.formula("b=2", "TF")
        self.formula("b=9", "MCQ", prep_section=self.section)

        self.assertEqual(scoring_formulas_by_type(self.exam.prepExamScoringFormulas.filter(prep_section__isnull=True)),
                         {"SCQ": "b=1", "TF": "b=2"})

    def test_global_file(self):
        with tempfile.TemporaryDirectory() as project:
            path = write_global_scoring_file({"SCQ": "b=1,m=0", "MCQ": "b=2", "TF": "b=1,m=-1"}, project)

            self.assertEqual(path.read_text(), (
                "% Auto-generated scoring formulas of the exam - do not edit\n"
                "\\baremeDefautS{b=1,m=0}\n"
                "\\baremeDefautM{b=2}\n"
                "\\newcommand{\\baremeDefautTF}{b=1,m=-1}\n"
            ))
            self.assertEqual(write_global_scoring_file({}, project).read_text(),
                             "% Auto-generated scoring formulas of the exam - do not edit\n")


class ScoringLatexTestCase(ScoringTestCase):
    def test_formulas_written_at_their_level(self):
        scq = self.question("SCQ")
        self.question("TF", 2)
        mcq = self.question("MCQ", 3)
        other_section = PrepSection.objects.create(exam=self.exam, title="Geometry", position=2)
        self.question("SCQ", 1, section=other_section)
        self.formula("b=1,m=0", "SCQ")
        self.formula("b=1,m=-1", "TF")
        self.formula("b=2,m=-1", "SCQ", prep_section=self.section)
        self.formula("b=4", prep_question=mcq)
        self.formula("b=1", prep_answer=scq.prepAnswers.get(position=2))

        with tempfile.TemporaryDirectory() as root, override_settings(AMC_PROJECTS_ROOT=root):
            update_exam_latex(self.exam)
            project = next(Path(root).rglob("exam.tex")).parent
            section_1 = (project / "section_1.tex").read_text()
            section_2 = (project / "section_2.tex").read_text()

            self.assertIn("\\baremeDefautS{b=1,m=0}", (project / "global_scoring.tex").read_text())
            self.assertIn("\\begin{question}{SECTION-1-SCQ-1}\\bareme{b=2,m=-1}", section_1)
            self.assertIn("\\begin{question}{SECTION-1-TF-2}\\bareme{\\baremeDefautTF}", section_1)
            self.assertIn("\\begin{questionmult}{SECTION-1-MCQ-3}\\bareme{b=4}", section_1)
            self.assertIn("\\bareme{b=1}", section_1)
            # Other section: the exam default
            self.assertIn("\\begin{question}{SECTION-2-SCQ-1}\n", section_2)


class ScoringFormulaFormTestCase(ScoringTestCase):
    def form(self, data, scope="exam"):
        return PrepScoringFormulaForm(data, scope=scope, exam_pk=self.exam.pk)

    def test_question_type_choices(self):
        self.formula("b=1", "SCQ")

        choices = [label for _, label in self.form(None).fields["question_type"].choices]

        # SCQ already has an exam formula, OPEN is scored by its corrector boxes
        self.assertEqual(choices, ["Choose a question type", "MCQ - MCQ", "TF - TF"])

    def test_formula_characters(self):
        form = self.form({"formula": "formula=NBC%2", "question_type": self.types["MCQ"].pk})

        self.assertFalse(form.is_valid())
        self.assertEqual(form.errors["formula"], ["These characters are not allowed: %"])
        self.assertTrue(self.form({"formula": " formula=\"max(0,NBC-NMC)\" ",
                                   "question_type": self.types["MCQ"].pk}).is_valid())


class AppliedScoringsTestCase(ScoringTestCase):
    def applied(self, question):
        return get_applied_scorings(self.exam)["questions"][question.pk]

    def test_most_specific_level_of_a_question(self):
        scq = self.question("SCQ")
        self.formula("b=1", "SCQ")
        self.assertEqual(self.applied(scq), {"level": "Global", "formula": "b=1"})

        self.formula("b=2", "SCQ", prep_section=self.section)
        self.assertEqual(self.applied(scq), {"level": "Section", "formula": "b=2"})

        self.formula("b=3", prep_question=scq)
        self.assertEqual(self.applied(scq), {"level": "Question", "formula": "b=3"})

    def test_formulas_are_by_question_type(self):
        scq = self.question("SCQ")
        tf = self.question("TF", 2)
        self.formula("b=1,m=-1", "TF", prep_section=self.section)
        self.formula("b=5", "MCQ")

        self.assertEqual(self.applied(tf), {"level": "Section", "formula": "b=1,m=-1"})
        # Neither the section nor the exam has a formula for the simple questions: the default of AMC
        self.assertEqual(self.applied(scq), {"level": "", "formula": ""})

    def test_section_formula_is_not_applied_to_another_section(self):
        other = PrepSection.objects.create(exam=self.exam, title="Geometry", position=2)
        scq = self.question("SCQ", 1, other)
        self.formula("b=2", "SCQ", prep_section=self.section)

        self.assertEqual(self.applied(scq), {"level": "", "formula": ""})

    def test_answer_has_its_own_formula_or_the_one_of_its_question(self):
        scq = self.question("SCQ")
        first, second = scq.prepAnswers.order_by("position")
        self.formula("b=3", prep_question=scq)
        self.formula("b=9", prep_answer=first)

        answers = get_applied_scorings(self.exam)["answers"]

        self.assertEqual(answers[first.pk], {"level": "Answer", "formula": "b=9"})
        self.assertEqual(answers[second.pk], {"level": "Question", "formula": "b=3"})

    def test_open_question_and_its_answers_have_no_formula(self):
        open_question = self.question("OPEN")
        self.formula("b=1", "SCQ")

        scorings = get_applied_scorings(self.exam)

        self.assertIsNone(scorings["questions"][open_question.pk])
        self.assertTrue(all(scorings["answers"][answer.pk] is None for answer in open_question.prepAnswers.all()))

    def test_the_formulas_of_another_exam_are_not_read(self):
        scq = self.question("SCQ")
        other_exam = create_mock_exam(code="OTHER-101")
        PrepScoringFormula.objects.create(exam=other_exam, formula="b=7", question_type=self.types["SCQ"])

        self.assertEqual(self.applied(scq), {"level": "", "formula": ""})

    def test_texts(self):
        self.assertEqual(scoring_info_text({"level": "Section", "formula": "b=2,m=-1"}), 'Section : "b=2,m=-1"')
        self.assertEqual(scoring_info_text({"level": "", "formula": ""}), "AMC default")
        self.assertEqual(scoring_info_text(None), "")

    def test_tag_renders_the_text_with_what_the_page_needs_to_update_it(self):
        scq = self.question("SCQ")
        self.formula("b=2", "SCQ", prep_section=self.section)

        html = prep_scoring_info(self.exam, "question", scq.pk)

        self.assertIn(f'data-prep-scoring-kind="question" data-prep-scoring-id="{scq.pk}"', html)
        self.assertIn('Section : &quot;b=2&quot;', html)

    def test_formulas_are_read_once_for_all_the_tags_of_a_page(self):
        scq = self.question("SCQ")
        answers = list(scq.prepAnswers.all())
        prep_scoring_info(self.exam, "question", scq.pk)

        with self.assertNumQueries(0):
            for answer in answers:
                prep_scoring_info(self.exam, "answer", answer.pk)


class ScoringInfoPagesTestCase(ScoringTestCase):
    def setUp(self):
        super().setUp()
        user = create_mock_user()
        user.is_superuser = True
        user.save()
        self.client.force_login(user)

    def test_question_and_answer_panels_show_the_applied_formula(self):
        scq = self.question("SCQ")
        answer = scq.prepAnswers.order_by("position").first()
        self.formula("b=3,m=-1", "SCQ")
        self.formula("b=9", prep_answer=answer)

        question_html = self.client.get(
            reverse("prep_question_panel", kwargs={"exam_pk": self.exam.pk, "question_id": scq.pk})).content.decode()
        answer_html = self.client.get(
            reverse("prep_answer_panel", kwargs={"exam_pk": self.exam.pk, "answer_id": answer.pk})).content.decode()
        other_answer_html = self.client.get(
            reverse("prep_answer_panel", kwargs={"exam_pk": self.exam.pk,
                                                 "answer_id": scq.prepAnswers.order_by("position").last().pk})
        ).content.decode()

        self.assertIn(f'data-prep-scoring-kind="question" data-prep-scoring-id="{scq.pk}">Global : &quot;b=3,m=-1&quot;<',
                      question_html)
        self.assertIn('>Answer : &quot;b=9&quot;<', answer_html)
        self.assertIn('>Global : &quot;b=3,m=-1&quot;<', other_answer_html)

    def test_infos_of_the_page_for_the_refresh(self):
        scq = self.question("SCQ")
        open_question = self.question("OPEN", 2)
        self.formula("b=2", prep_question=scq)

        response = self.client.get(reverse("scoring_infos", kwargs={"exam_pk": self.exam.pk}))

        infos = response.json()
        self.assertEqual(infos["questions"][str(scq.pk)], 'Question : "b=2"')
        self.assertEqual(infos["questions"][str(open_question.pk)], "")
        self.assertEqual({infos["answers"][str(answer.pk)] for answer in scq.prepAnswers.all()}, {'Question : "b=2"'})
