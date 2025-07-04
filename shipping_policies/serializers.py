from rest_framework import serializers
from .models import ShippingPolicy, ShippingZone


class ShippingZoneSerializer(serializers.ModelSerializer):
    """Serializer for shipping zones"""

    class Meta:
        model = ShippingZone
        fields = ["id", "name", "states", "shipping_cost", "estimated_days"]


class ShippingPolicySerializer(serializers.ModelSerializer):
    """Serializer for shipping policies"""

    zones = ShippingZoneSerializer(many=True, required=False)
    seller_name = serializers.SerializerMethodField()

    class Meta:
        model = ShippingPolicy
        fields = [
            "id",
            "title",
            "description",
            "return_policy",
            "delivery_time",
            "shipping_cost",
            "seller",
            "seller_name",
            "is_active",
            "is_default",
            "max_weight",
            "zones",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def get_seller_name(self, obj):
        return str(obj.seller) if obj.seller else None

    def create(self, validated_data):
        zones_data = validated_data.pop("zones", [])
        shipping_policy = ShippingPolicy.objects.create(**validated_data)

        # Create related shipping zones
        for zone_data in zones_data:
            ShippingZone.objects.create(policy=shipping_policy, **zone_data)

        return shipping_policy

    def update(self, instance, validated_data):
        zones_data = validated_data.pop("zones", None)

        # Update shipping policy fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        # Update zones if provided
        if zones_data is not None:
            # Delete existing zones
            instance.zones.all().delete()

            # Create new zones
            for zone_data in zones_data:
                ShippingZone.objects.create(policy=instance, **zone_data)

        return instance
