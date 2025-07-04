from rest_framework import serializers
from .models import ReturnRequest

class ReturnRequestSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReturnRequest
        fields = "__all__"
