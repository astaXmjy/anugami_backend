# customers/views.py
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.contrib.auth import get_user_model, authenticate
from django.utils.timezone import now
from rest_framework.authtoken.models import Token
from django.core.mail import EmailMessage
from django.conf import settings
from django.template.loader import render_to_string

from .models import Customer, ContactUs
from .serializers import (
    CustomerSerializer,
    CustomerRegistrationSerializer,
    CustomerLoginSerializer,
    CustomerProfileUpdateSerializer,
    AddressSerializer,
    AddressUpdateSerializer,
    CartItemSerializer,
    SessionCartItemSerializer,
    CartItemCreateSerializer,
    CartBulkUpdateSerializer,
    CartItemUpdateSerializer,
    RemoveCartItemSerializer,
    WishlistItemSerializer,
    SessionWishlistItemSerializer,
    ContactUSSerializer,
)


from .services import (
    CustomerService,
    AddressService,
    CartService,
    WishlistService,
)

import logging

logger = logging.getLogger(__name__)
User = get_user_model()


class CustomerViewSet(viewsets.ModelViewSet):
    serializer_class = CustomerSerializer
    # authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        print(self.action)
        print(hasattr(self.request.user, "has_module_permission"))
        if (
            self.request.user.is_superuser
            or hasattr(self.request.user, "has_module_permission")
            and self.request.user.has_module_permission("customer", "list")
        ):
            print("inside this")
            return Customer.objects.all()
        return Customer.objects.filter(user=self.request.user)

    def get_permissions(self):
        """
        Override to set permissions based on action
        """
        # Cart-related endpoints should be accessible to anonymous users
        if self.action in [
            "cart",
            "add_to_cart",
            "update_cart_item",
            "remove_from_cart",
            "update_cart",
            "clear_cart",
            "cart_summary",
            "sync_cart_prices",
            "wishlist",
            "add_to_wishlist",
            "remove_from_wishlist",
            "clear_wishlist",
            "is_in_wishlist",
            "wishlist_count",
        ]:
            permission_classes = [AllowAny]
        # Authentication endpoints don't require authentication
        elif self.action in ["register", "login"]:
            permission_classes = [AllowAny]
        # All other endpoints require authentication
        else:
            permission_classes = [IsAuthenticated]

        return [permission() for permission in permission_classes]

    @action(detail=False, methods=["POST"], permission_classes=[AllowAny])
    def register(self, request):
        """Register new customer"""
        try:
            serializer = CustomerRegistrationSerializer(data=request.data)
            if not serializer.is_valid():
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

            customer_service = CustomerService()
            customer = customer_service.create_customer(
                email=serializer.validated_data["email"],
                phone=serializer.validated_data["phone"],
                full_name=serializer.validated_data["full_name"],
                password=serializer.validated_data["password"],
            )

            token, _ = Token.objects.get_or_create(user=customer.user)

            return Response(
                {
                    "message": "Registration successful",
                    "token": token.key,
                    "id": str(customer.id),
                    "email": customer.user.email,
                    "full_name": customer.full_name,
                },
                status=status.HTTP_201_CREATED,
            )

        except Exception as e:
            logger.error(f"Registration error: {str(e)}")
            return Response(
                {"error": "Registration failed", "detail": str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )

    @action(detail=False, methods=["POST"], permission_classes=[AllowAny])
    def login(self, request):
        """Login customer"""
        serializer = CustomerLoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = authenticate(
            request,
            username=serializer.validated_data["email"],
            password=serializer.validated_data["password"],
        )

        if not user:
            return Response(
                {"error": "Invalid credentials"}, status=status.HTTP_401_UNAUTHORIZED
            )

        try:
            customer = user.customer
            if customer.status != "active":
                return Response(
                    {"error": "Account is inactive or suspended"},
                    status=status.HTTP_403_FORBIDDEN,
                )
        except Customer.DoesNotExist:
            return Response(
                {"error": "No customer profile found"}, status=status.HTTP_404_NOT_FOUND
            )

        token, _ = Token.objects.get_or_create(user=user)

        user.last_login = now()
        user.save()

        return Response(
            {
                "token": token.key,
                "customer_id": str(customer.id),
                "email": user.email,
                "full_name": customer.full_name,
            },
            status=status.HTTP_200_OK,
        )

    @action(detail=False, methods=["POST"])
    def contact_us(self, request):
        """Contact us form submission"""
        print("inside this contact us action")
        try:
            serializer = ContactUSSerializer(data=request.data)
            if not serializer.is_valid():
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

            # Save contact form data to database
            contact_data = {
                "name": serializer.validated_data["name"],
                "email": serializer.validated_data["email"],
                "phone": serializer.validated_data["phone"],
                "subject": serializer.validated_data["subject"],
                "message": serializer.validated_data["message"],
            }

            if request.user.is_authenticated and hasattr(request.user, "customer"):
                contact_data["customer"] = request.user.customer
                print(contact_data["customer"])

            contact_entry = ContactUs.objects.create(**contact_data)
            # Get contact email from settings
            contact_email = getattr(
                settings, "CONTACT_US_EMAIL", settings.DEFAULT_FROM_EMAIL
            )

            # Prepare email context
            context = {
                "name": serializer.validated_data["name"],
                "email": serializer.validated_data["email"],
                "subject": serializer.validated_data["subject"],
                "message": serializer.validated_data["message"],
                "phone": serializer.validated_data["phone"],
            }

            # Render email template
            email_body = render_to_string("contact_us.html", context)

            # Create and send email
            email = EmailMessage(
                subject=f"Contact Form: {serializer.validated_data['subject']}",
                body=email_body,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[contact_email],
                reply_to=[serializer.validated_data["email"]],
            )
            email.content_subtype = "html"
            email.send()

            return Response(
                {"message": "Contact us request sent successfully"},
                status=status.HTTP_200_OK,
            )
        except Exception as e:
            logger.error(f"Contact us error: {str(e)}")
            return Response(
                {"error": "Contact us request failed", "detail": str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )

    @action(detail=False, methods=["GET"])
    def profile(self, request):
        """Get customer profile"""
        try:
            customer = request.user.customer
            serializer = CustomerSerializer(customer)
            return Response(serializer.data)
        except Customer.DoesNotExist:
            return Response(
                {"error": "Customer profile not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

    @action(detail=False, methods=["PUT"])
    def update_profile(self, request):
        """Update customer profile"""
        try:
            serializer = CustomerProfileUpdateSerializer(
                data=request.data, context={"request": request}
            )
            serializer.is_valid(raise_exception=True)

            customer = request.user.customer
            for field, value in serializer.validated_data.items():
                setattr(customer, field, value)
            customer.save()

            return Response(CustomerSerializer(customer).data)

        except Customer.DoesNotExist:
            return Response(
                {"error": "Customer profile not found"},
                status=status.HTTP_404_NOT_FOUND,
            )
        except Exception as e:
            logger.error(f"Profile update error: {str(e)}")
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=["GET"])
    def addresses(self, request):
        """Get customer addresses"""
        try:
            addresses = request.user.customer.addresses.all()
            serializer = AddressSerializer(addresses, many=True)
            return Response(serializer.data)
        except Customer.DoesNotExist:
            return Response(
                {"error": "Customer profile not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

    @action(detail=False, methods=["POST"])
    def add_address(self, request):
        """Add new address"""
        try:
            serializer = AddressSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)

            address = AddressService().add_address(
                request.user.customer.id, serializer.validated_data
            )
            return Response(AddressSerializer(address).data)

        except Exception as e:
            logger.error(f"Add address error: {str(e)}")
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=["PUT"])
    def update_address(self, request, pk=None):
        """Update existing address"""
        try:
            serializer = AddressUpdateSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)

            address = AddressService().update_address(pk, serializer.validated_data)
            return Response(AddressSerializer(address).data)

        except Exception as e:
            logger.error(f"Update address error: {str(e)}")
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=["DELETE"])
    def delete_address(self, request, pk=None):
        """Delete address"""
        try:
            success = AddressService().delete_address(pk)
            if success:
                return Response(status=status.HTTP_204_NO_CONTENT)
            return Response(
                {"error": "Address not found"}, status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            logger.error(f"Delete address error: {str(e)}")
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=["POST"])
    def logout(self, request):
        """Logout customer"""
        try:
            request.user.auth_token.delete()
            return Response(
                {"message": "Successfully logged out"}, status=status.HTTP_200_OK
            )
        except Exception as e:
            logger.error(f"Logout error: {str(e)}")
            return Response(
                {"error": "Logout failed"}, status=status.HTTP_400_BAD_REQUEST
            )

    # Modified cart view methods to support anonymous users with product information

    @action(detail=False, methods=["GET"])
    def cart(self, request):
        """
        Get cart items with product information - works for both authenticated and anonymous users
        """
        try:
            cart_service = CartService()

            # We'll pass either the user or session to the cart service
            user_or_session = (
                request.user if request.user.is_authenticated else request.session
            )

            # Get cart items using the service
            cart_items = cart_service.get_cart_items(user_or_session)

            # Calculate totals
            cart_count = cart_service.get_cart_count(user_or_session)
            cart_total = cart_service.get_cart_total(user_or_session)

            # Use appropriate serializer based on authentication
            if request.user.is_authenticated and hasattr(request.user, "customer"):
                # For authenticated users, use database model serializer
                serialized_items = CartItemSerializer(cart_items, many=True).data
            else:
                # For anonymous users, use session serializer
                serialized_items = SessionCartItemSerializer(cart_items, many=True).data

            return Response(
                {
                    "items": serialized_items,
                    "total_items": cart_count,
                    "item_count": len(cart_items),
                    "subtotal": float(cart_total) if cart_total else 0,
                }
            )

        except Exception as e:
            logger.error(f"Error getting cart: {str(e)}")
            return Response(
                {"error": "Failed to retrieve cart", "detail": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @action(detail=False, methods=["POST"], permission_classes=[AllowAny])
    def add_to_cart(self, request):
        """
        Add item to cart with product information - works for both authenticated and anonymous users
        """
        try:
            # Validate request data
            serializer = CartItemCreateSerializer(data=request.data)
            if not serializer.is_valid():
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

            # Extract data
            product_id = serializer.validated_data["product_id"]
            variant_id = serializer.validated_data.get("variant_id")
            quantity = serializer.validated_data["quantity"]
            price = serializer.validated_data.get("price")

            # Get user or session
            user_or_session = (
                request.user if request.user.is_authenticated else request.session
            )

            # Add to cart using the service
            cart_service = CartService()
            cart_item = cart_service.add_to_cart(
                user_or_session, product_id, quantity, variant_id, price
            )

            # Return the updated cart item with product info
            if request.user.is_authenticated and hasattr(request.user, "customer"):
                cart_item_data = CartItemSerializer(cart_item).data
            else:
                cart_item_data = SessionCartItemSerializer(cart_item).data

            return Response(cart_item_data, status=status.HTTP_201_CREATED)

        except Exception as e:
            logger.error(f"Error adding to cart: {str(e)}")
            return Response(
                {"error": "Failed to add item to cart", "detail": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @action(detail=True, methods=["PUT", "PATCH"], permission_classes=[AllowAny])
    def update_cart_item(self, request, pk=None):
        """
        Update a specific cart item with product info - works for both authenticated and anonymous users
        """
        try:
            # Validate request data
            serializer = CartItemUpdateSerializer(data=request.data)
            if not serializer.is_valid():
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

            # Get quantity/price updates
            quantity = serializer.validated_data.get("quantity")
            price = serializer.validated_data.get("price")

            # Get user or session
            user_or_session = (
                request.user if request.user.is_authenticated else request.session
            )

            # Check if we need to remove the item (quantity=0)
            if quantity == 0:
                cart_service = CartService()
                removed = cart_service.remove_from_cart(user_or_session, pk)

                if removed:
                    return Response(
                        {"message": "Item removed from cart"}, status=status.HTTP_200_OK
                    )
                else:
                    return Response(
                        {"error": "Cart item not found"},
                        status=status.HTTP_404_NOT_FOUND,
                    )

            # Update the cart item
            cart_service = CartService()
            cart_item = cart_service.update_cart_item(
                user_or_session, pk, quantity, price
            )

            if cart_item:
                # Use appropriate serializer with product info
                if request.user.is_authenticated and hasattr(request.user, "customer"):
                    cart_item_data = CartItemSerializer(cart_item).data
                else:
                    cart_item_data = SessionCartItemSerializer(cart_item).data

                return Response(cart_item_data)
            else:
                return Response(
                    {"error": "Cart item not found"}, status=status.HTTP_404_NOT_FOUND
                )

        except Exception as e:
            logger.error(f"Error updating cart item: {str(e)}")
            return Response(
                {"error": "Failed to update cart item", "detail": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @action(detail=False, methods=["POST"], permission_classes=[AllowAny])
    def remove_from_cart(self, request):
        """
        Remove a product from cart - works for both authenticated and anonymous users
        """
        try:
            # Validate request data
            serializer = RemoveCartItemSerializer(data=request.data)
            if not serializer.is_valid():
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

            # Extract data
            product_id = serializer.validated_data["product_id"]
            variant_id = serializer.validated_data.get("variant_id")

            # Get user or session
            user_or_session = (
                request.user if request.user.is_authenticated else request.session
            )

            # Remove from cart using the service
            cart_service = CartService()
            removed = cart_service.remove_product_from_cart(
                user_or_session, product_id, variant_id
            )

            if removed:
                return Response({"message": "Item removed from cart"})
            else:
                return Response(
                    {"error": "Item not found in cart"},
                    status=status.HTTP_404_NOT_FOUND,
                )

        except Exception as e:
            logger.error(f"Error removing from cart: {str(e)}")
            return Response(
                {"error": "Failed to remove item from cart", "detail": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @action(detail=False, methods=["POST"], permission_classes=[AllowAny])
    def update_cart(self, request):
        """
        Bulk update cart (replace entire cart) - works for both authenticated and anonymous users
        """
        try:
            # Validate request data
            serializer = CartBulkUpdateSerializer(data=request.data)
            if not serializer.is_valid():
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

            # Extract data
            cart_items = serializer.validated_data["items"]

            # Get user or session
            user_or_session = (
                request.user if request.user.is_authenticated else request.session
            )

            # Update cart using the service
            cart_service = CartService()
            cart_service.update_cart(user_or_session, cart_items)

            # Return the updated cart with product info
            updated_items = cart_service.get_cart_items(user_or_session)

            # Use appropriate serializer
            if request.user.is_authenticated and hasattr(request.user, "customer"):
                updated_items = CartItemSerializer(updated_items, many=True).data
            else:
                updated_items = SessionCartItemSerializer(updated_items, many=True).data

            return Response(updated_items)

        except Exception as e:
            logger.error(f"Error updating cart: {str(e)}")
            return Response(
                {"error": "Failed to update cart", "detail": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @action(detail=True, methods=["DELETE"], permission_classes=[AllowAny])
    def remove_cart_item(self, request, pk=None):
        """
        Remove a specific cart item by ID - works for both authenticated and anonymous users
        """
        try:
            # Get user or session
            user_or_session = (
                request.user if request.user.is_authenticated else request.session
            )

            # Remove item using the service
            cart_service = CartService()
            removed = cart_service.remove_from_cart(user_or_session, pk)

            if removed:
                return Response({"message": "Item removed from cart"})
            else:
                return Response(
                    {"error": "Cart item not found"}, status=status.HTTP_404_NOT_FOUND
                )

        except Exception as e:
            logger.error(f"Error removing cart item: {str(e)}")
            return Response(
                {"error": "Failed to remove cart item", "detail": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @action(detail=False, methods=["POST"], permission_classes=[AllowAny])
    def clear_cart(self, request):
        """
        Clear all items from cart - works for both authenticated and anonymous users
        """
        try:
            # Get user or session
            user_or_session = (
                request.user if request.user.is_authenticated else request.session
            )

            # Clear cart using the service
            cart_service = CartService()
            cart_service.clear_cart(user_or_session)

            return Response({"message": "Cart cleared successfully"})

        except Exception as e:
            logger.error(f"Error clearing cart: {str(e)}")
            return Response(
                {"error": "Failed to clear cart", "detail": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @action(detail=False, methods=["GET"], permission_classes=[AllowAny])
    def cart_summary(self, request):
        """
        Get cart summary (count, total, etc.) - works for both authenticated and anonymous users
        """
        try:
            # Get user or session
            user_or_session = (
                request.user if request.user.is_authenticated else request.session
            )

            # Get cart data using the service
            cart_service = CartService()
            cart_items = cart_service.get_cart_items(user_or_session)
            cart_count = cart_service.get_cart_count(user_or_session)
            cart_total = cart_service.get_cart_total(user_or_session)

            # Return summary
            return Response(
                {
                    "total_items": cart_count,
                    "item_count": len(cart_items),
                    "subtotal": float(cart_total) if cart_total else 0,
                }
            )

        except Exception as e:
            logger.error(f"Error getting cart summary: {str(e)}")
            return Response(
                {"error": "Failed to get cart summary", "detail": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @action(detail=False, methods=["POST"])
    def merge_carts(self, request):
        """
        Merge session cart into user's cart after login
        """
        try:
            # This should only be called for authenticated users
            if not request.user.is_authenticated:
                return Response(
                    {"error": "User must be authenticated to merge carts"},
                    status=status.HTTP_401_UNAUTHORIZED,
                )

            # Ensure the user has a customer profile
            if not hasattr(request.user, "customer"):
                return Response(
                    {"error": "Customer profile not found"},
                    status=status.HTTP_404_NOT_FOUND,
                )

            # Merge carts
            cart_service = CartService()
            success = cart_service.merge_carts(request.user, request.session)

            if success:
                # Get updated cart with product information
                cart_items = cart_service.get_cart_items(request.user)
                return Response(
                    {
                        "message": "Carts merged successfully",
                        "items": CartItemSerializer(cart_items, many=True).data,
                    }
                )
            else:
                return Response(
                    {"error": "Failed to merge carts"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        except Exception as e:
            logger.error(f"Error merging carts: {str(e)}")
            return Response(
                {"error": "Failed to merge carts", "detail": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    # Wishlist methods with product information

    @action(detail=False, methods=["GET"], permission_classes=[AllowAny])
    def wishlist(self, request):
        """
        Get wishlist items with product information - works for both authenticated and anonymous users
        """
        try:
            wishlist_service = WishlistService()

            # We'll pass either the user or session to the wishlist service
            user_or_session = (
                request.user if request.user.is_authenticated else request.session
            )

            # Get wishlist items using the service
            wishlist_items = wishlist_service.get_wishlist(user_or_session)

            # Use appropriate serializer based on authentication
            if request.user.is_authenticated and hasattr(request.user, "customer"):
                # For authenticated users, use database model serializer
                serialized_items = WishlistItemSerializer(
                    wishlist_items, many=True
                ).data
            else:
                # For anonymous users, use session serializer
                serialized_items = SessionWishlistItemSerializer(
                    wishlist_items, many=True
                ).data

            return Response({"items": serialized_items, "count": len(wishlist_items)})

        except Exception as e:
            logger.error(f"Error getting wishlist: {str(e)}")
            return Response(
                {"error": "Failed to retrieve wishlist", "detail": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @action(detail=False, methods=["POST"], permission_classes=[AllowAny])
    def add_to_wishlist(self, request):
        """
        Add item to wishlist with product information - works for both authenticated and anonymous users
        """
        try:
            # Validate request data
            if not request.data.get("product_id"):
                return Response(
                    {"error": "product_id is required"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            product_id = request.data.get("product_id")
            variant_id = request.data.get("variant_id")

            # Get user or session
            user_or_session = (
                request.user if request.user.is_authenticated else request.session
            )

            # Add to wishlist using the service
            wishlist_service = WishlistService()
            wishlist_item = wishlist_service.add_to_wishlist(
                user_or_session, product_id, variant_id
            )

            # Return the updated wishlist item with product info
            if request.user.is_authenticated and hasattr(request.user, "customer"):
                wishlist_item_data = WishlistItemSerializer(wishlist_item).data
            else:
                wishlist_item_data = SessionWishlistItemSerializer(wishlist_item).data

            return Response(wishlist_item_data, status=status.HTTP_201_CREATED)

        except Exception as e:
            logger.error(f"Error adding to wishlist: {str(e)}")
            return Response(
                {"error": "Failed to add item to wishlist", "detail": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @action(detail=False, methods=["POST"], permission_classes=[AllowAny])
    def remove_from_wishlist(self, request):
        """
        Remove a product from wishlist - works for both authenticated and anonymous users
        """
        try:
            # Validate request data
            if not request.data.get("product_id"):
                return Response(
                    {"error": "product_id is required"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            product_id = request.data.get("product_id")
            variant_id = request.data.get("variant_id")

            # Get user or session
            user_or_session = (
                request.user if request.user.is_authenticated else request.session
            )

            # Remove from wishlist using the service
            wishlist_service = WishlistService()
            removed = wishlist_service.remove_from_wishlist(
                user_or_session, product_id, variant_id
            )

            if removed:
                return Response({"message": "Item removed from wishlist"})
            else:
                return Response(
                    {"error": "Item not found in wishlist"},
                    status=status.HTTP_404_NOT_FOUND,
                )

        except Exception as e:
            logger.error(f"Error removing from wishlist: {str(e)}")
            return Response(
                {"error": "Failed to remove item from wishlist", "detail": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @action(detail=True, methods=["DELETE"], permission_classes=[AllowAny])
    def remove_wishlist_item(self, request, pk=None):
        """
        Remove a specific wishlist item by ID - works for both authenticated and anonymous users
        """
        try:
            # Get user or session
            user_or_session = (
                request.user if request.user.is_authenticated else request.session
            )

            # Remove item using the service
            wishlist_service = WishlistService()
            removed = wishlist_service.remove_item_by_id(user_or_session, pk)

            if removed:
                return Response({"message": "Item removed from wishlist"})
            else:
                return Response(
                    {"error": "Wishlist item not found"},
                    status=status.HTTP_404_NOT_FOUND,
                )

        except Exception as e:
            logger.error(f"Error removing wishlist item: {str(e)}")
            return Response(
                {"error": "Failed to remove wishlist item", "detail": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @action(detail=False, methods=["POST"], permission_classes=[AllowAny])
    def clear_wishlist(self, request):
        """
        Clear all items from wishlist - works for both authenticated and anonymous users
        """
        try:
            # Get user or session
            user_or_session = (
                request.user if request.user.is_authenticated else request.session
            )

            # Clear wishlist using the service
            wishlist_service = WishlistService()
            wishlist_service.clear_wishlist(user_or_session)

            return Response({"message": "Wishlist cleared successfully"})

        except Exception as e:
            logger.error(f"Error clearing wishlist: {str(e)}")
            return Response(
                {"error": "Failed to clear wishlist", "detail": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @action(detail=False, methods=["GET"], permission_classes=[AllowAny])
    def wishlist_count(self, request):
        """
        Get wishlist count - works for both authenticated and anonymous users
        """
        try:
            # Get user or session
            user_or_session = (
                request.user if request.user.is_authenticated else request.session
            )

            # Get wishlist count using the service
            wishlist_service = WishlistService()
            count = wishlist_service.get_wishlist_count(user_or_session)

            # Return count
            return Response({"count": count})

        except Exception as e:
            logger.error(f"Error getting wishlist count: {str(e)}")
            return Response(
                {"error": "Failed to get wishlist count", "detail": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @action(detail=False, methods=["POST"], permission_classes=[AllowAny])
    def is_in_wishlist(self, request):
        """
        Check if a product is in the wishlist - works for both authenticated and anonymous users
        """
        try:
            # Validate request data
            if not request.data.get("product_id"):
                return Response(
                    {"error": "product_id is required"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            product_id = request.data.get("product_id")
            variant_id = request.data.get("variant_id")

            # Get user or session
            user_or_session = (
                request.user if request.user.is_authenticated else request.session
            )

            # Check if in wishlist using the service
            wishlist_service = WishlistService()
            is_in_wishlist = wishlist_service.is_in_wishlist(
                user_or_session, product_id, variant_id
            )

            # Return result
            return Response({"in_wishlist": is_in_wishlist})

        except Exception as e:
            logger.error(f"Error checking wishlist: {str(e)}")
            return Response(
                {"error": "Failed to check wishlist", "detail": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @action(detail=False, methods=["POST"])
    def merge_wishlists(self, request):
        """
        Merge session wishlist into user's wishlist after login
        """
        try:
            # This should only be called for authenticated users
            if not request.user.is_authenticated:
                return Response(
                    {"error": "User must be authenticated to merge wishlists"},
                    status=status.HTTP_401_UNAUTHORIZED,
                )

            # Ensure the user has a customer profile
            if not hasattr(request.user, "customer"):
                return Response(
                    {"error": "Customer profile not found"},
                    status=status.HTTP_404_NOT_FOUND,
                )

            # Merge wishlists
            wishlist_service = WishlistService()
            success = wishlist_service.merge_wishlists(request.user, request.session)

            if success:
                # Get updated wishlist with product information
                wishlist_items = wishlist_service.get_wishlist(request.user)
                return Response(
                    {
                        "message": "Wishlists merged successfully",
                        "items": WishlistItemSerializer(wishlist_items, many=True).data,
                    }
                )
            else:
                return Response(
                    {"error": "Failed to merge wishlists"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        except Exception as e:
            logger.error(f"Error merging wishlists: {str(e)}")
            return Response(
                {"error": "Failed to merge wishlists", "detail": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    # Additional utility methods

    @action(detail=False, methods=["POST"], permission_classes=[AllowAny])
    def sync_cart_prices(self, request):
        """
        Sync cart prices with current product prices - works for both authenticated and anonymous users
        """
        try:
            # Get user or session
            user_or_session = (
                request.user if request.user.is_authenticated else request.session
            )

            # Get cart items
            cart_service = CartService()
            cart_items = cart_service.get_cart_items(user_or_session)

            updated_items = []

            # Update prices for each item
            for item in cart_items:
                try:
                    # Import here to avoid circular imports
                    from products.models import Product

                    product = Product.objects.get(
                        id=(
                            item.product_id
                            if hasattr(item, "product_id")
                            else item["product_id"]
                        )
                    )
                    current_price = (
                        product.sale_price
                        if hasattr(product, "sale_price") and product.sale_price
                        else product.regular_price
                    )

                    if hasattr(item, "price"):
                        # Database item
                        if item.price != current_price:
                            item.price = current_price
                            item.save()
                            updated_items.append(item.id)
                    else:
                        # Session item
                        if item.get("price") != current_price:
                            item["price"] = float(current_price)
                            updated_items.append(item.get("id"))

                except Exception as e:
                    logger.warning(
                        f"Could not sync price for product {item.product_id if hasattr(item, 'product_id') else item['product_id']}: {str(e)}"
                    )
                    continue

            # Save session changes if needed
            if not (
                request.user.is_authenticated and hasattr(request.user, "customer")
            ):
                request.session.modified = True

            return Response(
                {
                    "message": "Cart prices synced successfully",
                    "updated_items": len(updated_items),
                }
            )

        except Exception as e:
            logger.error(f"Error syncing cart prices: {str(e)}")
            return Response(
                {"error": "Failed to sync cart prices", "detail": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    # Additional customer management methods

    @action(detail=False, methods=["GET"])
    def wallet_transactions(self, request):
        """Get customer wallet transactions"""
        try:
            customer = request.user.customer
            from .services import TransactionService

            transactions = TransactionService().get_transactions(customer.id)
            from .serializers import CustomerTransactionSerializer

            serializer = CustomerTransactionSerializer(transactions, many=True)
            return Response(
                {
                    "transactions": serializer.data,
                    "current_balance": float(customer.wallet_balance),
                }
            )

        except Customer.DoesNotExist:
            return Response(
                {"error": "Customer profile not found"},
                status=status.HTTP_404_NOT_FOUND,
            )
        except Exception as e:
            logger.error(f"Error getting wallet transactions: {str(e)}")
            return Response(
                {"error": "Failed to get wallet transactions", "detail": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @action(detail=False, methods=["POST"])
    def record_activity(self, request):
        """Record customer activity"""
        try:
            customer = request.user.customer

            activity_type = request.data.get("activity_type")
            product_id = request.data.get("product_id")
            category_id = request.data.get("category_id")

            if not activity_type:
                return Response(
                    {"error": "activity_type is required"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            from .services import CustomerActivityService

            activity_details = {
                "product_id": product_id,
                "category_id": category_id,
            }

            activity = CustomerActivityService().record_activity(
                customer.id, activity_type, activity_details
            )

            from .serializers import CustomerActivitySerializer

            return Response(CustomerActivitySerializer(activity).data)

        except Customer.DoesNotExist:
            return Response(
                {"error": "Customer profile not found"},
                status=status.HTTP_404_NOT_FOUND,
            )
        except Exception as e:
            logger.error(f"Error recording activity: {str(e)}")
            return Response(
                {"error": "Failed to record activity", "detail": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @action(detail=False, methods=["GET"])
    def order_stats(self, request):
        """Get customer order statistics"""
        try:
            customer = request.user.customer

            # Get or create order stats
            from .models import CustomerOrderStats

            stats, created = CustomerOrderStats.objects.get_or_create(
                customer=customer,
                defaults={
                    "total_orders": customer.total_orders,
                    "total_order_value": customer.total_order_value,
                },
            )

            from .serializers import CustomerOrderStatsSerializer

            return Response(CustomerOrderStatsSerializer(stats).data)

        except Customer.DoesNotExist:
            return Response(
                {"error": "Customer profile not found"},
                status=status.HTTP_404_NOT_FOUND,
            )
        except Exception as e:
            logger.error(f"Error getting order stats: {str(e)}")
            return Response(
                {"error": "Failed to get order stats", "detail": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @action(detail=False, methods=["GET"])
    def get_interactions(self, request):
        """Get customer interactions/activities"""
        try:
            customer = request.user.customer

            # Get recent activities
            activities = customer.activities.all()[:50]  # Last 50 activities

            from .serializers import CustomerActivitySerializer

            return Response(
                {
                    "activities": CustomerActivitySerializer(
                        activities, many=True
                    ).data,
                    "total_activities": customer.activities.count(),
                }
            )

        except Customer.DoesNotExist:
            return Response(
                {"error": "Customer profile not found"},
                status=status.HTTP_404_NOT_FOUND,
            )
        except Exception as e:
            logger.error(f"Error getting interactions: {str(e)}")
            return Response(
                {"error": "Failed to get interactions", "detail": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @action(detail=False, methods=["POST"])
    def update_wallet(self, request):
        """Update customer wallet balance (admin only or through valid transaction)"""
        try:
            # This should be restricted to admin users or valid payment gateways
            if not request.user.is_staff:
                return Response(
                    {"error": "Unauthorized to update wallet"},
                    status=status.HTTP_403_FORBIDDEN,
                )

            customer_id = request.data.get("customer_id")
            transaction_type = request.data.get(
                "transaction_type"
            )  # 'credit' or 'debit'
            amount = request.data.get("amount")
            transaction_id = request.data.get("transaction_id")

            if not all([customer_id, transaction_type, amount, transaction_id]):
                return Response(
                    {"error": "Missing required fields"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            from .services import TransactionService

            transaction = TransactionService().create_transaction(
                customer_id, transaction_type, float(amount), transaction_id
            )

            from .serializers import CustomerTransactionSerializer

            return Response(CustomerTransactionSerializer(transaction).data)

        except Exception as e:
            logger.error(f"Error updating wallet: {str(e)}")
            return Response(
                {"error": "Failed to update wallet", "detail": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
