from django.utils.deprecation import MiddlewareMixin
from .services import CartService
import logging
from .services import WishlistService

logger = logging.getLogger(__name__)


class CartMergeMiddleware(MiddlewareMixin):
    """
    Middleware to automatically merge session cart into user cart when a user logs in
    """

    def process_request(self, request):
        """
        Process request and merge carts if needed
        """
        # Skip for anonymous users
        if not request.user.is_authenticated:
            return None

        # Skip if no session key (not initialized)
        if not request.session.session_key:
            return None

        # Check for cart merge flag in session
        if not request.session.get("cart_merged", False):
            try:
                # Check if user has a customer profile
                if hasattr(request.user, "customer") and request.user.customer:
                    # Check if there are items in the session cart
                    if "cart" in request.session and request.session["cart"]:
                        # Merge carts
                        cart_service = CartService()
                        cart_service.merge_carts(request.user, request.session)
                        logger.info(f"Merged session cart for user {request.user.id}")

                # Mark as merged to avoid future attempts
                request.session["cart_merged"] = True

            except Exception as e:
                logger.error(f"Error in CartMergeMiddleware: {e}")

        return None


class WishlistMergeMiddleware(MiddlewareMixin):
    """
    Middleware to automatically merge session wishlist into user wishlist when a user logs in
    """

    def process_request(self, request):
        """
        Process request and merge wishlists if needed
        """
        # Skip for anonymous users
        if not request.user.is_authenticated:
            return None

        # Skip if no session key (not initialized)
        if not request.session.session_key:
            return None

        # Check for wishlist merge flag in session
        if not request.session.get("wishlist_merged", False):
            try:
                # Check if user has a customer profile
                if hasattr(request.user, "customer") and request.user.customer:
                    # Check if there are items in the session wishlist
                    if "wishlist" in request.session and request.session["wishlist"]:
                        # Merge wishlists
                        wishlist_service = WishlistService()
                        wishlist_service.merge_wishlists(request.user, request.session)
                        logger.info(
                            f"Merged session wishlist for user {request.user.id}"
                        )

                # Mark as merged to avoid future attempts
                request.session["wishlist_merged"] = True

            except Exception as e:
                logger.error(f"Error in WishlistMergeMiddleware: {e}")

        return None
