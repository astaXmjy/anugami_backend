import requests
import json
import base64
from hashlib import sha256
from django.conf import settings

PHONEPE_BASE_URL = (
    "https://api-preprod.phonepe.com/apis/pg-sandbox"  # Use UAT URL for testing
)


class PhonePeAPI:
    """Handles PhonePe API authentication & payments"""

    @staticmethod
    def generate_checksum(payload):
        """Generate checksum for the payload."""
        payload_str = json.dumps(payload)
        base64_payload = base64.b64encode(payload_str.encode("utf-8")).decode("utf-8")
        checksum_str = f"{base64_payload}/pg/v1/pay{settings.PHONEPE_SALT_KEY}"
        checksum = sha256(checksum_str.encode("utf-8")).hexdigest()
        return f"{checksum}###{settings.PHONEPE_SALT_INDEX}"

    @staticmethod
    def initiate_payment(order_id, amount, callback_url):
        """Initiate a payment request with PhonePe."""
        payload = {
            "merchantId": settings.PHONEPE_MERCHANT_ID,
            "merchantTransactionId": order_id,
            "amount": int(amount * 100),  # Amount in paisa
            "redirectUrl": callback_url,
            "redirectMode": "POST",
            "callbackUrl": callback_url,
            "paymentInstrument": {"type": "PAY_PAGE"},
        }

        checksum = PhonePeAPI.generate_checksum(payload)
        base64_payload = base64.b64encode(json.dumps(payload).encode("utf-8")).decode(
            "utf-8"
        )

        headers = {"Content-Type": "application/json", "X-VERIFY": checksum}

        response = requests.post(
            f"{PHONEPE_BASE_URL}/pg/v1/pay",
            json={"request": base64_payload},
            headers=headers,
        )

        return response.json()

    @staticmethod
    def check_payment_status(transaction_id):
        """Check the payment status of a transaction."""
        checksum_str = f"/pg/v1/status/{settings.PHONEPE_MERCHANT_ID}/{transaction_id}{settings.PHONEPE_SALT_KEY}"
        checksum = sha256(checksum_str.encode("utf-8")).hexdigest()
        headers = {
            "Content-Type": "application/json",
            "X-VERIFY": f"{checksum}###{settings.PHONEPE_SALT_INDEX}",
        }

        response = requests.get(
            f"{PHONEPE_BASE_URL}/pg/v1/status/{settings.PHONEPE_MERCHANT_ID}/{transaction_id}",
            headers=headers,
        )

        return response.json()

    @staticmethod
    def refund_payment(transaction_id, amount):
        """Initiate a refund for a transaction."""
        payload = {
            "merchantId": settings.PHONEPE_MERCHANT_ID,
            "transactionId": transaction_id,
            "amount": int(amount * 100),  # Amount in paisa
        }

        checksum = PhonePeAPI.generate_checksum(payload)
        base64_payload = base64.b64encode(json.dumps(payload).encode("utf-8")).decode(
            "utf-8"
        )

        headers = {"Content-Type": "application/json", "X-VERIFY": checksum}

        response = requests.post(
            f"{PHONEPE_BASE_URL}/pg/v1/refund",
            json={"request": base64_payload},
            headers=headers,
        )

        return response.json()
