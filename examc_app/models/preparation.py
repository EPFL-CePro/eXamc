##############################
# PREPARATION
##############################

from django.db import models
from simple_history.models import HistoricalRecords

from examc_app.models import QuestionType, Exam


class PrepSection(models.Model):
    exam = models.ForeignKey(Exam, on_delete=models.CASCADE, related_name='prepSections')
    title = models.CharField(max_length=500)
    section_text = models.TextField(default='')
    position = models.IntegerField(default=0)
    random_questions = models.BooleanField(default=False)
    history = HistoricalRecords()

class PrepQuestion(models.Model):
    POINT_INCREMENT_CHOICES = [("50", "0.5"), ("100", "1")]

    prep_section = models.ForeignKey(PrepSection, on_delete=models.CASCADE, related_name='prepQuestions')
    question_type = models.ForeignKey(QuestionType, on_delete=models.CASCADE, related_name='prepQuestions', blank=True, null=True)
    title = models.CharField(max_length=500)
    question_text = models.TextField(default='')
    position = models.IntegerField(default=0)
    random_answers = models.BooleanField(default=False)
    max_points = models.DecimalField(max_digits=10, decimal_places=5,default=0.0)
    point_increment = models.CharField(max_length=10, choices=POINT_INCREMENT_CHOICES,default="grid", blank=True, null=True)
    canceled = models.BooleanField(default=False)
    history = HistoricalRecords()

class PrepQuestionAnswer(models.Model):
    BOX_TYPE_CHOICES = [("grid","Grid"),("line","Line"),("blank","Blank")]

    prep_question = models.ForeignKey(PrepQuestion, on_delete=models.CASCADE, related_name='prepAnswers')
    title = models.CharField(max_length=500)
    answer_text = models.TextField(default='')
    is_correct = models.BooleanField(default=False)
    box_type = models.CharField(max_length=10, choices=BOX_TYPE_CHOICES,default="grid", blank=True, null=True)
    box_height_mm = models.IntegerField(default=0,blank=True, null=True)
    position = models.IntegerField(default=0)
    fix_position = models.BooleanField(default=False)
    history = HistoricalRecords()

class PrepScoringFormula(models.Model):
    exam = models.ForeignKey(Exam, on_delete=models.CASCADE, related_name='prepExamScoringFormulas')
    prep_section = models.ForeignKey(PrepSection, on_delete=models.CASCADE, related_name='prepSectionScoringFormulas', blank=True, null=True)
    prep_question = models.ForeignKey(PrepQuestion, on_delete=models.CASCADE, related_name='prepQuestionScoringFormulas', blank=True, null=True)
    prep_answer = models.ForeignKey(PrepQuestionAnswer, on_delete=models.CASCADE, related_name='prepAnswersScoringFormulas', blank=True, null=True)
    question_type = models.ForeignKey(QuestionType, on_delete=models.CASCADE, related_name='prepScoringFormulas', blank=True, null=True)
    formula = models.CharField(max_length=500)
    history = HistoricalRecords()
