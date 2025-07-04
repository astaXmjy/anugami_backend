from rest_framework import serializers
from .models import SupportTicket, TicketResponse, TicketCategory, TicketNote
from orders.models import Order, OrderItem  # Import Order models
from customers.models import Customer
from sellers.models import Seller


class TicketCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = TicketCategory
        fields = ["id", "name", "description", "is_active"]


class TicketResponseSerializer(serializers.ModelSerializer):
    responder_name = serializers.SerializerMethodField()
    responder_type = serializers.ReadOnlyField()

    class Meta:
        model = TicketResponse
        fields = [
            "id",
            "message",
            "created_at",
            "responder_name",
            "responder_type",
            "attachments",
        ]
        read_only_fields = ["id", "created_at", "responder_name", "responder_type"]

    def get_responder_name(self, obj):
        if obj.customer:
            return obj.customer.full_name
        elif obj.seller:
            return obj.seller.full_name
        elif obj.staff:
            return obj.staff.name
        return "Unknown"


class TicketNoteSerializer(serializers.ModelSerializer):
    user_name = serializers.ReadOnlyField(source="user.name")

    class Meta:
        model = TicketNote
        fields = ["id", "note", "created_at", "user", "user_name"]
        read_only_fields = ["id", "created_at", "user", "user_name"]


class SupportTicketSerializer(serializers.ModelSerializer):
    responses = TicketResponseSerializer(many=True, read_only=True)
    notes = TicketNoteSerializer(many=True, read_only=True)
    requester_name = serializers.SerializerMethodField()
    category_name = serializers.ReadOnlyField(source="category.name")
    assigned_to_name = serializers.ReadOnlyField(source="assigned_to.name")

    class Meta:
        model = SupportTicket
        fields = [
            "id",
            "requester_type",
            "requester_name",
            "order_id",
            "subject",
            "description",
            "status",
            "priority",
            "category",
            "category_name",
            "created_at",
            "updated_at",
            "last_activity",
            "assigned_to",
            "assigned_to_name",
            "sla_due_date",
            "is_overdue",
            "responses",
            "notes",
        ]
        read_only_fields = [
            "id",
            "requester_type",
            "requester_name",
            "created_at",
            "updated_at",
            "last_activity",
            "responses",
            "notes",
            "is_overdue",
            "assigned_to",  # This will be auto-assigned based on order
        ]

    def get_requester_name(self, obj):
        if obj.requester_type == "customer" and obj.customer:
            return obj.customer.full_name
        elif obj.requester_type == "seller" and obj.seller:
            return obj.seller.full_name
        return "Unknown"

    def create(self, validated_data):
        """
        Handle the specifics of creating a ticket based on user type
        and auto-assign to seller if order_id is provided
        """
        request = self.context.get("request")
        if not request or not request.user:
            raise serializers.ValidationError("Authentication required")

        user = request.user

        # Determine if the user is a customer or seller
        if hasattr(user, "customer") and user.customer:
            validated_data["customer"] = user.customer
            validated_data["requester_type"] = "customer"

        elif hasattr(user, "seller_profile") and user.seller_profile:
            validated_data["seller"] = user.seller_profile
            validated_data["requester_type"] = "seller"

        else:
            raise serializers.ValidationError(
                "User must be either a customer or seller"
            )

        # Set default priority based on request data or use 'medium'
        if "priority" not in validated_data:
            validated_data["priority"] = "medium"

        # Handle order-based assignment
        order_id = validated_data.get("order_id")
        if order_id:
            try:
                # First, try to find the order by order_number (string)
                order = Order.objects.filter(order_number=order_id).first()

                if not order:
                    # If not found by order_number, try by ID (integer)
                    try:
                        order_id_int = int(order_id)
                        order = Order.objects.filter(id=order_id_int).first()
                    except (ValueError, TypeError):
                        pass

                if order:
                    # Get the seller's CustomUser from the order
                    # Your Order model has: seller = ForeignKey(Seller, ...)
                    # Your Seller model has: user = ForeignKey(CustomUser, ...)
                    if hasattr(order, "seller") and order.seller:
                        # Get the CustomUser from the Seller
                        if hasattr(order.seller, "user") and order.seller.user:
                            validated_data["assigned_to"] = order.seller.user

                    # Store order reference for easy access
                    validated_data["order_id"] = (
                        str(order.order_number)
                        if hasattr(order, "order_number")
                        else str(order.id)
                    )
                else:
                    # Order not found, but don't fail - just log it
                    print(f"Order with ID/number {order_id} not found")

            except Exception as e:
                # Don't fail ticket creation if order lookup fails
                print(f"Error looking up order {order_id}: {str(e)}")

        # Calculate SLA due date based on priority
        from datetime import timedelta
        from django.utils import timezone

        priority_sla_map = {
            "urgent": timedelta(hours=4),
            "high": timedelta(hours=8),
            "medium": timedelta(hours=24),
            "low": timedelta(hours=48),
        }

        validated_data["sla_due_date"] = (
            timezone.now() + priority_sla_map[validated_data["priority"]]
        )

        return super().create(validated_data)
