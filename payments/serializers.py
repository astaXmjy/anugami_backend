from rest_framework import serializers

class PaymentInitiateSerializer(serializers.Serializer):
    order_id = serializers.CharField(max_length=50)
    amount = serializers.DecimalField(max_digits=10, decimal_places=2)
    callback_url = serializers.URLField()

class PaymentStatusSerializer(serializers.Serializer):
    transaction_id = serializers.CharField(max_length=100)

class RefundSerializer(serializers.Serializer):
    transaction_id = serializers.CharField(max_length=100)
    amount = serializers.DecimalField(max_digits=10, decimal_places=2)
