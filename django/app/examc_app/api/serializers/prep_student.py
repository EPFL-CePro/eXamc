from rest_framework import serializers

from examc_app.models import PrepStudent


class PrepStudentRowSerializer(serializers.ModelSerializer):
    class Meta:
        model = PrepStudent
        fields = ["id", "copy_no", "sciper", "last_name", "first_name", "email", "section", "room", "seat"]
