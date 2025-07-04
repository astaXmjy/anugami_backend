from firebase_admin import firestore
from django.db.models import Count, Sum
from django.contrib.auth.models import User
from products.models import Product
from categories.models import Category
from sellers.models import Seller
from datetime import datetime

db = firestore.client()  # Firestore database connection

def get_analytics():
    # Firestore Orders Collection
    orders_ref = db.collection("orders")
    orders_active = 0
    total_earning = 0
    order_outlines = []
    seller_earnings = {}
    category_sales = {}

    # Fetch orders from Firestore efficiently
    orders_query = orders_ref.stream()

    for order in orders_query:
        order_data = order.to_dict()
        total_price = order_data.get("total_price", 0)

        # Count active orders
        if order_data.get("status") == "pending":
            orders_active += 1

        # Collect order outlines
        order_outlines.append(
            {
                "id": order.id,
                "status": order_data.get("status"),
                "product_name": order_data.get("product_name"),
                "total_price": total_price,
                "quantity": order_data.get("quantity"),
            }
        )

        # Compute total earnings
        total_earning += total_price

        # Aggregate seller earnings
        seller_id = order_data.get("seller_id")
        if seller_id:
            seller_earnings[seller_id] = seller_earnings.get(seller_id, 0) + total_price

        # Aggregate category sales
        category_name = order_data.get("category_name")
        if category_name:
            category_sales[category_name] = (
                category_sales.get(category_name, 0) + total_price
            )

    # Convert Seller IDs to usernames (if stored in Django)
    seller_earning_list = []
    for seller_id, earnings in seller_earnings.items():
        seller = Seller.objects.filter(id=seller_id).first()
        if seller:
            seller_earning_list.append(
                {"seller": seller.user.username, "earnings": earnings}
            )

    # Top Sellers
    top_sellers = sorted(
        seller_earning_list, key=lambda x: x["earnings"], reverse=True
    )[:5]

    # Top Categories
    top_categories = sorted(category_sales.items(), key=lambda x: x[1], reverse=True)[
        :5
    ]
    top_categories = [{"name": c[0], "sales": c[1]} for c in top_categories]

    # Compute admin earnings (assuming 10% commission)
    admin_earning = total_earning * 0.1

    # Get new user signups (correcting datetime filter)
    start_date = datetime(2024, 1, 1)
    new_signups = User.objects.filter(date_joined__gte=start_date).count()

    # Product & Category Statistics (from Django ORM)
    products_count = Product.objects.count()
    products_sold_out = Product.objects.filter(stock=0).count()
    low_stock_products = Product.objects.filter(stock__lt=15).count()

    categorywise_product_count = list(
        Category.objects.annotate(product_count=Count("product")).values(
            "name", "product_count"
        )
    )

    # Seller Statistics (if stored in Django)
    seller_details = {
        "approved": Seller.objects.filter(is_approved=True).count(),
        "not_approved": Seller.objects.filter(is_approved=False).count(),
        "deactivated": Seller.objects.filter(is_deactivated=True).count(),
    }

    return {
        "orders_active": orders_active,
        "new_signups": new_signups,
        "products_count": products_count,
        "product_sales": total_earning,
        "categorywise_product_count": categorywise_product_count,
        "total_earning": total_earning,
        "admin_earning": admin_earning,
        "seller_earning": seller_earning_list,  # Fixed seller name mapping
        "products_sold_out": products_sold_out,
        "low_stock_products": low_stock_products,
        "seller_details": seller_details,
        "top_sellers": top_sellers,
        "top_categories": top_categories,
        "order_outlines": order_outlines,
    }
