# serializers.py
from rest_framework import serializers
from django.db import transaction
from .models import (
    Order,
    OrderItem,
    OrderAddress,
    ShippingDetails,
    PaymentDetails,
    InvoiceRequest,
)


class OrderItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderItem
        fields = "__all__"


class OrderAddressSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderAddress
        fields = "__all__"


class ShippingDetailsSerializer(serializers.ModelSerializer):
    class Meta:
        model = ShippingDetails
        fields = "__all__"


class PaymentDetailsSerializer(serializers.ModelSerializer):
    class Meta:
        model = PaymentDetails
        fields = "__all__"


class OrderCreateSerializer(serializers.ModelSerializer):
    items = serializers.ListField(write_only=True)
    shipping_address = serializers.DictField(write_only=True)
    billing_address = serializers.DictField(write_only=True, required=False)
    shipping_details = serializers.DictField(write_only=True, required=False)
    payment_details = serializers.DictField(write_only=True, required=False)

    class Meta:
        model = Order
        fields = [
            "id",
            "user",
            "seller",
            "total_amount",
            "items",
            "shipping_address",
            "billing_address",
            "shipping_details",
            "payment_details",
        ]
        read_only_fields = ["id"]

    def create(self, validated_data):
        items_data = validated_data.pop("items", [])
        shipping_address_data = validated_data.pop("shipping_address", None)
        billing_address_data = validated_data.pop("billing_address", None)
        shipping_details_data = validated_data.pop("shipping_details", None)
        payment_details_data = validated_data.pop("payment_details", None)

        with transaction.atomic():
            # Create Order
            order = Order.objects.create(**validated_data)

            # Create Order Items
            for item in items_data:
                OrderItem.objects.create(order=order, **item)

            # Create Shipping Address
            if shipping_address_data:
                shipping_address_data["address_type"] = "shipping"
                OrderAddress.objects.create(order=order, **shipping_address_data)

            # Create Billing Address
            if billing_address_data:
                billing_address_data["address_type"] = "billing"
                OrderAddress.objects.create(order=order, **billing_address_data)

            # Create Shipping Details
            if shipping_details_data:
                ShippingDetails.objects.create(order=order, **shipping_details_data)

            # Create Payment Details
            if payment_details_data:
                PaymentDetails.objects.create(order=order, **payment_details_data)

        return order


class OrderListSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)
    addresses = OrderAddressSerializer(
        source="orderaddress_set", many=True, read_only=True
    )
    shipping = ShippingDetailsSerializer(read_only=True)
    payment = PaymentDetailsSerializer(read_only=True)

    class Meta:
        model = Order
        fields = [
            "id",
            "order_number",
            "user",
            "seller",
            "status",
            "total_amount",
            "items",
            "addresses",
            "shipping",
            "payment",
            "created_at",
            "updated_at",
        ]


class OrderDetailSerializer(OrderListSerializer):
    class Meta(OrderListSerializer.Meta):
        # Inherit all fields from OrderListSerializer - no additional fields needed
        fields = OrderListSerializer.Meta.fields


class OrderUpdateSerializer(serializers.ModelSerializer):
    items = serializers.ListField(write_only=True, required=False)
    shipping_address = serializers.DictField(write_only=True, required=False)
    billing_address = serializers.DictField(write_only=True, required=False)
    shipping_details = serializers.DictField(write_only=True, required=False)
    payment_details = serializers.DictField(write_only=True, required=False)

    class Meta:
        model = Order
        fields = [
            "status",
            "items",
            "shipping_address",
            "billing_address",
            "shipping_details",
            "payment_details",
        ]

    def update(self, instance, validated_data):
        with transaction.atomic():
            # Update items if provided
            if "items" in validated_data:
                items_data = validated_data.pop("items")
                instance.items.all().delete()
                for item in items_data:
                    OrderItem.objects.create(order=instance, **item)

            # Update addresses if provided
            if "shipping_address" in validated_data:
                shipping_data = validated_data.pop("shipping_address")
                OrderAddress.objects.update_or_create(
                    order=instance, address_type="shipping", defaults=shipping_data
                )

            if "billing_address" in validated_data:
                billing_data = validated_data.pop("billing_address")
                OrderAddress.objects.update_or_create(
                    order=instance, address_type="billing", defaults=billing_data
                )

            # Update shipping details if provided
            if "shipping_details" in validated_data:
                shipping_details = validated_data.pop("shipping_details")
                ShippingDetails.objects.update_or_create(
                    order=instance, defaults=shipping_details
                )

            # Update payment details if provided
            if "payment_details" in validated_data:
                payment_details = validated_data.pop("payment_details")
                PaymentDetails.objects.update_or_create(
                    order=instance, defaults=payment_details
                )

            # Update order status if provided
            for attr, value in validated_data.items():
                setattr(instance, attr, value)
            instance.save()

        return instance


class OrderStatusUpdateSerializer(serializers.Serializer):
    status = serializers.ChoiceField(
        choices=[
            ("pending", "Pending"),
            ("confirmed", "Confirmed"),
            ("processing", "Processing"),
            ("shipped", "Shipped"),
            ("delivered", "Delivered"),
            ("cancelled", "Cancelled"),
            ("returned", "Returned"),
        ]
    )
    notes = serializers.CharField(required=False)


# Add this to your serializers.py file
class InvoiceRequestSerializer(serializers.ModelSerializer):
    class Meta:
        model = InvoiceRequest
        fields = [
            "id",
            "order",
            "requested_by",
            "requested_at",
            "notes",
            "status",
            "processed_at",
        ]
        read_only_fields = ["id", "requested_at", "status", "processed_at"]


class InvoiceRequestCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = InvoiceRequest
        fields = ["notes"]


# Add this to handle responses
class InvoiceRequestResponseSerializer(serializers.ModelSerializer):
    order_number = serializers.CharField(source="order.order_number", read_only=True)

    class Meta:
        model = InvoiceRequest
        fields = [
            "id",
            "order",
            "order_number",
            "requested_at",
            "notes",
            "status",
            "seller_notes",
            "processed_at",
        ]
        read_only_fields = [
            "id",
            "order",
            "order_number",
            "requested_at",
            "status",
            "processed_at",
        ]
