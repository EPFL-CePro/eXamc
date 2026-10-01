from rest_framework import serializers


class ScanUrlQuerySerializer(serializers.Serializer):
    copy = serializers.RegexField(r'^\d+$')
    page = serializers.RegexField(r'^\d+(\.\d+)?$')