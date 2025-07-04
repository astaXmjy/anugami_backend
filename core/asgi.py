import os
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from django.urls import path

# Import websocket URL patterns from your apps
import system_users.routing
import chat.routing

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")

# Combine websocket URL patterns from different apps
websocket_urlpatterns = (
    system_users.routing.websocket_urlpatterns + chat.routing.websocket_urlpatterns
)

application = ProtocolTypeRouter(
    {
        "http": get_asgi_application(),
        "websocket": AuthMiddlewareStack(URLRouter(websocket_urlpatterns)),
    }
)
