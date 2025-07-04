from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings


def send_email(template_name, context, subject, recipient_list):
    """
    Utility function to send emails using templates.

    :param template_name: Path to the email template (e.g., 'account/welcome.html').
    :param context: Dictionary of context variables for the template.
    :param subject: Email subject.
    :param recipient_list: List of recipient email addresses.
    """
    # Render the email template
    message = render_to_string(f"email_templates/{template_name}", context)

    # Send the email
    send_mail(
        subject=subject,
        message="",  # Leave empty for HTML emails
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=recipient_list,
        html_message=message,  # Use HTML content
    )
