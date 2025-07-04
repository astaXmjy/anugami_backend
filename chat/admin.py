from django.contrib import admin
from .models import ChatRoom, Message, UserStatus

@admin.register(ChatRoom)
class ChatRoomAdmin(admin.ModelAdmin):
    list_display = ('name', 'room_type', 'created_by', 'is_active', 'created_at', 'updated_at')
    list_filter = ('room_type', 'is_active', 'created_at')
    search_fields = ('name', 'created_by__email')
    readonly_fields = ('id', 'created_at', 'updated_at')
    
    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related('participants')

@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ('id', 'chat_room', 'sender', 'message_type', 'created_at', 'is_deleted')
    list_filter = ('message_type', 'created_at', 'is_deleted')
    search_fields = ('content', 'sender__email', 'chat_room__name')
    readonly_fields = ('id', 'created_at', 'updated_at')

@admin.register(UserStatus)
class UserStatusAdmin(admin.ModelAdmin):
    list_display = ('user', 'is_online', 'last_seen', 'last_activity')
    list_filter = ('is_online',)
    search_fields = ('user__email',)
    readonly_fields = ('last_seen', 'last_activity')