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
    history = HistoricalRecords()

class PrepQuestion(models.Model):
    prep_section = models.ForeignKey(PrepSection, on_delete=models.CASCADE, related_name='prepQuestions')
    question_type = models.ForeignKey(QuestionType, on_delete=models.CASCADE, related_name='prepQuestions', blank=True, null=True)
    title = models.CharField(max_length=500)
    question_text = models.TextField(default='')
    position = models.IntegerField(default=0)
    history = HistoricalRecords()

class PrepQuestionAnswer(models.Model):
    prep_question = models.ForeignKey(PrepQuestion, on_delete=models.CASCADE, related_name='prepAnswers')
    title = models.CharField(max_length=500)
    answer_text = models.TextField(default='')
    is_correct = models.BooleanField(default=False)
    position = models.IntegerField(default=0)
    history = HistoricalRecords()