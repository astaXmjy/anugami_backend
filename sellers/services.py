# sellers/services.py
import os
import logging
from typing import Dict, Any, Optional
import pyotp
import firebase_admin
from firebase_admin import auth, storage, credentials
from django.conf import settings
from django.db import transaction
from django.core.exceptions import ValidationError
from django.core.files.storage import default_storage
import requests
from django.contrib.auth import get_user_model
from .models import Seller, ShippingLocation
from .email_otp import EmailOTP
from django.core.mail import send_mail
from django.template.loader import render_to_string
import random
import string
from django.core.cache import cache


logger = logging.getLogger(__name__)

User = get_user_model()


class FirebaseAuthService:
    """
    Service for handling Firebase Authentication operations.
    """

    # Initialize Firebase if not already initialized
    if not firebase_admin._apps:
        try:
            CREDENTIALS_PATH = os.path.join(
                settings.BASE_DIR, "firebase", "firebase-credentials.json"
            )
            cred = credentials.Certificate(CREDENTIALS_PATH)
            firebase_admin.initialize_app(cred)
            logger.info("Firebase initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Firebase: {str(e)}")

    @staticmethod
    def create_vendor_account(
        email: str, password: str, phone_number: Optional[str] = None
    ) -> str:
        """
        Create a new vendor account in Firebase Authentication.
        Returns Firebase User UID.
        """
        try:
            user = auth.create_user(
                email=email,
                password=password,
                phone_number=phone_number,
                email_verified=False,
            )
            auth.set_custom_user_claims(
                user.uid, {"role": "vendor", "status": "pending", "is_verified": False}
            )
            return user.uid
        except firebase_admin.auth.AuthError as e:
            logger.error(f"Firebase Auth Error: {str(e)}")
            raise ValueError(f"Authentication failed: {str(e)}")

    @staticmethod
    def verify_phone_number(uid: str, phone_number: str) -> bool:
        """
        Verify vendor's phone number

        Args:
            uid (str): Firebase User UID
            phone_number (str): Phone number to verify

        Returns:
            bool: Verification status
        """
        try:
            # Update user's phone number
            auth.update_user(uid, phone_number=phone_number)

            # Update custom claims
            auth.set_custom_user_claims(
                uid,
                {"role": "vendor", "status": "phone_verified", "is_verified": False},
            )

            return True

        except Exception as e:
            logger.error(f"Phone verification failed: {str(e)}")
            return False

    @staticmethod
    def approve_vendor(uid: str) -> bool:
        """
        Finalize vendor approval in Firebase

        Args:
            uid (str): Firebase User UID

        Returns:
            bool: Approval status
        """
        try:
            auth.set_custom_user_claims(
                uid, {"role": "vendor", "status": "approved", "is_verified": True}
            )
            return True
        except Exception as e:
            logger.error(f"Vendor approval failed: {str(e)}")
            return False


class DocumentUploadService:
    """
    Service for handling document uploads
    """

    ALLOWED_EXTENSIONS = [".pdf", ".jpg", ".jpeg", ".png"]
    MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB

    @classmethod
    def validate_document(cls, document):
        """
        Validate uploaded document

        Args:
            document: File to validate

        Raises:
            ValidationError: If document is invalid
        """
        if not document:
            return

        # Check file size
        if document.size > cls.MAX_FILE_SIZE:
            raise ValidationError(
                f"File size must be less than {cls.MAX_FILE_SIZE / 1024 / 1024}MB"
            )

        # Check file extension
        ext = os.path.splitext(document.name)[1].lower()
        if ext not in cls.ALLOWED_EXTENSIONS:
            raise ValidationError(
                f"Invalid file type. Allowed types: {', '.join(cls.ALLOWED_EXTENSIONS)}"
            )

    def upload_to_firebase_storage(self, document, seller_id, doc_type):
        """
        Upload document to Firebase Storage

        Args:
            document: File to upload
            seller_id (str): Seller's unique identifier
            doc_type (str): Type of document

        Returns:
            str: Download URL of uploaded document
        """
        try:
            # Validate document first
            filename = f"sellers/{seller_id}/{doc_type}_{document.name}"
            bucket = storage.bucket()
            blob = bucket.blob(filename)
            blob.upload_from_file(document)
            blob.make_public()
            return blob.public_url

        except Exception as e:
            logger.error(f"Document upload failed: {str(e)}")
            raise ValidationError(f"Failed to upload document: {str(e)}")


class EmailOTP:
    @staticmethod
    def generate_otp(length=6):
        """Generate a random OTP."""
        return "".join(random.choices(string.digits, k=length))

    @staticmethod
    def store_otp(email, otp, timeout=300):
        """Store OTP in cache with 5 minutes expiry."""
        cache_key = f"email_otp_{email}"
        cache.set(cache_key, otp, timeout)

    @staticmethod
    def verify_otp(email, otp):
        """Verify the OTP for given email."""
        cache_key = f"email_otp_{email}"
        stored_otp = cache.get(cache_key)

        if not stored_otp:
            return False

        # Delete OTP after verification attempt
        cache.delete(cache_key)

        return stored_otp == otp

    @staticmethod
    def send_verification_email(email, otp):
        """Send OTP verification email."""
        try:
            # Render email template
            html_message = render_to_string(
                "sellers/verification.html", {"otp": otp, "valid_minutes": 5}
            )

            # Send email
            send_mail(
                subject="Email Verification OTP",
                message=f"Your verification code is: {otp}",
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[email],
                html_message=html_message,
                fail_silently=False,
            )
            return True
        except Exception as e:
            print(f"Failed to send verification email: {str(e)}")
            return False


class SellerVerificationService:
    """
    Comprehensive service for seller verification process.
    """

    def __init__(self):
        self.firebase_service = FirebaseAuthService()

    @transaction.atomic
    def create_seller_application(self, data: Dict[str, Any]):
        """
        Create a seller application in PostgreSQL, ensuring all fields align with the new database schema.
        """
        try:
            # Validate unique email and phone
            if Seller.objects.filter(email=data["email"]).exists():
                raise ValidationError("Email already registered")
            if Seller.objects.filter(phone=data["phone"]).exists():
                raise ValidationError("Phone number already registered")

            # Extract PAN card image if present
            pan_card_image = data.pop("pan_card_image", None)

            # Fetch or create User instance (adjusted for PostgreSQL)
            user, _ = User.objects.get_or_create(
                email=data["email"],
                defaults={
                    "name": data["full_name"],  # Use 'name' instead of 'username'
                },
            )
            if _:
                user.set_password(data["password"])
                user.save()

            # Create Seller record linked to Django User
            seller = Seller.objects.create(
                user=user,
                full_name=data["full_name"],
                email=data["email"],
                phone=data["phone"],
                business_name=data["business_name"],
                business_address=data.get("business_address", ""),
                gst_number=data.get("gst_number", ""),
                pan_number=data.get("pan_number", ""),
                account_name=data.get("account_name", ""),
                account_number=data.get("account_number", ""),
                ifsc_code=data.get("ifsc_code", ""),
                bank_name=data.get("bank_name", ""),
            )

            # Upload PAN card if available
            if pan_card_image:
                try:
                    document_service = DocumentUploadService()
                    pan_url = document_service.upload_pan_to_firebase(
                        pan_card_image, seller.id
                    )
                    seller.pan_document_url = pan_url
                    seller.save()
                except Exception as e:
                    logger.error(f"Failed to upload PAN card: {str(e)}")
                    # Continue with registration despite upload failure

            # Send verification email
            otp = EmailOTP.generate_otp()  # Correct usage of static method
            EmailOTP.store_otp(seller.email, otp)  # Correct usage of static method
            EmailOTP.send_verification_email(
                seller.email, otp
            )  # Correct usage of static method

            return seller

        except Exception as e:
            logger.error(f"Seller application creation failed: {str(e)}")
            raise ValidationError(f"Registration failed: {str(e)}")


class FirebaseAuthService:
    @staticmethod
    def reset_password(email):
        """Send Firebase password reset email"""
        from firebase_admin import auth

        try:
            auth.generate_password_reset_link(email)
            return {"message": "Password reset email sent"}
        except Exception as e:
            return {"error": str(e)}


class TwoFactorAuthService:
    @staticmethod
    def generate_secret():
        """Generate a unique secret key for TOTP authentication"""
        return pyotp.random_base32()

    @staticmethod
    def generate_qr_url(secret, email):
        """Generate a QR Code URL for Google Authenticator"""
        return pyotp.totp.TOTP(secret).provisioning_uri(
            email, issuer_name="YourPlatform"
        )

    @staticmethod
    def verify_otp(secret, otp):
        """Verify OTP from Google Authenticator"""
        totp = pyotp.TOTP(secret)
        return totp.verify(otp)


class ShiprocketService:
    BASE_URL = "https://apiv2.shiprocket.in/v1/external"

    @staticmethod
    def get_auth_token():
        """Authenticate with Shiprocket and return the token."""
        response = requests.post(
            f"{ShiprocketService.BASE_URL}/auth/login",
            json={"email": "your_email", "password": "your_password"},
        )
        if response.status_code == 200:
            return response.json().get("token")
        return None

    @staticmethod
    def add_pickup_location(seller):
        """
        Sync a seller's shipping location with Shiprocket.
        Adjusted to retrieve `ShippingLocation` via PostgreSQL instead of MongoDB.
        """
        shipping_location = ShippingLocation.objects.filter(seller=seller).first()
        if not shipping_location:
            return {"error": "No shipping location found for seller"}

        token = ShiprocketService.get_auth_token()
        if not token:
            return {"error": "Failed to authenticate with Shiprocket"}

        payload = {
            "pickup_location": f"{seller.business_name}",
            "phone": shipping_location.phone_number,
            "address": shipping_location.address,
            "city": shipping_location.city,
            "state": shipping_location.state,
            "country": "India",
            "pincode": shipping_location.pincode,
            "email": seller.email,
        }

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        response = requests.post(
            f"{ShiprocketService.BASE_URL}/settings/company/addpickup",
            json=payload,
            headers=headers,
        )
        return response.json()

    @staticmethod
    def check_serviceability(seller, delivery_pincode, weight, cod=0):
        """Check if a shipment can be delivered"""
        token = ShiprocketService.get_auth_token()
        if not token:
            return {"error": "Failed to authenticate with Shiprocket"}

        params = {
            "pickup_postcode": seller.shipping_location.pincode,
            "delivery_postcode": delivery_pincode,
            "cod": cod,
            "weight": weight,
        }

        headers = {"Authorization": f"Bearer {token}"}
        response = requests.get(
            f"{ShiprocketService.BASE_URL}/courier/serviceability/",
            params=params,
            headers=headers,
        )
        return response.json()

    @staticmethod
    def create_order(order):
        """Create an order in Shiprocket"""
        token = ShiprocketService.get_auth_token()
        if not token:
            return {"error": "Failed to authenticate with Shiprocket"}

        payload = {
            "order_id": order.id,
            "order_date": str(order.created_at),
            "pickup_location": order.seller.business_name,
            "billing_customer_name": order.customer_name,
            "billing_address": order.customer_address,
            "billing_pincode": order.customer_pincode,
            "billing_city": order.customer_city,
            "billing_state": order.customer_state,
            "billing_country": "India",
            "billing_phone": order.customer_phone,
            "order_items": [
                {
                    "name": item.product_name,
                    "sku": item.sku,
                    "units": item.quantity,
                    "selling_price": item.price,
                }
                for item in order.items
            ],
            "payment_method": "Prepaid",
            "sub_total": order.total_price,
            "length": order.length,
            "breadth": order.breadth,
            "height": order.height,
            "weight": order.weight,
        }

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        response = requests.post(
            f"{ShiprocketService.BASE_URL}/orders/create/adhoc",
            json=payload,
            headers=headers,
        )
        return response.json()

    @staticmethod
    def update_order_status(order_id, status):
        """
        Update the status of an order in Shiprocket.

        Args:
            order_id (str): The unique identifier of the order.
            status (str): The new status of the order.

        Returns:
            dict: The response from the Shiprocket API.
        """
        token = ShiprocketService.get_auth_token()
        if not token:
            return {"error": "Failed to authenticate with Shiprocket"}

        payload = {"order_id": order_id, "order_status": status}

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        response = requests.put(
            f"{ShiprocketService.BASE_URL}/orders/update/status",
            json=payload,
            headers=headers,
        )
        return response.json()

    @staticmethod
    def get_order_tracking(order_id):
        """
        Retrieve the tracking information for an order in Shiprocket.

        Args:
            order_id (str): The unique identifier of the order.

        Returns:
            dict: The tracking information for the order.
        """
        token = ShiprocketService.get_auth_token()
        if not token:
            return {"error": "Failed to authenticate with Shiprocket"}

        headers = {"Authorization": f"Bearer {token}"}
        response = requests.get(
            f"{ShiprocketService.BASE_URL}/orders/{order_id}/track", headers=headers
        )
        return response.json()

    @staticmethod
    def get_shipping_rates(seller, delivery_pincode, weight, cod=0):
        """
        Retrieve shipping rates for a given order from Shiprocket.

        Args:
            seller (Seller): The seller associated with the order.
            delivery_pincode (str): The delivery pincode.
            weight (float): The total weight of the order.
            cod (int, optional): Indicates if the order is a Cash on Delivery. Defaults to 0.

        Returns:
            dict: A dictionary containing the available shipping rates.
        """
        token = ShiprocketService.get_auth_token()
        if not token:
            return {"error": "Failed to authenticate with Shiprocket"}

        params = {
            "pickup_postcode": seller.shipping_location.pincode,
            "delivery_postcode": delivery_pincode,
            "cod": cod,
            "weight": weight,
        }

        headers = {"Authorization": f"Bearer {token}"}
        response = requests.get(
            f"{ShiprocketService.BASE_URL}/courier/serviceability/",
            params=params,
            headers=headers,
        )
        return response.json()


class DocumentUploadService:
    """
    Service for handling PAN card document uploads to Firebase Storage
    """

    ALLOWED_EXTENSIONS = [".pdf", ".jpg", ".jpeg", ".png"]
    MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB

    @classmethod
    def validate_document(cls, document):
        """
        Validate uploaded PAN card document

        Args:
            document: File to validate

        Raises:
            ValidationError: If document is invalid
        """
        if not document:
            return

        # Check file size
        if document.size > cls.MAX_FILE_SIZE:
            raise ValidationError(
                f"File size must be less than {cls.MAX_FILE_SIZE / 1024 / 1024}MB"
            )

        # Check file extension
        ext = os.path.splitext(document.name)[1].lower()
        if ext not in cls.ALLOWED_EXTENSIONS:
            raise ValidationError(
                f"Invalid file type. Allowed types: {', '.join(cls.ALLOWED_EXTENSIONS)}"
            )

    @staticmethod
    def upload_pan_to_firebase(document, seller_id):
        """
        Upload PAN card document to Firebase Storage

        Args:
            document: PAN card file to upload
            seller_id (str): Seller's unique identifier

        Returns:
            str: Download URL of uploaded PAN card
        """
        try:
            from firebase_admin import storage

            # Generate unique filename
            filename = f"sellers/{seller_id}/pan_{document.name}"

            # Get Firebase bucket
            bucket = storage.bucket()

            # Create a blob and upload the file
            blob = bucket.blob(filename)

            # Read file content
            document.seek(0)  # Ensure we're at the beginning of the file
            file_content = document.read()

            # Upload content
            blob.upload_from_string(file_content, content_type=document.content_type)

            # Make the blob publicly accessible
            blob.make_public()

            # Return the public URL
            return blob.public_url

        except Exception as e:
            logger.error(f"PAN card upload failed: {str(e)}")
            raise ValidationError(f"Failed to upload PAN card: {str(e)}")
