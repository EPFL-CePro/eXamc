import json

from examc_app.models import PrepQuestion, PrepQuestionAnswer, PrepSection
from examc_app.tests.helpers.models import create_mock_exam
from examc_app.tests.helpers.prep import PrepViewsTestCase


def save_feedback(response):
    """What the page is told about the save (the HX-Trigger header of the panels)."""
    return json.loads(response["HX-Trigger"])["prepSaveFeedback"]["saved"]


class SectionViewsTestCase(PrepViewsTestCase):
    def data(self, section, **changes):
        fields = {"title": section.title, "section_text": "Text", "position": section.position, **changes}
        return {f"section-{section.pk}-{name}": value for name, value in fields.items()}

    def panel_url(self, section):
        return self.url("prep_section_panel", section_id=section.pk)

    def test_panel_shows_the_section(self):
        response = self.client.get(self.panel_url(self.section))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'value="Algebra"')
        self.assertNotIn("HX-Trigger", response)

    def test_saving_the_panel_updates_the_section_and_its_latex(self):
        response = self.client.post(self.panel_url(self.section), self.data(self.section, title="Calculus"))

        self.assertEqual(response.status_code, 200)
        self.assertTrue(save_feedback(response))
        self.section.refresh_from_db()
        self.assertEqual(self.section.title, "Calculus")
        self.assertIn("Calculus", (self.project_path() / "section_header_1.tex").read_text())

    def test_invalid_panel_is_not_saved(self):
        response = self.client.post(self.panel_url(self.section), self.data(self.section, title=""))

        self.assertEqual(response.status_code, 200)
        self.assertFalse(save_feedback(response))
        self.section.refresh_from_db()
        self.assertEqual(self.section.title, "Algebra")

    def test_locked_exam_cannot_be_saved(self):
        self.lock()

        response = self.client.post(self.panel_url(self.section), self.data(self.section, title="Calculus"))

        self.assertEqual(response.status_code, 403)
        self.section.refresh_from_db()
        self.assertEqual(self.section.title, "Algebra")

    def test_section_of_another_exam_is_not_found(self):
        other = PrepSection.objects.create(exam=create_mock_exam(code="OTHER-101"), title="Other", position=1)

        self.assertEqual(self.client.get(self.panel_url(other)).status_code, 404)

    def test_add_creates_a_section_at_the_end(self):
        PrepSection.objects.create(exam=self.exam, title="Geometry", position=2)

        response = self.client.post(self.url("add_prep_section"))

        self.assertEqual(response.status_code, 200)
        added = PrepSection.objects.filter(exam=self.exam).order_by("-position").first()
        self.assertEqual((added.title, added.position), ("New section", 3))

    def test_add_to_a_locked_exam_is_refused(self):
        self.lock()

        self.assertEqual(self.client.post(self.url("add_prep_section")).status_code, 403)
        self.assertEqual(PrepSection.objects.filter(exam=self.exam).count(), 1)

    def test_delete_renumbers_the_other_sections(self):
        middle = PrepSection.objects.create(exam=self.exam, title="Geometry", position=2)
        PrepSection.objects.create(exam=self.exam, title="Analysis", position=3)

        response = self.client.post(self.url("delete_prep_section", section_id=middle.pk))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.positions(PrepSection.objects.filter(exam=self.exam)),
                         [("Algebra", 1), ("Analysis", 2)])

    def test_delete_from_a_locked_exam_is_refused(self):
        self.lock()

        response = self.client.post(self.url("delete_prep_section", section_id=self.section.pk))

        self.assertEqual(response.status_code, 403)
        self.assertTrue(PrepSection.objects.filter(pk=self.section.pk).exists())

    def test_delete_section_of_another_exam_is_not_found(self):
        other = PrepSection.objects.create(exam=create_mock_exam(code="OTHER-101"), title="Other", position=1)

        response = self.client.post(self.url("delete_prep_section", section_id=other.pk))

        self.assertEqual(response.status_code, 404)
        self.assertTrue(PrepSection.objects.filter(pk=other.pk).exists())


class QuestionViewsTestCase(PrepViewsTestCase):
    def data(self, question, **changes):
        fields = {"title": question.title, "question_type": question.question_type_id, "question_text": "Text",
                  "position": question.position, "max_points": "0", "point_increment": "1", **changes}
        return {f"question-{question.pk}-{name}": value for name, value in fields.items()}

    def panel_url(self, question):
        return self.url("prep_question_panel", question_id=question.pk)

    def test_saving_the_panel_updates_the_question(self):
        question = self.question("SCQ")

        response = self.client.post(self.panel_url(question), self.data(question, title="Renamed"))

        self.assertEqual(response.status_code, 200)
        self.assertTrue(save_feedback(response))
        question.refresh_from_db()
        self.assertEqual(question.title, "Renamed")

    def test_points_that_are_not_a_multiple_of_half_a_point_are_not_saved(self):
        question = self.question("OPEN", answers=0)

        response = self.client.post(self.panel_url(question), self.data(question, max_points="1.3"))

        self.assertFalse(save_feedback(response))
        question.refresh_from_db()
        self.assertEqual(question.max_points, 0)

    def test_open_question_gets_one_points_answer_per_step(self):
        question = self.question("OPEN", answers=0)

        response = self.client.post(self.panel_url(question), self.data(question, max_points="2"))

        self.assertTrue(save_feedback(response))
        self.assertEqual([answer.title for answer in question.prepAnswers.order_by("position", "pk")],
                         ["0 points", "1 point", "2 points"])

    def test_max_points_that_the_increment_does_not_divide_are_refused(self):
        question = self.question("OPEN", answers=0)

        response = self.client.post(self.panel_url(question), self.data(question, max_points="2.5"))

        self.assertEqual(response.status_code, 200)
        self.assertFalse(save_feedback(response))
        self.assertContains(response, "must be a multiple of the point increment (1)")
        question.refresh_from_db()
        self.assertEqual(question.max_points, 0)
        self.assertEqual(question.prepAnswers.count(), 0)

    def test_half_points_are_accepted_with_an_increment_of_half_a_point(self):
        question = self.question("OPEN", answers=0)

        response = self.client.post(self.panel_url(question),
                                    self.data(question, max_points="2.5", point_increment="0.5"))

        self.assertTrue(save_feedback(response))
        self.assertEqual(question.prepAnswers.count(), 6)

    def test_an_open_question_needs_an_increment_and_maximum_points(self):
        question = self.question("OPEN", answers=0)

        no_increment = self.client.post(self.panel_url(question), self.data(question, max_points="2", point_increment=""))
        no_maximum = self.client.post(self.panel_url(question), self.data(question, max_points=""))

        self.assertFalse(save_feedback(no_increment))
        self.assertContains(no_increment, "Choose the point increment.")
        self.assertFalse(save_feedback(no_maximum))
        self.assertContains(no_maximum, "Give the maximum points.")
        self.assertEqual(question.prepAnswers.count(), 0)

    def test_the_points_of_a_choice_question_are_not_checked_against_the_increment(self):
        question = self.question("SCQ")

        response = self.client.post(self.panel_url(question), self.data(question, max_points="2.5"))

        self.assertTrue(save_feedback(response))

    def test_locked_exam_cannot_be_saved(self):
        question = self.question("SCQ")
        self.lock()

        response = self.client.post(self.panel_url(question), self.data(question, title="Renamed"))

        self.assertEqual(response.status_code, 403)
        question.refresh_from_db()
        self.assertEqual(question.title, "Q1")

    def test_add_form_is_shown(self):
        response = self.client.get(self.url("add_prep_question", section_id=self.section.pk))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "nb_answers")

    def add(self, **fields):
        return self.client.post(self.url("add_prep_question", section_id=self.section.pk),
                                {"section_pk": self.section.pk, **fields})

    def test_add_a_choice_question_with_its_answers(self):
        self.question("SCQ")

        response = self.add(question_type="MCQ", title="Which ones?", nb_answers=3)

        self.assertEqual(response.status_code, 200)
        added = PrepQuestion.objects.get(title="Which ones?")
        self.assertEqual((added.question_type.code, added.position), ("MCQ", 2))
        self.assertEqual([answer.title for answer in added.prepAnswers.order_by("position")],
                         ["Answer 1", "Answer 2", "Answer 3"])
        self.assertTrue((self.project_path() / "section_1.tex").exists())

    def test_add_a_true_false_question_with_its_two_answers(self):
        self.add(question_type="TF")

        added = PrepQuestion.objects.get(prep_section=self.section)
        self.assertEqual(added.title, "New question")
        self.assertEqual(added.prepAnswers.count(), 2)

    def test_add_an_open_question_without_answers(self):
        self.add(question_type="OPEN")

        self.assertEqual(PrepQuestion.objects.get(prep_section=self.section).prepAnswers.count(), 0)

    def test_add_with_too_few_answers_shows_the_form_again(self):
        response = self.add(question_type="SCQ", nb_answers=1)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "nb_answers")
        self.assertFalse(PrepQuestion.objects.exists())

    def test_add_to_a_locked_exam_is_refused(self):
        self.lock()

        self.assertEqual(self.add(question_type="SCQ", nb_answers=2).status_code, 403)
        self.assertFalse(PrepQuestion.objects.exists())

    def test_add_to_a_section_of_another_exam_is_not_found(self):
        other = PrepSection.objects.create(exam=create_mock_exam(code="OTHER-101"), title="Other", position=1)

        response = self.client.post(self.url("add_prep_question", section_id=other.pk),
                                    {"section_pk": other.pk, "question_type": "SCQ", "nb_answers": 2})

        self.assertEqual(response.status_code, 404)

    def test_delete_renumbers_the_other_questions(self):
        first, second, third = (self.question("SCQ", position) for position in (1, 2, 3))

        response = self.client.post(self.url("delete_prep_question", question_id=second.pk))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.positions(PrepQuestion.objects.filter(prep_section=self.section)),
                         [("Q1", 1), ("Q3", 2)])
        self.assertFalse(PrepQuestionAnswer.objects.filter(prep_question=second).exists())

    def test_delete_from_a_locked_exam_is_refused(self):
        question = self.question("SCQ")
        self.lock()

        self.assertEqual(self.client.post(self.url("delete_prep_question", question_id=question.pk)).status_code, 403)
        self.assertTrue(PrepQuestion.objects.filter(pk=question.pk).exists())

    def test_delete_question_of_another_exam_is_not_found(self):
        other_exam = create_mock_exam(code="OTHER-101")
        other_section = PrepSection.objects.create(exam=other_exam, title="Other", position=1)
        question = self.question("SCQ", section=other_section)

        response = self.client.post(self.url("delete_prep_question", question_id=question.pk))

        self.assertEqual(response.status_code, 404)
        self.assertTrue(PrepQuestion.objects.filter(pk=question.pk).exists())


class ReorderViewsTestCase(PrepViewsTestCase):
    def setUp(self):
        super().setUp()
        self.questions = [self.question("SCQ", position) for position in (1, 2, 3)]
        self.answers = list(self.questions[0].prepAnswers.order_by("position"))

    def questions_url(self):
        return self.url("reorder_prep_questions", section_id=self.section.pk)

    def answers_url(self):
        return self.url("reorder_prep_answers", question_id=self.questions[0].pk)

    def test_questions_are_reordered(self):
        first, second, third = self.questions

        response = self.post_json(self.questions_url(), {"questions": [
            {"id": first.pk, "position": 3}, {"id": second.pk, "position": 1}, {"id": third.pk, "position": 2}]})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.positions(PrepQuestion.objects.filter(prep_section=self.section)),
                         [("Q2", 1), ("Q3", 2), ("Q1", 3)])
        self.assertTrue((self.project_path() / "section_1.tex").exists())

    def test_unknown_and_malformed_items_are_ignored(self):
        first = self.questions[0]
        other_exam = create_mock_exam(code="OTHER-101")
        foreign = self.question("SCQ", section=PrepSection.objects.create(exam=other_exam, title="O", position=1))

        response = self.post_json(self.questions_url(), {"questions": [
            {"id": foreign.pk, "position": 9}, {"id": "x", "position": 1}, {"position": 2}, {"id": first.pk}]})

        self.assertEqual(response.status_code, 200)
        foreign.refresh_from_db()
        self.assertEqual(foreign.position, 1)
        self.assertEqual(self.positions(PrepQuestion.objects.filter(prep_section=self.section)),
                         [("Q1", 1), ("Q2", 2), ("Q3", 3)])

    def test_questions_need_a_post_with_json(self):
        self.assertEqual(self.client.get(self.questions_url()).status_code, 400)
        response = self.client.post(self.questions_url(), data="not json", content_type="application/json")

        self.assertEqual(response.status_code, 400)

    def test_locked_exam_cannot_be_reordered(self):
        first, second, _ = self.questions
        self.lock()

        response = self.post_json(self.questions_url(), {"questions": [{"id": first.pk, "position": 2},
                                                                      {"id": second.pk, "position": 1}]})

        self.assertEqual(response.status_code, 403)
        first.refresh_from_db()
        self.assertEqual(first.position, 1)

    def test_section_of_another_exam_is_not_found(self):
        other = PrepSection.objects.create(exam=create_mock_exam(code="OTHER-101"), title="Other", position=1)

        response = self.post_json(self.url("reorder_prep_questions", section_id=other.pk), {"questions": []})

        self.assertEqual(response.status_code, 404)

    def test_answers_are_reordered(self):
        first, second = self.answers

        response = self.post_json(self.answers_url(), {"answers": [
            {"id": first.pk, "position": 2}, {"id": second.pk, "position": 1}]})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.positions(PrepQuestionAnswer.objects.filter(prep_question=self.questions[0])),
                         [("A2", 1), ("A1", 2)])

    def test_answers_need_a_post_with_json(self):
        self.assertEqual(self.client.get(self.answers_url()).status_code, 400)
        response = self.client.post(self.answers_url(), data="{", content_type="application/json")

        self.assertEqual(response.status_code, 400)

    def test_locked_exam_cannot_have_its_answers_reordered(self):
        first, second = self.answers
        self.lock()

        response = self.post_json(self.answers_url(), {"answers": [{"id": first.pk, "position": 2},
                                                                   {"id": second.pk, "position": 1}]})

        self.assertEqual(response.status_code, 403)
        first.refresh_from_db()
        self.assertEqual(first.position, 1)

    def test_question_of_another_exam_is_not_found(self):
        other = PrepSection.objects.create(exam=create_mock_exam(code="OTHER-101"), title="Other", position=1)
        foreign = self.question("SCQ", section=other)

        response = self.post_json(self.url("reorder_prep_answers", question_id=foreign.pk), {"answers": []})

        self.assertEqual(response.status_code, 404)


class AnswerViewsTestCase(PrepViewsTestCase):
    def setUp(self):
        super().setUp()
        self.question_ = self.question("SCQ", answers=3)

    def data(self, answer, **changes):
        fields = {"title": answer.title, "answer_text": "Text", "position": answer.position, **changes}
        return {f"answer-{answer.pk}-{name}": value for name, value in fields.items()}

    def test_saving_the_panel_updates_the_answer(self):
        answer = self.question_.prepAnswers.get(position=2)

        response = self.client.post(self.url("prep_answer_panel", answer_id=answer.pk),
                                    self.data(answer, title="Renamed", is_correct="on"))

        self.assertEqual(response.status_code, 200)
        self.assertTrue(save_feedback(response))
        answer.refresh_from_db()
        self.assertEqual((answer.title, answer.is_correct), ("Renamed", True))

    def test_invalid_answer_is_not_saved(self):
        answer = self.question_.prepAnswers.get(position=2)

        response = self.client.post(self.url("prep_answer_panel", answer_id=answer.pk), self.data(answer, title=""))

        self.assertFalse(save_feedback(response))
        answer.refresh_from_db()
        self.assertEqual(answer.title, "A2")

    def test_locked_exam_cannot_be_saved(self):
        answer = self.question_.prepAnswers.get(position=2)
        self.lock()

        response = self.client.post(self.url("prep_answer_panel", answer_id=answer.pk), self.data(answer, title="X"))

        self.assertEqual(response.status_code, 403)

    def test_add_creates_the_next_answer(self):
        response = self.client.post(self.url("add_prep_answer", question_id=self.question_.pk))

        self.assertEqual(response.status_code, 200)
        added = self.question_.prepAnswers.order_by("-position").first()
        self.assertEqual((added.title, added.position, added.box_type), ("New answer", 4, None))

    def test_add_to_an_open_question_gives_a_grid_box(self):
        open_question = self.question("OPEN", position=2, answers=0)

        self.client.post(self.url("add_prep_answer", question_id=open_question.pk))

        self.assertEqual(open_question.prepAnswers.get().box_type, "grid")

    def test_add_to_a_locked_exam_is_refused(self):
        self.lock()

        self.assertEqual(self.client.post(self.url("add_prep_answer", question_id=self.question_.pk)).status_code, 403)
        self.assertEqual(self.question_.prepAnswers.count(), 3)

    def test_delete_renumbers_the_other_answers(self):
        middle = self.question_.prepAnswers.get(position=2)

        response = self.client.post(self.url("delete_prep_answer", answer_id=middle.pk))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.positions(self.question_.prepAnswers), [("A1", 1), ("A3", 2)])

    def test_delete_from_a_locked_exam_is_refused(self):
        answer = self.question_.prepAnswers.get(position=2)
        self.lock()

        self.assertEqual(self.client.post(self.url("delete_prep_answer", answer_id=answer.pk)).status_code, 403)
        self.assertTrue(PrepQuestionAnswer.objects.filter(pk=answer.pk).exists())
