from django.shortcuts import render
from django.http import HttpResponse
from django.db.models import Sum, Count
from django.urls import reverse
from .models import OrderItem, Order
from sellers.models import Seller


def products_table_view(request):
    """
    HTML view that displays order products in a table format matching your image
    """
    # Get query parameters
    seller_id = request.GET.get("seller_id")

    # Base queryset
    items = OrderItem.objects.select_related("order", "order__seller").all()

    # Apply seller filter if provided
    seller_info = None
    if seller_id:
        try:
            seller = Seller.objects.get(id=seller_id)
            items = items.filter(order__seller_id=seller_id)
            seller_info = {
                "id": seller.id,
                "name": seller.business_name,
                "commission_rate": seller.commission_rate,
            }
        except Seller.DoesNotExist:
            seller_info = None

    # Prepare table data
    table_data = []
    for item in items:
        # Calculate values to match your table structure
        sale_price = float(item.sale_price or item.price)
        quantity = item.quantity
        total_sale_amount = sale_price * quantity

        # GST calculations
        gst_rate = float(
            item.gst_rate
            if hasattr(item, "gst_rate") and item.gst_rate
            else item.tax_rate or 18
        )
        delivery_charges = float(
            item.delivery_charges if hasattr(item, "delivery_charges") else 0
        )

        # Listing price and consumer price calculations
        listing_price = (
            float(item.listing_price)
            if hasattr(item, "listing_price") and item.listing_price
            else total_sale_amount * 1.18
        )
        consumer_price = (
            float(item.consumer_price)
            if hasattr(item, "consumer_price") and item.consumer_price
            else listing_price * 1.02
        )

        # Commission calculations
        commission_rate = (
            float(item.commission_rate) if hasattr(item, "commission_rate") else 15.0
        )
        commission_amount = (
            float(item.commission_for_each_seller)
            if hasattr(item, "commission_for_each_seller")
            else listing_price * commission_rate / 100
        )

        # GST amounts
        gst_amount = (
            float(item.gst_amount_inclusive)
            if hasattr(item, "gst_amount_inclusive")
            else total_sale_amount * gst_rate / 100
        )
        gst_commission = (
            float(item.commission_for_each_seller_gst)
            if hasattr(item, "commission_for_each_seller_gst")
            else commission_amount * 18 / 100
        )

        # Seller financial calculations
        amount_seller_receives = (
            float(item.amount_seller_receives)
            if hasattr(item, "amount_seller_receives")
            else total_sale_amount - commission_amount - gst_amount
        )
        amount_after_paying = (
            float(item.amount_receives_after_paying)
            if hasattr(item, "amount_receives_after_paying")
            else amount_seller_receives - 150
        )
        claimable_amount = (
            float(item.claimable_amount)
            if hasattr(item, "claimable_amount")
            else amount_after_paying
        )

        # Additional calculations
        gst_amount_seller = (
            float(item.gst_amount_seller)
            if hasattr(item, "gst_amount_seller")
            else gst_amount
        )
        profit_amount = (
            float(item.profit_amount)
            if hasattr(item, "profit_amount")
            else consumer_price - total_sale_amount
        )
        shipping_cost = (
            float(item.shipping_cost) if hasattr(item, "shipping_cost") else 150.0
        )
        cod_charges = float(item.cod_charges) if hasattr(item, "cod_charges") else 0.0

        table_row = {
            "seller_name": (
                item.order.seller.business_name
                if hasattr(item.order.seller, "business_name")
                else str(item.order.seller)
            ),
            "product_name": item.name,
            "sale_price": sale_price,
            "gst_rate": gst_rate,
            "delivery_charges": delivery_charges,
            "listing_price": listing_price,
            "consumer_price": consumer_price,
            "commission_rate": commission_rate,
            "commission_for_each_seller": commission_amount,
            "commission_for_each_seller_gst": gst_commission,
            "gst_amount_inclusive": gst_amount,
            "amount_seller_receives": amount_seller_receives,
            "amount_receives_after_paying": amount_after_paying,
            "claimable_amount": claimable_amount,
            "gst_amount_seller": gst_amount_seller,
            "profit_amount": profit_amount,
            "shipping_cost": shipping_cost,
            "cod_charges": cod_charges,
            "quantity": quantity,
            "sku": item.sku or "N/A",
        }
        table_data.append(table_row)

    # Calculate totals
    totals = {
        "total_items": len(table_data),
        "total_sale_amount": sum(
            row["sale_price"] * row["quantity"] for row in table_data
        ),
        "total_commission": sum(
            row["commission_for_each_seller"] for row in table_data
        ),
        "total_seller_receives": sum(
            row["amount_seller_receives"] for row in table_data
        ),
        "total_profit": sum(row["profit_amount"] for row in table_data),
        "total_shipping": sum(row["shipping_cost"] for row in table_data),
    }

    # Get all sellers for filter dropdown
    all_sellers = Seller.objects.all()

    # Get current URL path for form action (without namespace)
    current_url = request.path

    context = {
        "table_data": table_data,
        "totals": totals,
        "seller_info": seller_info,
        "all_sellers": all_sellers,
        "selected_seller_id": seller_id,
        "current_url": current_url,
    }

    return render(request, "orders/products_table.html", context)
