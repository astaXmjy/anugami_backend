import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from asgiref.sync import sync_to_async
from django.contrib.auth import get_user_model
from django.utils import timezone
import logging

# Import models from respective apps
from chat.models import ChatRoom, Message
from .models import UserStatus

User = get_user_model()
logger = logging.getLogger(__name__)


class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.room_id = self.scope["url_route"]["kwargs"]["room_id"]
        self.room_group_name = f"chat_{self.room_id}"

        # Add this channel to the group
        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        # Remove from group on disconnect
        await self.channel_layer.group_discard(self.room_group_name, self.channel_name)

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
            message = data.get("message", "")
            user_id = data.get("user_id")

            if not message.strip():
                await self.send(
                    text_data=json.dumps({"error": "Message cannot be empty"})
                )
                return

            # Handle admin user case
            if user_id == "admin":
                user = None
                user_name = "Admin"
                user_email = "admin@system"
                user_display_id = "admin"
            else:
                try:
                    user = await sync_to_async(User.objects.get)(id=user_id)

                    # Handle custom user model without get_full_name method
                    if hasattr(user, "get_full_name"):
                        user_name = user.get_full_name() or user.email
                    elif hasattr(user, "full_name"):
                        user_name = user.full_name or user.email
                    elif hasattr(user, "first_name") and hasattr(user, "last_name"):
                        user_name = (
                            f"{user.first_name} {user.last_name}".strip() or user.email
                        )
                    else:
                        user_name = user.email

                    user_email = user.email
                    user_display_id = str(user.id)
                except User.DoesNotExist:
                    await self.send(
                        text_data=json.dumps(
                            {"error": f"User with ID {user_id} not found"}
                        )
                    )
                    return

            # Get room and save message
            try:
                room = await sync_to_async(ChatRoom.objects.get)(id=self.room_id)

                # Create message with proper sender handling
                msg = await sync_to_async(Message.objects.create)(
                    chat_room=room,
                    sender=user,  # Can be None for admin
                    content=message,
                    message_type="text",
                )

                # Send message to group
                await self.channel_layer.group_send(
                    self.room_group_name,
                    {
                        "type": "chat_message",
                        "message": message,
                        "user": user_email,
                        "user_id": user_display_id,
                        "user_name": user_name,
                        "message_id": str(msg.id),
                        "created_at": msg.created_at.isoformat(),
                    },
                )

            except ChatRoom.DoesNotExist:
                await self.send(
                    text_data=json.dumps(
                        {"error": "Chat room not found", "room_id": self.room_id}
                    )
                )

            except Exception as e:
                logger.error(f"Error creating message: {e}")
                await self.send(
                    text_data=json.dumps(
                        {"error": "Failed to save message", "details": str(e)}
                    )
                )

        except json.JSONDecodeError:
            await self.send(text_data=json.dumps({"error": "Invalid JSON format"}))
        except Exception as e:
            logger.error(f"Unexpected error in receive: {e}")
            await self.send(
                text_data=json.dumps(
                    {"error": "An unexpected error occurred", "details": str(e)}
                )
            )

    async def chat_message(self, event):
        # Send message to WebSocket
        await self.send(text_data=json.dumps(event))


class NotificationConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        # For admin interface, we might want to allow non-authenticated connections
        # or handle authentication differently

        # Check if it's an admin connection (you can implement your own logic)
        user = self.scope.get("user")

        if user and user.is_authenticated:
            self.group_name = "notifications"
            self.user_group_name = f"user_notifications_{user.id}"
        else:
            # Allow admin panel connections without authentication
            self.group_name = "admin_notifications"
            self.user_group_name = None

        # Add this channel to the notification group
        await self.channel_layer.group_add(self.group_name, self.channel_name)

        if self.user_group_name:
            await self.channel_layer.group_add(self.user_group_name, self.channel_name)

        await self.accept()

    async def disconnect(self, close_code):
        # Remove from groups on disconnect
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

        if hasattr(self, "user_group_name") and self.user_group_name:
            await self.channel_layer.group_discard(
                self.user_group_name, self.channel_name
            )

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
            message_type = data.get("type")

            if message_type == "ping":
                await self.send(
                    text_data=json.dumps(
                        {"type": "pong", "timestamp": timezone.now().isoformat()}
                    )
                )

        except json.JSONDecodeError:
            await self.send(text_data=json.dumps({"error": "Invalid JSON format"}))
        except Exception as e:
            logger.error(f"Error in notification consumer: {e}")

    async def send_notification(self, event):
        # Send notification to WebSocket
        await self.send(text_data=json.dumps(event))

    async def send_admin_notification(self, event):
        # Send admin-specific notifications
        await self.send(text_data=json.dumps(event))


class UserStatusConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        # Get the current user
        self.user = self.scope.get("user")

        # For admin panel, allow connections without authentication
        if not self.user or not self.user.is_authenticated:
            # Create a guest connection for admin monitoring
            self.group_name = "admin_status_monitor"
            self.user = None
        else:
            # Regular user connection
            await self.update_user_status(is_online=True)
            self.group_name = f"user_{self.user.id}"

        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        # Update user status to offline if it's a real user
        if self.user and self.user.is_authenticated:
            await self.update_user_status(is_online=False)

        # Remove user from group
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
            message_type = data.get("type")

            if message_type == "update_activity" and self.user:
                await self.update_user_status(last_activity=True)

            elif message_type == "ping":
                await self.send(
                    text_data=json.dumps(
                        {
                            "type": "pong",
                            "timestamp": timezone.now().isoformat(),
                            "user_id": str(self.user.id) if self.user else "admin",
                        }
                    )
                )

            elif message_type == "get_status" and self.user:
                status = await self.get_user_status()
                await self.send(
                    text_data=json.dumps(
                        {
                            "type": "status_update",
                            "user_id": str(self.user.id),
                            "is_online": status.get("is_online", False),
                            "last_seen": status.get("last_seen"),
                            "last_activity": status.get("last_activity"),
                        }
                    )
                )

        except json.JSONDecodeError:
            await self.send(text_data=json.dumps({"error": "Invalid JSON format"}))
        except Exception as e:
            logger.error(f"Error in status consumer: {e}")

    @database_sync_to_async
    def update_user_status(self, is_online=None, last_activity=False):
        """
        Update user's online status and last activity
        """
        if not self.user or not self.user.is_authenticated:
            return None

        try:
            status_obj, created = UserStatus.objects.get_or_create(
                user=self.user,
                defaults={
                    "is_online": is_online if is_online is not None else False,
                    "last_seen": timezone.now(),
                    "last_activity": timezone.now(),
                },
            )

            if not created:
                if is_online is not None:
                    status_obj.is_online = is_online

                if last_activity:
                    status_obj.last_activity = timezone.now()

                status_obj.last_seen = timezone.now()
                status_obj.save()

            return status_obj
        except Exception as e:
            logger.error(f"Error updating user status: {e}")
            return None

    @database_sync_to_async
    def get_user_status(self):
        """
        Get current user status
        """
        if not self.user or not self.user.is_authenticated:
            return {}

        try:
            status_obj = UserStatus.objects.get(user=self.user)
            return {
                "is_online": status_obj.is_online,
                "last_seen": (
                    status_obj.last_seen.isoformat() if status_obj.last_seen else None
                ),
                "last_activity": (
                    status_obj.last_activity.isoformat()
                    if status_obj.last_activity
                    else None
                ),
            }
        except UserStatus.DoesNotExist:
            return {"is_online": False, "last_seen": None, "last_activity": None}
        except Exception as e:
            logger.error(f"Error getting user status: {e}")
            return {}

    async def send_personal_notification(self, event):
        """
        Send a personal notification to the user
        """
        await self.send(
            text_data=json.dumps(
                {
                    "type": "notification",
                    "message": event["message"],
                    "timestamp": timezone.now().isoformat(),
                }
            )
        )

    async def broadcast_status_update(self, event):
        """
        Broadcast status updates to connected clients
        """
        await self.send(text_data=json.dumps(event))
