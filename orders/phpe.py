# services/phonepe.py
import requests
import json
import logging
import hashlib
import base64
from django.conf import settings
from django.urls import reverse
from decimal import Decimal
from datetime import datetime

logger = logging.getLogger(__name__)


class PhonePeService:
    """
    Service class for PhonePe payment integration
    """

    # PhonePe API endpoints
    PRODUCTION_URL = "https://api.phonepe.com/apis/hermes"
    SANDBOX_URL = "https://api-preprod.phonepe.com/apis/pg-sandbox"

    def __init__(self):
        # Use sandbox for development, production for live
        self.base_url = (
            self.PRODUCTION_URL
            if settings.PHONEPE_ENVIRONMENT == "production"
            else self.SANDBOX_URL
        )
        self.merchant_id = settings.PHONEPE_MERCHANT_ID
        self.salt_key = settings.PHONEPE_SALT_KEY
        self.salt_index = settings.PHONEPE_SALT_INDEX
        print(
            f"PhonePe Service initialized with: URL={self.base_url}, MID={self.merchant_id}")

    def _generate_checksum(self, payload):
        """
        Generate checksum for PhonePe API - FIXED VERSION
        """
        print("inside checksumphoenpe")
        # Convert payload to string if it's a dict
        if isinstance(payload, dict):
            payload_str = json.dumps(payload)
        else:
            payload_str = payload

        # Base64 encode the payload
        base64_payload = base64.b64encode(payload_str.encode("utf-8")).decode("utf-8")

        # Create message to hash (payload + endpoint + salt_key)
        message = f"{base64_payload}/pg/v1/pay{self.salt_key}"

        # Generate SHA256 hash (hexdigest, not digest)
        checksum = hashlib.sha256(message.encode("utf-8")).hexdigest()

        # Append salt index
        return f"{checksum}###{self.salt_index}"

    def _verify_checksum(self, payload, checksum):
        """
        Verify checksum from PhonePe response
        """
        # Extract actual checksum and salt index
        parts = checksum.split("###")
        if len(parts) != 2:
            return False

        actual_checksum, salt_index = parts

        # Create message to hash
        message = f"{payload}{self.salt_key}"

        # Generate SHA256 hash
        expected_checksum = hashlib.sha256(message.encode("utf-8")).hexdigest()

        # Compare checksums
        return actual_checksum == expected_checksum

    def create_payment(self, order, callback_url=None, redirect_url=None):
        """
        Create a payment request for an order
        """
        try:
            # Callback URL (for server-to-server notification)
            if not callback_url:
                callback_url = settings.PHONEPE_CALLBACK_URL

            # Redirect URL (user will be redirected here after payment)
            if not redirect_url:
                redirect_url = settings.PHONEPE_REDIRECT_URL

            # Convert Decimal to int paise amount (must be in paise - multiply by 100)
            amount_in_paise = int(order.total_amount * 100)

            import time
            transaction_id = f"ANUGAMI-{order.order_number}-{int(time.time())}"

            # Create payload
            payload = {
                "merchantId": self.merchant_id,
                "merchantTransactionId": transaction_id,
                "merchantUserId": str(order.user.id),
                "amount": 100,
                "redirectUrl": redirect_url,
                "redirectMode": "POST",
                "callbackUrl": callback_url,
                "mobileNumber": order.user.phone,
                "paymentInstrument": {"type": "PAY_PAGE"},
            }

            # Generate checksum
            checksum = self._generate_checksum(payload)

            # Base64 encode the payload
            payload_base64 = base64.b64encode(
                json.dumps(payload).encode("utf-8")
            ).decode("utf-8")

            # Prepare the final request
            request_data = {"request": payload_base64}

            # Make API request
            headers = {"Content-Type": "application/json", "X-VERIFY": checksum}

            # API endpoint
            api_url = f"{self.base_url}/pg/v1/pay"

            response = requests.post(api_url, headers=headers, json=request_data)

            if response.status_code == 200:
                response_data = response.json()

                # Check if response is successful
                if response_data.get("success"):
                    # Store response for future reference
                    if hasattr(order, "payment"):
                        order.payment.phonepe_response = response_data
                        order.payment.save()

                    # Return PhonePe payment page URL
                    return {
                        "success": True,
                        "payment_url": response_data.get("data", {})
                        .get("instrumentResponse", {})
                        .get("redirectInfo", {})
                        .get("url"),
                        "transaction_id": response_data.get("data", {}).get(
                            "merchantTransactionId"
                        ),
                        "phonepe_transaction_id": response_data.get("data", {}).get(
                            "transactionId"
                        ),
                    }
                else:
                    logger.error(
                        f"PhonePe payment creation failed: {response_data.get('message')}"
                    )
                    return {
                        "success": False,
                        "error": response_data.get(
                            "message", "Payment creation failed"
                        ),
                    }
            else:
                logger.error(
                    f"PhonePe API error: {response.status_code}, {response.text}"
                )
                return {
                    "success": False,
                    "error": f"PhonePe API error: {response.status_code}, {response.text}",
                }

        except Exception as e:
            logger.error(f"Error creating PhonePe payment: {str(e)}")
            return {"success": False, "error": str(e)}

    def check_payment_status(self, merchant_transaction_id):
        """
        Check payment status using merchantTransactionId
        """
        try:
            # Create message for checksum
            checksum_str = f"/pg/v1/status/{self.merchant_id}/{merchant_transaction_id}{self.salt_key}"

            # Generate SHA256 hash
            checksum = hashlib.sha256(checksum_str.encode("utf-8")).hexdigest()

            # Format with salt index
            x_verify = f"{checksum}###{self.salt_index}"

            # Make API request
            headers = {
                "Content-Type": "application/json",
                "X-VERIFY": x_verify,
                "X-MERCHANT-ID": self.merchant_id,
            }

            # API endpoint
            api_url = f"{self.base_url}/pg/v1/status/{self.merchant_id}/{merchant_transaction_id}"

            response = requests.get(api_url, headers=headers)

            if response.status_code == 200:
                response_data = response.json()

                # Check if response is successful
                if response_data.get("success"):
                    return {
                        "success": True,
                        "status": response_data.get("data", {}).get("state"),
                        "transaction_id": response_data.get("data", {}).get(
                            "transactionId"
                        ),
                        "amount": Decimal(
                            response_data.get("data", {}).get("amount", 0) / 100
                        ),  # Convert paise to rupees
                        "response": response_data,
                    }
                else:
                    logger.error(
                        f"PhonePe status check failed: {response_data.get('message')}"
                    )
                    return {
                        "success": False,
                        "error": response_data.get("message", "Status check failed"),
                    }
            else:
                logger.error(
                    f"PhonePe API error: {response.status_code}, {response.text}"
                )
                return {
                    "success": False,
                    "error": f"PhonePe API error: {response.status_code}, {response.text}",
                }

        except Exception as e:
            logger.error(f"Error checking PhonePe payment status: {str(e)}")
            return {"success": False, "error": str(e)}

    def process_refund(
        self, transaction_id, amount, refund_id=None, reason="Customer requested refund"
    ):
        """
        Process refund for a transaction

        Parameters:
        - transaction_id: Original transaction ID
        - amount: Refund amount (decimal)
        - refund_id: Unique ID for refund (default: "REF-" + transaction_id)
        - reason: Reason for refund
        """
        try:
            # Generate refund ID if not provided
            if not refund_id:
                refund_id = (
                    f"REF-{transaction_id}-{datetime.now().strftime('%Y%m%d%H%M%S')}"
                )

            # Convert amount to paise
            amount_in_paise = int(amount * 100)

            # Create payload
            payload = {
                "merchantId": self.merchant_id,
                "transactionId": transaction_id,
                "amount": amount_in_paise,
            }

            # Generate base64 encoded payload
            payload_str = json.dumps(payload)
            base64_payload = base64.b64encode(payload_str.encode("utf-8")).decode(
                "utf-8"
            )

            # Generate checksum
            checksum_str = f"{base64_payload}/pg/v1/refund{self.salt_key}"
            checksum = hashlib.sha256(checksum_str.encode("utf-8")).hexdigest()
            x_verify = f"{checksum}###{self.salt_index}"

            # Prepare the final payload
            request_data = {"request": base64_payload}

            # Make API request
            headers = {"Content-Type": "application/json", "X-VERIFY": x_verify}

            # API endpoint
            api_url = f"{self.base_url}/pg/v1/refund"

            response = requests.post(api_url, headers=headers, json=request_data)

            if response.status_code == 200:
                response_data = response.json()

                # Check if response is successful
                if response_data.get("success"):
                    return {
                        "success": True,
                        "refund_id": refund_id,
                        "status": response_data.get("data", {}).get("state"),
                        "response": response_data,
                    }
                else:
                    logger.error(
                        f"PhonePe refund failed: {response_data.get('message')}"
                    )
                    return {
                        "success": False,
                        "error": response_data.get("message", "Refund failed"),
                    }
            else:
                logger.error(
                    f"PhonePe API error: {response.status_code}, {response.text}"
                )
                return {
                    "success": False,
                    "error": f"PhonePe API error: {response.status_code}, {response.text}",
                }

        except Exception as e:
            logger.error(f"Error processing PhonePe refund: {str(e)}")
            return {"success": False, "error": str(e)}

    def check_refund_status(self, refund_id):
        """
        Check refund status
        """
        try:
            # Generate checksum
            checksum_str = (
                f"/pg/v1/refund/status/{self.merchant_id}/{refund_id}{self.salt_key}"
            )
            checksum = hashlib.sha256(checksum_str.encode("utf-8")).hexdigest()
            x_verify = f"{checksum}###{self.salt_index}"

            # Make API request
            headers = {
                "Content-Type": "application/json",
                "X-VERIFY": x_verify,
                "X-MERCHANT-ID": self.merchant_id,
            }

            # API endpoint
            api_url = (
                f"{self.base_url}/pg/v1/refund/status/{self.merchant_id}/{refund_id}"
            )

            response = requests.get(api_url, headers=headers)

            if response.status_code == 200:
                response_data = response.json()

                # Check if response is successful
                if response_data.get("success"):
                    return {
                        "success": True,
                        "status": response_data.get("data", {}).get("state"),
                        "refund_id": refund_id,
                        "amount": Decimal(
                            response_data.get("data", {}).get("amount", 0) / 100
                        ),  # Convert paise to rupees
                        "response": response_data,
                    }
                else:
                    logger.error(
                        f"PhonePe refund status check failed: {response_data.get('message')}"
                    )
                    return {
                        "success": False,
                        "error": response_data.get(
                            "message", "Refund status check failed"
                        ),
                    }
            else:
                logger.error(
                    f"PhonePe API error: {response.status_code}, {response.text}"
                )
                return {
                    "success": False,
                    "error": f"PhonePe API error: {response.status_code}, {response.text}",
                }

        except Exception as e:
            logger.error(f"Error checking PhonePe refund status: {str(e)}")
            return {"success": False, "error": str(e)}
