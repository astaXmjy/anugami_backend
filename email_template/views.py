import django
import django.conf
from django.shortcuts import render
from core.settings import DEFAULT_FROM_EMAIL
from .utils import send_email
from . import generate_invoice
from django.conf import settings

# Account Related Emails
def send_welcome_email(user):
    context = {"user": user}
    send_email(
        "account/welcome.html", context, "Welcome to Our Platform!", [user.email]
    )


def send_email_verification_email(user, verification_link):
    context = {"user": user, "verification_link": verification_link}
    send_email(
        "account/email_verification.html", context, "Verify Your Email", [user.email]
    )


def send_password_reset_email(user, reset_link):
    context = {"user": user, "reset_link": reset_link}
    send_email(
        "account/password_reset.html", context, "Password Reset Request", [user.email]
    )


def send_account_activation_email(user, activation_link):
    context = {"user": user, "activation_link": activation_link}
    send_email(
        "account/account_activation.html",
        context,
        "Activate Your Account",
        [user.email],
    )


def send_login_alert_email(user):
    context = {"user": user}
    send_email(
        "account/login_alerts.html", context, "Suspicious Login Activity", [user.email]
    )


def send_two_factor_auth_email(user, code):
    context = {"user": user, "code": code}
    send_email(
        "account/two_factor_auth.html",
        context,
        "Two-Factor Authentication Code",
        [user.email],
    )

from django.core.mail import EmailMessage
from django.template.loader import render_to_string
from io import BytesIO

# Order Related Emails
def send_order_invoice_email(order):
    """Send invoice PDF for an order via email."""

    # Get the customer email
    shipping_address = order.orderaddress_set.filter(address_type="shipping").first()
    billing_address = order.orderaddress_set.filter(address_type="billing").first()

    customer_email = None
    if billing_address:
        customer_email = billing_address.email
    elif shipping_address:
        customer_email = shipping_address.email
    else:
        customer_email = order.user.email

    if not customer_email:
        return False

    # Generate the invoice PDF
    pdf_buffer = generate_invoice.generate_order_invoice(order)
    if not pdf_buffer:
        return False

    # Render the email template
    context = {
        "order": order,
        "order_number": order.order_number,
        "order_date": order.created_at,
        "total_amount": order.total_amount,
        "order_status": (
            order.get_status_display()
            if hasattr(order, "get_status_display")
            else order.status
        ),
        "shipping_address": shipping_address,
        "billing_address": billing_address,
        "order_items": order.items.all(),
    }

    email_body = render_to_string("email_templates/order/order_confirmation.html", context)

    # Create the email
    subject = f"Invoice for your order #{order.order_number}"
    email = EmailMessage(
        subject=subject,
        body=email_body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[customer_email],
    )

    # Attach the invoice PDF
    email.attach(
        f"Invoice_{order.order_number}.pdf", pdf_buffer.getvalue(), "application/pdf"
    )

    # Send the email
    email.content_subtype = "html"  # Ensure email is sent as HTML
    email.send()

    return True


def send_order_status_update_email(user, order):
    context = {"user": user, "order": order}
    send_email(
        "order/order_status_update.html", context, "Order Status Update", [user.email]
    )


def send_order_cancellation_email(user, order):
    context = {"user": user, "order": order}
    send_email(
        "order/order_cancellation.html", context, "Order Cancellation", [user.email]
    )


def send_order_return_refund_email(user, order):
    context = {"user": user, "order": order}
    send_email(
        "order/order_return_refund.html",
        context,
        "Return/Refund Confirmation",
        [user.email],
    )


def send_shipping_tracking_email(user, order, tracking_link):
    context = {"user": user, "order": order, "tracking_link": tracking_link}
    send_email("order/shipping_tracking.html", context, "Shipping Update", [user.email])


def send_delivery_confirmation_email(user, order):
    context = {"user": user, "order": order}
    send_email(
        "order/delivery_confirmation.html",
        context,
        "Delivery Confirmation",
        [user.email],
    )


def send_payment_confirmation_email(user, order):
    context = {"user": user, "order": order}
    send_email(
        "order/payment_confirmation.html", context, "Payment Confirmation", [user.email]
    )


def send_payment_failure_email(user, order):
    context = {"user": user, "order": order}
    send_email("order/payment_failure.html", context, "Payment Failed", [user.email])


# Customer Service Emails
def send_support_ticket_confirmation_email(user, ticket):
    context = {"user": user, "ticket": ticket}
    send_email(
        "customer_service/support_ticket_confirmation.html",
        context,
        "Support Ticket Confirmation",
        [user.email],
    )


def send_support_ticket_update_email(user, ticket, response):
    context = {"user": user, "ticket": ticket, "response": response}
    send_email(
        "customer_service/support_ticket_update.html",
        context,
        "Support Ticket Update",
        [user.email],
    )


def send_feedback_request_email(user, order):
    context = {"user": user, "order": order}
    send_email(
        "customer_service/feedback_request.html",
        context,
        "We Value Your Feedback",
        [user.email],
    )


def send_product_review_reminder_email(user, order):
    context = {"user": user, "order": order}
    send_email(
        "customer_service/product_review_reminder.html",
        context,
        "Review Your Purchase",
        [user.email],
    )


def send_customer_survey_email(user):
    context = {"user": user}
    send_email(
        "customer_service/customer_survey.html",
        context,
        "We'd Love Your Feedback",
        [user.email],
    )


# Marketing Related Emails
def send_new_product_announcement_email(user, product, product_link):
    context = {"user": user, "product": product, "product_link": product_link}
    send_email(
        "marketing/new_product_announcement.html",
        context,
        "New Product Alert!",
        [user.email],
    )


def send_back_in_stock_email(user, product, product_link):
    context = {"user": user, "product": product, "product_link": product_link}
    send_email("marketing/back_in_stock.html", context, "Back in Stock!", [user.email])


def send_price_drop_alert_email(user, product, product_link):
    context = {"user": user, "product": product, "product_link": product_link}
    send_email(
        "marketing/price_drop_alert.html", context, "Price Drop Alert!", [user.email]
    )


def send_personalized_recommendations_email(user, products):
    context = {"user": user, "products": products}
    send_email(
        "marketing/personalized_recommendations.html",
        context,
        "Recommended for You",
        [user.email],
    )


def send_newsletter_confirmation_email(user):
    context = {"user": user}
    send_email(
        "marketing/newsletter_confirmation.html",
        context,
        "Newsletter Subscription Confirmed",
        [user.email],
    )


def send_promotional_offers_email(user, offers):
    context = {"user": user, "offers": offers}
    send_email(
        "marketing/promotional_offers.html",
        context,
        "Exclusive Promotional Offers",
        [user.email],
    )


def send_special_occasion_offers_email(user, offers):
    context = {"user": user, "offers": offers}
    send_email(
        "marketing/special_occasion_offers.html",
        context,
        "Special Occasion Offers",
        [user.email],
    )


def send_seasonal_sale_email(user, sale_link):
    context = {"user": user, "sale_link": sale_link}
    send_email("marketing/seasonal_sale.html", context, "Seasonal Sale!", [user.email])


# Vendor Related Emails
def send_new_order_notification_email(vendor, order):
    context = {"vendor": vendor, "order": order}
    send_email(
        "vendor/new_order_notification.html",
        context,
        "New Order Received",
        [vendor.email],
    )


def send_low_stock_alert_email(vendor, product):
    context = {"vendor": vendor, "product": product}
    send_email(
        "vendor/low_stock_alert.html", context, "Low Stock Alert", [vendor.email]
    )


def send_product_approval_rejection_email(vendor, product, status):
    context = {"vendor": vendor, "product": product, "status": status}
    send_email(
        "vendor/product_approval_rejection.html",
        context,
        f"Product {status}",
        [vendor.email],
    )


def send_payment_settlement_email(vendor, order):
    context = {"vendor": vendor, "order": order}
    send_email(
        "vendor/payment_settlement.html", context, "Payment Settlement", [vendor.email]
    )


def send_performance_report_email(vendor, total_sales, total_orders):
    context = {
        "vendor": vendor,
        "total_sales": total_sales,
        "total_orders": total_orders,
    }
    send_email(
        "vendor/performance_report.html", context, "Performance Report", [vendor.email]
    )


def send_account_status_update_email(vendor, status):
    context = {"vendor": vendor, "status": status}
    send_email(
        "vendor/account_status_update.html",
        context,
        "Account Status Update",
        [vendor.email],
    )


# Administrative Emails
def send_system_alert_email(admin, message):
    context = {"admin": admin, "message": message}
    send_email("admin/system_alerts.html", context, "System Alert", [admin.email])


def send_error_report_email(admin, error_message):
    context = {"admin": admin, "error_message": error_message}
    send_email("admin/error_reports.html", context, "Error Report", [admin.email])


def send_daily_summary_email(admin, total_orders, total_revenue, new_users):
    context = {
        "admin": admin,
        "total_orders": total_orders,
        "total_revenue": total_revenue,
        "new_users": new_users,
    }
    send_email("admin/daily_summary.html", context, "Daily Summary", [admin.email])


def send_weekly_summary_email(admin, total_orders, total_revenue, new_users):
    context = {
        "admin": admin,
        "total_orders": total_orders,
        "total_revenue": total_revenue,
        "new_users": new_users,
    }
    send_email("admin/weekly_summary.html", context, "Weekly Summary", [admin.email])


def send_monthly_summary_email(admin, total_orders, total_revenue, new_users):
    context = {
        "admin": admin,
        "total_orders": total_orders,
        "total_revenue": total_revenue,
        "new_users": new_users,
    }
    send_email("admin/monthly_summary.html", context, "Monthly Summary", [admin.email])


def send_inventory_alert_email(admin, low_stock_products):
    context = {"admin": admin, "low_stock_products": low_stock_products}
    send_email("admin/inventory_alerts.html", context, "Inventory Alert", [admin.email])


def send_critical_update_email(admin, update_message):
    context = {"admin": admin, "update_message": update_message}
    send_email("admin/critical_updates.html", context, "Critical Update", [admin.email])
