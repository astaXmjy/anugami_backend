# customers/services.py
from django.contrib.auth import get_user_model
from django.db import transaction
from django.core.exceptions import ObjectDoesNotExist
from django.utils.timezone import now
import logging
from django.db import models
from datetime import datetime

from .models import (
    Customer,
    Address,
    CartItem,
    WishlistItem,
    CustomerPreferences,
    CustomerActivity,
    CustomerTransaction,
    CustomerOrderStats,
)

logger = logging.getLogger(__name__)
User = get_user_model()


class CustomerService:
    @transaction.atomic
    def create_customer(self, email, phone, full_name, password):
        """Create a new customer"""
        try:
            # Create CustomUser first
            user = User.objects.create_user(
                email=email, password=password, name=full_name, phone_number=phone
            )
            logger.info(f"Created user with email: {email}")

            # Create Customer profile
            customer = Customer.objects.create(user=user, full_name=full_name)
            logger.info(f"Created customer profile for: {email}")

            # Create default preferences
            CustomerPreferences.objects.create(customer=customer)
            logger.info(f"Created default preferences for: {email}")

            return customer

        except Exception as e:
            logger.error(f"Error creating customer: {str(e)}")
            raise

    def get_customer(self, customer_id):
        """Retrieve customer details"""
        try:
            return Customer.objects.get(id=customer_id)
        except Customer.DoesNotExist:
            logger.error(f"Customer not found: {customer_id}")
            return None

    def update_customer(self, customer_id, data):
        """Update customer details"""
        try:
            customer = self.get_customer(customer_id)
            if not customer:
                return None

            with transaction.atomic():
                # Update user-related fields if present
                user_fields = ["name", "phone_number"]
                user_data = {k: v for k, v in data.items() if k in user_fields}
                if user_data:
                    for field, value in user_data.items():
                        setattr(customer.user, field, value)
                    customer.user.save()

                # Update customer fields
                customer_fields = [
                    "full_name",
                    "date_of_birth",
                    "gender",
                    "profile_picture",
                ]
                customer_data = {k: v for k, v in data.items() if k in customer_fields}
                if customer_data:
                    for field, value in customer_data.items():
                        setattr(customer, field, value)
                    customer.save()

            return customer

        except Exception as e:
            logger.error(f"Error updating customer: {str(e)}")
            raise

    @transaction.atomic
    def delete_customer(self, customer_id):
        """Delete customer"""
        try:
            customer = self.get_customer(customer_id)
            if customer:
                user = customer.user
                user.delete()  # This will cascade delete the customer
                return True
            return False
        except Exception as e:
            logger.error(f"Error deleting customer: {str(e)}")
            raise


class AddressService:
    @transaction.atomic
    def add_address(self, customer_id, address_data):
        """Add a new address"""
        try:
            customer = Customer.objects.get(id=customer_id)

            # If this is set as default, unset other defaults
            if address_data.get("is_default"):
                Address.objects.filter(customer=customer).update(is_default=False)

            address = Address.objects.create(customer=customer, **address_data)
            logger.info(f"Added new address for customer: {customer_id}")
            return address

        except Exception as e:
            logger.error(f"Error adding address: {str(e)}")
            raise

    @transaction.atomic
    def update_address(self, address_id, address_data):
        """Update an existing address"""
        try:
            address = Address.objects.get(id=address_id)

            # Handle default address change
            if address_data.get("is_default"):
                Address.objects.filter(customer=address.customer).update(
                    is_default=False
                )

            for key, value in address_data.items():
                setattr(address, key, value)
            address.save()

            return address

        except Address.DoesNotExist:
            logger.error(f"Address not found: {address_id}")
            return None
        except Exception as e:
            logger.error(f"Error updating address: {str(e)}")
            raise

    def delete_address(self, address_id):
        """Delete an address"""
        try:
            address = Address.objects.get(id=address_id)
            address.delete()
            return True
        except Address.DoesNotExist:
            return False
        except Exception as e:
            logger.error(f"Error deleting address: {str(e)}")
            raise


class CartService:
    """
    Enhanced CartService that works for both authenticated and anonymous users
    - For authenticated users: uses database storage
    - For anonymous users: uses session storage
    """
    
    def _get_session_cart(self, session):
        """Helper to get the cart from session"""
        return session.get('cart', [])
    
    def _save_session_cart(self, session, cart_items):
        """Helper to save the cart to session"""
        session['cart'] = cart_items
        session.modified = True
    
    def _find_session_item(self, session_cart, product_id, variant_id=None):
        """Find an item in the session cart"""
        for index, item in enumerate(session_cart):
            if (item['product_id'] == product_id and 
                item.get('variant_id') == variant_id):
                return index
        return -1
    
    def _is_authenticated_user(self, user_or_session):
        """Check if we're dealing with an authenticated user or session"""
        # If it's a User model instance with a customer attribute
        return hasattr(user_or_session, 'customer') and user_or_session.customer is not None
    
    def get_cart_items(self, user_or_session):
        """
        Get cart items for authenticated or anonymous user
        
        Args:
            user_or_session: User object or session object
        """
        try:
            if self._is_authenticated_user(user_or_session):
                # Authenticated user - use database
                return CartItem.objects.filter(customer_id=user_or_session.customer.id).order_by('added_at')
            else:
                # Anonymous user - use session
                session_cart = self._get_session_cart(user_or_session)
                # Convert session cart to a format similar to CartItem model
                cart_items = []
                for i, item in enumerate(session_cart):
                    item['id'] = f"session-{i}"  # Add virtual ID
                    # Add missing fields that would be in the model
                    if 'added_at' not in item:
                        item['added_at'] = datetime.now().isoformat()
                    if 'updated_at' not in item:
                        item['updated_at'] = datetime.now().isoformat()
                    cart_items.append(item)
                return cart_items
                
        except Exception as e:
            logger.error(f"Error retrieving cart items: {str(e)}")
            raise
            
    def add_to_cart(self, user_or_session, product_id, quantity, variant_id=None, price=None):
        """
        Add item to cart for authenticated or anonymous user
        
        Args:
            user_or_session: User object or session object
            product_id: ID of the product
            quantity: Quantity to add
            variant_id: Optional variant ID
            price: Optional price
        """
        try:
            if self._is_authenticated_user(user_or_session):
                # Authenticated user - use database
                customer = user_or_session.customer
                cart_item, created = CartItem.objects.get_or_create(
                    customer=customer,
                    product_id=product_id,
                    variant_id=variant_id,
                    defaults={
                        "quantity": quantity,
                        "price": float(price) if price is not None else 0.0  # Default price if not provided
                    }
                )
    
                if not created:
                    # Update existing item
                    cart_item.quantity += quantity
                    if price is not None:
                        cart_item.price =float(price)
                    cart_item.save()
                cart_item_price=float(cart_item.price)
                return cart_item
            else:
                # Anonymous user - use session
                session = user_or_session
                cart_items = self._get_session_cart(session)
                
                # Check if item already exists
                index = self._find_session_item(cart_items, product_id, variant_id)
                
                if index >= 0:
                    # Update existing item
                    cart_items[index]['quantity'] += quantity
                    if price is not None:
                        cart_items[index]['price'] = float(price)
                    cart_items[index]['updated_at'] = datetime.now().isoformat()
                    item = cart_items[index]
                else:
                    # Add new item
                    item = {
                        'product_id': product_id,
                        'variant_id': variant_id,
                        'quantity': quantity,
                        'price': float(price) if price is not None else 0.0,
                        'added_at': datetime.now().isoformat(),
                        'updated_at': datetime.now().isoformat()
                    }
                    cart_items.append(item)
                
                # Save to session
                self._save_session_cart(session, cart_items)
                
                # Add an ID for consistency with DB model
                item['id'] = f"session-{index if index >= 0 else len(cart_items) - 1}"
                return item
                
        except Exception as e:
            logger.error(f"Error adding to cart: {str(e)}")
            raise
            
    def update_cart_item(self, user_or_session, item_id, quantity=None, price=None):
        """
        Update a specific cart item
        
        Args:
            user_or_session: User object or session object
            item_id: ID of the cart item
            quantity: New quantity
            price: New price
        """
        try:
            if self._is_authenticated_user(user_or_session):
                # Authenticated user - use database
                try:
                    cart_item = CartItem.objects.get(id=item_id)
                    
                    if quantity is not None:
                        cart_item.quantity = quantity
                    
                    if price is not None:
                        cart_item.price = price
                    
                    cart_item.save()
                    return cart_item
                except CartItem.DoesNotExist:
                    logger.error(f"Cart item not found: {item_id}")
                    return None
            else:
                # Anonymous user - use session
                session = user_or_session
                cart_items = self._get_session_cart(session)

                # Extract index from session-{index} format
                if isinstance(item_id, str) and item_id.startswith('session-'):
                    try:
                        index = int(item_id.split('-')[1])
                        if 0 <= index < len(cart_items):
                            if quantity is not None:
                                cart_items[index]['quantity'] = quantity
                            
                            if price is not None:
                                cart_items[index]['price'] = price
                                
                            cart_items[index]['updated_at'] = datetime.now().isoformat()
                            
                            # Save to session
                            self._save_session_cart(session, cart_items)
                            
                            # Return updated item
                            item = cart_items[index].copy()
                            item['id'] = item_id
                            return item
                    except (ValueError, IndexError):
                        pass
                        
                logger.error(f"Session cart item not found: {item_id}")
                return None
                
        except Exception as e:
            logger.error(f"Error updating cart item: {str(e)}")
            raise
            
    def remove_from_cart(self, user_or_session, item_id):
        """
        Remove an item from cart by ID
        
        Args:
            user_or_session: User object or session object
            item_id: ID of the cart item
        """
        try:
            if self._is_authenticated_user(user_or_session):
                # Authenticated user - use database
                try:
                    cart_item = CartItem.objects.get(id=item_id)
                    cart_item.delete()
                    return True
                except CartItem.DoesNotExist:
                    logger.error(f"Cart item not found: {item_id}")
                    return False
            else:
                # Anonymous user - use session
                session = user_or_session
                cart_items = self._get_session_cart(session)
                
                # Extract index from session-{index} format
                if isinstance(item_id, str) and item_id.startswith('session-'):
                    try:
                        index = int(item_id.split('-')[1])
                        if 0 <= index < len(cart_items):
                            # Remove item
                            cart_items.pop(index)
                            
                            # Save to session
                            self._save_session_cart(session, cart_items)
                            return True
                    except (ValueError, IndexError):
                        pass
                        
                logger.error(f"Session cart item not found: {item_id}")
                return False
                
        except Exception as e:
            logger.error(f"Error removing from cart: {str(e)}")
            raise
    
    def remove_product_from_cart(self, user_or_session, product_id, variant_id=None):
        """
        Remove a product from cart
        
        Args:
            user_or_session: User object or session object
            product_id: ID of the product
            variant_id: Optional variant ID
        """
        try:
            if self._is_authenticated_user(user_or_session):
                # Authenticated user - use database
                filters = {
                    'customer_id': user_or_session.customer.id,
                    'product_id': product_id
                }
                if variant_id is not None:
                    filters['variant_id'] = variant_id
                    
                result = CartItem.objects.filter(**filters).delete()
                return result[0] > 0  # Return True if something was deleted
            else:
                # Anonymous user - use session
                session = user_or_session
                cart_items = self._get_session_cart(session)
                
                # Find all matching items
                new_cart = [item for item in cart_items if 
                           not (item['product_id'] == product_id and 
                                item.get('variant_id') == variant_id)]
                
                # Check if any items were removed
                if len(new_cart) < len(cart_items):
                    # Save to session
                    self._save_session_cart(session, new_cart)
                    return True
                    
                return False
                
        except Exception as e:
            logger.error(f"Error removing product from cart: {str(e)}")
            raise
    
    def update_cart(self, user_or_session, cart_items):
        """
        Bulk update cart
        
        Args:
            user_or_session: User object or session object
            cart_items: List of cart items to replace the current cart
        """
        try:
            if self._is_authenticated_user(user_or_session):
                # Authenticated user - use database
                customer = user_or_session.customer
                CartItem.objects.filter(customer=customer).delete()
    
                new_items = []
                for item in cart_items:
                    new_items.append(CartItem(customer=customer, **item))
    
                CartItem.objects.bulk_create(new_items)
                logger.info(f"Updated cart for customer: {customer.id}")
                return True
            else:
                # Anonymous user - use session
                session = user_or_session
                
                # Add timestamps to each item
                now = datetime.now().isoformat()
                for item in cart_items:
                    if 'added_at' not in item:
                        item['added_at'] = now
                    item['updated_at'] = now
                
                # Save to session
                self._save_session_cart(session, cart_items)
                logger.info("Updated session cart")
                return True
                
        except Exception as e:
            logger.error(f"Error updating cart: {str(e)}")
            raise
    
    def clear_cart(self, user_or_session):
        """
        Clear cart
        
        Args:
            user_or_session: User object or session object
        """
        try:
            if self._is_authenticated_user(user_or_session):
                # Authenticated user - use database
                result = CartItem.objects.filter(customer_id=user_or_session.customer.id).delete()
                logger.info(f"Cleared cart for customer: {user_or_session.customer.id}")
                return result[0] > 0  # Return True if something was deleted
            else:
                # Anonymous user - use session
                session = user_or_session
                
                # Check if cart exists
                if 'cart' in session:
                    # Clear cart
                    session['cart'] = []
                    session.modified = True
                    logger.info("Cleared session cart")
                    return True
                    
                return False
                
        except Exception as e:
            logger.error(f"Error clearing cart: {str(e)}")
            raise
    
    def get_cart_total(self, user_or_session):
        """
        Calculate cart total
        
        Args:
            user_or_session: User object or session object
        """
        try:
            if self._is_authenticated_user(user_or_session):
                # Authenticated user - use database
                cart_items = CartItem.objects.filter(customer_id=user_or_session.customer.id)
                total = sum(item.price * item.quantity for item in cart_items)
                return total
            else:
                # Anonymous user - use session
                session = user_or_session
                cart_items = self._get_session_cart(session)
                
                # Calculate total
                total = sum(item.get('price', 0) * item.get('quantity', 0) for item in cart_items)
                return total
                
        except Exception as e:
            logger.error(f"Error calculating cart total: {str(e)}")
            raise
    
    def get_cart_count(self, user_or_session):
        """
        Get count of items in cart
        
        Args:
            user_or_session: User object or session object
        """
        try:
            if self._is_authenticated_user(user_or_session):
                # Authenticated user - use database
                # Get sum of all quantities
                result = CartItem.objects.filter(customer_id=user_or_session.customer.id).aggregate(
                    total_items=models.Sum('quantity')
                )
                return result['total_items'] or 0
            else:
                # Anonymous user - use session
                session = user_or_session
                cart_items = self._get_session_cart(session)
                
                # Calculate total quantity
                return sum(item.get('quantity', 0) for item in cart_items)
                
        except Exception as e:
            logger.error(f"Error getting cart count: {str(e)}")
            raise

    def merge_carts(self, user, session):
        """
        Merge a session cart into a user's cart
        This is typically called after login if there are items in the session cart
        
        Args:
            user: User object with a customer profile
            session: Session object containing a session cart
        """
        try:
            # Don't merge if user doesn't have a customer profile
            if not hasattr(user, 'customer') or not user.customer:
                logger.warning("Cannot merge carts: User has no customer profile")
                return False
                
            # Get session cart
            session_cart = self._get_session_cart(session)
            
            # Skip if empty
            if not session_cart:
                return True
                
            # Process each item
            for item in session_cart:
                # Add to user's cart
                self.add_to_cart(
                    user,
                    product_id=item['product_id'],
                    quantity=item['quantity'],
                    variant_id=item.get('variant_id'),
                    price=item.get('price')
                )
                
            # Clear session cart
            session['cart'] = []
            session.modified = True
            
            logger.info(f"Merged session cart into customer cart for user: {user.id}")
            return True
            
        except Exception as e:
            logger.error(f"Error merging carts: {str(e)}")
            raise


class TransactionService:
    @transaction.atomic
    def create_transaction(self, customer_id, transaction_type, amount, transaction_id):
        """Create a new transaction"""
        try:
            customer = Customer.objects.get(id=customer_id)

            # Update wallet balance
            if transaction_type == "credit":
                customer.wallet_balance += amount
            elif transaction_type == "debit":
                if customer.wallet_balance < amount:
                    raise ValueError("Insufficient wallet balance")
                customer.wallet_balance -= amount

            customer.save()

            # Create transaction record
            transaction = CustomerTransaction.objects.create(
                customer=customer,
                transaction_type=transaction_type,
                amount=amount,
                transaction_id=transaction_id,
            )

            return transaction

        except Exception as e:
            logger.error(f"Error creating transaction: {str(e)}")
            raise

    def get_transactions(self, customer_id):
        """Get customer transactions"""
        return CustomerTransaction.objects.filter(customer_id=customer_id).order_by(
            "-created_at"
        )


class CustomerActivityService:
    def record_activity(self, customer_id, activity_type, details=None):
        """Record customer activity"""
        try:
            customer = Customer.objects.get(id=customer_id)
            activity = CustomerActivity.objects.create(
                customer=customer,
                interaction_type=activity_type,
                **details if details else {},
            )

            # Update last active timestamp
            customer.last_active = now()
            customer.save()

            return activity

        except Exception as e:
            logger.error(f"Error recording activity: {str(e)}")
            raise


class OrderStatsService:
    @transaction.atomic
    def update_stats(self, customer_id, order_value):
        """Update order statistics"""
        try:
            customer = Customer.objects.get(id=customer_id)
            stats, _ = CustomerOrderStats.objects.get_or_create(customer=customer)

            stats.total_orders += 1
            stats.total_order_value += order_value
            stats.last_order_date = now()
            stats.save()

            # Update customer totals
            customer.total_orders += 1
            customer.total_order_value += order_value
            customer.save()

            return stats

        except Exception as e:
            logger.error(f"Error updating order stats: {str(e)}")
            raise


class WishlistService:
    """
    Enhanced WishlistService that works for both authenticated and anonymous users
    - For authenticated users: uses database storage
    - For anonymous users: uses session storage
    """

    def _get_session_wishlist(self, session):
        """Helper to get the wishlist from session"""
        return session.get("wishlist", [])

    def _save_session_wishlist(self, session, wishlist_items):
        """Helper to save the wishlist to session"""
        session["wishlist"] = wishlist_items
        session.modified = True

    def _find_session_item(self, session_wishlist, product_id, variant_id=None):
        """Find an item in the session wishlist"""
        for index, item in enumerate(session_wishlist):
            if (
                item["product_id"] == product_id
                and item.get("variant_id") == variant_id
            ):
                return index
        return -1

    def _is_authenticated_user(self, user_or_session):
        """Check if we're dealing with an authenticated user or session"""
        # If it's a User model instance with a customer attribute
        return (
            hasattr(user_or_session, "customer")
            and user_or_session.customer is not None
        )

    def get_wishlist(self, user_or_session):
        """
        Get wishlist items for authenticated or anonymous user

        Args:
            user_or_session: User object or session object
        """
        try:
            if self._is_authenticated_user(user_or_session):
                # Authenticated user - use database
                return WishlistItem.objects.filter(
                    customer_id=user_or_session.customer.id
                ).order_by("-added_at")
            else:
                # Anonymous user - use session
                session_wishlist = self._get_session_wishlist(user_or_session)
                # Convert session wishlist to a format similar to WishlistItem model
                wishlist_items = []
                for i, item in enumerate(session_wishlist):
                    item["id"] = f"session-{i}"  # Add virtual ID
                    # Add missing fields that would be in the model
                    if "added_at" not in item:
                        item["added_at"] = datetime.now().isoformat()
                    wishlist_items.append(item)
                return wishlist_items

        except Exception as e:
            logger.error(f"Error retrieving wishlist items: {str(e)}")
            raise

    def add_to_wishlist(self, user_or_session, product_id, variant_id=None):
        """
        Add item to wishlist for authenticated or anonymous user

        Args:
            user_or_session: User object or session object
            product_id: ID of the product
            variant_id: Optional variant ID
        """
        try:
            if self._is_authenticated_user(user_or_session):
                # Authenticated user - use database
                customer = user_or_session.customer
                wishlist_item, created = WishlistItem.objects.get_or_create(
                    customer=customer, product_id=product_id, variant_id=variant_id
                )

                if created:
                    logger.info(f"Added item to wishlist for customer: {customer.id}")

                return wishlist_item
            else:
                # Anonymous user - use session
                session = user_or_session
                wishlist_items = self._get_session_wishlist(session)

                # Check if item already exists
                index = self._find_session_item(wishlist_items, product_id, variant_id)

                if index >= 0:
                    # Item already exists, no need to add again
                    item = wishlist_items[index]
                else:
                    # Add new item
                    item = {
                        "product_id": product_id,
                        "variant_id": variant_id,
                        "added_at": datetime.now().isoformat(),
                    }
                    wishlist_items.append(item)

                    # Save to session
                    self._save_session_wishlist(session, wishlist_items)
                    logger.info("Added item to session wishlist")

                # Add an ID for consistency with DB model
                item["id"] = (
                    f"session-{index if index >= 0 else len(wishlist_items) - 1}"
                )
                return item

        except Exception as e:
            logger.error(f"Error adding to wishlist: {str(e)}")
            raise

    def remove_from_wishlist(self, user_or_session, product_id, variant_id=None):
        """
        Remove an item from wishlist

        Args:
            user_or_session: User object or session object
            product_id: ID of the product
            variant_id: Optional variant ID
        """
        try:
            if self._is_authenticated_user(user_or_session):
                # Authenticated user - use database
                result = WishlistItem.objects.filter(
                    customer_id=user_or_session.customer.id,
                    product_id=product_id,
                    variant_id=variant_id,
                ).delete()

                logger.info(
                    f"Removed item from wishlist for customer: {user_or_session.customer.id}"
                )
                return result[0] > 0  # Return True if something was deleted
            else:
                # Anonymous user - use session
                session = user_or_session
                wishlist_items = self._get_session_wishlist(session)

                # Find all matching items
                index = self._find_session_item(wishlist_items, product_id, variant_id)

                if index >= 0:
                    # Remove item
                    wishlist_items.pop(index)

                    # Save to session
                    self._save_session_wishlist(session, wishlist_items)
                    logger.info("Removed item from session wishlist")
                    return True

                return False

        except Exception as e:
            logger.error(f"Error removing from wishlist: {str(e)}")
            raise

    def remove_item_by_id(self, user_or_session, item_id):
        """
        Remove an item from wishlist by ID

        Args:
            user_or_session: User object or session object
            item_id: ID of the wishlist item
        """
        try:
            if self._is_authenticated_user(user_or_session):
                # Authenticated user - use database
                try:
                    wishlist_item = WishlistItem.objects.get(id=item_id)
                    wishlist_item.delete()
                    return True
                except WishlistItem.DoesNotExist:
                    logger.error(f"Wishlist item not found: {item_id}")
                    return False
            else:
                # Anonymous user - use session
                session = user_or_session
                wishlist_items = self._get_session_wishlist(session)

                # Extract index from session-{index} format
                if isinstance(item_id, str) and item_id.startswith("session-"):
                    try:
                        index = int(item_id.split("-")[1])
                        if 0 <= index < len(wishlist_items):
                            # Remove item
                            wishlist_items.pop(index)

                            # Save to session
                            self._save_session_wishlist(session, wishlist_items)
                            return True
                    except (ValueError, IndexError):
                        pass

                logger.error(f"Session wishlist item not found: {item_id}")
                return False

        except Exception as e:
            logger.error(f"Error removing from wishlist: {str(e)}")
            raise

    def clear_wishlist(self, user_or_session):
        """
        Clear wishlist

        Args:
            user_or_session: User object or session object
        """
        try:
            if self._is_authenticated_user(user_or_session):
                # Authenticated user - use database
                result = WishlistItem.objects.filter(
                    customer_id=user_or_session.customer.id
                ).delete()
                logger.info(
                    f"Cleared wishlist for customer: {user_or_session.customer.id}"
                )
                return result[0] > 0  # Return True if something was deleted
            else:
                # Anonymous user - use session
                session = user_or_session

                # Check if wishlist exists
                if "wishlist" in session:
                    # Clear wishlist
                    session["wishlist"] = []
                    session.modified = True
                    logger.info("Cleared session wishlist")
                    return True

                return False

        except Exception as e:
            logger.error(f"Error clearing wishlist: {str(e)}")
            raise

    def is_in_wishlist(self, user_or_session, product_id, variant_id=None):
        """
        Check if an item is in the wishlist

        Args:
            user_or_session: User object or session object
            product_id: ID of the product
            variant_id: Optional variant ID
        """
        try:
            if self._is_authenticated_user(user_or_session):
                # Authenticated user - use database
                return WishlistItem.objects.filter(
                    customer_id=user_or_session.customer.id,
                    product_id=product_id,
                    variant_id=variant_id,
                ).exists()
            else:
                # Anonymous user - use session
                session = user_or_session
                wishlist_items = self._get_session_wishlist(session)

                # Check if item exists
                index = self._find_session_item(wishlist_items, product_id, variant_id)
                return index >= 0

        except Exception as e:
            logger.error(f"Error checking wishlist: {str(e)}")
            raise

    def get_wishlist_count(self, user_or_session):
        """
        Get count of items in wishlist

        Args:
            user_or_session: User object or session object
        """
        try:
            if self._is_authenticated_user(user_or_session):
                # Authenticated user - use database
                return WishlistItem.objects.filter(
                    customer_id=user_or_session.customer.id
                ).count()
            else:
                # Anonymous user - use session
                session = user_or_session
                wishlist_items = self._get_session_wishlist(session)
                return len(wishlist_items)

        except Exception as e:
            logger.error(f"Error getting wishlist count: {str(e)}")
            raise

    def merge_wishlists(self, user, session):
        """
        Merge a session wishlist into a user's wishlist
        This is typically called after login if there are items in the session wishlist

        Args:
            user: User object with a customer profile
            session: Session object containing a session wishlist
        """
        try:
            # Don't merge if user doesn't have a customer profile
            if not hasattr(user, "customer") or not user.customer:
                logger.warning("Cannot merge wishlists: User has no customer profile")
                return False

            # Get session wishlist
            session_wishlist = self._get_session_wishlist(session)

            # Skip if empty
            if not session_wishlist:
                return True

            # Process each item
            for item in session_wishlist:
                # Add to user's wishlist
                self.add_to_wishlist(
                    user,
                    product_id=item["product_id"],
                    variant_id=item.get("variant_id"),
                )

            # Clear session wishlist
            session["wishlist"] = []
            session.modified = True

            logger.info(
                f"Merged session wishlist into customer wishlist for user: {user.id}"
            )
            return True

        except Exception as e:
            logger.error(f"Error merging wishlists: {str(e)}")
            raise
