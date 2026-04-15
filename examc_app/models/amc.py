from django.conf import settings
from django.db import models
from simple_history.models import HistoricalRecords

from examc_app.models import Exam, PrepQuestion, PrepQuestionAnswer, AUTH_USER_MODEL


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

    # Snapshots to preserve build history even if preparation content changes later.
    title_snapshot = models.CharField(max_length=500, blank=True, default="")
    text_snapshot = models.TextField(blank=True, default="")
    max_points_snapshot = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    point_increment_snapshot = models.CharField(max_length=10, blank=True, default="")
    random_answers_snapshot = models.BooleanField(default=False)
    new_page_snapshot = models.BooleanField(default=False)
    canceled_snapshot = models.BooleanField(default=False)

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
    fix_position_snapshot = models.BooleanField(default=False)

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
class LayoutPage(models.Model):
    build = models.ForeignKey(ExamBuild, on_delete=models.CASCADE, related_name="layout_pages")

    # Copy/student are kept nullable because preview builds may exist before copy generation.
    copy_number = models.PositiveIntegerField(blank=True, null=True)
    page_number = models.PositiveIntegerField()
    checksum = models.BigIntegerField(blank=True, null=True)

    source_page_number = models.PositiveIntegerField(blank=True, null=True)
    dpi = models.FloatField(blank=True, null=True)
    width = models.FloatField(blank=True, null=True)
    height = models.FloatField(blank=True, null=True)
    mark_diameter = models.FloatField(blank=True, null=True)

    class Meta:
        ordering = ["copy_number", "page_number", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["build", "copy_number", "page_number"],
                name="layout_page_build_copy_page_uniq",
            )
        ]

    def __str__(self):
        return f"Build {self.build_id} / copy {self.copy_number} / page {self.page_number}"


class LayoutMark(models.Model):
    page = models.ForeignKey(LayoutPage, on_delete=models.CASCADE, related_name="marks")
    corner = models.PositiveSmallIntegerField()
    x = models.FloatField()
    y = models.FloatField()

    class Meta:
        ordering = ["corner", "id"]
        constraints = [
            models.UniqueConstraint(fields=["page", "corner"], name="layout_mark_page_corner_uniq")
        ]


class LayoutZone(models.Model):
    ZONE_TYPE_CHOICES = [
        ("namefield", "Name field"),
        ("idzone", "ID zone"),
        ("custom", "Custom"),
    ]

    page = models.ForeignKey(LayoutPage, on_delete=models.CASCADE, related_name="zones")
    zone_type = models.CharField(max_length=20, choices=ZONE_TYPE_CHOICES, default="custom")
    zone_code = models.CharField(max_length=100, blank=True, default="")
    flags = models.PositiveIntegerField(default=0)
    xmin = models.FloatField()
    xmax = models.FloatField()
    ymin = models.FloatField()
    ymax = models.FloatField()

    class Meta:
        ordering = ["id"]
        indexes = [
            models.Index(fields=["page", "zone_type"]),
        ]


class LayoutBox(models.Model):
    ROLE_CHOICES = [
        ("answer", "Answer"),
        ("question_only", "Question only"),
        ("score", "Score"),
        ("score_question", "Score question"),
        ("question_text", "Question text"),
        ("answer_text", "Answer text"),
        ("open_grid", "Open grid"),
        ("open_box", "Open box"),
    ]

    page = models.ForeignKey(LayoutPage, on_delete=models.CASCADE, related_name="boxes")
    build_question = models.ForeignKey(
        ExamBuildQuestion,
        on_delete=models.CASCADE,
        related_name="layout_boxes",
    )
    build_answer = models.ForeignKey(
        ExamBuildAnswer,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="layout_boxes",
    )

    role = models.CharField(max_length=30, choices=ROLE_CHOICES, default="answer")
    answer_number = models.PositiveIntegerField(default=0)
    flags = models.PositiveIntegerField(default=0)
    char = models.CharField(max_length=20, blank=True, default="")

    xmin = models.FloatField()
    xmax = models.FloatField()
    ymin = models.FloatField()
    ymax = models.FloatField()

    class Meta:
        ordering = ["id"]
        indexes = [
            models.Index(fields=["page", "role"]),
            models.Index(fields=["build_question", "build_answer"]),
        ]


class LayoutDigit(models.Model):
    page = models.ForeignKey(LayoutPage, on_delete=models.CASCADE, related_name="digits")
    number_id = models.PositiveIntegerField()
    digit_id = models.PositiveIntegerField()
    xmin = models.FloatField()
    xmax = models.FloatField()
    ymin = models.FloatField()
    ymax = models.FloatField()

    class Meta:
        ordering = ["number_id", "digit_id", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["page", "number_id", "digit_id"],
                name="layout_digit_page_number_digit_uniq",
            )
        ]


class ExamCopy(models.Model):
    STATUS_CHOICES = [
        ("generated", "Generated"),
        ("printed", "Printed"),
        ("scanned", "Scanned"),
        ("captured", "Captured"),
        ("graded", "Graded"),
        ("error", "Error"),
    ]

    build = models.ForeignKey(ExamBuild, on_delete=models.CASCADE, related_name="copies")
    copy_number = models.PositiveIntegerField()
    candidate_code = models.CharField(max_length=100, blank=True, default="")
    candidate_name = models.CharField(max_length=255, blank=True, default="")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="generated")

    class Meta:
        ordering = ["copy_number", "id"]
        constraints = [
            models.UniqueConstraint(fields=["build", "copy_number"], name="exam_copy_build_copy_number_uniq")
        ]

    def __str__(self):
        return f"Build {self.build_id} / copy {self.copy_number}"


class ScanPage(models.Model):
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("processed", "Processed"),
        ("error", "Error"),
    ]

    build = models.ForeignKey(ExamBuild, on_delete=models.CASCADE, related_name="scan_pages")
    exam_copy = models.ForeignKey(
        ExamCopy,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="scan_pages",
    )
    layout_page = models.ForeignKey(
        LayoutPage,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="scan_pages",
    )

    uploaded_file = models.TextField(blank=True, default="")
    page_number = models.PositiveIntegerField(blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    error_message = models.TextField(blank=True, default="")

    detected_dpi = models.FloatField(blank=True, null=True)
    rotation_deg = models.FloatField(blank=True, null=True)
    shift_x = models.FloatField(blank=True, null=True)
    shift_y = models.FloatField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["build_id", "page_number", "id"]
        indexes = [
            models.Index(fields=["build", "status"]),
            models.Index(fields=["exam_copy", "page_number"]),
        ]


class CaptureBox(models.Model):
    scan_page = models.ForeignKey(ScanPage, on_delete=models.CASCADE, related_name="captured_boxes")
    layout_box = models.ForeignKey(LayoutBox, on_delete=models.CASCADE, related_name="captures")

    black_ratio = models.FloatField(blank=True, null=True)
    threshold = models.FloatField(blank=True, null=True)
    is_ticked = models.BooleanField(default=False)
    manually_overridden = models.BooleanField(default=False)
    override_value = models.BooleanField(blank=True, null=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["scan_page", "layout_box"], name="capture_box_scan_layout_uniq")
        ]


class ScoreResult(models.Model):
    build = models.ForeignKey(ExamBuild, on_delete=models.CASCADE, related_name="score_results")
    exam_copy = models.ForeignKey(ExamCopy, on_delete=models.CASCADE, related_name="score_results")
    build_question = models.ForeignKey(
        ExamBuildQuestion,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="score_results",
    )

    score = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    max_score = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    details = models.JSONField(blank=True, null=True)
    calculated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["build", "exam_copy", "build_question"],
                name="score_result_build_copy_question_uniq",
            )
        ]