import os
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.core.mail import send_mail
from django.utils.timezone import now
from django.conf import settings
from system_users.models import CustomUser, QRCode, UserActivityLog

### ✅ Send Welcome Email When a User is Created ###
@receiver(post_save, sender=CustomUser)
def send_welcome_email(sender, instance, created, **kwargs):
    """Send a welcome email with login credentials when a user is created."""
    if created:
        subject = "Welcome to Anugami - Your Account is Ready!"
        message = f"""
        Hello {instance.name},

        Your Anugami account has been successfully created.
        You can now log in using your email.

        If you require any assistance, feel free to contact support.

        Best Regards,
        Anugami Team
        """
        send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [instance.email])

### ✅ Delete Expired QR Codes ###
@receiver(post_save, sender=QRCode)
def cleanup_expired_qr_codes(sender, instance, **kwargs):
    """Delete expired QR codes."""
    expired_qrs = QRCode.objects.filter(expires_at__lt=now())
    for qr in expired_qrs:
        qr_path = f"qrcodes/{qr.user.email}.png"
        if os.path.exists(qr_path):
            os.remove(qr_path)
        qr.delete()

### ✅ Log User Activity ###
@receiver(post_save, sender=CustomUser)
def log_user_activity(sender, instance, **kwargs):
    """Log user login and profile updates."""
    UserActivityLog.objects.create(
        user=instance,
        action="User updated profile" if instance.updated_at != instance.created_at else "User registered",
        ip_address="127.0.0.1"  # Replace with request.META['REMOTE_ADDR'] in views
    )

### ✅ Delete User-Related Data Upon Deletion ###
@receiver(post_delete, sender=CustomUser)
def cleanup_user_data(sender, instance, **kwargs):
    """Cleanup data when a user is deleted."""
    try:
        qr = QRCode.objects.get(user=instance)
        qr_path = f"qrcodes/{instance.email}.png"
        if os.path.exists(qr_path):
            os.remove(qr_path)
        qr.delete()
    except QRCode.DoesNotExist:
        pass
