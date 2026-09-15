from rest_framework import serializers

from examc_app.models import Exam


class ExamSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = Exam
        fields = ["code", "name", "date"]