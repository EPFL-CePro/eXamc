from django.conf import settings
from django.db import models
from simple_history.models import HistoricalRecords

from examc_app.models import Exam, PrepQuestion, PrepQuestionAnswer


class ExamBuild(models.Model):
    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("building", "Building"),
        ("ready", "Ready"),
        ("error", "Error"),
        ("archived", "Archived"),
    ]

    exam = models.ForeignKey(Exam, on_delete=models.CASCADE, related_name="builds")
    version = models.PositiveIntegerField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="draft")

    # Once locked, this build becomes the immutable reference for layout/scans/grading.
    is_locked = models.BooleanField(default=False)
    locked_at = models.DateTimeField(blank=True, null=True)
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="requested_exam_builds",
    )

    # Reproducibility / traceability.
    source_hash = models.CharField(max_length=128, blank=True, default="")
    latex_engine = models.CharField(max_length=100, blank=True, default="pdflatex")
    build_log = models.TextField(blank=True, default="")
    error_message = models.TextField(blank=True, default="")

    # File artifacts produced by the build pipeline.
    project_path = models.TextField(blank=True, default="")
    latex_main_path = models.TextField(blank=True, default="")
    compiled_pdf_path = models.TextField(blank=True, default="")
    amc_log_path = models.TextField(blank=True, default="")
    xy_path = models.TextField(blank=True, default="")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    history = HistoricalRecords()

    class Meta:
        ordering = ["-created_at", "-id"]
        constraints = [
            models.UniqueConstraint(fields=["exam", "version"], name="exam_build_exam_version_uniq")
        ]

    def __str__(self):
        return f"Build #{self.version} - {self.exam}"


class ExamBuildQuestion(models.Model):
    build = models.ForeignKey(ExamBuild, on_delete=models.CASCADE, related_name="build_questions")
    prep_question = models.ForeignKey(
        PrepQuestion,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="exam_build_questions",
    )

    # Frozen identifier used in LaTeX / layout extraction for this build.
    rendered_id = models.CharField(max_length=100)
    rendered_code = models.CharField(max_length=150, blank=True, default="")
    rendered_position = models.PositiveIntegerField()
    section_position = models.PositiveIntegerField(default=1)
    question_type_code = models.CharField(max_length=20)
    prep_question_id_snapshot = models.IntegerField(blank=True, null=True)
    amc_question_number = models.PositiveIntegerField(null=True, blank=True)

    # Snapshots to preserve build history even if preparation content changes later.
    title_snapshot = models.CharField(max_length=500, blank=True, default="")
    text_snapshot = models.TextField(blank=True, default="")
    max_points_snapshot = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    point_increment_snapshot = models.CharField(max_length=10, blank=True, default="")
    random_answers_snapshot = models.BooleanField(default=False)

    class Meta:
        ordering = ["section_position", "rendered_position", "id"]
        constraints = [
            models.UniqueConstraint(fields=["build", "rendered_id"], name="build_question_rendered_id_uniq"),
            models.UniqueConstraint(
                fields=["build", "rendered_position", "section_position"],
                name="build_question_section_position_uniq",
            ),
        ]

    def __str__(self):
        return self.rendered_id


class ExamBuildAnswer(models.Model):
    build_question = models.ForeignKey(
        ExamBuildQuestion,
        on_delete=models.CASCADE,
        related_name="build_answers",
    )
    prep_answer = models.ForeignKey(
        PrepQuestionAnswer,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="exam_build_answers",
    )

    rendered_answer_number = models.PositiveIntegerField()
    rendered_code = models.CharField(max_length=150, blank=True, default="")
    rendered_position = models.PositiveIntegerField()

    prep_answer_id_snapshot = models.IntegerField(blank=True, null=True)
    title_snapshot = models.CharField(max_length=500, blank=True, default="")
    answer_text_snapshot = models.TextField(blank=True, default="")
    is_correct_snapshot = models.BooleanField(default=False)
    box_type_snapshot = models.CharField(max_length=20, blank=True, default="")
    box_height_mm_snapshot = models.IntegerField(blank=True, null=True)

    class Meta:
        ordering = ["rendered_position", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["build_question", "rendered_answer_number"],
                name="build_answer_number_uniq",
            )
        ]

    def __str__(self):
        return f"{self.build_question.rendered_id} / {self.rendered_answer_number}"


# Layout* models intentionally stay close to AMC concepts because they are the
# natural boundary between the LaTeX-rendered document and scan/capture logic.
