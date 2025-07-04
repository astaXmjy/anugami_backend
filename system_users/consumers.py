import json
from channels.generic.websocket import AsyncWebsocketConsumer
from django.contrib.auth import get_user_model

User = get_user_model()

class UserStatusConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        # Reject connection if user is not authenticated
        if not self.scope["user"].is_authenticated:
            await self.close()
            return

        # Get the current user
        self.user = self.scope["user"]
        
        # Add user to a personal group
        self.group_name = f"user_{self.user.id}"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        
        await self.accept()

    async def disconnect(self, close_code):
        # Remove user from group on disconnect
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive(self, text_data):
        # Handle incoming WebSocket messages
        try:
            data = json.loads(text_data)
            # Add any specific message handling logic here
            print(f"Received message: {data}")
        except json.JSONDecodeError:
            print("Invalid JSON received")

    async def send_personal_notification(self, event):
        """
        Send a personal notification to the user
        """
        await self.send(text_data=json.dumps({
            'type': 'notification',
            'message': event['message']
        }))