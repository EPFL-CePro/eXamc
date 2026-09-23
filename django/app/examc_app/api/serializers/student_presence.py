from django.urls import reverse
from django.utils.html import format_html
from django.utils.safestring import SafeString, mark_safe
from rest_framework import serializers

from examc_app.models import Student


class StudentPresenceSerializer(serializers.Serializer):
    present = serializers.BooleanField()


def student_presence_url(student: Student) -> str:
    return reverse(
        "exam-students-presence-presence",
        kwargs={"exam_pk": student.exam_id, "pk": student.pk},
    )


def render_presence_toggle(student: Student) -> SafeString:
    def option(value: bool, icon: str) -> SafeString:
        active = value == student.present
        return format_html(
            '<label class="btn btn-light btn-sm{}" style="background-color: transparent;">'
            '<button type="button" class="btn btn-link p-0 border-0" style="background-color: transparent;" data-present="{}">'
            '<i class="fa-solid {} fa-2xl"{}></i>'
            '</button>'
            '</label>',
            " active" if active else "",
            int(value),
            icon,
            "" if active else mark_safe(' style="color:lightgray;"'),
        )

    return format_html(
        '<div class="btn-group btn-group-toggle presence-toggle" style="margin-left:-20px;" data-url="{}">{}{}</div>',
        student_presence_url(student),
        option(True, "fa-circle-check"),
        option(False, "fa-circle-xmark"),
    )


class StudentPresenceRowSerializer(serializers.Serializer):
    copy_no = serializers.CharField(source="copie_no")
    sciper = serializers.CharField()
    name = serializers.CharField()
    present = serializers.SerializerMethodField()
    points = serializers.FloatField(allow_null=True)
    scales = serializers.SerializerMethodField()

    # noinspection PyMethodMayBeStatic
    def get_present(self, student: Student) -> SafeString:
        return render_presence_toggle(student)

    # noinspection PyMethodMayBeStatic
    def get_scales(self, student: Student) -> dict[str, str]:
        # {str(scale.pk): value} for each scale column
        return {}