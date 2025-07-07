# orders/seller_grouped.py
from orders.models import (
    ShippingDetails,
    Order,
    OrderItem,
    OrderAddress,
    PaymentDetails,
)
from django.db import transaction
from customers.models import CartItem
from .ship import ShipmojoService
import logging

logger = logging.getLogger(__name__)


def create_orders_from_cart_items(user):
    """
    Create orders from user's existing cart items, grouped by seller
    """
    logger.info(
        f"Starting checkout for user: {user.email if hasattr(user, 'email') else user}"
    )

    # Check if user has a customer profile
    if not hasattr(user, "customer") or not user.customer:
        logger.error(f"User has no customer profile: {user}")
        raise ValueError("Customer profile not found")

    customer = user.customer
    print(customer)
    logger.info(f"Found customer: {customer.id}")

    # Get cart items from your CartItem model
    try:
        logger.info(f"Fetching cart items for customer: {customer.id}")
        cart_items = CartItem.objects.filter(customer=customer)
        print(cart_items)
        logger.info(f"Found {cart_items.count()} cart items")

        if not cart_items.exists():
            logger.warning(f"No cart items found for customer: {customer.id}")
            raise ValueError("Cart is empty")

    except Exception as e:
        logger.error(f"Error fetching cart items: {str(e)}")
        raise ValueError(f"Error accessing cart items: {str(e)}")

    # Group cart items by seller
    items_by_seller = {}

    # Process each cart item
    for cart_item in cart_items:
        try:
            # Get product
            from products.models import Product

            logger.info(f"Fetching product ID: {cart_item.product_id}")
            print("iske baad")
            product = Product.objects.get(id=cart_item.product_id)

            # Get seller from product
            seller = product.seller
            logger.info(f"Product {product.id} belongs to seller {seller.id}")

            # Group by seller
            if seller.id not in items_by_seller:
                items_by_seller[seller.id] = {
                    "seller": seller,
                    "items": [],
                    "total": 0,
                }

            # Calculate item totals
            item_price = product.final_price or product.price
            item_total = item_price * cart_item.quantity

            items_by_seller[seller.id]["items"].append(
                {
                    "cart_item": cart_item,
                    "product": product,
                    "quantity": cart_item.quantity,
                    "unit_price": item_price,
                    "total_price": item_total,
                }
            )

            items_by_seller[seller.id]["total"] += item_total

            logger.info(
                f"Added item {product.name} (qty: {cart_item.quantity}) to seller {seller.business_name}"
            )

        except Exception as e:
            logger.error(f"Error processing cart item {cart_item.id}: {str(e)}")
            continue

    if not items_by_seller:
        logger.error("No valid items found to create orders")
        raise ValueError("No valid items found in cart")

    logger.info(f"Items grouped by {len(items_by_seller)} sellers")

    # Create orders for each seller
    orders = []

    with transaction.atomic():
        for seller_id, seller_data in items_by_seller.items():
            try:
                seller = seller_data["seller"]
                logger.info(
                    f"Creating order for seller {seller.business_name} with {len(seller_data['items'])} items"
                )

                # Generate unique order number
                import uuid
                from django.utils import timezone

                order_number = f"ORD-{timezone.now().strftime('%Y%m%d')}-{str(uuid.uuid4())[:8].upper()}"

                # Create order
                order = Order.objects.create(
                    customer=customer,
                    seller=seller,
                    order_number=order_number,
                    total_amount=seller_data["total"],
                    status="pending",
                )

                logger.info(f"Created order {order.id} with number {order_number}")

                # Create order items
                for item_data in seller_data["items"]:
                    cart_item = item_data["cart_item"]
                    product = item_data["product"]

                    # Create order item
                    order_item = OrderItem.objects.create(
                        order=order,
                        product=product,
                        name=product.name,
                        sku=product.sku or f"SKU-{product.id}",
                        quantity=cart_item.quantity,
                        unit_price=item_data["unit_price"],
                        final_price=item_data["total_price"],
                        discount_amount=0,  # Calculate if you have discounts
                        tax_amount=0,  # Calculate if you have taxes
                    )

                    logger.info(
                        f"Created order item {order_item.id} for product {product.name}"
                    )

                # Copy shipping address from customer's default address
                # You'll need to adapt this based on your address model
                try:
                    # Assuming you have a customer address model
                    customer_address = customer.addresses.filter(
                        is_default=True
                    ).first()
                    if customer_address:
                        OrderAddress.objects.create(
                            order=order,
                            address_type="shipping",
                            full_name=customer_address.full_name,
                            phone=customer_address.phone,
                            street=customer_address.street,
                            landmark=customer_address.landmark or "",
                            city=customer_address.city,
                            state=customer_address.state,
                            pincode=customer_address.pincode,
                            country="India",
                        )
                        logger.info(f"Added shipping address to order {order.id}")
                    else:
                        logger.warning(
                            f"No default address found for customer {customer.id}"
                        )

                except Exception as e:
                    logger.error(f"Error adding address to order {order.id}: {str(e)}")

                orders.append(order)
                logger.info(
                    f"Successfully created order {order.id} for seller {seller.business_name}"
                )

            except Exception as e:
                logger.error(f"Error creating order for seller {seller_id}: {str(e)}")
                raise

    logger.info(f"Successfully created {len(orders)} orders")
    return orders


def create_shipments_for_orders(orders):
    """
    Create ShipMojo shipments for multiple orders
    This is separated from order creation to handle it independently
    """
    logger.info(f"Creating shipments for {len(orders)} orders")

    shipmojo_service = ShipmojoService()
    shipment_results = []

    # Group orders by seller for efficient processing
    orders_by_seller = {}
    for order in orders:
        seller_id = order.seller.id
        if seller_id not in orders_by_seller:
            orders_by_seller[seller_id] = []
        orders_by_seller[seller_id].append(order)

    # Process each seller's orders
    for seller_id, seller_orders in orders_by_seller.items():
        seller = seller_orders[0].seller

        # Get seller's shipping location
        from sellers.models import ShippingLocation

        shipping_location = ShippingLocation.objects.filter(seller=seller).first()

        if not shipping_location:
            error_msg = f"No shipping location found for seller {seller.business_name}"
            logger.error(error_msg)

            for order in seller_orders:
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

        # Create pickup address
        pickup_address = {
            "name": "Primary",
            "contact_person": seller.business_name,
            "address": shipping_location.address,
            "city": shipping_location.city,
            "state": shipping_location.state,
            "pincode": shipping_location.pincode,
            "phone": shipping_location.phone_number,
        }

        # Create shipments for each order
        for order in seller_orders:
            try:
                logger.info(f"Creating shipment for order {order.id}")

                # Create shipment via ShipMojo
                shipment_response = shipmojo_service.create_order(order, pickup_address)

                if "error" not in shipment_response:
                    # Create shipping details
                    shipping = ShippingDetails.objects.create(
                        order=order,
                        provider="shipmojo",
                        weight=0.5,  # Default weight
                        length=20,
                        width=15,
                        height=10,
                        pickup_location=seller.business_name,
                    )

                    # Update with ShipMojo response
                    if "order_id" in shipment_response:
                        shipping.shipmojo_order_id = shipment_response["order_id"]
                    if "shipment_id" in shipment_response:
                        shipping.shipment_id = shipment_response["shipment_id"]
                    if "tracking_id" in shipment_response:
                        shipping.tracking_id = shipment_response["tracking_id"]
                    if "courier_partner_id" in shipment_response:
                        shipping.courier_partner_id = shipment_response[
                            "courier_partner_id"
                        ]
                    if "courier_name" in shipment_response:
                        shipping.courier_name = shipment_response["courier_name"]

                    shipping.shipmojo_response = shipment_response
                    shipping.status = "Order Created in ShipMojo"
                    shipping.save()

                    # Update order status
                    order.status = "processing"
                    order.save()

                    shipment_results.append(
                        {
                            "order_id": order.id,
                            "order_number": order.order_number,
                            "success": True,
                            "message": "Shipment created successfully",
                            "shipmojo_order_id": shipping.shipmojo_order_id,
                            "seller": seller.business_name,
                        }
                    )

                    logger.info(f"Shipment created successfully for order {order.id}")

                else:
                    error_msg = shipment_response.get("error", "Unknown error")
                    logger.error(
                        f"Shipment creation failed for order {order.id}: {error_msg}"
                    )

                    shipment_results.append(
                        {
                            "order_id": order.id,
                            "order_number": order.order_number,
                            "success": False,
                            "seller": seller.business_name,
                            "error": error_msg,
                        }
                    )

            except Exception as e:
                logger.error(f"Error creating shipment for order {order.id}: {str(e)}")
                shipment_results.append(
                    {
                        "order_id": order.id,
                        "order_number": order.order_number,
                        "success": False,
                        "seller": seller.business_name,
                        "error": str(e),
                    }
                )

    return shipment_results
