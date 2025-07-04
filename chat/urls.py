from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views
from . import consumers

app_name = "chat"

# REST API routes
router = DefaultRouter()
router.register(r"rooms", views.ChatRoomViewSet, basename="chatroom")
router.register(r"status", views.UserChatStatusViewSet, basename="chatstatus")

urlpatterns = [
    # REST API endpoints
    path(
        "api/",
        include(
            [
                path("", include(router.urls)),
                path(
                    "rooms/<uuid:room_id>/messages/",
                    views.ChatRoomViewSet.as_view({"get": "messages"}),
                    name="room-messages",
                ),
                path(
                    "rooms/<uuid:room_id>/mark-read/",
                    views.ChatRoomViewSet.as_view({"post": "mark_read"}),
                    name="mark-messages-read",
                ),
            ]
        ),
    ),
    # WebSocket endpoints
    path("ws/chat/<str:room_name>/", consumers.ChatConsumer.as_asgi()),
    path("ws/notifications/", consumers.NotificationConsumer.as_asgi()),
]

# WebSocket URL patterns
websocket_urlpatterns = [
    path("ws/chat/<str:room_name>/", consumers.ChatConsumer.as_asgi()),
    path("ws/notifications/", consumers.NotificationConsumer.as_asgi()),
]
