import os
import random
import string
import pyotp
import qrcode
from datetime import timedelta
from django.utils.timezone import now
from django.core.mail import send_mail
from django.conf import settings
from django.shortcuts import get_object_or_404
from system_users.models import CustomUser, Role, QRCode, PasswordResetToken

### ✅ Generate Random Password ###
def generate_random_password(length=12):
    """Generate a secure random password"""
    return ''.join(random.choices(string.ascii_letters + string.digits, k=length))

### ✅ Send Welcome Email ###
def send_welcome_email(user_email, password):
    """Send welcome email with login credentials"""
    subject = "Welcome to Anugami - Your Login Credentials"
    message = f"""
    Hello,

    Your account has been created successfully.
    Here are your login details:

    Email: {user_email}
    Password: {password}

    Please log in and change your password immediately.
    """
    send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [user_email])

### ✅ Create a New System User ###
def create_system_user(email, name, role_name):
    """Create a system user, assign a role, and send credentials"""
    role = get_object_or_404(Role, name=role_name)
    password = generate_random_password()

    user, created = CustomUser.objects.get_or_create(
        email=email,
        defaults={'name': name, 'role': role, 'is_staff': True, 'is_admin': (role_name == "Super Admin")}
    )

    if created:
        user.set_password(password)
        user.save()
        send_welcome_email(email, password)

    return user, created


### ✅ Generate QR Code for 2FA ###
def generate_qr_code(user):
    """
    Ensure QR code generation uses a valid Base32 secret
    """
    try:
        # Validate existing or generate new secret
        if not user.otp_secret:
            user.otp_secret = pyotp.random_base32()
            user.save()

        # Validate Base32 encoding
        base64.b32decode(user.otp_secret, casefold=True)

        # Generate QR Code with validated secret
        otp_uri = pyotp.totp.TOTP(user.otp_secret).provisioning_uri(
            name=user.email, issuer_name="Anugami"
        )

        # Rest of QR code generation remains the same
        qr_code_path = f"qrcodes/{user.email}.png"
        os.makedirs("qrcodes", exist_ok=True)

        qr = qrcode.make(otp_uri)
        qr.save(qr_code_path)

        return {
            "qr_code_url": f"/qrcodes/{user.email}.png",
            "expires_at": now() + timedelta(minutes=5),
        }

    except (binascii.Error, TypeError) as e:
        # Regenerate secret if invalid
        user.otp_secret = pyotp.random_base32()
        user.save()

        # Recursive call to regenerate QR code
        return generate_qr_code(user)


### ✅ Verify OTP Code ###
import pyotp
import base64
import binascii


def verify_otp(user, otp):
    """
    Enhanced OTP verification with detailed logging
    """
    try:
        # Extensive logging
        print(f"User OTP Secret: {user.otp_secret}")
        print(f"Received OTP: {otp}")

        if not user.otp_secret:
            print("No OTP secret found")
            return False, "2FA is not enabled for this user."

        # Create TOTP object
        totp = pyotp.TOTP(user.otp_secret)

        # Try current OTP
        current_otp_valid = totp.verify(otp)
        print(f"Current OTP Valid: {current_otp_valid}")

        # Additional checks for time-based variations
        # Check previous and next OTPs to account for time drift
        previous_otp_valid = totp.verify(otp, valid_window=1)
        print(f"Previous OTP Valid: {previous_otp_valid}")

        if current_otp_valid or previous_otp_valid:
            return True, "✅ OTP Verified Successfully!"

        return False, "❌ Invalid OTP!"

    except Exception as e:
        print(f"OTP Verification Error: {str(e)}")
        return False, f"Verification Error: {str(e)}"


import pyotp
import base64
import binascii


def verify_otp(user, otp):
    """
    Robust OTP verification with error handling
    """
    try:
        # Check if OTP secret exists
        if not user.otp_secret:
            return False, "2FA is not enabled for this user."

        # Validate Base32 encoding
        try:
            # Attempt to decode the secret to ensure it's valid Base32
            base64.b32decode(user.otp_secret, casefold=True)
        except (binascii.Error, TypeError):
            # If secret is invalid, regenerate a new valid secret
            user.otp_secret = pyotp.random_base32()
            user.save()
            return False, "Invalid 2FA secret. Please reset 2FA."

        # Verify OTP
        totp = pyotp.TOTP(user.otp_secret)
        if totp.verify(otp):
            return True, "✅ OTP Verified Successfully!"

        return False, "❌ Invalid OTP!"

    except Exception as e:
        return False, f"Verification error: {str(e)}"


### ✅ Generate Password Reset Token ###
def generate_password_reset_token(user):
    """Create a password reset token for the user"""
    token = PasswordResetToken.objects.create(user=user)
    return token.token

### ✅ Send Password Reset Email ###
def send_password_reset_email(user, token):
    """Send an email with password reset link"""
    reset_link = f"{settings.FRONTEND_URL}/reset-password?token={token}"

    subject = "Password Reset Request - Anugami"
    message = f"""
    Hello {user.name},

    We received a request to reset your password. Click the link below to reset it:
    
    {reset_link}

    This link will expire in 1 hour.

    If you did not request this, please ignore this email.
    """
    send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [user.email])

### ✅ Reset User Password ###
def reset_user_password(token, new_password):
    """Reset user password using token"""
    reset_token = get_object_or_404(PasswordResetToken, token=token)

    if reset_token.is_expired():
        return False, "Token has expired."

    user = reset_token.user
    user.set_password(new_password)
    user.save()

    reset_token.delete()  # Delete token after successful reset
    return True, "✅ Password reset successfully!"

### ✅ Update User Profile ###
def update_user_profile(user, name=None, address=None, phone_number=None, profile_image=None):
    """Update user profile details"""
    if name:
        user.name = name
    if address:
        user.address = address
    if phone_number:
        user.phone_number = phone_number
    if profile_image:
        user.profile_image = profile_image
    user.save()
    return user
