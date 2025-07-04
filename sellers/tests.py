import os
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.conf import settings
from rest_framework.test import APIClient
from rest_framework import status
from firebase_admin import auth
import tempfile

from .models import Seller, ShippingLocation, Order, OrderItem
from .serializers import (
    SellerRegistrationSerializer, 
    DocumentUploadSerializer, 
    SellerProfileUpdateSerializer
)
from .services import (
    FirebaseAuthService, 
    SellerVerificationService, 
    DocumentUploadService,
    EmailOTP,
    TwoFactorAuthService
)

User = get_user_model()

class SellerModelTests(TestCase):
    def setUp(self):
        # Create a test user and seller
        self.user = User.objects.create_user(
            username='testvendor', 
            email='vendor@example.com', 
            password='testpassword123'
        )
        
        self.seller = Seller.objects.create(
            user=self.user,
            full_name='Test Vendor',
            email='vendor@example.com',
            phone='+919876543210',
            business_name='Test Business',
            business_address='123 Test Street',
            gst_number='07AACCV1234D1ZL',
            pan_number='AACCV1234D',
            status='pending'
        )

    def test_seller_creation(self):
        """Test seller model creation"""
        self.assertEqual(self.seller.full_name, 'Test Vendor')
        self.assertEqual(self.seller.status, 'pending')
        self.assertFalse(self.seller.is_email_verified)
        self.assertFalse(self.seller.is_phone_verified)

    def test_seller_str_method(self):
        """Test seller string representation"""
        self.assertEqual(str(self.seller), 'Test Business - pending')

class SellerRegistrationSerializerTests(TestCase):
    def setUp(self):
        self.valid_data = {
            'full_name': 'John Doe',
            'email': 'johndoe@example.com',
            'phone': '+919876543210',
            'business_name': 'Doe Enterprises',
            'password': 'StrongPass123!',
            'confirm_password': 'StrongPass123!'
        }

    def test_valid_registration_data(self):
        """Test serializer with valid registration data"""
        serializer = SellerRegistrationSerializer(data=self.valid_data)
        self.assertTrue(serializer.is_valid())

    def test_password_mismatch(self):
        """Test serializer with mismatched passwords"""
        invalid_data = self.valid_data.copy()
        invalid_data['confirm_password'] = 'DifferentPassword123!'
        serializer = SellerRegistrationSerializer(data=invalid_data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('confirm_password', serializer.errors)

    def test_invalid_email(self):
        """Test serializer with invalid email"""
        invalid_data = self.valid_data.copy()
        invalid_data['email'] = 'invalid-email'
        serializer = SellerRegistrationSerializer(data=invalid_data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('email', serializer.errors)

class DocumentUploadServiceTests(TestCase):
    def setUp(self):
        # Create a test seller for document upload
        self.user = User.objects.create_user(
            username='docvendor', 
            email='docvendor@example.com', 
            password='testpassword123'
        )
        
        self.seller = Seller.objects.create(
            user=self.user,
            full_name='Doc Vendor',
            email='docvendor@example.com',
            phone='+919876541230'
        )

        # Create test document files
        self.gst_document = SimpleUploadedFile(
            "gst.pdf", 
            b"file_content", 
            content_type="application/pdf"
        )
        self.pan_document = SimpleUploadedFile(
            "pan.pdf", 
            b"file_content", 
            content_type="application/pdf"
        )

    def test_document_validation(self):
        """Test document validation in DocumentUploadService"""
        service = DocumentUploadService()

        # Test valid documents
        try:
            service.validate_document(self.gst_document)
            service.validate_document(self.pan_document)
        except Exception as e:
            self.fail(f"Document validation failed: {str(e)}")

    def test_invalid_document_size(self):
        """Test document size validation"""
        service = DocumentUploadService()
        
        # Create an oversized file
        large_file = SimpleUploadedFile(
            "large.pdf", 
            b"0" * (6 * 1024 * 1024),  # 6MB file
            content_type="application/pdf"
        )

        with self.assertRaises(Exception):
            service.validate_document(large_file)

class EmailOTPTests(TestCase):
    def setUp(self):
        self.test_email = 'test@example.com'

    def test_otp_generation_and_verification(self):
        """Test OTP generation, storage, and verification"""
        # Generate OTP
        otp = EmailOTP.generate_otp()
        self.assertEqual(len(otp), 6)
        self.assertTrue(otp.isdigit())

        # Store OTP
        EmailOTP.store_otp(self.test_email, otp)

        # Verify correct OTP
        self.assertTrue(EmailOTP.verify_otp(self.test_email, otp))

        # Verify incorrect OTP fails
        self.assertFalse(EmailOTP.verify_otp(self.test_email, '123456'))

        # Verify OTP can only be used once
        self.assertFalse(EmailOTP.verify_otp(self.test_email, otp))

class TwoFactorAuthServiceTests(TestCase):
    def test_two_factor_auth_flow(self):
        """Test two-factor authentication service"""
        # Generate secret
        secret = TwoFactorAuthService.generate_secret()
        self.assertIsNotNone(secret)

        # Generate QR URL
        qr_url = TwoFactorAuthService.generate_qr_url(secret, 'test@example.com')
        self.assertTrue(qr_url.startswith('otpauth://totp/'))

        # Simulate OTP generation
        from pyotp import TOTP
        totp = TOTP(secret)
        otp = totp.now()

        # Verify OTP
        self.assertTrue(TwoFactorAuthService.verify_otp(secret, otp))

class ShippingLocationTests(TestCase):
    def setUp(self):
        # Create a test seller
        self.user = User.objects.create_user(
            username='shipvendor', 
            email='shipvendor@example.com', 
            password='testpassword123'
        )
        
        self.seller = Seller.objects.create(
            user=self.user,
            full_name='Ship Vendor',
            email='shipvendor@example.com',
            phone='+919876542210'
        )

    def test_shipping_location_creation(self):
        """Test shipping location creation"""
        shipping_location = ShippingLocation.objects.create(
            seller=self.seller,
            address='123 Shipping Street',
            city='Test City',
            state='Test State',
            pincode='400001',
            phone_number='+919876542210'
        )

        self.assertEqual(shipping_location.seller, self.seller)
        self.assertEqual(shipping_location.pincode, '400001')

class OrderTests(TestCase):
    def setUp(self):
        # Create a test seller
        self.user = User.objects.create_user(
            username='ordervendor', 
            email='ordervendor@example.com', 
            password='testpassword123'
        )
        
        self.seller = Seller.objects.create(
            user=self.user,
            full_name='Order Vendor',
            email='ordervendor@example.com',
            phone='+919876543310'
        )

    def test_order_creation(self):
        """Test order creation with order items"""
        order = Order.objects.create(
            seller=self.seller,
            customer_name='Test Customer',
            customer_email='customer@example.com',
            customer_phone='+919876543210',
            customer_address='123 Customer Street',
            customer_city='Test City',
            customer_state='Test State',
            customer_pincode='400001',
            total_price=1000.00,
            length=10.0,
            breadth=5.0,
            height=3.0,
            weight=2.0,
            payment_method='Prepaid'
        )

        # Add order items
        OrderItem.objects.create(
            order=order,
            product_name='Test Product',
            sku='TEST-PROD-001',
            quantity=2,
            price=500.00
        )

        # Verify order and order item creation
        self.assertEqual(order.customer_name, 'Test Customer')
        self.assertEqual(order.items.count(), 1)
        self.assertEqual(order.items.first().product_name, 'Test Product')

class SellerProfileUpdateTests(TestCase):
    def setUp(self):
        # Create a test seller
        self.user = User.objects.create_user(
            username='profilevendor', 
            email='profilevendor@example.com', 
            password='testpassword123'
        )
        
        self.seller = Seller.objects.create(
            user=self.user,
            full_name='Profile Vendor',
            email='profilevendor@example.com',
            phone='+919876544410',
            business_name='Initial Business'
        )

    def test_seller_profile_update(self):
        """Test seller profile update with valid data"""
        update_data = {
            'business_name': 'Updated Business Name',
            'business_address': '456 Updated Street',
            'account_name': 'Updated Account',
            'account_number': '1234567890',
            'ifsc_code': 'BANK0001234',
            'bank_name': 'Updated Bank'
        }

        serializer = SellerProfileUpdateSerializer(
            self.seller, 
            data=update_data, 
            partial=True
        )
        
        self.assertTrue(serializer.is_valid())
        updated_seller = serializer.save()

        self.assertEqual(updated_seller.business_name, 'Updated Business Name')
        self.assertEqual(updated_seller.business_address, '456 Updated Street')

class SellerVerificationServiceTests(TestCase):
    def setUp(self):
        self.verification_service = SellerVerificationService()
        self.registration_data = {
            'full_name': 'Verification Vendor',
            'email': 'verifyvendor@example.com',
            'phone': '+919876545510',
            'business_name': 'Verification Business',
            'password': 'StrongPass123!',
            'confirm_password': 'StrongPass123!'
        }

    def test_seller_application_creation(self):
        """Test comprehensive seller application creation"""
        # Create seller application
        seller = self.verification_service.create_seller_application(
            self.registration_data
        )

        # Verify seller creation
        self.assertIsNotNone(seller)
        self.assertEqual(seller.email, self.registration_data['email'])
        self.assertEqual(seller.status, 'pending')
        self.assertFalse(seller.is_email_verified)