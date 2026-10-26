from django.urls import reverse
from django.utils.html import format_html
from django.utils.safestring import SafeString
from rest_framework import serializers

from examc_app.models import Student


class StudentPresenceSerializer(serializers.Serializer):
    present = serializers.BooleanField()


def render_presence_toggle(student: Student) -> SafeString:
    """Present / absent toggle; data-url is where the script sends the PATCH."""

    def option(present: bool, icon: str, color_class: str) -> SafeString:
        active = present == student.present

        # The current state stands out (solid, colored); the other option is a faded outline
        icon_style = "fa-solid" if active else "fa-regular"
        icon_color = color_class if active else "text-secondary"
        return format_html(
            '<label class="btn btn-icon{}">'
                '<button type="button" class="btn btn-link p-0 border-0" style="background-color: transparent;" data-present="{}">'
                '<i class="{} {} {} fa-xl"></i>'
                "</button>"
            "</label>",
            " active" if active else "",
            int(present),
            icon_style,
            icon,
            icon_color,
        )

    return format_html(
        '<div class="btn-group btn-group-toggle presence-toggle" data-url="{}">{}{}</div>',
        reverse(
            "api-exam-students-presence-patch",
            kwargs={"exam_pk": student.exam_id, "pk": student.pk},
        ),
        option(present=True, icon="fa-circle-check", color_class="text-success"),
        option(present=False, icon="fa-circle-xmark", color_class="text-danger"),
    )


class StudentPresenceRowSerializer(serializers.Serializer):
    """
    One row of the DataTables presence table.

    Context: "scale_values" = {student_pk: {scale_pk: grade}} for the current page,
    built once by the view (see get_scale_values).
    """

    copy_no = serializers.CharField(source="copie_no")
    sciper = serializers.CharField()
    name = serializers.CharField()
    present = serializers.SerializerMethodField()
    points = serializers.FloatField(allow_null=True)
    scales = serializers.SerializerMethodField()

    # noinspection PyMethodMayBeStatic
    def get_present(self, student: Student) -> SafeString:
        return render_presence_toggle(student)

    def get_scales(self, student: Student) -> dict[str, str]:
        # {str(scale_pk): grade} for the scales this student has a grade for.
        # The table shows missing ones as empty cells (defaultContent: "").
        values: dict[int, dict[int, str]] = self.context.get("scale_values", {})
        return {str(scale_pk): grade for scale_pk, grade in values.get(student.pk, {}).items()}
