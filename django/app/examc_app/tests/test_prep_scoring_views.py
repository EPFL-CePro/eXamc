from examc_app.models import PrepScoringFormula
from examc_app.tests.helpers.models import create_mock_exam
from examc_app.tests.helpers.prep import PrepViewsTestCase


class ScoringFormulasModalTestCase(PrepViewsTestCase):
    def formula(self, formula, code=None, **level):
        return PrepScoringFormula.objects.create(exam=self.exam, formula=formula,
                                                 question_type=self.types[code] if code else None, **level)

    def modal(self, **level):
        return self.client.get(self.url("scoring_formulas_modal"), level)

    def post(self, rows, **level):
        """Saves the rows (formula, question type code or None) of the formset of a level."""
        data = {"form-TOTAL_FORMS": len(rows), "form-INITIAL_FORMS": 0, "form-MIN_NUM_FORMS": 0,
                "form-MAX_NUM_FORMS": 1000, "prep_section": "", "prep_question": "", "prep_answer": "", **level}
        for index, (formula, code) in enumerate(rows):
            data[f"form-{index}-formula"] = formula
            data[f"form-{index}-question_type"] = self.types[code].pk if code else ""
        return self.client.post(self.url("scoring_formulas_modal"), data)

    def test_get_shows_the_formulas_of_the_level(self):
        # The help of the dialog quotes formulas: the formulas of the fields are told apart by their value attribute
        self.formula("b=4,m=-4", "SCQ")
        self.formula("b=8", "TF", prep_section=self.section)

        exam_level = self.modal()
        section_level = self.modal(prep_section=self.section.pk)

        self.assertContains(exam_level, 'value="b=4,m=-4"')
        self.assertNotContains(exam_level, 'value="b=8"')
        self.assertContains(section_level, 'value="b=8"')
        self.assertNotContains(section_level, 'value="b=4,m=-4"')

    def test_get_for_a_question_and_an_answer(self):
        question = self.question("SCQ")
        answer = question.prepAnswers.first()
        self.formula("b=3", prep_question=question)
        self.formula("b=7", prep_answer=answer)

        self.assertContains(self.modal(prep_question=question.pk), 'value="b=3"')
        self.assertContains(self.modal(prep_answer=answer.pk), 'value="b=7"')

    def test_post_saves_the_formulas_of_the_exam_and_rewrites_the_latex(self):
        response = self.post([("b=2,m=-1", "SCQ"), ("b=1", "MCQ")])

        self.assertEqual(response.json()["success"], True)
        self.assertEqual({f.question_type.code: f.formula for f in PrepScoringFormula.objects.filter(exam=self.exam)},
                         {"SCQ": "b=2,m=-1", "MCQ": "b=1"})
        self.assertIn("\\baremeDefautS{b=2,m=-1}", (self.project_path() / "global_scoring.tex").read_text())

    def test_post_saves_the_formula_of_a_section_a_question_and_an_answer(self):
        question = self.question("SCQ")
        answer = question.prepAnswers.first()

        self.post([("b=2", "SCQ")], prep_section=self.section.pk)
        self.post([("b=3", None)], prep_question=question.pk)
        self.post([("b=4", None)], prep_answer=answer.pk)

        saved = {(f.prep_section_id, f.prep_question_id, f.prep_answer_id): f.formula
                 for f in PrepScoringFormula.objects.filter(exam=self.exam)}
        self.assertEqual(saved, {(self.section.pk, None, None): "b=2", (None, question.pk, None): "b=3",
                                 (None, None, answer.pk): "b=4"})

    def test_post_with_characters_that_break_latex_shows_the_form_again(self):
        response = self.post([("b={1}", "SCQ")])

        body = response.json()
        self.assertFalse(body["success"])
        self.assertIn("These characters are not allowed", body["html"])
        self.assertFalse(PrepScoringFormula.objects.exists())

    def test_post_without_the_question_type_of_an_exam_formula_is_refused(self):
        body = self.post([("b=1", None)]).json()

        self.assertFalse(body["success"])
        self.assertFalse(PrepScoringFormula.objects.exists())

    def test_post_twice_the_same_question_type_is_refused(self):
        body = self.post([("b=1", "SCQ"), ("b=2", "SCQ")]).json()

        self.assertFalse(body["success"])
        self.assertIn("already used", body["html"])
        self.assertFalse(PrepScoringFormula.objects.exists())

    def test_other_methods_are_refused(self):
        response = self.client.put(self.url("scoring_formulas_modal"))

        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.json()["success"])


class DeleteScoringFormulaTestCase(PrepViewsTestCase):
    def setUp(self):
        super().setUp()
        self.formula = PrepScoringFormula.objects.create(exam=self.exam, formula="b=2", question_type=self.types["SCQ"])

    def delete(self, formula=None):
        return self.client.post(self.url("delete_scoring_formula", pk=(formula or self.formula).pk))

    def test_delete_removes_the_formula_and_rewrites_the_latex(self):
        global_scoring = self.project_path() / "global_scoring.tex"
        global_scoring.write_text("\\baremeDefautS{b=2}\n")

        response = self.delete()

        self.assertEqual(response.json()["success"], True)
        self.assertFalse(PrepScoringFormula.objects.exists())
        self.assertNotIn("baremeDefautS", global_scoring.read_text())

    def test_get_is_refused(self):
        response = self.client.get(self.url("delete_scoring_formula", pk=self.formula.pk))

        self.assertEqual(response.status_code, 405)
        self.assertTrue(PrepScoringFormula.objects.exists())

    def test_locked_exam_is_refused(self):
        self.lock()

        self.assertEqual(self.delete().status_code, 403)
        self.assertTrue(PrepScoringFormula.objects.exists())

    def test_formula_of_another_exam_is_not_found(self):
        other = PrepScoringFormula.objects.create(exam=create_mock_exam(code="OTHER-101"), formula="b=5",
                                                  question_type=self.types["SCQ"])

        self.assertEqual(self.delete(other).status_code, 404)
        self.assertTrue(PrepScoringFormula.objects.filter(pk=other.pk).exists())
