from django.conf import settings
from django.db import models
from simple_history.models import HistoricalRecords

from examc_app.models import Exam


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

    # A locked build is never deleted by the retention policy (see amc_build_retention).
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
