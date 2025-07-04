import os
import uuid
import logging
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from django.core.files.uploadedfile import InMemoryUploadedFile

from rest_framework import viewsets, status, permissions
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.decorators import action

import firebase_admin
from firebase_admin import credentials, firestore

from .models import FirestoreMedia, FirestoreProductImage
from .serializers import (
    FirestoreMediaSerializer, 
    FirestoreProductImageSerializer,
    MediaUploadSerializer
)
from .media_validators import validate_file_size, validate_image_type, validate_video_type
from .image_utils import ImageOptimizer

logger = logging.getLogger(__name__)

class FirestoreMediaManager:
    """Handles Firestore media operations"""
    
    def __init__(self):
        if not firebase_admin._apps:
            try:
                cred_path = getattr(settings, 'FIREBASE_CREDENTIALS_PATH', None)
                if not cred_path:
                    raise ValueError("Firebase credentials path not set")
                
                cred = credentials.Certificate(cred_path)
                firebase_admin.initialize_app(cred)
            except Exception as e:
                logger.error(f"Firebase initialization error: {str(e)}")
                raise
        
        self.db = firestore.client()
        self.media_collection = self.db.collection('media_files')
        self.image_optimizer = ImageOptimizer()

    def _generate_unique_filename(self, original_filename):
        """Generate unique filename with preserved extension"""
        ext = os.path.splitext(original_filename)[1].lower()
        return f"{uuid.uuid4()}{ext}"

    def upload_file(self, file, user_id=None, directory='uploads/'):
        """Upload file metadata to Firestore with optimization for images"""
        try:
            # Validate file size
            validate_file_size(file)
            
            content_type = file.content_type
            optimized_file = None
            thumbnail = None
            
            # Handle image optimization
            if content_type.startswith('image/'):
                validate_image_type(file)
                optimized_file, content_type = self.image_optimizer.optimize_image(file)
                thumbnail = self.image_optimizer.create_thumbnail(file)
            elif content_type.startswith('video/'):
                validate_video_type(file)
            
            # Generate unique filenames
            unique_filename = self._generate_unique_filename(file.name)
            storage_path = f"{directory}{unique_filename}"
            thumbnail_path = None
            
            if thumbnail:
                thumbnail_filename = f"thumbnails/{unique_filename}"
                thumbnail_path = f"{directory}{thumbnail_filename}"
            
            # Prepare metadata
            file_metadata = {
                'filename': unique_filename,
                'original_name': file.name,
                'content_type': content_type,
                'size': optimized_file.tell() if optimized_file else file.size,
                'storage_path': storage_path,
                'thumbnail_path': thumbnail_path,
                'uploaded_at': firestore.SERVER_TIMESTAMP,
                'user_id': user_id,
                'directory': directory
            }
            
            # Add to Firestore
            doc_ref = self.media_collection.document()
            doc_ref.set(file_metadata)
            
            # Add document ID to metadata
            file_metadata['id'] = doc_ref.id
            
            return file_metadata
            
        except ValidationError as ve:
            logger.error(f"File validation error: {str(ve)}")
            raise
        except Exception as e:
            logger.error(f"File upload failed: {str(e)}")
            raise

    def delete_file(self, file_id):
        """Delete file metadata from Firestore"""
        try:
            self.media_collection.document(file_id).delete()
        except Exception as e:
            logger.error(f"File deletion failed: {str(e)}")
            raise

class MediaViewSet(viewsets.ModelViewSet):
    queryset = FirestoreMedia.objects.all()
    serializer_class = FirestoreMediaSerializer
    parser_classes = [MultiPartParser, FormParser]
    permission_classes = [permissions.IsAuthenticated]
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.media_manager = FirestoreMediaManager()

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        """Handle file upload with optimization"""
        try:
            file = request.FILES.get('file')
            if not file:
                return Response(
                    {'error': 'No file provided'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Determine directory based on content type
            directory = 'uploads/'
            if file.content_type.startswith('image/'):
                directory = 'images/'
            elif file.content_type.startswith('video/'):
                directory = 'videos/'

            # Upload to Firestore
            file_metadata = self.media_manager.upload_file(
                file,
                user_id=str(request.user.id),
                directory=directory
            )

            # Create database record
            media = FirestoreMedia.objects.create(
                firestore_id=file_metadata['id'],
                original_name=file_metadata['original_name'],
                storage_path=file_metadata['storage_path'],
                content_type=file_metadata['content_type'],
                size=file_metadata['size'],
                directory=file_metadata['directory'],
                user=request.user,
                thumbnail_path=file_metadata.get('thumbnail_path')
            )

            # Handle product association if specified
            product_id = request.data.get('product_id')
            is_primary = request.data.get('is_primary', False)

            if product_id:
                FirestoreProductImage.objects.create(
                    product_id=product_id,
                    media=media,
                    is_primary=is_primary,
                    position=FirestoreProductImage.objects.filter(product_id=product_id).count()
                )

            serializer = self.get_serializer(media)
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        except ValidationError as ve:
            return Response(
                {'error': str(ve)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.error(f"Upload failed: {str(e)}")
            return Response(
                {'error': 'Upload failed'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @transaction.atomic
    def destroy(self, request, *args, **kwargs):
        """Handle file deletion from both Firestore and database"""
        instance = self.get_object()
        try:
            # Delete from Firestore
            self.media_manager.delete_file(instance.firestore_id)
            
            # Delete from database
            instance.delete()
            
            return Response(status=status.HTTP_204_NO_CONTENT)
        except Exception as e:
            logger.error(f"Deletion failed: {str(e)}")
            return Response(
                {'error': 'Deletion failed'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=True, methods=['post'])
    def attach_to_product(self, request, pk=None):
        """Attach media to a product"""
        media = self.get_object()
        try:
            product_id = request.data.get('product_id')
            is_primary = request.data.get('is_primary', False)
            position = request.data.get('position', None)

            if not product_id:
                return Response(
                    {'error': 'product_id is required'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Get current max position if not specified
            if position is None:
                position = FirestoreProductImage.objects.filter(product_id=product_id).count()

            # Create product image association
            FirestoreProductImage.objects.create(
                product_id=product_id,
                media=media,
                is_primary=is_primary,
                position=position
            )

            return Response({'status': 'attached to product'})

        except Exception as e:
            logger.error(f"Failed to attach to product: {str(e)}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=True, methods=['get'])
    def products(self, request, pk=None):
        """Get all products associated with this media"""
        media = self.get_object()
        product_images = media.product_images.all().select_related('product')
        data = [{
            'product_id': pi.product.id,
            'product_name': pi.product.name,
            'is_primary': pi.is_primary,
            'position': pi.position
        } for pi in product_images]
        return Response(data)