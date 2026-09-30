from rest_framework import serializers


class AmcDataCaptureManualSerializer(serializers.Serializer):
    pages = serializers.ListField(child=serializers.DictField())
    questions = serializers.ListField(child=serializers.DictField())
    copies = serializers.ListField()