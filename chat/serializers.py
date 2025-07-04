from rest_framework import serializers
from .models import ChatRoom, Message, UserChatStatus
from system_users.serializers import UserDetailSerializer
from .models import UserStatus

class MessageSerializer(serializers.ModelSerializer):
    sender = UserDetailSerializer(read_only=True)
    read_by = UserDetailSerializer(many=True, read_only=True)

    class Meta:
        model = Message
        fields = [
            "id",
            "chat_room",
            "sender",
            "content",
            "message_type",
            "file_url",
            "read_by",
            "created_at",
            "is_deleted",
        ]
        read_only_fields = ["id", "created_at"]


class ChatRoomListSerializer(serializers.ModelSerializer):
    last_message = MessageSerializer(read_only=True)
    participants = UserDetailSerializer(many=True, read_only=True)
    unread_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = ChatRoom
        fields = [
            "id",
            "name",
            "room_type",
            "participants",
            "last_message",
            "unread_count",
            "updated_at",
        ]


class ChatRoomDetailSerializer(ChatRoomListSerializer):
    messages = MessageSerializer(many=True, read_only=True)

    class Meta(ChatRoomListSerializer.Meta):
        fields = ChatRoomListSerializer.Meta.fields + ["messages", "created_by"]


class ChatRoomCreateSerializer(serializers.ModelSerializer):
    participant_ids = serializers.ListField(
        child=serializers.UUIDField(), write_only=True
    )

    class Meta:
        model = ChatRoom
        fields = ["name", "room_type", "participant_ids"]

    def create(self, validated_data):
        participant_ids = validated_data.pop("participant_ids")
        validated_data["participants"] = participant_ids
        return super().create(validated_data)


class UserChatStatusSerializer(serializers.ModelSerializer):
    user = UserDetailSerializer(read_only=True)

    class Meta:
        model = UserChatStatus
        fields = ["user", "is_online", "last_seen", "current_room"]
        read_only_fields = ["last_seen"]

class UserStatusSerializer(serializers.ModelSerializer):
    """
    Serializer for User Online Status
    """
    class Meta:
        model = UserStatus
        fields = ['is_online', 'last_seen', 'last_activity']
        read_only_fields = ['last_seen']