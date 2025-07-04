from django.urls import path
from . import consumers

websocket_urlpatterns = [
    # Add 'chats/' prefix to match your frontend URLs
    path('chats/ws/chat/<str:room_id>/', consumers.ChatConsumer.as_asgi()),
    path('chats/ws/notifications/', consumers.NotificationConsumer.as_asgi()),
    path('chats/ws/status/', consumers.UserStatusConsumer.as_asgi()),
]