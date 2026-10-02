from rest_framework import serializers

from examc_app.models import PrepStudent


class PrepStudentRowSerializer(serializers.ModelSerializer):
    class Meta:
        model = PrepStudent
        fields = ["id", "copy_no", "sciper", "last_name", "first_name", "email", "section", "room", "seat",
                  "needs_correction"]


class PrepStudentUpdateSerializer(serializers.ModelSerializer):
    """Fields of a student edited in the students table (see correct_prep_student)."""

    class Meta:
        model = PrepStudent
        fields = ["sciper", "last_name", "first_name", "email", "section", "room", "seat"]
        extra_kwargs = {
            # Filled from the EPFL directory when the SCIPER is found
            "last_name": {"required": False, "allow_blank": True},
            "first_name": {"required": False, "allow_blank": True},
            "seat": {"required": False, "allow_blank": True},
        }

    def validate_sciper(self, value: int) -> int:
        if not 100000 <= value <= 999999:
            raise serializers.ValidationError("The SCIPER must have 6 digits.")
        others = PrepStudent.objects.filter(exam_id=self.instance.exam_id, sciper=value).exclude(pk=self.instance.pk)
        if others.exists():
            raise serializers.ValidationError("This SCIPER is already used by another student of the exam.")
        return value

    def validate_email(self, value):
        return value or None

    def validate_section(self, value):
        return value or None

    def validate_room(self, value):
        return value or None
