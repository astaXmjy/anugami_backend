from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.decorators import action
from .services import PhonePeAPI
from rest_framework.views import APIView
from rest_framework import status
import base64
import json
from hashlib import sha256
from django.conf import settings
from .models import Payment, PaymentStatus

class PaymentViewSet(viewsets.ViewSet):
    """Handles payment processing and verification"""

    @action(detail=False, methods=["POST"])
    def initiate_payment(self, request):
        print("inside initiate payments")
        """Initiate a new payment."""
        order_id = request.data.get("order_id")
        amount = request.data.get("amount")
        callback_url = request.data.get("callback_url")

        if not order_id or not amount or not callback_url:
            return Response(
                {"error": "Missing required fields: order_id, amount, callback_url"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Create a Payment record in the database
        payment = Payment.objects.create(
            order_id=order_id,
            amount=amount,
            total_amount=amount,  # You can call calculate_total() if needed
        )

        # Initiate payment with PhonePe
        response = PhonePeAPI.initiate_payment(order_id, amount, callback_url)

        if response.get("success"):
            payment.transaction_id = response.get("transactionId")
            payment.save()
            return Response(response, status=status.HTTP_200_OK)
        else:
            return Response(
                {"error": "Payment initiation failed"},
                status=status.HTTP_400_BAD_REQUEST,
            )

    @action(detail=False, methods=["GET"])
    def check_status(self, request):
        """Check payment status."""
        transaction_id = request.query_params.get("transaction_id")

        if not transaction_id:
            return Response(
                {"error": "Missing transaction_id"}, status=status.HTTP_400_BAD_REQUEST
            )

        response = PhonePeAPI.check_payment_status(transaction_id)
        return Response(response, status=status.HTTP_200_OK)

    @action(detail=False, methods=["POST"])
    def refund_payment(self, request):
        """Process a refund."""
        transaction_id = request.data.get("transaction_id")
        amount = request.data.get("amount")

        if not transaction_id or not amount:
            return Response(
                {"error": "Missing required fields: transaction_id, amount"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        response = PhonePeAPI.refund_payment(transaction_id, amount)
        return Response(response, status=status.HTTP_200_OK)


class PhonePeCallbackView(APIView):
    def post(self, request):
        data = request.data
        encoded_response = data.get("response")
        decoded_response = base64.b64decode(encoded_response).decode("utf-8")
        response_data = json.loads(decoded_response)

        # Verify checksum
        checksum_str = f"{encoded_response}/pg/v1/pay{settings.PHONEPE_SALT_KEY}"
        checksum = sha256(checksum_str.encode("utf-8")).hexdigest()
        if checksum != data.get("checksum"):
            return Response(
                {"error": "Invalid checksum"}, status=status.HTTP_400_BAD_REQUEST
            )

        # Update payment status
        transaction_id = response_data.get("transactionId")
        payment_status = response_data.get("code")

        try:
            payment = Payment.objects.get(transaction_id=transaction_id)
            if payment_status == "PAYMENT_SUCCESS":
                payment.status = PaymentStatus.SUCCESS
            else:
                payment.status = PaymentStatus.FAILURE
            payment.save()
            return Response(
                {"message": "Payment status updated"}, status=status.HTTP_200_OK
            )
        except Payment.DoesNotExist:
            return Response(
                {"error": "Payment not found"}, status=status.HTTP_404_NOT_FOUND
            )
