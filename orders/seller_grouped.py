from orders.models import ShippingDetails, Order, OrderItem, OrderAddress, PaymentDetails
from django.db import transaction
from customers.models import CartItem
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
    logger.info(f"Found customer: {customer.id}")

    # Get cart items from your CartItem model
    try: 

        logger.info(f"Fetching cart items for customer: {customer.id}")
        cart_items = CartItem.objects.filter(customer=customer)
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
            from products.models import Product  # Update with correct import

            logger.info(f"Fetching product ID: {cart_item.product_id}")
            product = Product.objects.get(id=cart_item.product_id)

            # IMPORTANT FIX: Get the Seller instance from the CustomUser
            # Your Product.seller field points to CustomUser, not Seller
            # We need to get the seller_profile for this user
            if not hasattr(product, "seller") or not product.seller:
                logger.warning(f"Product {product.id} has no seller, skipping")
                continue

            # The custom user who is the seller
            seller_user = product.seller

            # Get the actual Seller model instance using the seller_profile relationship
            # This depends on how your related_name is set in Seller.user field
            if not hasattr(seller_user, "seller_profile"):
                logger.warning(f"User {seller_user.id} has no seller profile, skipping")
                continue

            # Get the Seller instance
            seller = seller_user.seller_profile
            seller_id = seller.id

            logger.info(f"Product {product.id} belongs to seller {seller_id}")

            quantity = cart_item.quantity

            # Initialize seller group if not exists
            if seller_id not in items_by_seller:
                logger.info(f"Creating new seller group for seller {seller_id}")
                items_by_seller[seller_id] = {
                    "seller": seller,
                    "items": [],
                    "total_amount": 0,
                }

            # Calculate item price
            product_price = getattr(product, "regular_price", 0)
            sale_price = getattr(product, "sale_price", product_price)

            # If CartItem has price, use that instead
            cart_item_price = getattr(cart_item, "price", None)
            if cart_item_price:
                product_price = cart_item_price
                sale_price = cart_item_price

            item_total = float(sale_price) * quantity

            logger.info(
                f"Added product {product.id} to seller {seller_id}: price={product_price}, quantity={quantity}, total={item_total}"
            )

            # Add item to seller group
            items_by_seller[seller_id]["items"].append(
                {
                    "product": product,
                    "product_id": str(product.id),
                    "name": product.name,
                    "price": product_price,
                    "sale_price": sale_price,
                    "quantity": quantity,
                    "sku": getattr(product, "sku", ""),
                    "final_price": item_total,
                }
            )

            # Update seller group total
            items_by_seller[seller_id]["total_amount"] += item_total

        except Product.DoesNotExist:
            logger.warning(
                f"Product with ID {cart_item.product_id} not found, skipping"
            )
            continue
        except Exception as e:
            logger.error(f"Error processing cart item {cart_item.id}: {str(e)}")
            continue

    # Create orders for each seller group
    created_orders = []

    for seller_id, seller_data in items_by_seller.items():
        seller = seller_data["seller"]
        items = seller_data["items"]
        total_amount = seller_data["total_amount"]

        logger.info(
            f"Creating order for seller {seller_id} with {len(items)} items and total {total_amount}"
        )

        # Create order with transaction
        try:
            with transaction.atomic():
                # Create the order
                order = Order.objects.create(
                    user=customer,
                    seller=seller,  # Now this is correctly a Seller instance
                    total_amount=total_amount,
                    status="pending",
                )

                logger.info(
                    f"Created order {order.id} with number {order.order_number}"
                )

                # Add order items
                for item in items:
                    OrderItem.objects.create(
                        order=order,
                        product_id=item["product_id"],
                        name=item["name"],
                        price=item["price"],
                        sale_price=item["sale_price"],
                        quantity=item["quantity"],
                        sku=item["sku"],
                        final_price=item["final_price"],
                        status="pending",
                    )

                logger.info(f"Added {len(items)} items to order {order.id}")
                created_orders.append(order)
        except Exception as e:
            logger.error(f"Error creating order for seller {seller_id}: {str(e)}")
            continue

    logger.info(f"Created {len(created_orders)} orders successfully")

    # Clear the cart after successful order creation
    if created_orders:
        try:
            logger.info(f"Clearing {cart_items.count()} cart items")
            cart_items.delete()
            logger.info("Cart cleared successfully")
        except Exception as e:
            logger.warning(f"Error clearing cart: {str(e)}")

    return created_orders
