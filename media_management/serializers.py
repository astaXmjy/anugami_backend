from rest_framework import serializers
from .models import FirestoreMedia, FirestoreProductImage

class FirestoreMediaSerializer(serializers.ModelSerializer):
    file_size_display = serializers.CharField(read_only=True)
    
    class Meta:
        model = FirestoreMedia
        fields = [
            'id',
            'firestore_id',
            'original_name',
            'storage_path',
            'thumbnail_path',
            'content_type',
            'size',
            'file_size_display',
            'directory',
            'user',
            'created_at',
            'updated_at'
        ]
        read_only_fields = fields

class FirestoreProductImageSerializer(serializers.ModelSerializer):
    media = FirestoreMediaSerializer(read_only=True)
    
    class Meta:
        model = FirestoreProductImage
        fields = ['id', 'product', 'media', 'is_primary', 'position']
        read_only_fields = ['id']

class MediaUploadSerializer(serializers.Serializer):
    file = serializers.FileField(required=True)
    product_id = serializers.IntegerField(required=False)
    is_primary = serializers.BooleanField(default=False, required=False)
    
    def validate_file(self, value):
        from .media_validators import validate_file_size
        validate_file_size(value)
        return value