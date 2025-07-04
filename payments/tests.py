from rest_framework.test import APITestCase
from rest_framework import status

class PaymentTests(APITestCase):
    def test_initiate_payment(self):
        """Test initiating a payment"""
        data = {
            "order_id": "ORD12345",
            "amount": "100.50",
            "callback_url": "https://example.com/payment-success"
        }
        response = self.client.post("/api/payments/initiate_payment/", data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_check_payment_status(self):
        """Test checking payment status"""
        response = self.client.get("/api/payments/check_status/?transaction_id=TXN12345")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_refund_payment(self):
        """Test refunding a payment"""
        data = {
            "transaction_id": "TXN12345",
            "amount": "50.00"
        }
        response = self.client.post("/api/payments/refund_payment/", data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
