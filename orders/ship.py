# services/shiprocket.py
import requests
import json
import logging
from django.conf import settings
from datetime import datetime, timedelta
from django.utils import timezone

logger = logging.getLogger(__name__)


class ShiprocketService:
    """
    Service class for Shiprocket integration
    """

    BASE_URL = "https://apiv2.shiprocket.in/v1/external"

    def __init__(self):
        self.token = self._get_token()

    def _get_token(self):
        """
        Authenticate with Shiprocket API
        """
        try:
            response = requests.post(
                f"{self.BASE_URL}/auth/login",
                json={
                    "email": settings.SHIPROCKET_EMAIL,
                    "password": settings.SHIPROCKET_PASSWORD,
                },
            )

            print("zzxx")

            if response.status_code == 200:
                return response.json().get("token")

            logger.error(
                f"Failed to get Shiprocket token. Status: {response.status_code}, Response: {response.text}"
            )
            return None

        except Exception as e:
            logger.error(f"Error getting Shiprocket token: {str(e)}")
            return None

    def check_serviceability(self, pickup_pincode, delivery_pincode, weight, cod=False):
        """
        Check courier serviceability between two pincodes
        """
        if not self.token:
            logger.error("No Shiprocket token available")
            return {"error": "Authentication failed"}

        headers = {"Authorization": f"Bearer {self.token}"}
        params = {
            "pickup_postcode": pickup_pincode,
            "delivery_postcode": delivery_pincode,
            "weight": weight,
            "cod": 1 if cod else 0,
        }

        try:
            response = requests.get(
                f"{self.BASE_URL}/courier/serviceability/",
                headers=headers,
                params=params,
            )

            if response.status_code == 200:
                return response.json()

            logger.error(
                f"Serviceability check failed. Status: {response.status_code}, Response: {response.text}"
            )
            return {"error": f"Failed with status {response.status_code}"}

        except Exception as e:
            logger.error(f"Error checking serviceability: {str(e)}")
            return {"error": str(e)}

    def generate_awb(self, shipment_id):
        """
        Generate AWB number for a shipment
        """
        if not self.token:
            return {"error": "Authentication failed"}

        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }

        try:
            response = requests.post(
                f"{self.BASE_URL}/courier/assign/awb",
                headers=headers,
                json={"shipment_id": shipment_id},
            )

            awb_response = response.json()

            # Handle different response structures
            if awb_response.get("awb_assign_status") == 1:
                awb_data = awb_response["response"]["data"]
                return {
                    "awb_code": awb_data.get("awb_code", ""),
                    "courier_company_id": awb_data.get("courier_company_id", ""),
                    "courier_name": awb_data.get("courier_name", ""),
                }
            elif "data" in awb_response:
                # Fallback for other potential response structures
                return {
                    "awb_code": awb_response["data"].get("awb_code", ""),
                    "courier_company_id": awb_response["data"].get(
                        "courier_company_id", ""
                    ),
                    "courier_name": awb_response["data"].get("courier_name", ""),
                }
            else:
                # If no AWB details found, return empty strings
                return {
                    "awb_code": "",
                    "courier_company_id": "",
                    "courier_name": "",
                }

        except Exception as e:
            logger.error(f"Error generating AWB: {str(e)}")
            return {
                "awb_code": "",
                "courier_company_id": "",
                "courier_name": "",
            }

    def create_order(self, order, pickup_address):
        """
        Create a new order in Shiprocket
        """
        if not self.token:
            return {"error": "Authentication failed"}

        # Get shipping address from order
        shipping_address = None
        for address in order.orderaddress_set.all():
            if address.address_type == "shipping":
                shipping_address = address
                break

        if not shipping_address:
            return {"error": "No shipping address found"}

        # Get order items
        order_items = []
        for item in order.items.all():
            order_items.append(
                {
                    "name": item.name,
                    "sku": item.sku or f"SKU-{item.id}",
                    "units": item.quantity,
                    "selling_price": float(item.final_price / item.quantity),
                    "discount": float(item.discount_amount),
                    "tax": float(item.tax_amount or 0),
                }
            )

        # Calculate expected delivery date (7 days from now as default)
        expected_delivery = timezone.now() + timedelta(days=14)

        # Determine if COD based on payment method
        is_cod = order.payment.method == "COD" if hasattr(order, "payment") else False

        # Create payload
        payload = {
            "order_id": order.order_number,
            "order_date": order.created_at.strftime("%Y-%m-%d %H:%M"),
            "pickup_location": pickup_address.get("name", "Primary"),
            "channel_id": "",
            "comment": f"Order {order.order_number}",
            "billing_customer_name": shipping_address.full_name,
            "billing_last_name": "",
            "billing_address": shipping_address.street,
            "billing_address_2": shipping_address.landmark,
            "billing_city": shipping_address.city,
            "billing_pincode": shipping_address.pincode,
            "billing_state": shipping_address.state,
            "billing_country": shipping_address.country,
            "billing_email": shipping_address.email,
            "billing_phone": str(shipping_address.phone)
            .replace("+91", "")
            .replace("-", "")
            .replace(" ", "")[-10:],
            "shipping_is_billing": True,
            "shipping_customer_name": shipping_address.full_name,
            "shipping_address": shipping_address.street,
            "shipping_address_2": shipping_address.landmark,
            "shipping_city": shipping_address.city,
            "shipping_pincode": shipping_address.pincode,
            "shipping_state": shipping_address.state,
            "shipping_country": shipping_address.country,
            "shipping_email": shipping_address.email,
            "shipping_phone": str(shipping_address.phone)
            .replace("+91", "")
            .replace("-", "")
            .replace(" ", "")[-10:],
            "order_items": order_items,
            "payment_method": "COD" if is_cod else "Prepaid",
            "shipping_charges": (
                float(order.shipping.shipping_cost)
                if hasattr(order, "shipping") and order.shipping.shipping_cost
                else 0
            ),
            "giftwrap_charges": 0,
            "transaction_charges": 0,
            "total_discount": sum(
                float(item.discount_amount) for item in order.items.all()
            ),
            "sub_total": float(order.total_amount),
            "length": order.shipping.length if hasattr(order, "shipping") else 10,
            "breadth": order.shipping.width if hasattr(order, "shipping") else 10,
            "height": order.shipping.height if hasattr(order, "shipping") else 10,
            "weight": order.shipping.weight if hasattr(order, "shipping") else 0.5,
        }

        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }

        try:
            # Create Order
            order_response = requests.post(
                f"{self.BASE_URL}/orders/create/adhoc", headers=headers, json=payload
            )
            order_data = order_response.json()

            # Check if order creation was successful
            if order_response.status_code != 200 or "order_id" not in order_data:
                logger.error(f"Failed to create order: {order_data}")
                return {"error": "Failed to create order", "details": order_data}

            # Extract shipment_id from order creation response
            shipment_id = order_data.get("shipment_id")

            # Generate AWB for the shipment
            awb_response = self.generate_awb(shipment_id)

            # Combine responses in the requested format
            combined_response = {
                "order_id": order_data.get("order_id"),
                "channel_order_id": order_data.get("channel_order_id", ""),
                "shipment_id": shipment_id,
                "status": order_data.get("status", "NEW"),
                "status_code": order_data.get("status_code", 1),
                "onboarding_completed_now": order_data.get(
                    "onboarding_completed_now", 0
                ),
                "new_channel": order_data.get("new_channel", False),
                "packaging_box_error": order_data.get("packaging_box_error", ""),
                # Add AWB details, defaulting to empty strings if not available
                "awb_code": awb_response.get("awb_code", ""),
                "courier_company_id": awb_response.get("courier_company_id", ""),
                "courier_name": awb_response.get("courier_name", ""),
                # Optional: Include full response details for debugging
                "_full_order_response": order_data,
                "_full_awb_response": awb_response,
            }

            return combined_response
        except Exception as e:
            logger.error(f"Error creating Shiprocket order: {str(e)}")
            return {"error": str(e)}

    def get_tracking_details(self, shipment_id=None, order_id=None, awb=None):
        """
        Get tracking details for a shipment
        """
        if not self.token:
            return {"error": "Authentication failed"}

        headers = {"Authorization": f"Bearer {self.token}"}

        url = f"{self.BASE_URL}/courier/track"
        if shipment_id:
            url = f"{url}/shipment/{shipment_id}"
        elif order_id:
            url = f"{url}/order/{order_id}"
        elif awb:
            url = f"{url}/awb/{awb}"
        else:
            return {"error": "No tracking identifier provided"}

        try:
            response = requests.get(url, headers=headers)
            return response.json()

        except Exception as e:
            logger.error(f"Error getting tracking details: {str(e)}")
            return {"error": str(e)}

    def generate_manifest(self, shipment_ids):
        """
        Generate manifest for shipments
        """
        if not self.token:
            return {"error": "Authentication failed"}

        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }

        try:
            response = requests.post(
                f"{self.BASE_URL}/manifests/generate",
                headers=headers,
                json={"shipment_id": shipment_ids},
            )

            return response.json()

        except Exception as e:
            logger.error(f"Error generating manifest: {str(e)}")
            return {"error": str(e)}

    def generate_label(self, shipment_id):
        """
        Generate label for a shipment
        """
        if not self.token:
            return {"error": "Authentication failed"}

        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }

        try:
            response = requests.post(
                f"{self.BASE_URL}/courier/generate/label",
                headers=headers,
                json={"shipment_id": [shipment_id]},
            )

            return response.json()

        except Exception as e:
            logger.error(f"Error generating label: {str(e)}")
            return {"error": str(e)}

    def cancel_shipment(self, shipment_id):
        """
        Cancel a shipment
        """
        if not self.token:
            return {"error": "Authentication failed"}

        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }

        try:
            response = requests.post(
                f"{self.BASE_URL}/orders/cancel/shipment/request",
                headers=headers,
                json={"shipment_id": shipment_id},
            )

            return response.json()

        except Exception as e:
            logger.error(f"Error cancelling shipment: {str(e)}")
            return {"error": str(e)}

    def get_all_pickup_locations(self):
        """
        Get all pickup locations
        """
        if not self.token:
            return {"error": "Authentication failed"}

        headers = {"Authorization": f"Bearer {self.token}"}

        try:
            response = requests.get(
                f"{self.BASE_URL}/settings/company/pickup", headers=headers
            )

            return response.json()

        except Exception as e:
            logger.error(f"Error getting pickup locations: {str(e)}")
            return {"error": str(e)}

    def request_pickup(self, shipment_id, pickup_date):
        """
        Request pickup for a shipment
        """
        if not self.token:
            return {"error": "Authentication failed"}

        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }

        try:
            response = requests.post(
                f"{self.BASE_URL}/courier/generate/pickup",
                headers=headers,
                json={
                    "shipment_id": [shipment_id],
                    "pickup_date": pickup_date.strftime("%Y-%m-%d"),
                },
            )

            return response.json()

        except Exception as e:
            logger.error(f"Error requesting pickup: {str(e)}")
            return {"error": str(e)}
