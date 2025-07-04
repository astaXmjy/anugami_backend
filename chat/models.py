from django.db import models
import uuid
from django.utils import timezone
from django.conf import settings


class ChatRoom(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(
        max_length=255, blank=True, null=True
    )  # Optional for private chats
    room_type = models.CharField(
        max_length=10,
        choices=[("private", "Private"), ("group", "Group")],
        default="private",
    )
    participants = models.ManyToManyField(
        settings.AUTH_USER_MODEL, related_name="chat_rooms"
    )  # Store user IDs as many-to-many relationships
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="created_chat_rooms",
        on_delete=models.CASCADE,
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(default=timezone.now)
    last_message = models.ForeignKey(
        "Message",
        related_name="last_message_in_chat",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )

    class Meta:
        db_table = "chat_rooms"
        indexes = [
            models.Index(fields=["-updated_at"]),
        ]


class Message(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    chat_room = models.ForeignKey(
        ChatRoom, related_name="messages", on_delete=models.CASCADE
    )
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="sent_messages",
        on_delete=models.CASCADE,
        null=True,  # Allow null for admin/system messages
        blank=True,
    )  # Store sender's user ID
    content = models.TextField()
    message_type = models.CharField(
        max_length=10,
        choices=[
            ("text", "Text"),
            ("image", "Image"),
            ("file", "File"),
            ("system", "System"),
        ],
        default="text",
    )
    file_url = models.URLField(blank=True, null=True)
    read_by = models.ManyToManyField(
        settings.AUTH_USER_MODEL, related_name="read_messages"
    )  # Store read users' IDs
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(default=timezone.now)
    is_deleted = models.BooleanField(default=False)

    class Meta:
        db_table = "messages"
        indexes = [
            models.Index(fields=["chat_room", "-created_at"]),
            models.Index(fields=["sender"]),
        ]


class UserChatStatus(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, related_name="chat_status", on_delete=models.CASCADE
    )  # Store user ID as string
    is_online = models.BooleanField(default=False)
    last_seen = models.DateTimeField(default=timezone.now)
    current_room = models.ForeignKey(
        ChatRoom,
        related_name="user_chat_statuses",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )

    class Meta:
        db_table = "user_chat_status"
        indexes = [models.Index(fields=["user"]), models.Index(fields=["last_seen"])]


class UserStatus(models.Model):
    """
    Track user online/offline status and last activity
    """

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="online_status"
    )
    is_online = models.BooleanField(default=False)
    last_seen = models.DateTimeField(default=timezone.now)
    last_activity = models.DateTimeField(default=timezone.now)

    # Optional: Track current active session
    current_session_key = models.CharField(max_length=40, null=True, blank=True)

    def __str__(self):
        return f"{self.user.email} - {'Online' if self.is_online else 'Offline'}"

    class Meta:
        verbose_name_plural = "User Statuses"
        ordering = ["-last_seen"]
