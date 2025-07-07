# orders/ship.py
import requests
import json
import logging
from django.conf import settings
from datetime import datetime, timedelta
from django.utils import timezone

logger = logging.getLogger(__name__)


class ShipmojoService:
    """
    Service class for Shipmojo integration
    """

    BASE_URL = "https://shipping-api.com/app/api/v1"

    def __init__(self):
        self.public_key = getattr(settings, 'SHIPMOJO_PUBLIC_KEY', None)
        self.private_key = getattr(settings, 'SHIPMOJO_PRIVATE_KEY', None)
        
        if not self.public_key or not self.private_key:
            logger.error("Shipmojo API keys not found in settings")

    def _get_headers(self):
        """
        Get headers for Shipmojo API requests
        """
        return {
            'public-key': self.public_key,
            'private-key': self.private_key,
            'Content-Type': 'application/json'
        }

    def login(self, username, password):
        """
        Login to Shipmojo API to get keys
        """
        try:
            response = requests.post(
                f"{self.BASE_URL}/login",
                json={
                    "username": username,
                    "password": password,
                },
            )

            if response.status_code == 200:
                data = response.json()
                if data.get('result') == '1':
                    user_data = data.get('data', [{}])[0]
                    return {
                        'public_key': user_data.get('public_key'),
                        'private_key': user_data.get('private_key'),
                        'name': user_data.get('name')
                    }
            
            logger.error(f"Shipmojo login failed: {response.text}")
            return None

        except Exception as e:
            logger.error(f"Error during Shipmojo login: {str(e)}")
            return None

    def check_api_info(self):
        """
        Check if API is operational
        """
        try:
            response = requests.get(f"{self.BASE_URL}/info")
            
            if response.status_code == 200:
                return response.json()
            
            logger.error(f"API info check failed: {response.text}")
            return {"error": "API not available"}

        except Exception as e:
            logger.error(f"Error checking API info: {str(e)}")
            return {"error": str(e)}

    def check_serviceability(self, pickup_pincode, delivery_pincode):
        """
        Check courier serviceability between two pincodes
        """
        if not self.public_key or not self.private_key:
            return {"error": "Authentication credentials not available"}

        try:
            response = requests.post(
                f"{self.BASE_URL}/pincode-serviceability",
                headers=self._get_headers(),
                json={
                    "pickup_pincode": int(pickup_pincode),
                    "delivery_pincode": int(delivery_pincode)
                }
            )

            if response.status_code == 200:
                return response.json()

            logger.error(f"Serviceability check failed: {response.text}")
            return {"error": "Serviceability check failed"}

        except Exception as e:
            logger.error(f"Error checking serviceability: {str(e)}")
            return {"error": str(e)}

    def calculate_shipping_rates(self, pickup_pincode, delivery_pincode, payment_type, 
                               order_amount, weight, dimensions, shipment_type="FORWARD"):
        """
        Calculate shipping rates
        """
        if not self.public_key or not self.private_key:
            return {"error": "Authentication credentials not available"}

        try:
            payload = {
                "order_id": "",
                "pickup_pincode": int(pickup_pincode),
                "delivery_pincode": int(delivery_pincode),
                "payment_type": payment_type.upper(),
                "shipment_type": shipment_type,
                "order_amount": int(order_amount),
                "type_of_package": "SPS",
                "rov_type": "ROV_OWNER",
                "cod_amount": "",
                "weight": int(weight),
                "dimensions": dimensions
            }

            response = requests.post(
                f"{self.BASE_URL}/rate-calculator",
                headers=self._get_headers(),
                json=payload
            )

            if response.status_code == 200:
                return response.json()

            logger.error(f"Rate calculation failed: {response.text}")
            return {"error": "Rate calculation failed"}

        except Exception as e:
            logger.error(f"Error calculating rates: {str(e)}")
            return {"error": str(e)}

    def create_warehouse(self, warehouse_data):
        """
        Create warehouse in Shipmojo
        """
        if not self.public_key or not self.private_key:
            return {"error": "Authentication credentials not available"}

        try:
            response = requests.post(
                f"{self.BASE_URL}/create-warehouse",
                headers=self._get_headers(),
                json=warehouse_data
            )

            if response.status_code == 200:
                return response.json()

            logger.error(f"Warehouse creation failed: {response.text}")
            return {"error": "Warehouse creation failed"}

        except Exception as e:
            logger.error(f"Error creating warehouse: {str(e)}")
            return {"error": str(e)}

    def get_warehouses(self):
        """
        Get all warehouses
        """
        if not self.public_key or not self.private_key:
            return {"error": "Authentication credentials not available"}

        try:
            response = requests.get(
                f"{self.BASE_URL}/get-warehouses",
                headers=self._get_headers()
            )

            if response.status_code == 200:
                return response.json()

            logger.error(f"Get warehouses failed: {response.text}")
            return {"error": "Failed to fetch warehouses"}

        except Exception as e:
            logger.error(f"Error getting warehouses: {str(e)}")
            return {"error": str(e)}

    def push_order(self, order_data):
        """
        Push order to Shipmojo
        """
        if not self.public_key or not self.private_key:
            return {"error": "Authentication credentials not available"}

        try:
            response = requests.post(
                f"{self.BASE_URL}/push-order",
                headers=self._get_headers(),
                json=order_data
            )

            if response.status_code == 200:
                data = response.json()
                if data.get('result') == '1':
                    return data
                else:
                    logger.error(f"Order push failed: {data.get('message', 'Unknown error')}")
                    return {"error": data.get('message', 'Order push failed')}

            logger.error(f"Order push failed with status {response.status_code}: {response.text}")
            return {"error": "Order push failed"}

        except Exception as e:
            logger.error(f"Error pushing order: {str(e)}")
            return {"error": str(e)}

    def assign_courier(self, order_id, courier_id):
        """
        Assign courier to order
        """
        if not self.public_key or not self.private_key:
            return {"error": "Authentication credentials not available"}

        try:
            response = requests.post(
                f"{self.BASE_URL}/assign-courier",
                headers=self._get_headers(),
                json={
                    "order_id": str(order_id),
                    "courier_id": int(courier_id)
                }
            )

            if response.status_code == 200:
                return response.json()

            logger.error(f"Courier assignment failed: {response.text}")
            return {"error": "Courier assignment failed"}

        except Exception as e:
            logger.error(f"Error assigning courier: {str(e)}")
            return {"error": str(e)}

    def auto_assign_courier(self, order_id):
        """
        Auto assign courier to order
        """
        if not self.public_key or not self.private_key:
            return {"error": "Authentication credentials not available"}

        try:
            response = requests.post(
                f"{self.BASE_URL}/auto-assign-order",
                headers=self._get_headers(),
                json={"order_id": str(order_id)}
            )

            if response.status_code == 200:
                return response.json()

            logger.error(f"Auto courier assignment failed: {response.text}")
            return {"error": "Auto courier assignment failed"}

        except Exception as e:
            logger.error(f"Error auto assigning courier: {str(e)}")
            return {"error": str(e)}

    def schedule_pickup(self, order_id):
        """
        Schedule pickup for order
        """
        if not self.public_key or not self.private_key:
            return {"error": "Authentication credentials not available"}

        try:
            response = requests.post(
                f"{self.BASE_URL}/schedule-pickup",
                headers=self._get_headers(),
                json={"order_id": str(order_id)}
            )

            if response.status_code == 200:
                return response.json()

            logger.error(f"Pickup scheduling failed: {response.text}")
            return {"error": "Pickup scheduling failed"}

        except Exception as e:
            logger.error(f"Error scheduling pickup: {str(e)}")
            return {"error": str(e)}

    def track_order(self, awb_number):
        """
        Track order using AWB number
        """
        if not self.public_key or not self.private_key:
            return {"error": "Authentication credentials not available"}

        try:
            response = requests.get(
                f"{self.BASE_URL}/track-order",
                headers=self._get_headers(),
                params={"awb_number": str(awb_number)}
            )

            if response.status_code == 200:
                return response.json()

            logger.error(f"Order tracking failed: {response.text}")
            return {"error": "Order tracking failed"}

        except Exception as e:
            logger.error(f"Error tracking order: {str(e)}")
            return {"error": str(e)}

    def get_order_label(self, awb_number):
        """
        Get shipping label for order
        """
        if not self.public_key or not self.private_key:
            return {"error": "Authentication credentials not available"}

        try:
            response = requests.get(
                f"{self.BASE_URL}/get-order-label/{awb_number}",
                headers=self._get_headers()
            )

            if response.status_code == 200:
                return response.json()

            logger.error(f"Label generation failed: {response.text}")
            return {"error": "Label generation failed"}

        except Exception as e:
            logger.error(f"Error getting label: {str(e)}")
            return {"error": str(e)}

    def cancel_order(self, order_id, awb_number):
        """
        Cancel order
        """
        if not self.public_key or not self.private_key:
            return {"error": "Authentication credentials not available"}

        try:
            response = requests.post(
                f"{self.BASE_URL}/cancel-order",
                headers=self._get_headers(),
                json={
                    "order_id": str(order_id),
                    "awb_number": int(awb_number)
                }
            )

            if response.status_code == 200:
                return response.json()

            logger.error(f"Order cancellation failed: {response.text}")
            return {"error": "Order cancellation failed"}

        except Exception as e:
            logger.error(f"Error cancelling order: {str(e)}")
            return {"error": str(e)}

    def get_return_reasons(self):
        """
        Get return reasons
        """
        if not self.public_key or not self.private_key:
            return {"error": "Authentication credentials not available"}

        try:
            response = requests.get(
                f"{self.BASE_URL}/get-return-reason",
                headers=self._get_headers()
            )

            if response.status_code == 200:
                return response.json()

            logger.error(f"Get return reasons failed: {response.text}")
            return {"error": "Failed to get return reasons"}

        except Exception as e:
            logger.error(f"Error getting return reasons: {str(e)}")
            return {"error": str(e)}

    def push_return_order(self, return_order_data):
        """
        Push return order
        """
        if not self.public_key or not self.private_key:
            return {"error": "Authentication credentials not available"}

        try:
            response = requests.post(
                f"{self.BASE_URL}/push-return-order",
                headers=self._get_headers(),
                json=return_order_data
            )

            if response.status_code == 200:
                return response.json()

            logger.error(f"Return order push failed: {response.text}")
            return {"error": "Return order push failed"}

        except Exception as e:
            logger.error(f"Error pushing return order: {str(e)}")
            return {"error": str(e)}

    def get_order_detail(self, order_id):
        """
        Get order details
        """
        if not self.public_key or not self.private_key:
            return {"error": "Authentication credentials not available"}

        try:
            response = requests.get(
                f"{self.BASE_URL}/get-order-detail/{order_id}",
                headers=self._get_headers()
            )

            if response.status_code == 200:
                return response.json()

            logger.error(f"Get order detail failed: {response.text}")
            return {"error": "Failed to get order details"}

        except Exception as e:
            logger.error(f"Error getting order details: {str(e)}")
            return {"error": str(e)}

    def update_warehouse(self, order_id, warehouse_id):
        """
        Update warehouse for order
        """
        if not self.public_key or not self.private_key:
            return {"error": "Authentication credentials not available"}

        try:
            response = requests.post(
                f"{self.BASE_URL}/order/update-warehouse",
                headers=self._get_headers(),
                json={
                    "order_id": str(order_id),
                    "warehouse_id": int(warehouse_id)
                }
            )

            if response.status_code == 200:
                return response.json()

            logger.error(f"Warehouse update failed: {response.text}")
            return {"error": "Warehouse update failed"}

        except Exception as e:
            logger.error(f"Error updating warehouse: {str(e)}")
            return {"error": str(e)}

    def create_order(self, order, pickup_address):
        """
        Create a complete order workflow:
        1. Push order
        2. Auto-assign courier (if enabled) or manual assignment
        3. Schedule pickup
        """
        # Get shipping address from order
        print("inside this for creating shipping")
        shipping_address = None
        for address in order.orderaddress_set.all():
            if address.address_type == "shipping":
                shipping_address = address
                break

        if not shipping_address:
            return {"error": "No shipping address found"}

        # Get order items and build product details
        product_details = []
        for item in order.items.all():
            product_details.append({
                "name": item.name,
                "sku_number": item.sku or f"SKU-{item.id}",
                "quantity": item.quantity,
                "discount": "",
                "hsn": "#123",  # You might want to get this from product model
                "unit_price": float(item.final_price / item.quantity),
                "product_category": "Other"  # You might want to get this from product model
            })

        # Determine payment type
        is_cod = order.payment.method == "COD" if hasattr(order, "payment") else False
        payment_type = "COD" if is_cod else "PREPAID"
        cod_amount = str(float(order.total_amount)) if is_cod else ""

        # Calculate package dimensions based on items
        total_weight = sum(item.quantity * 200 for item in order.items.all())  # 200g per item default
        
        # Prepare order data for Shipmojo
        order_data = {
            "order_id": order.order_number,
            "order_date": order.created_at.strftime("%Y-%m-%d"),
            "order_type": "ESSENTIALS",
            "consignee_name": shipping_address.full_name,
            "consignee_phone": int(shipping_address.phone.replace("+", "").replace("-", "").replace(" ", "")),
            "consignee_alternate_phone": int(shipping_address.phone.replace("+", "").replace("-", "").replace(" ", "")),
            "consignee_email": shipping_address.email,
            "consignee_address_line_one": shipping_address.street,
            "consignee_address_line_two": shipping_address.area,
            "consignee_pin_code": int(shipping_address.pincode),
            "consignee_city": shipping_address.city,
            "consignee_state": shipping_address.state,
            "product_detail": product_details,
            "payment_type": payment_type,
            "cod_amount": cod_amount,
            "weight": max(200, total_weight),  # Minimum 200g
            "length": 20,
            "width": 15,
            "height": 10,
            "warehouse_id": "",  # Will be set based on seller
            "gst_ewaybill_number": "",
            "gstin_number": ""
        }

        # Step 1: Push order to Shipmojo
        logger.info(f"Pushing order {order.order_number} to Shipmojo")
        push_response = self.push_order(order_data)
        
        if "error" in push_response:
            return push_response

        # Return the push response - AWB will be generated later when courier is assigned
        return {
            "order_id": push_response.get("data", {}).get("order_id"),
            "reference_id": push_response.get("data", {}).get("reference_id"),
            "message": "Order pushed to Shipmojo successfully",
            "status": "Order Created"
        }


# Backward compatibility - keep old class name as alias
ShiprocketService = ShipmojoService