from django.urls import reverse
from django.utils.html import format_html
from django.utils.safestring import SafeString, mark_safe
from rest_framework import serializers

from examc_app.models import Student


class StudentPresenceSerializer(serializers.Serializer):
    present = serializers.BooleanField()


def render_presence_toggle(student: Student) -> SafeString:
    def option(present: bool, icon: str, colorClass: str) -> SafeString:
        active = present == student.present
        return format_html(
            '<label class="btn btn-icon {}">'
                '<button type="button" class="btn btn-link p-0 border-0" style="background-color: transparent;" data-present="{}">'
                    '<i class="{} fa-xl"></i>'
                '</button>'
            '</label>',
            " active" if active else "",
            int(present),
            f"{"fa-regular" if active else "fa-solid"} {icon} {"text-secondary" if active else colorClass}",
        )

    return format_html(
        '<div class="btn-group btn-group-toggle presence-toggle" data-url="{}">{}{}</div>',
        reverse("api-exam-students-presence-patch", kwargs={"exam_pk": student.exam_id, "pk": student.pk}),
        option(present=True, icon="fa-circle-check", colorClass="text-success"),
        option(present=False, icon="fa-circle-xmark", colorClass="text-danger"),
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