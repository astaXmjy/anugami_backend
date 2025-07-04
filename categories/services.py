# categories/services.py
from typing import Optional, Tuple, BinaryIO, Dict
from PIL import Image
from io import BytesIO
import logging
from django.utils.text import slugify
from django.core.cache import cache
import firebase_admin
from firebase_admin import storage
import uuid
from datetime import datetime

logger = logging.getLogger(__name__)

class ImageOptimizer:
    """Service for optimizing category images"""
    
    SIZES = {
        'thumbnail': (150, 150),    # For admin/list views
        'medium': (300, 300),       # For category cards
        'large': (800, 600)         # For category banners
    }

    def optimize_image(
        self, 
        image_file: BinaryIO,
        size_preset: str = 'medium',
        quality: int = 85
    ) -> Tuple[BytesIO, Dict[str, int]]:
        """
        Optimize image for web use
        Returns: (optimized_image, metadata)
        """
        img = Image.open(image_file)
        original_format = img.format or 'JPEG'
        
        # Convert RGBA to RGB if necessary
        if img.mode in ('RGBA', 'P'):
            img = img.convert('RGB')
        
        # Get target size
        target_size = self.SIZES.get(size_preset, self.SIZES['medium'])
        
        # Calculate new dimensions maintaining aspect ratio
        original_width, original_height = img.size
        ratio = min(target_size[0]/original_width, target_size[1]/original_height)
        new_size = (int(original_width * ratio), int(original_height * ratio))
        
        # Resize using high-quality resampling
        img = img.resize(new_size, Image.Resampling.LANCZOS)
        
        # Prepare output
        output = BytesIO()
        
        # Save with optimization
        img.save(
            output, 
            format='JPEG',
            quality=quality,
            optimize=True,
            progressive=True
        )
        
        # Get file size
        output.seek(0, 2)  # Go to end of file
        file_size = output.tell()  # Get size in bytes
        output.seek(0)  # Reset to beginning
        
        metadata = {
            'width': new_size[0],
            'height': new_size[1],
            'original_width': original_width,
            'original_height': original_height,
            'file_size': file_size,
            'format': 'jpeg'
        }
        
        return output, metadata

class FirebaseStorageService:
    """Service for handling Firebase Storage operations"""
    
    def __init__(self):
        self.bucket = storage.bucket()
        self.image_optimizer = ImageOptimizer()
    
    def upload_category_image(
        self, 
        category_id: str, 
        image_file: BinaryIO,
        size_preset: str = 'medium'
    ) -> Optional[Dict[str, str]]:
        """
        Upload optimized category image to Firebase Storage
        Returns URLs for different sizes if successful
        """
        try:
            # Optimize image
            optimized_image, metadata = self.image_optimizer.optimize_image(
                image_file,
                size_preset=size_preset
            )
            
            # Generate unique filename
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"categories/{category_id}/{size_preset}_{timestamp}.jpg"
            
            # Upload to Firebase
            blob = self.bucket.blob(filename)
            blob.content_type = 'image/jpeg'
            blob.metadata = metadata
            
            # Upload optimized image
            blob.upload_from_file(
                optimized_image,
                content_type='image/jpeg'
            )
            
            # Make public and get URL
            blob.make_public()
            
            return {
                'url': blob.public_url,
                'metadata': metadata,
                'path': filename
            }
            
        except Exception as e:
            logger.error(f"Failed to upload category image: {str(e)}")
            return None

    def delete_image(self, image_path: str) -> bool:
        """Delete image from Firebase Storage"""
        try:
            blob = self.bucket.blob(image_path)
            blob.delete()
            return True
        except Exception as e:
            logger.error(f"Failed to delete image: {str(e)}")
            return False

class CategoryService:
    """Core service for category management"""
    CACHE_PREFIX = "category:"
    CACHE_TIMEOUT = 3600  # 1 hour
    
    def __init__(self):
        self.storage_service = FirebaseStorageService()
    
    def generate_unique_slug(self, name: str, parent_slug: Optional[str] = None) -> str:
        """Generate SEO-friendly unique slug for category"""
        # Base slug from name
        base_slug = slugify(name)
        
        # Add parent slug if exists
        if parent_slug:
            base_slug = f"{parent_slug}-{base_slug}"
        
        # Initially try without number
        slug = base_slug
        counter = 1
        
        # Keep trying until we find a unique slug
        while self.slug_exists(slug):
            slug = f"{base_slug}-{counter}"
            counter += 1
        
        return slug

    def slug_exists(self, slug: str) -> bool:
        """Check if slug already exists in database"""
        from .models import Category  # Import here to avoid circular import
        return Category.objects.filter(slug=slug).exists()
    
    def handle_category_image(
        self,
        category_id: str,
        image_file: BinaryIO,
        size_preset: str = 'medium'
    ) -> Optional[Dict[str, str]]:
        """Handle category image upload with optimization"""
        return self.storage_service.upload_category_image(
            category_id,
            image_file,
            size_preset
        )

    def delete_category_image(self, image_path: str) -> bool:
        """Delete category image"""
        return self.storage_service.delete_image(image_path)

    def generate_meta_description(self, category_name: str, description: str) -> str:
        """Generate SEO meta description"""
        if description:
            # Clean and truncate description
            clean_desc = ' '.join(description.split())
            return clean_desc[:160]  # Standard meta description length
        return f"Explore our {category_name} collection."