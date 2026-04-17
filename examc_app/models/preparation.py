##############################
# PREPARATION
##############################

from django.db import models
from simple_history.models import HistoricalRecords

from examc import settings
from examc_app.models import QuestionType, Exam

AUTH_USER_MODEL = "auth.User"
BOX_TYPE_CHOICES = [("grid","Grid"),("blank","Blank")]


class PrepSection(models.Model):
    exam = models.ForeignKey(Exam, on_delete=models.CASCADE, related_name='prepSections')
    title = models.CharField(max_length=500)
    section_text = models.TextField(default='')
    position = models.IntegerField(default=0)
    random_questions = models.BooleanField(default=False)
    history = HistoricalRecords()

class PrepQuestion(models.Model):
    POINT_INCREMENT_CHOICES = [("0.5", "0.5"), ("1", "1")]

    prep_section = models.ForeignKey(PrepSection, on_delete=models.CASCADE, related_name='prepQuestions')
    question_type = models.ForeignKey(QuestionType, on_delete=models.CASCADE, related_name='prepQuestions', blank=True, null=True)
    title = models.CharField(max_length=500)
    question_text = models.TextField(default='')
    position = models.IntegerField(default=0)
    random_answers = models.BooleanField(default=False)
    max_points = models.DecimalField(max_digits=10, decimal_places=2,default=0.0,)
    point_increment = models.CharField(max_length=10, choices=POINT_INCREMENT_CHOICES,default="grid", blank=True, null=True)
    canceled = models.BooleanField(default=False)
    new_page = models.BooleanField(default=False)
    history = HistoricalRecords()

class PrepQuestionAnswer(models.Model):

    prep_question = models.ForeignKey(PrepQuestion, on_delete=models.CASCADE, related_name='prepAnswers')
    title = models.CharField(max_length=500)
    answer_text = models.TextField(default='', blank=True, null=True)
    is_correct = models.BooleanField(default=False)
    box_type = models.CharField(max_length=10, choices=BOX_TYPE_CHOICES,default="null", blank=True, null=True)
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

class ExamAMCJob(models.Model):
    JOB_TYPE_CHOICES = [
        ("preview", "Preview"),
        ("final_build", "Final build"),
        ("layout_extract", "Layout extraction"),
        ("scoring_extract", "Scoring extraction"),
        ("data_capture", "Data capture"),
    ]

    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("running", "Running"),
        ("success", "Success"),
        ("error", "Error"),
    ]

    exam = models.ForeignKey("Exam", on_delete=models.CASCADE)
    requested_by = models.ForeignKey(AUTH_USER_MODEL, on_delete=models.CASCADE)

    job_type = models.CharField(max_length=30, choices=JOB_TYPE_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")

    exam_build = models.ForeignKey(
        "ExamBuild",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="jobs",
    )

    pdf_path = models.TextField(blank=True, default="")
    result_json = models.JSONField(blank=True, null=True)
    error_message = models.TextField(blank=True, default="")
    celery_task_id = models.CharField(max_length=255, blank=True, default="")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    progress_current = models.PositiveIntegerField(default=0)
    progress_total = models.PositiveIntegerField(default=0)
    progress_percent = models.PositiveIntegerField(default=0)
    progress_message = models.CharField(max_length=255, blank=True, default="")