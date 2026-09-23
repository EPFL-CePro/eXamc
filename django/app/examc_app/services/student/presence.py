from dataclasses import dataclass

from django.db import transaction
from django.shortcuts import get_object_or_404

from examc_app.models import Student
from examc_app.tasks import generate_statistics


@dataclass(frozen=True)
class PresenceResult:
    student: Student
    updated: bool
    present_students: int
    task_id: str | None


def set_student_presence(*, exam_pk: int, student_pk: int, present: bool) -> PresenceResult:
    with transaction.atomic():
        student = get_object_or_404(
            Student.objects.select_for_update().select_related("exam"),
            pk=student_pk,
            exam_id=exam_pk,
        )
        exam = student.exam
        updated = student.present != present

        if updated:
            student.present = present
            student.save(update_fields=["present"])
            exam.present_students = Student.objects.filter(exam_id=exam_pk, present=True).count()
            exam.save(update_fields=["present_students"])

    # Start the task after the commit so it sees the new data
    task_id = generate_statistics.delay(exam_pk).id if updated else None
    return PresenceResult(student, updated, exam.present_students, task_id)