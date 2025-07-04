from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Count, Q
from .models import ChatRoom, Message, UserChatStatus, UserStatus
from .serializers import (
    ChatRoomListSerializer,
    ChatRoomDetailSerializer,
    ChatRoomCreateSerializer,
    MessageSerializer,
    UserChatStatusSerializer,
    UserStatusSerializer
)


class ChatRoomViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return ChatRoom.objects.filter(participants=self.request.user).order_by(
            "-updated_at"
        )

    def get_serializer_class(self):
        if self.action == "create":
            return ChatRoomCreateSerializer
        if self.action in ["retrieve", "messages"]:
            return ChatRoomDetailSerializer
        return ChatRoomListSerializer

    def perform_create(self, serializer):
        serializer.save(
            created_by=self.request.user,
            participants=[
                self.request.user,
                *serializer.validated_data["participant_ids"],
            ],
        )

    @action(detail=True, methods=["get"])
    def messages(self, request, pk=None):
        room = self.get_object()
        messages = Message.objects.filter(chat_room=room).order_by("-created_at")

        page = self.paginate_queryset(messages)
        if page is not None:
            serializer = MessageSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = MessageSerializer(messages, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    def mark_read(self, request, pk=None):
        room = self.get_object()
        Message.objects.filter(chat_room=room, read_by__ne=request.user).update(
            push__read_by=request.user
        )
        return Response(status=status.HTTP_200_OK)


class UserChatStatusViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = UserChatStatusSerializer

    def get_queryset(self):
        return UserChatStatus.objects.filter(
            user__in=ChatRoom.objects.filter(
                participants=self.request.user
            ).values_list("participants", flat=True)
        )

    @action(detail=False, methods=["patch"])
    def set_status(self, request):
        status_obj, _ = UserChatStatus.objects.get_or_create(user=request.user)
        serializer = self.get_serializer(status_obj, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

class UserStatusViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing user online status
    """
    queryset = UserStatus.objects.all()
    serializer_class = UserStatusSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        # Only allow users to see their own status or admin to see all
        if self.request.user.is_staff or self.request.user.is_superuser:
            return UserStatus.objects.all()
        return UserStatus.objects.filter(user=self.request.user)

    @action(detail=False, methods=['patch', 'post'])
    def update_status(self, request):
        """
        Update user's online status
        """
        status_obj, created = UserStatus.objects.get_or_create(
            user=request.user,
            defaults={'is_online': True}
        )

        serializer = self.get_serializer(status_obj, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def my_status(self, request):
        """
        Retrieve current user's status
        """
        status_obj, _ = UserStatus.objects.get_or_create(user=request.user)
        serializer = self.get_serializer(status_obj)
        return Response(serializer.data)