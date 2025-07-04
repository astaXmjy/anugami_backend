# sellers/views.py
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.exceptions import ValidationError

from django.db import transaction
from django.core.exceptions import ObjectDoesNotExist
from django.conf import settings
from .services import ShiprocketService
import logging
import firebase_admin
from firebase_admin import auth

from .models import Seller, ShippingLocation, Order
from .serializers import (
    SellerSerializer,
    SellerRegistrationSerializer,
    DocumentUploadSerializer,
    ShippingLocationSerializer,
    OrderSerializer,
)
from .services import (
    SellerVerificationService,
    DocumentUploadService,
    ShiprocketService,
)
from .email_otp import EmailOTP
from rest_framework.permissions import IsAdminUser

logger = logging.getLogger(__name__)


class AdminSellerViewSet(viewsets.ModelViewSet):
    """
    Seller management API for Django Admin Panel in Next.js.
    """

    queryset = Seller.objects.all()
    serializer_class = SellerSerializer
    permission_classes = [IsAdminUser]

    @action(detail=True, methods=["POST"])
    def approve(self, request, pk=None):
        """Approve a seller"""
        seller = self.get_object()
        seller.status = "approved"
        seller.save()
        return Response(
            {"success": True, "message": "Seller approved successfully"},
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=["POST"])
    def reject(self, request, pk=None):
        """Reject a seller"""
        seller = self.get_object()
        seller.status = "rejected"
        seller.save()
        return Response(
            {"success": True, "message": "Seller rejected successfully"},
            status=status.HTTP_200_OK,
        )


class ShippingLocationViewSet(viewsets.ModelViewSet):
    """
    Viewset for managing shipping locations
    """

    queryset = ShippingLocation.objects.all()
    serializer_class = ShippingLocationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """
        Return shipping locations for the current seller
        """
        # Change this line to filter by seller instead of seller_email
        try:
            seller = self.request.user.seller_profile
            return ShippingLocation.objects.filter(seller=seller)
        except:
            return ShippingLocation.objects.none()

    def perform_create(self, serializer):
        """
        Set the seller when creating a new shipping location
        """
        # Change this line to save seller instead of seller_email
        try:
            seller = self.request.user.seller_profile
            serializer.save(seller=seller)
        except:
            raise ValidationError("User does not have a seller profile")


class OrderViewSet(viewsets.ModelViewSet):
    """
    Viewset for managing orders
    """

    queryset = Order.objects.all()
    serializer_class = OrderSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """
        Return orders for the current seller
        """
        return Order.objects.filter(seller=self.request.user.seller_profile)

    def perform_create(self, serializer):
        """
        Set the seller when creating a new order
        """
        order = serializer.save(seller=self.request.user.seller_profile)

        # Optional: Integrate with Shiprocket
        try:
            ShiprocketService.create_order(order)
        except Exception as e:
            logger.error(f"Failed to create order in Shiprocket: {str(e)}")


class SellerManagementViewSet(viewsets.ModelViewSet):
    """
    Comprehensive Seller Management Viewset
    Handles all seller-related operations with robust error handling
    """

    queryset = Seller.objects.all()
    serializer_class = SellerSerializer
    permission_classes = [IsAuthenticated]

    def get_permissions(self):
        """
        Custom permission mapping
        """
        if self.action in ["register", "request_email_otp", "verify_email_otp"]:
            return [AllowAny()]
        return [IsAuthenticated()]

    @action(detail=False, methods=["POST"], permission_classes=[AllowAny])
    def register(self, request):
        """
        Seller Registration Endpoint with PAN card upload and bank details
        """
        try:
            # Check if request has multipart form data (for file upload)
            if not request.content_type.startswith("multipart/form-data"):
                return Response(
                    {
                        "success": False,
                        "message": "Multipart form data required for PAN card upload",
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Log incoming data for debugging
            print("Incoming request data:", dict(request.data))
            print(
                "Bank details received:",
                {
                    "account_name": request.data.get("account_name"),
                    "account_number": request.data.get("account_number"),
                    "ifsc_code": request.data.get("ifsc_code"),
                    "bank_name": request.data.get("bank_name"),
                },
            )

            # Validate incoming data
            serializer = SellerRegistrationSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)

            # Extract PAN card from request
            pan_document = request.FILES.get("pan_card_image")
            pan_number = request.data.get("pan_number")

            # Validate PAN card image
            if not pan_document:
                return Response(
                    {"success": False, "message": "PAN card image is required"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Validate PAN number format
            import re

            if not pan_number or not re.match(
                r"^[A-Z]{5}[0-9]{4}[A-Z]{1}$", pan_number
            ):
                return Response(
                    {"success": False, "message": "Invalid PAN number format"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Create seller application with bank details
            verification_service = SellerVerificationService()

            # FIXED: Prepare seller_data with bank details and use it
            seller_data = serializer.validated_data.copy()
            seller_data.update(
                {
                    "account_name": request.data.get("account_name", ""),
                    "account_number": request.data.get("account_number", ""),
                    "ifsc_code": request.data.get("ifsc_code", ""),
                    "bank_name": request.data.get("bank_name", ""),
                }
            )

            print("Creating seller with bank details:", seller_data)  # Debug log

            # FIXED: Pass seller_data instead of serializer.validated_data
            seller = verification_service.create_seller_application(seller_data)

            # Upload PAN card to Firebase
            document_service = DocumentUploadService()
            document_service.validate_document(pan_document)
            pan_url = document_service.upload_pan_to_firebase(pan_document, seller.id)

            # Update seller with PAN details
            seller.pan_number = pan_number
            seller.pan_document_url = pan_url
            seller.save()

            return Response(
                {
                    "success": True,
                    "message": "Seller application with PAN card submitted successfully",
                    "seller_id": seller.id,
                    "status": seller.status,
                    "pan_document_url": pan_url,
                },
                status=status.HTTP_201_CREATED,
            )

        except ValidationError as e:
            logger.error(f"Seller Registration Error: {str(e)}")
            return Response(
                {"success": False, "message": str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as e:
            logger.error(f"Unexpected Seller Registration Error: {str(e)}")
            return Response(
                {
                    "success": False,
                    "message": "An unexpected error occurred during registration",
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @action(detail=False, methods=["POST"], permission_classes=[AllowAny])
    def request_email_otp(self, request):
        """
        Request Email OTP for Verification
        """
        try:
            email = request.data.get("email")
            if not email:
                return Response(
                    {"success": False, "message": "Email is required"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Generate and send OTP
            otp = EmailOTP.generate_otp()
            EmailOTP.store_otp(email, otp)
            EmailOTP.send_verification_email(email, otp)

            return Response(
                {"success": True, "message": "OTP sent successfully"},
                status=status.HTTP_200_OK,
            )

        except Exception as e:
            logger.error(f"Email OTP Request Error: {str(e)}")
            return Response(
                {"success": False, "message": "Failed to send OTP"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @action(detail=False, methods=["POST"], permission_classes=[AllowAny])
    def verify_email_otp(self, request):
        """
        Verify Email OTP
        """
        try:
            email = request.data.get("email")
            otp = request.data.get("otp")

            if not email or not otp:
                return Response(
                    {"success": False, "message": "Email and OTP are required"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Verify OTP
            if not EmailOTP.verify_otp(email, otp):
                return Response(
                    {"success": False, "message": "Invalid or expired OTP"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Mark email as verified
            seller = Seller.objects.filter(email=email).first()
            if seller:
                seller.is_email_verified = True
                seller.save()

            return Response(
                {"success": True, "message": "Email verified successfully"},
                status=status.HTTP_200_OK,
            )

        except Exception as e:
            logger.error(f"Email OTP Verification Error: {str(e)}")
            return Response(
                {"success": False, "message": "Verification failed"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @action(detail=False, methods=["POST"])
    def upload_pan_card(self, request):
        """
        Upload PAN card document to Firebase Storage
        """
        try:
            from .serializers import PanCardUploadSerializer

            # Use PAN card upload serializer
            serializer = PanCardUploadSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)

            # Get seller
            seller = request.user.seller_profile

            # Get PAN card document and number
            pan_document = serializer.validated_data.get("pan_document")
            pan_number = serializer.validated_data.get("pan_number")

            # Validate and upload PAN card
            document_service = DocumentUploadService()
            document_service.validate_document(pan_document)

            # Upload to Firebase
            pan_url = document_service.upload_pan_to_firebase(pan_document, seller.id)

            # Update seller model
            seller.pan_number = pan_number
            seller.pan_document_url = pan_url
            seller.is_document_verified = False  # Needs admin approval
            seller.save()

            return Response(
                {
                    "success": True,
                    "message": "PAN card uploaded successfully",
                    "pan_document_url": pan_url,
                },
                status=status.HTTP_200_OK,
            )

        except ValidationError as e:
            logger.error(f"PAN Card Upload Error: {str(e)}")
            return Response(
                {"success": False, "message": str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as e:
            logger.error(f"Unexpected PAN Card Upload Error: {str(e)}")
            return Response(
                {"success": False, "message": "Failed to upload PAN card"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @action(detail=False, methods=["GET"])
    def profile(self, request):
        """
        Get Seller Profile
        """
        try:
            seller = request.user.seller_profile
            serializer = self.get_serializer(seller)

            return Response(
                {"success": True, "profile": serializer.data}, status=status.HTTP_200_OK
            )

        except ObjectDoesNotExist:
            return Response(
                {"success": False, "message": "Seller profile not found"},
                status=status.HTTP_404_NOT_FOUND,
            )
        except Exception as e:
            logger.error(f"Profile Retrieval Error: {str(e)}")
            return Response(
                {"success": False, "message": "Failed to retrieve profile"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @action(detail=False, methods=["GET"])
    def account_settings(self, request):
        """
        Get seller's account settings including banking details and document verification status
        """
        try:
            seller = request.user.seller_profile

            # Create response with account settings
            account_data = {
                "bank_details": {
                    "account_name": seller.account_name,
                    "account_number": seller.account_number,
                    "ifsc_code": seller.ifsc_code,
                    "bank_name": seller.bank_name,
                },
                "pan_details": {
                    "pan_number": seller.pan_number,
                    "pan_document_url": seller.pan_document_url,
                    "is_verified": seller.is_document_verified,
                },
                "profile_status": {
                    "email_verified": seller.is_email_verified,
                    "phone_verified": seller.is_phone_verified,
                    "document_verified": seller.is_document_verified,
                    "account_status": seller.status,
                },
            }

            return Response(
                {"success": True, "account_settings": account_data},
                status=status.HTTP_200_OK,
            )

        except Exception as e:
            logger.error(f"Account Settings Error: {str(e)}")
            return Response(
                {"success": False, "message": "Failed to retrieve account settings"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @action(detail=False, methods=["PUT"])
    def update_bank_details(self, request):
        """
        Update seller's bank account details
        """
        try:
            seller = request.user.seller_profile

            # Validate bank details
            account_name = request.data.get("account_name")
            account_number = request.data.get("account_number")
            ifsc_code = request.data.get("ifsc_code")
            bank_name = request.data.get("bank_name")

            # Validate IFSC code
            import re

            if ifsc_code and not re.match(r"^[A-Z]{4}0[A-Z0-9]{6}$", ifsc_code):
                return Response(
                    {"success": False, "message": "Invalid IFSC code format"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Validate account number
            if account_number:
                # Remove any spaces or dashes
                account_number = "".join(filter(str.isdigit, account_number))

                # Check length (typical Indian bank account)
                if len(account_number) < 9 or len(account_number) > 18:
                    return Response(
                        {"success": False, "message": "Invalid bank account number"},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

            # Update seller model
            if account_name:
                seller.account_name = account_name
            if account_number:
                seller.account_number = account_number
            if ifsc_code:
                seller.ifsc_code = ifsc_code
            if bank_name:
                seller.bank_name = bank_name

            seller.save()

            return Response(
                {
                    "success": True,
                    "message": "Bank details updated successfully",
                    "bank_details": {
                        "account_name": seller.account_name,
                        "account_number": seller.account_number,
                        "ifsc_code": seller.ifsc_code,
                        "bank_name": seller.bank_name,
                    },
                },
                status=status.HTTP_200_OK,
            )

        except Exception as e:
            logger.error(f"Bank Details Update Error: {str(e)}")
            return Response(
                {"success": False, "message": "Failed to update bank details"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @action(detail=False, methods=["PUT"])
    def update_profile(self, request):
        """
        Update Seller Profile
        """
        try:
            seller = request.user.seller_profile
            serializer = self.get_serializer(seller, data=request.data, partial=True)
            serializer.is_valid(raise_exception=True)
            serializer.save()

            return Response(
                {
                    "success": True,
                    "message": "Profile updated successfully",
                    "profile": serializer.data,
                },
                status=status.HTTP_200_OK,
            )

        except ValidationError as e:
            logger.error(f"Profile Update Error: {str(e)}")
            return Response(
                {"success": False, "message": str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as e:
            logger.error(f"Unexpected Profile Update Error: {str(e)}")
            return Response(
                {"success": False, "message": "Failed to update profile"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
