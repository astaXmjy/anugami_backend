# views.py
import posixpath
import re
from urllib import request
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.authentication import TokenAuthentication
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.conf import settings
from django.http import HttpResponse, JsonResponse
import json
import logging
from sellers.models import ShippingLocation
from .permissions import (
    OrderModulePermission,
    IsOrderOwner,
    IsOrderCustomer,
    IsOrderSeller,
    CanProcessRefunds,
    CanManageShipping,
    CanCancelOrders,
    CanProcessPayments,
)
from .models import (
    Order,
    OrderItem,
    ShippingDetails,
    PaymentDetails,
    ShipmentStatusUpdate,
    RefundDetails,
    OrderAddress,
)
from .serializers import (
    OrderCreateSerializer,
    OrderListSerializer,
    OrderDetailSerializer,
    OrderUpdateSerializer,
    OrderStatusUpdateSerializer,
)
from .ship import ShiprocketService
from .phpe import PhonePeService
from sellers.models import ShippingLocation
from .seller_grouped import create_orders_from_cart_items

logger = logging.getLogger(__name__)


# Add to your views.py file
from django.views.generic import TemplateView
from django.shortcuts import render
from django.views import View
from orders.models import Order, PaymentDetails
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator



@method_decorator(csrf_exempt, name="dispatch")
class PaymentStatusView(View):
    def get(self, request):
        # For GET requests (rare with PhonePe)
        return self._handle_payment_status(request)

    def post(self, request):
        # PhonePe typically sends POST redirects
        return self._handle_payment_status(request)

    def _handle_payment_status(self, request):
        # Get parameters from the request
        transaction_id = request.GET.get("transactionId") or request.POST.get(
            "transactionId"
        )
        merchant_transaction_id = request.GET.get(
            "merchantTransactionId"
        ) or request.POST.get("merchantTransactionId")
        payment_status = request.GET.get("status") or request.POST.get("status")

        # Default context
        context = {
            "payment_status": "Unknown",
            "transaction_id": transaction_id or merchant_transaction_id,
            "message": "Unable to determine payment status",
        }

        # Try to find the payment
        if merchant_transaction_id:
            try:
                payment = PaymentDetails.objects.get(
                    transaction_id=merchant_transaction_id
                )
                order = payment.order

                context.update(
                    {
                        "payment_status": payment.payment_status,
                        "order_number": order.order_number,
                        "transaction_id": payment.transaction_id,
                        "amount": payment.amount_paid,
                        "message": self._get_status_message(payment.payment_status),
                    }
                )
            except PaymentDetails.DoesNotExist:
                context["message"] = "Payment record not found"

        # Use the status from PhonePe if available
        if payment_status:
            status_mapping = {
                "PAYMENT_SUCCESS": "paid",
                "PAYMENT_ERROR": "failed",
                "PAYMENT_DECLINED": "failed",
                "PAYMENT_CANCELLED": "failed",
            }
            context["payment_status"] = status_mapping.get(
                payment_status, payment_status
            )
            context["message"] = self._get_status_message(context["payment_status"])

        # Render a simple template
        return render(request, "payment_status.html", context)

    def _get_status_message(self, status):
        messages = {
            "paid": "Your payment was successful! Thank you for your order.",
            "pending": "Your payment is being processed. We will update you once confirmed.",
            "failed": "Your payment was not successful. Please try again or contact support.",
            "refund_initiated": "A refund has been initiated for your payment.",
            "refunded": "Your payment has been refunded.",
        }
        return messages.get(status, "Payment status is being verified.")


class OrderViewSet(viewsets.ModelViewSet):
    # authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]
    basename = "orders"

    def get_serializer_class(self):
        if self.action == "create":
            return OrderCreateSerializer
        elif self.action == "list" or self.action == "my_orders":
            return OrderListSerializer
        elif self.action == "update" or self.action == "partial_update":
            return OrderUpdateSerializer
        elif self.action == "update_status":
            return OrderStatusUpdateSerializer
        return OrderDetailSerializer

    def get_queryset(self):
        """
        Return filtered queryset based on user's role and permissions:
        - Superusers/Admins: See all orders
        - Users with orders.read permission: See all orders
        - Customers: See only their own orders
        - Sellers: See only orders they're selling
        """
        user = self.request.user
        queryset = Order.objects.prefetch_related(
            "items", "orderaddress_set", "shipping", "payment"
        )

        # Superusers and admins can see all orders
        if user.is_superuser or (hasattr(user, "is_admin") and user.is_admin):
            return queryset

        if hasattr(user, "seller_profile") and user.seller_profile:
            return queryset.filter(seller=user.seller_profile)

        # Users with orders.read permission via role-based system can see all orders
        if hasattr(user, "has_module_permission") and user.has_module_permission(
            "orders", "read"
        ):
            return queryset

        # Filter for customers - show only their orders
        if hasattr(user, "customer") and user.customer:
            return queryset.filter(user=user.customer)

        # Filter for sellers - show only orders where they are the seller

        # Fallback: Legacy staff permission
        if user.is_staff and user.has_perm("orders.view_order"):
            return queryset

        # Default return empty queryset if no matching criteria
        return Order.objects.none()

    def get_permissions(self):

        permission_classes = [IsAuthenticated]
        if (
            self.action == "create"
            or self.action == "checkout"
            or self.action == "create_shipment"
            or self.action == "check_serviceability"
        ):
            # Any authenticated user can create order
            pass
        elif self.action in ["list", "my_orders"]:
            # Use role-based permission with object-level filtering in get_queryset
            permission_classes.append(OrderModulePermission)
        elif self.action == "retrieve":
            # Use OrderModulePermission to handle object-level permissions
            permission_classes.append(OrderModulePermission)
        elif self.action in ["update", "partial_update", "update_status"]:
            # Only users with orders.update permission or sellers for their own orders
            permission_classes.append(OrderModulePermission)
        elif self.action == "cancel" or self.action == "cancel_shipment":
            # Customers can cancel own orders, sellers can cancel their orders
            permission_classes.append(CanCancelOrders)
        elif self.action in ["refund_payment", "check_refund_status"]:
            # Only staff with refund permission or sellers for their own orders
            permission_classes.append(CanProcessRefunds)
        elif self.action in [
            "update_shipment",
            "mark_as_shipped",
            "create_shipment",
            "generate_label",
            "generate_manifest",
            "request_pickup",
            "track",
            "mark_as_delivered",
        ]:
            # Only staff with shipping permission or sellers for their own orders
            permission_classes.append(CanManageShipping)
        elif self.action in ["initiate_payment", "check_payment_status"]:
            # Sellers for their orders, customers for their orders
            permission_classes.append(CanProcessPayments)
        elif self.action in ["phonepe_callback", "shiprocket_webhook"]:
            # Webhook endpoints don't need authentication
            return [AllowAny()]
        else:
            # Default to our OrderModulePermission which handles both role-basedc
            # and object-level permissions
            permission_classes.append(OrderModulePermission)
        return [permission() for permission in permission_classes]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            with transaction.atomic():
                order = serializer.save()
                return Response(
                    {
                        "message": "Order created successfully",
                        "order_id": order.id,
                        "order_number": order.order_number,
                    },
                    status=status.HTTP_201_CREATED,
                )
        except Exception as e:
            return Response(
                {"error": "Failed to create order", "detail": str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)

        try:
            with transaction.atomic():
                order = serializer.save()
                response_serializer = OrderDetailSerializer(order)
                return Response(response_serializer.data)
        except Exception as e:
            return Response(
                {"error": "Failed to update order", "detail": str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )

    @action(detail=False, methods=["GET"])
    def my_orders(self, request):
        """Get orders for the currently logged in user (customer or seller)"""
        user = request.user
        queryset = Order.objects.none()  # Start with empty queryset

        # If user has a customer profile, get their orders
        if hasattr(user, "customer") and user.customer:
            logger.info(f"Customer {user.customer.id} requesting their orders")
            queryset = Order.objects.filter(user=user.customer)

        # If user has a seller profile, get their seller orders
        elif hasattr(user, "seller_profile") and user.seller_profile:
            logger.info(f"Seller {user.seller_profile.id} requesting their orders")
            queryset = Order.objects.filter(seller=user.seller_profile)

        # Apply prefetch for better performance
        queryset = queryset.prefetch_related(
            "items", "orderaddress_set", "shipping", "payment"
        )

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["POST"])
    def update_status(self, request, pk=None):
        order = self.get_object()
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            with transaction.atomic():
                order.status = serializer.validated_data["status"]
                if "notes" in serializer.validated_data:
                    order.notes = serializer.validated_data["notes"]
                order.save()

                response_serializer = OrderDetailSerializer(order)
                return Response(response_serializer.data)
        except Exception as e:
            return Response(
                {"error": "Failed to update status", "detail": str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )

    @action(detail=True, methods=["GET"])
    def track(self, request, pk=None):
        order = self.get_object()

        # Check if order has shipping details
        if hasattr(order, "shipping"):
            shipping = order.shipping

            # If it's a Shiprocket order with a shipment_id
            if shipping.provider == "shiprocket" and shipping.shipment_id:
                # Get tracking details from Shiprocket API
                shiprocket_service = ShiprocketService()
                tracking_details = shiprocket_service.get_tracking_details(
                    shipment_id=shipping.shipment_id
                )

                if "error" not in tracking_details:
                    # Update status if needed
                    if tracking_details.get("tracking_data") and tracking_details[
                        "tracking_data"
                    ].get("shipment_track"):
                        current_status = tracking_details["tracking_data"][
                            "shipment_track"
                        ][0].get("current_status")
                        if current_status and current_status != shipping.status:
                            shipping.status = current_status
                            shipping.save()

                            # Store tracking history
                            if (
                                "tracking_data" in tracking_details
                                and "shipment_track_activities"
                                in tracking_details["tracking_data"]
                            ):
                                activities = tracking_details["tracking_data"][
                                    "shipment_track_activities"
                                ]
                                for activity in activities:
                                    ShipmentStatusUpdate.objects.get_or_create(
                                        shipping=shipping,
                                        status=activity.get("status", ""),
                                        status_date=timezone.datetime.strptime(
                                            activity.get("date", ""),
                                            "%Y-%m-%d %H:%M:%S",
                                        ),
                                        location=activity.get("location", ""),
                                        activity=activity.get("activity", ""),
                                        additional_info=activity,
                                    )

                    # Prepare response data
                    status_updates = ShipmentStatusUpdate.objects.filter(
                        shipping=shipping
                    )
                    status_history = []
                    for update in status_updates:
                        status_history.append(
                            {
                                "status": update.status,
                                "date": update.status_date,
                                "location": update.location,
                                "activity": update.activity,
                            }
                        )

                    return Response(
                        {
                            "order_number": order.order_number,
                            "status": order.status,
                            "shipping_details": {
                                "provider": "Shiprocket",
                                "tracking_id": shipping.shipment_id,
                                "awb_code": shipping.awb_number,
                                "courier": shipping.courier_name,
                                "tracking_url": shipping.tracking_url,
                                "status": shipping.status,
                                "status_history": status_history,
                                "pickup_date": shipping.pickup_scheduled,
                                "label_url": shipping.label_url,
                                "manifest_url": shipping.manifest_url,
                            },
                        }
                    )

            # Return standard shipping details
            return Response(
                {
                    "order_number": order.order_number,
                    "status": order.status,
                    "shipping_details": {
                        "tracking_id": shipping.tracking_id,
                        "courier": shipping.courier_name,
                        "tracking_url": shipping.tracking_url,
                        "status": shipping.status,
                        "expected_delivery": shipping.expected_delivery,
                    },
                }
            )

        return Response(
            {"error": "No shipping information available"},
            status=status.HTTP_404_NOT_FOUND,
        )

    @action(detail=False, methods=["POST"])
    def checkout(self, request):
        """
        Process checkout using existing cart items in the database
        and automatically create shipments using seller's shipping location
        """
        shipping_address = request.data.get("shipping_address", {})
        payment_method = request.data.get("payment_method", "COD")
        clear_cart = request.data.get("clear_cart", False)

        try:
            # Use your existing utility function to create orders from cart items

            logger.info(f"Starting checkout for user: {request.user}")
            orders = create_orders_from_cart_items(request.user)

            if not orders:
                logger.warning("No orders were created during checkout")
                return Response(
                    {"error": "No orders could be created. Your cart may be empty."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            logger.info(
                f"Created {len(orders)} orders, now adding shipping and payment details"
            )

            # Add shipping address, payment details and initialize shipping for each order
            for order in orders:
                try:
                    # Add shipping address
                    if shipping_address:
                        # Get customer
                        customer = request.user.customer

                        # Create shipping address
                        OrderAddress.objects.create(
                            order=order,
                            address_type="shipping",
                            full_name=shipping_address.get(
                                "full_name", customer.full_name
                            ),
                            phone=shipping_address.get("phone", customer.phone),
                            email=shipping_address.get("email", customer.email),
                            street=shipping_address.get("street", ""),
                            area=shipping_address.get("area", ""),
                            landmark=shipping_address.get("landmark", ""),
                            city=shipping_address.get("city", ""),
                            state=shipping_address.get("state", ""),
                            country=shipping_address.get("country", "India"),
                            pincode=shipping_address.get("pincode", ""),
                        )

                        # Use same address for billing if not provided separately
                        if shipping_address.get("use_for_billing", True):
                            OrderAddress.objects.create(
                                order=order,
                                address_type="billing",
                                full_name=shipping_address.get(
                                    "full_name", customer.full_name
                                ),
                                phone=shipping_address.get("phone", customer.phone),
                                email=shipping_address.get("email", customer.email),
                                street=shipping_address.get("street", ""),
                                area=shipping_address.get("area", ""),
                                landmark=shipping_address.get("landmark", ""),
                                city=shipping_address.get("city", ""),
                                state=shipping_address.get("state", ""),
                                country=shipping_address.get("country", "India"),
                                pincode=shipping_address.get("pincode", ""),
                            )

                    # Create payment details
                    PaymentDetails.objects.create(
                        order=order, method=payment_method, payment_status="pending"
                    )

                    # Calculate package dimensions based on items
                    # This is a simplified calculation
                    items = order.items.all()
                    total_weight = sum(
                        item.quantity * 0.5 for item in items
                    )  # Assuming 0.5 kg per item

                    # Create shipping details record
                    shipping = ShippingDetails.objects.create(
                        order=order,
                        provider="shiprocket",
                        weight=max(0.5, total_weight),
                        length=20,  # Default dimensions in cm
                        width=15,
                        height=10,
                        pickup_location=order.seller.business_name,  # Use seller's business name
                    )

                    logger.info(
                        f"Added shipping and payment details to order {order.id}"
                    )

                except Exception as e:
                    logger.error(f"Error adding details to order {order.id}: {str(e)}")

            # Now create shipments for each order
            logger.info("Starting shipment creation for all orders")
            shipment_results = []

            shiprocket_service = ShiprocketService()

            for order in orders:
                try:
                    # Get seller
                    seller = order.seller
                    logger.info(
                        f"Creating shipment for order {order.id} from seller {seller.id}"
                    )

                    shipping_location = ShippingLocation.objects.filter(
                        seller=seller
                    ).first()

                    if not shipping_location:
                        error_msg = f"No shipping location found for seller {seller.business_name}"
                        logger.error(error_msg)

                        shipment_results.append(
                            {
                                "order_id": order.id,
                                "order_number": order.order_number,
                                "success": False,
                                "seller": seller.business_name,
                                "error": error_msg,
                            }
                        )
                        continue

                    # Create pickup address from seller's shipping location
                    pickup_address = {
                        "name": "Primary",
                        "address": shipping_location.address,
                        "city": shipping_location.city,
                        "state": shipping_location.state,
                        "pincode": shipping_location.pincode,
                        "phone": shipping_location.phone_number,
                    }

                    logger.info(f"Using pickup address: {pickup_address}")

                    # Call the Shiprocket service to create shipment
                    shipment_response = shiprocket_service.create_order(
                        order, pickup_address
                    )

                    if "error" not in shipment_response:
                        # Update shipping details with shipment info
                        shipping = order.shipping

                        # Update with shipment details from response
                        if "order_id" in shipment_response:
                            shipping.shiprocket_order_id = shipment_response["order_id"]
                        if "shipment_id" in shipment_response:
                            shipping.shipment_id = shipment_response["shipment_id"]
                        if "awb_code" in shipment_response:
                            shipping.awb_number = shipment_response["awb_code"]
                        if "courier_name" in shipment_response:
                            shipping.courier_name = shipment_response["courier_name"]
                        if "courier_company_id" in shipment_response:
                            shipping.courier_company_id = shipment_response[
                                "courier_company_id"
                            ]
                        if (
                            "tracking_url" in shipment_response
                            and shipment_response["tracking_url"]
                        ):
                            shipping.tracking_url = shipment_response["tracking_url"]

                        shipping.shiprocket_response = shipment_response
                        shipping.status = "Order Created in Shiprocket"
                        shipping.save()

                        # Update order status
                        order.status = "processing"
                        order.save()

                        logger.info(
                            f"Shipment created successfully for order {order.id}"
                        )

                        # Add success result
                        shipment_results.append(
                            {
                                "order_id": order.id,
                                "order_number": order.order_number,
                                "success": True,
                                "message": "Shipment created successfully",
                                "shipment_id": shipping.shipment_id,
                                "seller": seller.business_name,
                                "pickup_location": shipping.pickup_location,
                            }
                        )
                    else:
                        logger.error(
                            f"Failed to create shipment for order {order.id}: {shipment_response.get('error')}"
                        )

                        # Add error result
                        shipment_results.append(
                            {
                                "order_id": order.id,
                                "order_number": order.order_number,
                                "success": False,
                                "seller": seller.business_name,
                                "error": shipment_response.get(
                                    "error", "Failed to create shipment"
                                ),
                            }
                        )

                except Exception as e:
                    logger.error(
                        f"Error creating shipment for order {order.id}: {str(e)}"
                    )
                    shipment_results.append(
                        {
                            "order_id": order.id,
                            "order_number": order.order_number,
                            "success": False,
                            "seller": (
                                order.seller.business_name
                                if order.seller
                                else "Unknown"
                            ),
                            "error": str(e),
                        }
                    )
            for order in orders:
                try:
                    send_order_details_email(order)
                    logger.info(f"Sent order confirmation email for order {order.id}")
                except Exception as e:
                    logger.error(
                        f"Error sending order confirmation email for order {order.id}: {str(e)}"
                    )
            # Return both order and shipment information
            logger.info("Checkout completed successfully")
            return Response(
                {
                    "success": True,
                    "message": f"Created {len(orders)} orders with shipments",
                    "orders": OrderDetailSerializer(orders, many=True).data,
                    "shipments": shipment_results,
                },
                status=status.HTTP_201_CREATED,
            )

        except ValueError as e:
            logger.error(f"Checkout validation error: {str(e)}")
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Unexpected checkout error: {str(e)}")
            return Response(
                {"error": f"Failed to process checkout: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @action(detail=True, methods=["POST"])
    def create_shipment(self, request, pk=None):
        """
        Create a shipment with Shiprocket for the order
        """

        order = get_object_or_404(Order, id=pk)

        # Check if order already has shipping details
        if hasattr(order, "shipping") and order.shipping.shipment_id:
            return Response(
                {
                    "error": "Shipment already created for this order",
                    "shipment_id": order.shipping.shipment_id,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        seller = order.seller
        shipping_location = ShippingLocation.objects.filter(seller=seller).first()
        # Get pickup address from request or use default
        pickup_address = {
            "name": "Primary",
            "address": shipping_location.address,
            "city": shipping_location.city,
            "state": shipping_location.state,
            "pincode": shipping_location.pincode,
            "phone": shipping_location.phone_number,
        }

        # Initialize Shiprocket service
        shiprocket_service = ShiprocketService()

        # Create shipment
        shipment_response = shiprocket_service.create_order(order, pickup_address)

        if "error" not in shipment_response:
            # Create or update shipping details
            shipping, created = ShippingDetails.objects.get_or_create(
                order=order,
                defaults={
                    "provider": "shiprocket",
                    "weight": request.data.get("weight", 0.5),
                    "length": request.data.get("length", 10),
                    "width": request.data.get("width", 10),
                    "height": request.data.get("height", 10),
                    "pickup_location": pickup_address.get("name", "Default Location"),
                },
            )

            # Update with shipment details
            if "order_id" in shipment_response:
                shipping.shiprocket_order_id = shipment_response["order_id"]
            if "shipment_id" in shipment_response:
                shipping.shipment_id = shipment_response["shipment_id"]
            if "awb_code" in shipment_response:
                shipping.awb_number = shipment_response["awb_code"]
            if "courier_name" in shipment_response:
                shipping.courier_name = shipment_response["courier_name"]
            if "courier_company_id" in shipment_response:
                shipping.courier_company_id = shipment_response["courier_company_id"]
            if (
                "tracking_url" in shipment_response
                and shipment_response["tracking_url"]
            ):
                shipping.tracking_url = shipment_response["tracking_url"]

            shipping.shiprocket_response = shipment_response
            shipping.status = "Order Created in Shiprocket"
            shipping.save()

            # Update order status if it's still pending
            if order.status == "pending":
                order.status = "processing"
                order.save()

            try:
                send_order_details_email(order)
                logger.info(f"Sent order confirmation email for order {order.id}")
            except Exception as e:
                logger.error(
                    f"Error sending order confirmation email for order {order.id}: {str(e)}"
                )

            return Response(
                {
                    "success": True,
                    "message": "Shipment created successfully",
                    "shipment_id": shipping.shipment_id,
                    "order_id": shipping.shiprocket_order_id,
                }
            )
        else:
            return Response(
                {
                    "success": False,
                    "error": shipment_response.get(
                        "error", "Failed to create shipment"
                    ),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

    @action(detail=True, methods=["POST"])
    def generate_label(self, request, pk=None):
        """
        Generate shipping label for the order
        """
        order = get_object_or_404(Order, id=pk)
     

        if not hasattr(order, "shipping") or not order.shipping.shipment_id:
            return Response(
                {"error": "No shipment found for this order"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Initialize Shiprocket service
        shiprocket_service = ShiprocketService()

        # Generate label
        label_response = shiprocket_service.generate_label(order.shipping.shipment_id)

        if "error" not in label_response:
            # Update shipping details with label URL
            if "label_url" in label_response:
                order.shipping.label_url = label_response["label_url"]
                order.shipping.save()

            return Response({"success": True, "label_url": order.shipping.label_url})
        else:
            return Response(
                {
                    "success": False,
                    "error": label_response.get("error", "Failed to generate label"),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

    @action(detail=True, methods=["POST"])
    def generate_manifest(self, request, pk=None):
        """
        Generate manifest for the order shipment
        """
        order = get_object_or_404(Order, id=pk)

        if not hasattr(order, "shipping") or not order.shipping.shipment_id:
            return Response(
                {"error": "No shipment found for this order"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Initialize Shiprocket service
        shiprocket_service = ShiprocketService()

        # Generate manifest
        manifest_response = shiprocket_service.generate_manifest(
            [order.shipping.shipment_id]
        )

        if "error" not in manifest_response:
            # Update shipping details with manifest URL
            if "manifest_url" in manifest_response:
                order.shipping.manifest_url = manifest_response["manifest_url"]
                order.shipping.save()

            return Response(
                {"success": True, "manifest_url": order.shipping.manifest_url}
            )
        else:
            return Response(
                {
                    "success": False,
                    "error": manifest_response.get(
                        "error", "Failed to generate manifest"
                    ),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

    @action(detail=True, methods=["POST"])
    def request_pickup(self, request, pk=None):
        """
        Request pickup for the order shipment
        """
        order = get_object_or_404(Order, id=pk)

        if not hasattr(order, "shipping") or not order.shipping.shipment_id:
            return Response(
                {"error": "No shipment found for this order"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Get pickup date from request or use tomorrow
        pickup_date = request.data.get(
            "pickup_date", (timezone.now() + timezone.timedelta(days=1)).date()
        )

        # Initialize Shiprocket service
        shiprocket_service = ShiprocketService()

        # Request pickup
        pickup_response = shiprocket_service.request_pickup(
            order.shipping.shipment_id, pickup_date
        )

        if "error" not in pickup_response:
            # Update shipping details with pickup details
            if "pickup_scheduled_date" in pickup_response:
                order.shipping.pickup_scheduled = pickup_response[
                    "pickup_scheduled_date"
                ]
            if "pickup_token_number" in pickup_response:
                order.shipping.pickup_token_number = pickup_response[
                    "pickup_token_number"
                ]

            order.shipping.status = "Pickup Scheduled"
            order.shipping.save()

            return Response(
                {
                    "success": True,
                    "message": "Pickup requested successfully",
                    "pickup_date": order.shipping.pickup_scheduled,
                }
            )
        else:
            return Response(
                {
                    "success": False,
                    "error": pickup_response.get("error", "Failed to request pickup"),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

    @action(detail=True, methods=["POST"])
    def cancel_shipment(self, request, pk=None):
        """
        Cancel shipment for the order
        """
        order = get_object_or_404(Order, id=pk)

        if not hasattr(order, "shipping") or not order.shipping.shipment_id:
            return Response(
                {"error": "No shipment found for this order"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Initialize Shiprocket service
        shiprocket_service = ShiprocketService()

        # Cancel shipment
        cancel_response = shiprocket_service.cancel_shipment(order.shipping.shipment_id)

        if "error" not in cancel_response:
            # Update shipping details
            order.shipping.status = "Cancelled"
            order.shipping.save()

            # Update order status
            order.status = "cancelled"
            order.save()

            return Response(
                {"success": True, "message": "Shipment cancelled successfully"}
            )
        else:
            return Response(
                {
                    "success": False,
                    "error": cancel_response.get("error", "Failed to cancel shipment"),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

    @action(detail=True, methods=["GET"])
    def download_invoice(self, request, pk=None):
        """
        Download invoice PDF for an order
        """
        from email_template.views import send_order_invoice_email
        from django.http import HttpResponse

        order = get_object_or_404(Order, id=pk)
        pdf_content = send_order_invoice_email(order)

        if pdf_content:
            response = HttpResponse(pdf_content, content_type="application/pdf")
            response["Content-Disposition"] = (
                f'attachment; filename="invoice_{order.order_number}.pdf"'
            )
            return response

        return Response(
            {"error": "Failed to generate invoice"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    @action(detail=True, methods=["POST"])
    def initiate_payment(self, request, pk=None):
        """
        Initiate payment for an order using PhonePe
        """
        order = get_object_or_404(Order, id=pk)
        print(order)
        # Check if order is already paid
        if hasattr(order, "payment") and order.payment.payment_status == "paid":
            return Response(
                {"error": "Order is already paid"}, status=status.HTTP_400_BAD_REQUEST
            )

        # Define callback and redirect URLs
        callback_url = request.data.get("callback_url", settings.PHONEPE_CALLBACK_URL)
        redirect_url = request.data.get("redirect_url", settings.PHONEPE_REDIRECT_URL)

        # Initialize PhonePe service
        phonepe_service = PhonePeService()

        # Create payment request
        payment_response = phonepe_service.create_payment(
            order, callback_url, redirect_url
        )
        if payment_response.get("success"):
            # Create or update payment details
            payment, created = PaymentDetails.objects.get_or_create(
                order=order,
                defaults={
                    "method": "PhonePe-UPI",  # Default to UPI, can be updated later
                    "payment_status": "pending",
                    "amount_paid": order.total_amount,
                },
            )

            # Update with PhonePe details
            payment.transaction_id = payment_response.get("transaction_id")
            payment.phonepe_transaction_id = payment_response.get(
                "phonepe_transaction_id"
            )
            payment.phonepe_status = "PAYMENT_INITIATED"
            payment.payment_url = payment_response.get("payment_url")
            payment.callback_url = callback_url
            payment.redirect_url = redirect_url
            payment.phonepe_response = payment_response
            payment.save()

            return Response(
                {
                    "success": True,
                    "payment_url": payment_response.get("payment_url"),
                    "transaction_id": payment_response.get("transaction_id"),
                }
            )
        else:
            return Response(
                {
                    "success": False,
                    "error": payment_response.get("error", "Payment initiation failed"),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

    @action(detail=True, methods=["GET"])
    def check_payment_status(self, request, pk=None):
        """
        Check payment status for an order
        """
        order = get_object_or_404(Order, id=pk)

        # Check if order has payment details
        if not hasattr(order, "payment"):
            return Response(
                {"success": False, "error": "No payment found for this order"},
                status=status.HTTP_404_NOT_FOUND,
            )

        payment = order.payment

        if not payment.transaction_id:
            return Response(
                {"success": False, "error": "No transaction ID found for this payment"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Initialize PhonePe service
        phonepe_service = PhonePeService()

        # Check payment status
        status_response = phonepe_service.check_payment_status(payment.transaction_id)

        if status_response.get("success"):
            # Update payment details
            payment.phonepe_status = status_response.get("status")
            payment.phonepe_response = status_response.get("response")

            # Update payment status based on PhonePe status
            if status_response.get("status") == "PAYMENT_SUCCESS":
                payment.payment_status = "paid"
                payment.amount_paid = status_response.get("amount")
                # Update order status
                if order.status == "pending":
                    order.status = "confirmed"
                    order.save()
            elif status_response.get("status") in [
                "PAYMENT_DECLINED",
                "PAYMENT_ERROR",
                "PAYMENT_CANCELLED",
            ]:
                payment.payment_status = "failed"

            payment.save()

            return Response(
                {
                    "success": True,
                    "transaction_id": payment.transaction_id,
                    "status": payment.phonepe_status,
                    "payment_status": payment.payment_status,
                    "amount": float(payment.amount_paid if payment.amount_paid else 0),
                }
            )
        else:
            return Response(
                {
                    "success": False,
                    "error": status_response.get(
                        "error", "Failed to check payment status"
                    ),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

    @action(detail=True, methods=["POST"])
    def refund_payment(self, request, pk=None):
        """
        Initiate refund for an order payment
        """
        order = order = get_object_or_404(Order, id=pk)

        # Validate request data
        refund_amount = request.data.get("amount")
        reason = request.data.get("reason", "Customer requested refund")

        if not refund_amount:
            return Response(
                {"success": False, "error": "Refund amount is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            refund_amount = float(refund_amount)
        except ValueError:
            return Response(
                {"success": False, "error": "Invalid refund amount"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Check if order has payment details
        if not hasattr(order, "payment"):
            return Response(
                {"success": False, "error": "No payment found for this order"},
                status=status.HTTP_404_NOT_FOUND,
            )

        payment = order.payment

        # Check if payment was successful
        if payment.payment_status != "paid":
            return Response(
                {
                    "success": False,
                    "error": "Cannot refund payment that was not successful",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Initialize PhonePe service
        phonepe_service = PhonePeService()

        # Process refund
        refund_response = phonepe_service.process_refund(
            payment.phonepe_transaction_id or payment.transaction_id,
            refund_amount,
            reason=reason,
        )

        if refund_response.get("success"):
            # Create refund record
            refund = RefundDetails.objects.create(
                payment=payment,
                refund_id=refund_response.get("refund_id"),
                refund_amount=refund_amount,
                status=refund_response.get("status", "REFUND_INITIATED"),
                reason=reason,
                raw_response=refund_response,
            )

            # Update payment details
            payment.refund_status = "refund_initiated"
            payment.refund_amount = refund_amount
            payment.save()

            return Response(
                {
                    "success": True,
                    "refund_id": refund.refund_id,
                    "status": refund.status,
                    "amount": float(refund.refund_amount),
                }
            )
        else:
            return Response(
                {
                    "success": False,
                    "error": refund_response.get("error", "Refund processing failed"),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

    @action(detail=True, methods=["GET"])
    def check_refund_status(self, request, pk=None):
        """
        Check refund status for an order
        """
        order = order = get_object_or_404(Order, id=pk)
        refund_id = request.query_params.get("refund_id")

        if not refund_id:
            return Response(
                {"success": False, "error": "Refund ID is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Check if order has payment details
        if not hasattr(order, "payment"):
            return Response(
                {"success": False, "error": "No payment found for this order"},
                status=status.HTTP_404_NOT_FOUND,
            )

        payment = order.payment

        try:
            refund = RefundDetails.objects.get(payment=payment, refund_id=refund_id)

            # Initialize PhonePe service
            phonepe_service = PhonePeService()

            # Check refund status
            status_response = phonepe_service.check_refund_status(refund.refund_id)

            if status_response.get("success"):
                # Update refund status
                refund.status = status_response.get("status")
                refund.raw_response = status_response.get("response")
                refund.save()

                # Update payment details
                if status_response.get("status") == "REFUND_SUCCESS":
                    payment.refund_status = "refunded"
                    payment.save()

                return Response(
                    {
                        "success": True,
                        "refund_id": refund.refund_id,
                        "status": refund.status,
                        "amount": float(refund.refund_amount),
                    }
                )
            else:
                return Response(
                    {
                        "success": False,
                        "error": status_response.get(
                            "error", "Failed to check refund status"
                        ),
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

        except RefundDetails.DoesNotExist:
            return Response(
                {"success": False, "error": "No refund found with this ID"},
                status=status.HTTP_404_NOT_FOUND,
            )

    @action(detail=False, methods=["POST"])
    def phonepe_callback(self, request):
        """
        Callback endpoint for PhonePe payment notifications
        """
        # Get the callback data
        try:
            payload = request.data.get("response")
            if not payload:
                return Response(
                    {"status": "error", "message": "Invalid callback data"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Initialize PhonePe service
            phonepe_service = PhonePeService()

            # Verify checksum if provided
            checksum = request.headers.get("X-VERIFY")
            if checksum and not phonepe_service._verify_checksum(payload, checksum):
                return Response(
                    {"status": "error", "message": "Invalid checksum"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Parse payload
            transaction_id = payload.get("merchantTransactionId")
            if not transaction_id:
                return Response(
                    {"status": "error", "message": "Missing transaction ID"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Find the payment
            try:
                payment = PaymentDetails.objects.get(transaction_id=transaction_id)
            except PaymentDetails.DoesNotExist:
                return Response(
                    {"status": "error", "message": "Payment not found"},
                    status=status.HTTP_404_NOT_FOUND,
                )

            # Update payment status
            payment_status = payload.get("code")
            if payment_status == "PAYMENT_SUCCESS":
                payment.payment_status = "paid"
                payment.phonepe_status = "PAYMENT_SUCCESS"
                payment.amount_paid = (
                    float(payload.get("amount", 0)) / 100
                )  # Convert paise to rupees

                # Update order status
                payment.order.status = "confirmed"
                payment.order.save()
            elif payment_status in [
                "PAYMENT_ERROR",
                "PAYMENT_DECLINED",
                "PAYMENT_CANCELLED",
            ]:
                payment.payment_status = "failed"
                payment.phonepe_status = payment_status

            # Save payment response
            payment.phonepe_response = payload
            payment.save()

            return Response(
                {"status": "success", "message": "Callback processed successfully"}
            )

        except Exception as e:
            logger.error(f"Error processing PhonePe callback: {str(e)}")
            return Response(
                {"status": "error", "message": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @action(detail=False, methods=["POST"])
    def shiprocket_webhook(self, request):
        """
        Webhook endpoint for Shiprocket status updates
        """
        try:
            # Get webhook data
            webhook_data = request.data
            if not webhook_data:
                return Response(
                    {"status": "error", "message": "Invalid webhook data"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Find the shipping record by awb or shipment_id
            awb = webhook_data.get("awb")
            shipment_id = webhook_data.get("shipment_id")

            shipping = None
            if awb:
                try:
                    shipping = ShippingDetails.objects.get(awb_number=awb)
                except ShippingDetails.DoesNotExist:
                    pass

            if not shipping and shipment_id:
                try:
                    shipping = ShippingDetails.objects.get(shipment_id=shipment_id)
                except ShippingDetails.DoesNotExist:
                    return Response(
                        {"status": "error", "message": "Shipping not found"},
                        status=status.HTTP_404_NOT_FOUND,
                    )

            if not shipping:
                return Response(
                    {"status": "error", "message": "Shipping not found"},
                    status=status.HTTP_404_NOT_FOUND,
                )

            # Get order
            order = shipping.order

            # Update shipping status
            current_status = webhook_data.get("current_status")
            if current_status:
                shipping.status = current_status

                # Add to status updates
                ShipmentStatusUpdate.objects.create(
                    shipping=shipping,
                    status=current_status,
                    status_date=timezone.now(),
                    activity=webhook_data.get("activity", "Status update from webhook"),
                    location=webhook_data.get("location"),
                    additional_info=webhook_data,
                )

                # Update order status based on shipping status
                if current_status == "Delivered":
                    order.status = "delivered"
                    order.save()
                elif current_status == "Shipped":
                    order.status = "shipped"
                    order.save()
                elif current_status == "Cancelled":
                    order.status = "cancelled"
                    order.save()

                # Save shipping changes
                shipping.shiprocket_response = webhook_data
                shipping.save()

            return Response(
                {"status": "success", "message": "Webhook processed successfully"}
            )

        except Exception as e:
            logger.error(f"Error processing Shiprocket webhook: {str(e)}")
            return Response(
                {"status": "error", "message": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @action(detail=True, methods=["GET"])
    def check_serviceability(self, request, pk=None):
        """
        Check shipping serviceability for an order using:
        - Pickup pincode from seller's first shipping location
        - Delivery pincode from order's customer address
        - Weight/dimensions from the order itself
        """
        try:
            order = get_object_or_404(Order, id=pk)  # Get order by ID

            # 1. Get delivery pincode from order (required)
            delivery_pincode = request.query_params.get("delivery_pincode")
            if not delivery_pincode:
                return Response(
                    {"success": False, "error": "Order missing delivery pincode"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # 2. Get pickup pincode from seller's shipping locations
            shipping_locations = ShippingLocation.objects.filter(seller=order.seller)
            if not shipping_locations.exists():
                return Response(
                    {
                        "success": False,
                        "error": "Seller has no shipping locations configured",
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )
            shipping_locations = shipping_locations.first()
            pickup_pincode = shipping_locations.pincode

            # 3. Prepare shipment parameters
            weight = 0.5  # Default to 0.5kg if not set
            dimensions = {
                "length": 10,
                "width": 10,
                "height": 10,
            }
            is_cod = request.data.get("is_cod", False)

            # 4. Call Shiprocket API
            shiprocket_service = ShiprocketService()
            serviceability = shiprocket_service.check_serviceability(
                pickup_pincode=pickup_pincode,
                delivery_pincode=delivery_pincode,
                weight=weight,
                cod=is_cod,
                # Pass dimensions if your ShiprocketService supports them
            )

            # 5. Format response
            if "error" in serviceability:
                return Response(
                    {"success": False, "error": serviceability["error"]},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            courier_options = []
            if serviceability.get("data", {}).get("available_courier_companies"):
                for courier in serviceability["data"]["available_courier_companies"]:
                    courier_options.append(
                        {
                            "courier_id": courier.get("courier_company_id"),
                            "courier_name": courier.get("courier_name"),
                            "delivery_days": courier.get("estimated_delivery_days"),
                            "rate": courier.get("rate"),
                            "cod_available": courier.get("is_cod_available", False),
                            "rating": courier.get("rating", 0),
                        }
                    )

            return Response(
                {
                    "success": True,
                    "pickup_pincode": pickup_pincode,
                    "delivery_pincode": delivery_pincode,
                    "weight_kg": weight,
                    "cod_available": is_cod,
                    "couriers": courier_options,
                    "is_serviceable": bool(courier_options),
                }
            )

        except Order.DoesNotExist:
            return Response(
                {"success": False, "error": "Order not found"},
                status=status.HTTP_404_NOT_FOUND,
            )
        except Exception as e:
            logger.error(f"Serviceability check failed: {str(e)}")
            return Response(
                {"success": False, "error": "Internal server error"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @action(detail=True, methods=["POST"])
    def mark_as_shipped(self, request, pk=None):
        """
        Manually mark an order as shipped
        """
        order = self.get_object()

        # Check if it can be marked as shipped
        if order.status not in ["processing", "confirmed"]:
            return Response(
                {
                    "success": False,
                    "error": f"Order cannot be marked as shipped from {order.status} status",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Get tracking details from request
        tracking_id = request.data.get("tracking_id")
        courier_name = request.data.get("courier_name")

        if not tracking_id or not courier_name:
            return Response(
                {
                    "success": False,
                    "error": "Tracking ID and courier name are required",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Update order status
        with transaction.atomic():
            order.status = "shipped"
            order.save()

            # Create or update shipping details
            shipping, created = ShippingDetails.objects.get_or_create(
                order=order,
                defaults={
                    "provider": "manual",
                    "weight": 0.5,
                    "length": 10,
                    "width": 10,
                    "height": 10,
                    "pickup_location": "Manual Entry",
                },
            )

            shipping.tracking_id = tracking_id
            shipping.awb_number = tracking_id
            shipping.courier_name = courier_name
            shipping.status = "Shipped"
            shipping.save()

            # Add status update
            ShipmentStatusUpdate.objects.create(
                shipping=shipping,
                status="Shipped",
                status_date=timezone.now(),
                activity="Order marked as shipped manually",
                location="",
            )

        return Response(
            {
                "success": True,
                "message": "Order marked as shipped successfully",
                "order_status": order.status,
            }
        )

    @action(detail=True, methods=["POST"])
    def mark_as_delivered(self, request, pk=None):
        """
        Manually mark an order as delivered
        """
        order = self.get_object()

        # Check if it can be marked as delivered
        if order.status != "shipped":
            return Response(
                {
                    "success": False,
                    "error": f"Order cannot be marked as delivered from {order.status} status",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Update order status
        with transaction.atomic():
            order.status = "delivered"
            order.save()

            # Update shipping details if exists
            if hasattr(order, "shipping"):
                shipping = order.shipping
                shipping.status = "Delivered"
                shipping.save()

                # Add status update
                ShipmentStatusUpdate.objects.create(
                    shipping=shipping,
                    status="Delivered",
                    status_date=timezone.now(),
                    activity="Order marked as delivered manually",
                    location="",
                )

        return Response(
            {
                "success": True,
                "message": "Order marked as delivered successfully",
                "order_status": order.status,
            }
        )

    @action(detail=False, methods=["GET"])
    def get_pickup_locations(self, request):
        """
        Get all pickup locations from Shiprocket
        """
        # Initialize Shiprocket service
        shiprocket_service = ShiprocketService()

        # Get pickup locations
        pickup_locations = shiprocket_service.get_all_pickup_locations()

        if "error" not in pickup_locations:
            return Response(
                {
                    "success": True,
                    "pickup_locations": pickup_locations.get("data", {}).get(
                        "shipping_address", []
                    ),
                }
            )
        else:
            return Response(
                {
                    "success": False,
                    "error": pickup_locations.get(
                        "error", "Failed to get pickup locations"
                    ),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
