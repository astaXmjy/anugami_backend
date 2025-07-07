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
from .ship import ShipmojoService
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

    @action(detail=False, methods=["POST"])
    def checkout(self, request):
        """
        Process checkout using existing cart items in the database
        and create orders ready for shipment creation
        """
        shipping_address = request.data.get("shipping_address", {})
        payment_method = request.data.get("payment_method", "COD")
        auto_create_shipments = request.data.get("auto_create_shipments", False)
        print(shipping_address)

        try:
            print("orders bnane ke liye aage badh chuke h hum")
            logger.info(f"Starting checkout for user: {request.user}")
            orders = create_orders_from_cart_items(request.user)
            print("lele bsdk")

            if not orders:
                logger.warning("No orders were created during checkout")
                return Response(
                    {"error": "No orders could be created. Your cart may be empty."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            logger.info(
                f"Created {len(orders)} orders, now adding shipping and payment details"
            )

            # Add shipping address, payment details for each order
            shipment_results = []
            shipmojo_service = ShipmojoService()

            for order in orders:
                try:
                    # Add shipping address
                    if shipping_address:
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
                    items = order.items.all()
                    total_weight = sum(
                        item.quantity * 0.2 for item in items
                    )  # 0.2 kg per item

                    # Create shipping details record
                    shipping = ShippingDetails.objects.create(
                        order=order,
                        provider="shipmojo",
                        weight=max(0.2, total_weight),
                        length=20,  # Default dimensions in cm
                        width=15,
                        height=10,
                        pickup_location=order.seller.business_name,
                        seller=order.seller,  # Link to seller
                    )

                    logger.info(
                        f"Added shipping and payment details to order {order.id}"
                    )

                    # Auto-create shipment if requested
                    if auto_create_shipments:
                        seller = order.seller
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

                        # Call Shipmojo service to create order
                        shipment_response = shipmojo_service.create_order(
                            order, pickup_address
                        )

                        if "error" not in shipment_response:
                            # Update shipping details
                            shipping.shipmojo_order_id = shipment_response.get(
                                "order_id"
                            )
                            shipping.shipmojo_reference_id = shipment_response.get(
                                "reference_id"
                            )
                            shipping.shipmojo_response = shipment_response
                            shipping.status = "Order Created in Shipmojo"
                            shipping.save()

                            # Update order status
                            order.status = "processing"
                            order.save()

                            shipment_results.append(
                                {
                                    "order_id": order.id,
                                    "order_number": order.order_number,
                                    "success": True,
                                    "message": "Order created in Shipmojo",
                                    "shipmojo_order_id": shipment_response.get(
                                        "order_id"
                                    ),
                                    "reference_id": shipment_response.get(
                                        "reference_id"
                                    ),
                                    "seller": seller.business_name,
                                }
                            )
                        else:
                            shipment_results.append(
                                {
                                    "order_id": order.id,
                                    "order_number": order.order_number,
                                    "success": False,
                                    "seller": seller.business_name,
                                    "error": shipment_response["error"],
                                }
                            )

                except Exception as e:
                    logger.error(f"Error processing order {order.id}: {str(e)}")
                    shipment_results.append(
                        {
                            "order_id": order.id,
                            "order_number": order.order_number,
                            "success": False,
                            "error": str(e),
                        }
                    )

            # Prepare response
            order_data = []
            for order in orders:
                order_data.append(
                    {
                        "order_id": order.id,
                        "order_number": order.order_number,
                        "seller": order.seller.business_name,
                        "total_amount": float(order.total_amount),
                        "status": order.status,
                        "items_count": order.items.count(),
                    }
                )

            response_data = {
                "message": f"Checkout successful! Created {len(orders)} orders.",
                "orders": order_data,
                "total_orders": len(orders),
            }

            if auto_create_shipments:
                response_data["shipment_results"] = shipment_results

            return Response(response_data, status=status.HTTP_201_CREATED)

        except Exception as e:
            logger.error(f"Unexpected checkout error: {str(e)}")
            return Response(
                {"error": f"Failed to process checkout: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @action(detail=True, methods=["POST"])
    def create_shipment(self, request, pk=None):
        """
        Create a shipment with Shipmojo for the order
        """
        order = get_object_or_404(Order, id=pk)

        # Check if order already has shipment created
        if hasattr(order, "shipping") and order.shipping.shipmojo_order_id:
            return Response(
                {
                    "error": "Shipment already created for this order",
                    "shipmojo_order_id": order.shipping.shipmojo_order_id,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        seller = order.seller
        shipping_location = ShippingLocation.objects.filter(seller=seller).first()

        if not shipping_location:
            return Response(
                {
                    "error": f"No shipping location found for seller {seller.business_name}"
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Get pickup address from seller's shipping location
        pickup_address = {
            "name": "Primary",
            "address": shipping_location.address,
            "city": shipping_location.city,
            "state": shipping_location.state,
            "pincode": shipping_location.pincode,
            "phone": shipping_location.phone_number,
        }

        # Initialize Shipmojo service
        shipmojo_service = ShipmojoService()

        # Create shipment
        shipment_response = shipmojo_service.create_order(order, pickup_address)

        if "error" not in shipment_response:
            # Create or update shipping details
            shipping, created = ShippingDetails.objects.get_or_create(
                order=order,
                defaults={
                    "provider": "shipmojo",
                    "weight": request.data.get("weight", 0.2),
                    "length": request.data.get("length", 20),
                    "width": request.data.get("width", 15),
                    "height": request.data.get("height", 10),
                    "pickup_location": pickup_address.get("name", "Primary"),
                    "seller": seller,
                },
            )

            # Update with shipment details
            shipping.shipmojo_order_id = shipment_response.get("order_id")
            shipping.shipmojo_reference_id = shipment_response.get("reference_id")
            shipping.shipmojo_response = shipment_response
            shipping.status = shipment_response.get("status", "Order Created")
            shipping.save()

            # Update order status
            order.status = "processing"
            order.save()

            return Response(
                {
                    "message": "Shipment created successfully",
                    "order_id": order.id,
                    "order_number": order.order_number,
                    "shipmojo_order_id": shipment_response.get("order_id"),
                    "reference_id": shipment_response.get("reference_id"),
                    "status": shipment_response.get("status"),
                }
            )
        else:
            return Response(
                {"error": shipment_response["error"]},
                status=status.HTTP_400_BAD_REQUEST,
            )

    @action(detail=True, methods=["POST"])
    def assign_courier(self, request, pk=None):
        """
        Assign courier to order and generate AWB
        """
        order = get_object_or_404(Order, id=pk)
        courier_id = request.data.get("courier_id")

        if not courier_id:
            return Response(
                {"error": "courier_id is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not hasattr(order, "shipping") or not order.shipping.shipmojo_order_id:
            return Response(
                {"error": "Order not pushed to Shipmojo yet. Create shipment first."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        shipmojo_service = ShipmojoService()

        # Assign courier
        assign_response = shipmojo_service.assign_courier(
            order.shipping.shipmojo_order_id, courier_id
        )

        if "error" not in assign_response and assign_response.get("result") == "1":
            shipping = order.shipping
            shipping.courier_name = assign_response.get("data", {}).get("courier")
            shipping.courier_assigned = True
            shipping.courier_assigned_at = timezone.now()
            shipping.status = "Courier Assigned"
            shipping.save()

            return Response(
                {
                    "message": "Courier assigned successfully",
                    "courier": assign_response.get("data", {}).get("courier"),
                    "order_id": assign_response.get("data", {}).get("order_id"),
                }
            )
        else:
            return Response(
                {"error": assign_response.get("error", "Courier assignment failed")},
                status=status.HTTP_400_BAD_REQUEST,
            )

    @action(detail=True, methods=["POST"])
    def auto_assign_courier(self, request, pk=None):
        """
        Auto assign courier to order
        """
        order = get_object_or_404(Order, id=pk)

        if not hasattr(order, "shipping") or not order.shipping.shipmojo_order_id:
            return Response(
                {"error": "Order not pushed to Shipmojo yet. Create shipment first."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        shipmojo_service = ShipmojoService()

        # Auto assign courier
        assign_response = shipmojo_service.auto_assign_courier(
            order.shipping.shipmojo_order_id
        )

        if "error" not in assign_response and assign_response.get("result") == "1":
            shipping = order.shipping
            data = assign_response.get("data", {})
            shipping.awb_number = data.get("awb_number")
            shipping.courier_name = data.get("courier_company")
            shipping.courier_company_service = data.get("courier_company_service")
            shipping.courier_assigned = True
            shipping.courier_assigned_at = timezone.now()
            shipping.status = "Courier Auto-Assigned"
            shipping.save()

            return Response(
                {
                    "message": "Courier auto-assigned successfully",
                    "awb_number": data.get("awb_number"),
                    "courier_company": data.get("courier_company"),
                    "courier_service": data.get("courier_company_service"),
                }
            )
        else:
            return Response(
                {
                    "error": assign_response.get(
                        "error", "Auto courier assignment failed"
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

    @action(detail=True, methods=["POST"])
    def schedule_pickup(self, request, pk=None):
        """
        Schedule pickup for order
        """
        order = get_object_or_404(Order, id=pk)

        if not hasattr(order, "shipping") or not order.shipping.shipmojo_order_id:
            return Response(
                {"error": "Order not pushed to Shipmojo yet. Create shipment first."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not order.shipping.courier_assigned:
            return Response(
                {"error": "Courier not assigned yet. Assign courier first."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        shipmojo_service = ShipmojoService()

        # Schedule pickup
        pickup_response = shipmojo_service.schedule_pickup(
            order.shipping.shipmojo_order_id
        )

        if "error" not in pickup_response and pickup_response.get("result") == "1":
            shipping = order.shipping
            data = pickup_response.get("data", {})

            shipping.awb_number = data.get("awb_number")
            shipping.lr_number = data.get("lr_number")
            shipping.courier_name = data.get("courier")
            shipping.pickup_scheduled = timezone.now()
            shipping.pickup_scheduled_manually = True
            shipping.status = "Pickup Scheduled"
            shipping.save()

            # Update order status
            order.status = "shipped"
            order.save()

            return Response(
                {
                    "message": "Pickup scheduled successfully",
                    "awb_number": data.get("awb_number"),
                    "lr_number": data.get("lr_number"),
                    "courier": data.get("courier"),
                }
            )
        else:
            return Response(
                {"error": pickup_response.get("error", "Pickup scheduling failed")},
                status=status.HTTP_400_BAD_REQUEST,
            )

    @action(detail=True, methods=["GET"])
    def get_shipping_rates(self, request, pk=None):
        """
        Get shipping rates for order
        """
        order = get_object_or_404(Order, id=pk)

        # Get shipping address
        shipping_address = None
        for address in order.orderaddress_set.all():
            if address.address_type == "shipping":
                shipping_address = address
                break

        if not shipping_address:
            return Response(
                {"error": "No shipping address found"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Get seller shipping location
        seller = order.seller
        shipping_location = ShippingLocation.objects.filter(seller=seller).first()

        if not shipping_location:
            return Response(
                {
                    "error": f"No shipping location found for seller {seller.business_name}"
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        shipmojo_service = ShipmojoService()

        # Determine payment type
        is_cod = order.payment.method == "COD" if hasattr(order, "payment") else False
        payment_type = "COD" if is_cod else "PREPAID"

        # Calculate weight
        items = order.items.all()
        total_weight = sum(
            item.quantity * 200 for item in items
        )  # 200g per item default

        # Prepare dimensions
        dimensions = [{"no_of_box": "1", "length": "20", "width": "15", "height": "10"}]

        # Get rates
        rates_response = shipmojo_service.calculate_shipping_rates(
            pickup_pincode=shipping_location.pincode,
            delivery_pincode=shipping_address.pincode,
            payment_type=payment_type,
            order_amount=int(order.total_amount),
            weight=max(200, total_weight),
            dimensions=dimensions,
        )

        if "error" not in rates_response:
            return Response(rates_response)
        else:
            return Response(
                {"error": rates_response["error"]},
                status=status.HTTP_400_BAD_REQUEST,
            )

    @action(detail=True, methods=["GET"])
    def track(self, request, pk=None):
        """
        Track order status using AWB number
        """
        order = get_object_or_404(Order, id=pk)

        if not hasattr(order, "shipping") or not order.shipping.awb_number:
            return Response(
                {"error": "No AWB number found. Schedule pickup first."},
                status=status.HTTP_404_NOT_FOUND,
            )

        shipmojo_service = ShipmojoService()
        tracking_response = shipmojo_service.track_order(order.shipping.awb_number)

        if "error" not in tracking_response and tracking_response.get("result") == "1":
            # Update shipping status
            shipping = order.shipping
            tracking_data = tracking_response.get("data", {})

            shipping.status = tracking_data.get("current_status", shipping.status)
            shipping.expected_delivery = tracking_data.get("expected_delivery_date")

            # Add to status updates
            if tracking_data.get("scan_detail"):
                shipping.status_updates = tracking_data.get("scan_detail", [])

            shipping.save()

            return Response(
                {
                    "order_number": order.order_number,
                    "awb_number": tracking_data.get("awb_number"),
                    "courier": tracking_data.get("courier"),
                    "current_status": tracking_data.get("current_status"),
                    "expected_delivery_date": tracking_data.get(
                        "expected_delivery_date"
                    ),
                    "status_time": tracking_data.get("status_time"),
                    "scan_details": tracking_data.get("scan_detail", []),
                }
            )
        else:
            return Response(
                {"error": tracking_response.get("error", "Tracking failed")},
                status=status.HTTP_400_BAD_REQUEST,
            )

    @action(detail=True, methods=["POST"])
    def generate_label(self, request, pk=None):
        """
        Generate shipping label for order
        """
        order = get_object_or_404(Order, id=pk)

        if not hasattr(order, "shipping") or not order.shipping.awb_number:
            return Response(
                {"error": "No AWB number found. Schedule pickup first."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        shipmojo_service = ShipmojoService()
        label_response = shipmojo_service.get_order_label(order.shipping.awb_number)

        if "error" not in label_response and label_response.get("result") == "1":
            # Save label data
            shipping = order.shipping
            label_data = label_response.get("data", [{}])[0]

            shipping.label_data = label_data.get("label")
            shipping.save()

            return Response(
                {
                    "message": "Label generated successfully",
                    "label": label_data.get("label"),
                    "created_at": label_data.get("created_at"),
                }
            )
        else:
            return Response(
                {"error": label_response.get("error", "Label generation failed")},
                status=status.HTTP_400_BAD_REQUEST,
            )

    @action(detail=True, methods=["POST"])
    def cancel_shipment(self, request, pk=None):
        """
        Cancel shipment
        """
        order = get_object_or_404(Order, id=pk)

        if not hasattr(order, "shipping") or not order.shipping.awb_number:
            return Response(
                {"error": "No AWB number found. Cannot cancel shipment."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        shipmojo_service = ShipmojoService()
        cancel_response = shipmojo_service.cancel_order(
            order.shipping.shipmojo_order_id, order.shipping.awb_number
        )

        if "error" not in cancel_response and cancel_response.get("result") == "1":
            # Update shipping status
            shipping = order.shipping
            shipping.status = "Cancelled"
            shipping.save()

            # Update order status
            order.status = "cancelled"
            order.save()

            return Response(
                {
                    "message": "Shipment cancelled successfully",
                    "order_id": cancel_response.get("data", {}).get("order_id"),
                }
            )
        else:
            return Response(
                {"error": cancel_response.get("error", "Shipment cancellation failed")},
                status=status.HTTP_400_BAD_REQUEST,
            )

    @action(detail=True, methods=["GET"])
    def check_serviceability(self, request, pk=None):
        """
        Check serviceability for order
        """
        order = get_object_or_404(Order, id=pk)

        # Get shipping address
        shipping_address = None
        for address in order.orderaddress_set.all():
            if address.address_type == "shipping":
                shipping_address = address
                break

        if not shipping_address:
            return Response(
                {"error": "No shipping address found"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Get seller shipping location
        seller = order.seller
        shipping_location = ShippingLocation.objects.filter(seller=seller).first()

        if not shipping_location:
            return Response(
                {
                    "error": f"No shipping location found for seller {seller.business_name}"
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        shipmojo_service = ShipmojoService()
        serviceability_response = shipmojo_service.check_serviceability(
            pickup_pincode=shipping_location.pincode,
            delivery_pincode=shipping_address.pincode,
        )

        if "error" not in serviceability_response:
            return Response(serviceability_response)
        else:
            return Response(
                {"error": serviceability_response["error"]},
                status=status.HTTP_400_BAD_REQUEST,
            )

    @action(detail=False, methods=["GET"])
    def get_warehouses(self, request):
        """
        Get all warehouses from Shipmojo
        """
        shipmojo_service = ShipmojoService()
        warehouses_response = shipmojo_service.get_warehouses()

        if "error" not in warehouses_response:
            return Response(warehouses_response)
        else:
            return Response(
                {"error": warehouses_response["error"]},
                status=status.HTTP_400_BAD_REQUEST,
            )

    @action(detail=False, methods=["POST"])
    def create_warehouse(self, request):
        """
        Create a new warehouse in Shipmojo
        """
        warehouse_data = request.data

        # Validate required fields
        required_fields = ["address_title", "address_line_one", "pin_code"]
        missing_fields = [
            field for field in required_fields if not warehouse_data.get(field)
        ]

        if missing_fields:
            return Response(
                {"error": f"Missing required fields: {', '.join(missing_fields)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        shipmojo_service = ShipmojoService()
        warehouse_response = shipmojo_service.create_warehouse(warehouse_data)

        if (
            "error" not in warehouse_response
            and warehouse_response.get("result") == "1"
        ):
            return Response(warehouse_response)
        else:
            return Response(
                {"error": warehouse_response.get("error", "Warehouse creation failed")},
                status=status.HTTP_400_BAD_REQUEST,
            )

    @action(detail=True, methods=["POST"])
    def update_warehouse(self, request, pk=None):
        """
        Update warehouse for an order
        """
        order = get_object_or_404(Order, id=pk)
        warehouse_id = request.data.get("warehouse_id")

        if not warehouse_id:
            return Response(
                {"error": "warehouse_id is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not hasattr(order, "shipping") or not order.shipping.shipmojo_order_id:
            return Response(
                {"error": "Order not pushed to Shipmojo yet. Create shipment first."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        shipmojo_service = ShipmojoService()
        update_response = shipmojo_service.update_warehouse(
            order.shipping.shipmojo_order_id, warehouse_id
        )

        if "error" not in update_response and update_response.get("result") == "1":
            # Update shipping details
            shipping = order.shipping
            shipping.warehouse_id = str(warehouse_id)
            shipping.save()

            return Response(
                {
                    "message": "Warehouse updated successfully",
                    "order_id": update_response.get("data", {}).get("order_id"),
                    "warehouse_id": warehouse_id,
                }
            )
        else:
            return Response(
                {"error": update_response.get("error", "Warehouse update failed")},
                status=status.HTTP_400_BAD_REQUEST,
            )

    @action(detail=False, methods=["GET"])
    def get_return_reasons(self, request):
        """
        Get available return reasons from Shipmojo
        """
        shipmojo_service = ShipmojoService()
        reasons_response = shipmojo_service.get_return_reasons()

        if "error" not in reasons_response:
            return Response(reasons_response)
        else:
            return Response(
                {"error": reasons_response["error"]},
                status=status.HTTP_400_BAD_REQUEST,
            )

    @action(detail=True, methods=["POST"])
    def create_return_order(self, request, pk=None):
        """
        Create a return order for the given order
        """
        order = get_object_or_404(Order, id=pk)

        # Get return reason and other details
        return_reason_id = request.data.get("return_reason_id")
        customer_request = request.data.get("customer_request", "REFUND")
        reason_comment = request.data.get("reason_comment", "")

        if not return_reason_id:
            return Response(
                {"error": "return_reason_id is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Get pickup address (original delivery address becomes pickup address for return)
        pickup_address = None
        for address in order.orderaddress_set.all():
            if address.address_type == "shipping":
                pickup_address = address
                break

        if not pickup_address:
            return Response(
                {"error": "No shipping address found for return pickup"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Build product details for return
        product_details = []
        for item in order.items.all():
            return_quantity = request.data.get(
                f"return_quantity_{item.id}", item.quantity
            )
            if return_quantity > 0:
                product_details.append(
                    {
                        "name": item.name,
                        "sku_number": item.sku or f"SKU-{item.id}",
                        "quantity": int(return_quantity),
                        "discount": "",
                        "hsn": "#123",
                        "unit_price": float(item.final_price / item.quantity),
                        "product_category": "Other",
                    }
                )

        if not product_details:
            return Response(
                {"error": "No items selected for return"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Calculate return weight
        total_return_weight = sum(
            item["quantity"] * 200 for item in product_details  # 200g per item
        )

        # Prepare return order data
        return_order_data = {
            "order_id": f"RET_{order.order_number}_{timezone.now().strftime('%Y%m%d%H%M%S')}",
            "order_date": timezone.now().strftime("%Y-%m-%d"),
            "order_type": "ESSENTIALS",
            "pickup_name": pickup_address.full_name,
            "pickup_phone": int(
                pickup_address.phone.replace("+", "").replace("-", "").replace(" ", "")
            ),
            "pickup_email": pickup_address.email,
            "pickup_address_line_one": pickup_address.street,
            "pickup_address_line_two": pickup_address.area,
            "pickup_pin_code": int(pickup_address.pincode),
            "pickup_city": pickup_address.city,
            "pickup_state": pickup_address.state,
            "product_detail": product_details,
            "payment_type": "PREPAID",  # Returns are typically prepaid
            "weight": max(200, total_return_weight),
            "length": 20,
            "width": 15,
            "height": 10,
            "warehouse_id": "",
            "return_reason_id": int(return_reason_id),
            "customer_request": customer_request.upper(),
            "reason_comment": reason_comment,
        }

        shipmojo_service = ShipmojoService()
        return_response = shipmojo_service.push_return_order(return_order_data)

        if "error" not in return_response and return_response.get("result") == "1":
            # Create a return shipping details record
            return_shipping = ShippingDetails.objects.create(
                order=order,
                provider="shipmojo",
                weight=max(0.2, total_return_weight / 1000),  # Convert to kg
                length=20,
                width=15,
                height=10,
                pickup_location=f"{pickup_address.city}, {pickup_address.state}",
                seller=order.seller,
                is_return_order=True,
                return_reason_id=return_reason_id,
                return_reason_comment=reason_comment,
                customer_request=customer_request,
                shipmojo_order_id=return_response.get("data", {}).get("order_id"),
                shipmojo_reference_id=return_response.get("data", {}).get(
                    "reference_id"
                ),
                shipmojo_response=return_response,
                status="Return Order Created",
            )

            return Response(
                {
                    "message": "Return order created successfully",
                    "return_order_id": return_response.get("data", {}).get("order_id"),
                    "reference_id": return_response.get("data", {}).get("reference_id"),
                    "return_shipping_id": return_shipping.id,
                }
            )
        else:
            return Response(
                {"error": return_response.get("error", "Return order creation failed")},
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
