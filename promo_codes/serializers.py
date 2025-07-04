from rest_framework import serializers
from .models import PromoCode
from django.utils.timezone import now


class PromoCodeSerializer(serializers.ModelSerializer):
    is_valid = serializers.SerializerMethodField()

    class Meta:
        model = PromoCode
        fields = "__all__"

    def get_is_valid(self, obj):
        return obj.is_valid()


class ApplyPromoCodeSerializer(serializers.Serializer):
    promo_code = serializers.CharField()
    order_amount = serializers.DecimalField(max_digits=10, decimal_places=2)

    def validate(self, data):
        try:
            promo = PromoCode.objects.get(promo_code=data["promo_code"])
        except PromoCode.DoesNotExist:
            raise serializers.ValidationError({"promo_code": "Invalid promo code."})

        if not promo.is_valid():
            raise serializers.ValidationError(
                {"promo_code": "Promo code is expired or inactive."}
            )

        if data["order_amount"] < promo.minimum_order_amount:
            raise serializers.ValidationError(
                {
                    "order_amount": f"Minimum order amount should be {promo.minimum_order_amount}."
                }
            )

        return data

    def apply_promo_code(self):
        print("Zz")
        promo = PromoCode.objects.get(promo_code=self.validated_data["promo_code"])
        new_amount, discount = promo.apply_discount(self.validated_data["order_amount"])
        return {
            "new_amount": new_amount,
            "discount": discount,
            "promo_code": promo.promo_code,
        }
