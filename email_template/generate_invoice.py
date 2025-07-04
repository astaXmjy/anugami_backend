from io import BytesIO
from reportlab.lib.pagesizes import letter  # type: ignore
from reportlab.pdfgen import canvas  # type: ignore
from reportlab.lib.units import inch  # type: ignore
from django.core.mail import EmailMessage
from django.http import HttpResponse
from decimal import Decimal


def generate_order_invoice(order):
    """Generate invoice PDF for Order model and return as BytesIO."""
    buffer = BytesIO()
    p = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter

    # Get shipping address
    shipping_address = order.orderaddress_set.filter(address_type="shipping").first()
    billing_address = order.orderaddress_set.filter(address_type="billing").first()

    # Use billing address if available, otherwise shipping
    customer_address = billing_address or shipping_address

    if not customer_address:
        return None

    # Company Info
    p.setFont("Helvetica-Bold", 18)
    p.drawString(50, height - 50, "INVOICE")

    p.setFont("Helvetica", 10)
    p.drawString(50, height - 70, "Your Company Name")
    p.drawString(50, height - 85, "Your Company Address")
    p.drawString(50, height - 100, "Phone: +91 1234567890")
    p.drawString(50, height - 115, "Email: support@yourcompany.com")

    # Order Details
    p.setFont("Helvetica-Bold", 12)
    p.drawString(400, height - 70, f"Invoice #{order.order_number}")
    p.setFont("Helvetica", 10)
    p.drawString(
        400, height - 85, f"Order Date: {order.created_at.strftime('%d/%m/%Y')}"
    )
    p.drawString(400, height - 100, f"Order Status: {order.status}")

    # Payment Details
    if hasattr(order, "payment") and order.payment:
        p.drawString(
            400, height - 115, f"Payment Method: {order.payment.get_method_display()}"
        )
        p.drawString(
            400,
            height - 130,
            f"Payment Status: {order.payment.get_payment_status_display()}",
        )

    # Bill To
    p.setFont("Helvetica-Bold", 12)
    p.drawString(50, height - 150, "Bill To:")
    p.setFont("Helvetica", 10)
    p.drawString(50, height - 165, f"{customer_address.full_name}")
    p.drawString(50, height - 180, f"{customer_address.street}")
    p.drawString(50, height - 195, f"{customer_address.area}, {customer_address.city}")
    p.drawString(
        50,
        height - 210,
        f"{customer_address.state}, {customer_address.country} - {customer_address.pincode}",
    )
    p.drawString(50, height - 225, f"Phone: {customer_address.phone}")
    p.drawString(50, height - 240, f"Email: {customer_address.email}")

    # Ship To (if different from billing)
    if (
        billing_address
        and shipping_address
        and billing_address.id != shipping_address.id
    ):
        p.setFont("Helvetica-Bold", 12)
        p.drawString(300, height - 150, "Ship To:")
        p.setFont("Helvetica", 10)
        p.drawString(300, height - 165, f"{shipping_address.full_name}")
        p.drawString(300, height - 180, f"{shipping_address.street}")
        p.drawString(
            300, height - 195, f"{shipping_address.area}, {shipping_address.city}"
        )
        p.drawString(
            300,
            height - 210,
            f"{shipping_address.state}, {shipping_address.country} - {shipping_address.pincode}",
        )
        p.drawString(300, height - 225, f"Phone: {shipping_address.phone}")

    # Draw a line
    p.line(50, height - 260, width - 50, height - 260)

    # Table Header
    p.setFont("Helvetica-Bold", 10)
    p.drawString(50, height - 280, "Item")
    p.drawString(250, height - 280, "SKU")
    p.drawString(325, height - 280, "Price")
    p.drawString(400, height - 280, "Qty")
    p.drawString(450, height - 280, "Discount")
    p.drawString(515, height - 280, "Total")

    # Draw a line
    p.line(50, height - 285, width - 50, height - 285)

    # Table Items
    y = height - 305
    p.setFont("Helvetica", 9)

    order_items = order.items.all()
    subtotal = Decimal("0.00")

    for item in order_items:
        if y < 150:  # Start a new page if we're running out of space
            p.showPage()
            p.setFont("Helvetica", 9)
            y = height - 50

        p.drawString(50, y, item.name[:30])  # Truncate long names
        p.drawString(250, y, item.sku or "-")
        p.drawString(325, y, f"₹{item.price}")
        p.drawString(400, y, str(item.quantity))
        p.drawString(450, y, f"₹{item.discount_amount}")
        p.drawString(515, y, f"₹{item.final_price}")

        subtotal += item.final_price
        y -= 20

    # Draw a line
    p.line(50, y - 10, width - 50, y - 10)

    # Totals
    p.setFont("Helvetica-Bold", 10)
    p.drawString(400, y - 30, "Subtotal:")
    p.drawString(515, y - 30, f"₹{subtotal}")

    # Shipping cost if available
    shipping_cost = Decimal("0.00")
    if hasattr(order, "shipping") and order.shipping and order.shipping.shipping_cost:
        shipping_cost = order.shipping.shipping_cost
        p.drawString(400, y - 50, "Shipping:")
        p.drawString(515, y - 50, f"₹{shipping_cost}")

    # Total
    p.setFont("Helvetica-Bold", 11)
    p.drawString(400, y - 70, "Total:")
    p.drawString(515, y - 70, f"₹{order.total_amount}")

    # Footer
    p.setFont("Helvetica", 8)
    p.drawString(50, 40, "Thank you for your business!")
    p.drawString(
        50,
        30,
        "For any questions regarding this invoice, please contact our customer support.",
    )
    p.drawString(
        50, 20, "This is a computer-generated invoice and does not require a signature."
    )

    p.showPage()
    p.save()

    buffer.seek(0)
    return buffer
