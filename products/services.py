# products/services.py
"""
Services for handling product-related functionality such as file uploads.
"""

import os
import uuid
import logging
from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils.text import slugify
from firebase_admin import storage
import re
from PIL import Image
from io import BytesIO
import magic

# Set up logging
logger = logging.getLogger(__name__)

import os
import uuid
import time
import logging
from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils.text import slugify
from firebase_admin import storage
import re
from PIL import Image
from io import BytesIO
import magic

# Set up logging
logger = logging.getLogger(__name__)


class ImageService:
    """Service for handling product image uploads and management."""

    def __init__(self):
        """Initialize the image service."""
        self.bucket = storage.bucket()

    def optimize_image(self, image_file, max_width=1200):
        """Optimize image for storage"""
        try:
            img = Image.open(image_file)

            # Convert RGBA to RGB if necessary
            if img.mode in ("RGBA", "LA"):
                background = Image.new("RGB", img.size, (255, 255, 255))
                background.paste(img, mask=img.split()[-1])
                img = background

            # Resize if too large
            if img.width > max_width:
                ratio = max_width / img.width
                height = int(img.height * ratio)
                img = img.resize((max_width, height), Image.Resampling.LANCZOS)

            # Optimize
            output = BytesIO()
            img.save(output, format="JPEG", quality=85, optimize=True)
            output.seek(0)
            return output
        except Exception as e:
            logger.error(f"Image optimization error: {str(e)}")
            # Return the original file if optimization fails
            image_file.seek(0)
            return image_file

    def upload_image(self, image_file, product_id, product_name=None):
        """
        Upload product image to Firebase Storage.

        Args:
            image_file: The image file object
            product_id: ID of the product
            product_name: Name of the product (for generating readable path)

        Returns:
            tuple: (storage_path, public_url)
        """
        try:
            # Validate file type
            image_file.seek(0)
            mime_type = magic.from_buffer(image_file.read(1024), mime=True)
            image_file.seek(0)

            ALLOWED_IMAGE_TYPES = ["image/jpeg", "image/png", "image/gif", "image/webp"]
            if mime_type not in ALLOWED_IMAGE_TYPES:
                raise ValidationError(
                    f"Invalid file type. Allowed types: {', '.join(ALLOWED_IMAGE_TYPES)}"
                )

            # Optimize image
            optimized = self.optimize_image(image_file)

            # Sanitize product name to avoid invalid characters in Firebase paths
            sanitized_product_name = re.sub(
                r"[^a-zA-Z0-9_]", "_", product_name if product_name else ""
            )

            # Get original filename if available
            original_filename = ""
            if hasattr(image_file, "name"):
                original_filename = os.path.splitext(image_file.name)[0]
                original_filename = re.sub(r"[^a-zA-Z0-9_]", "_", original_filename)

            # Generate a truly unique filename using:
            # 1. UUID for randomness
            # 2. Current timestamp for uniqueness
            # 3. Original filename (if available)
            unique_id = uuid.uuid4().hex[:8]  # Use first 8 chars of UUID
            timestamp = int(time.time())

            # Create the final unique filename
            filename = f"products/{product_id}/{sanitized_product_name}_{timestamp}_{unique_id}"

            # Add original filename if available
            if original_filename:
                filename = f"{filename}_{original_filename}"

            # Add file extension
            filename = f"{filename}.jpg"

            # Log the generated filename
            logger.info(f"Generating unique filename: {filename}")

            # Upload to Firebase
            blob = self.bucket.blob(filename)
            blob.upload_from_file(optimized, content_type="image/jpeg")

            # Make the blob publicly accessible
            blob.make_public()

            # Return the storage path and public URL
            logger.info(f"Image uploaded successfully: {filename}")
            return filename, blob.public_url

        except ValidationError as validation_error:
            # Re-raise validation errors
            logger.error(f"Validation error: {str(validation_error)}")
            raise
        except Exception as e:
            logger.error(f"Error uploading image: {str(e)}")
            raise ValidationError(f"Failed to upload image: {str(e)}")

    def delete_image(self, storage_path):
        """
        Delete an image from Firebase Storage.

        Args:
            storage_path: Path to the image in storage

        Returns:
            bool: True if deletion was successful
        """
        try:
            if not storage_path:
                logger.warning("Cannot delete image with empty storage path")
                return False

            blob = self.bucket.blob(storage_path)
            if blob.exists():
                blob.delete()
                logger.info(f"Image deleted successfully: {storage_path}")
                return True
            else:
                logger.warning(f"Image not found: {storage_path}")
                return False

        except Exception as e:
            logger.error(f"Error deleting image: {str(e)}")
            return False


class VideoService:
    """Service for handling product video uploads and management."""

    def __init__(self):
        """Initialize the video service."""
        self.bucket = storage.bucket()

    def upload_video(self, video_file, product_id):
        """
        Upload product video to Firebase Storage.

        Args:
            video_file: The video file object
            product_id: ID of the product

        Returns:
            tuple: (storage_path, public_url)
        """
        try:
            # Validate file type
            mime_type = magic.from_buffer(video_file.read(1024), mime=True)
            video_file.seek(0)

            ALLOWED_VIDEO_TYPES = ["video/mp4", "video/mpeg", "video/quicktime"]
            MAX_UPLOAD_SIZE = 10 * 1024 * 1024  # 10MB

            if mime_type not in ALLOWED_VIDEO_TYPES:
                raise ValidationError(
                    f"Invalid video type. Allowed types: {', '.join(ALLOWED_VIDEO_TYPES)}"
                )

            if video_file.size > MAX_UPLOAD_SIZE:
                raise ValidationError(
                    f"Video size cannot exceed {MAX_UPLOAD_SIZE/1024/1024}MB"
                )

            # Generate a unique filename
            filename = f"products/{product_id}/videos/{uuid.uuid4().hex}.mp4"

            # Upload to Firebase
            blob = self.bucket.blob(filename)
            blob.upload_from_file(video_file, content_type=mime_type)

            # Make the blob publicly accessible
            blob.make_public()

            # Generate a thumbnail - this would be implemented in a real app
            thumbnail_path, thumbnail_url = self.generate_thumbnail(filename)

            logger.info(f"Video uploaded successfully: {filename}")
            return filename, blob.public_url

        except Exception as e:
            logger.error(f"Error uploading video: {str(e)}")
            raise ValidationError(f"Failed to upload video: {str(e)}")

    def generate_thumbnail(self, video_path):
        """
        Generate a thumbnail for a video.

        Args:
            video_path: Path to the video in storage

        Returns:
            tuple: (thumbnail_path, thumbnail_url)
        """
        try:
            # In a real implementation, you would:
            # 1. Download the video from Firebase
            # 2. Use FFmpeg or similar to extract a frame
            # 3. Upload that frame as the thumbnail

            # For now, create a placeholder path
            thumbnail_filename = f"thumbnail_{uuid.uuid4().hex}.jpg"
            thumbnail_path = (
                f"{os.path.dirname(video_path)}/thumbnails/{thumbnail_filename}"
            )

            # You could upload a default thumbnail here
            # blob = self.bucket.blob(thumbnail_path)
            # blob.upload_from_filename('path/to/default/thumbnail.jpg', content_type='image/jpeg')
            # blob.make_public()
            # thumbnail_url = blob.public_url

            # For now, just return paths
            thumbnail_url = None

            return thumbnail_path, thumbnail_url

        except Exception as e:
            logger.error(f"Error generating thumbnail: {str(e)}")
            return None, None

    def delete_video(self, storage_path):
        """
        Delete a video from Firebase Storage.

        Args:
            storage_path: Path to the video in storage

        Returns:
            bool: True if deletion was successful
        """
        try:
            # Delete the video
            blob = self.bucket.blob(storage_path)
            if blob.exists():
                blob.delete()

                # Try to delete the thumbnail if it exists
                thumbnail_dir = f"{os.path.dirname(storage_path)}/thumbnails"
                thumbnail_base = os.path.basename(storage_path).split(".")[0]

                # List all blobs with the prefix
                blobs = list(
                    self.bucket.list_blobs(prefix=f"{thumbnail_dir}/{thumbnail_base}")
                )
                for thumb_blob in blobs:
                    thumb_blob.delete()

                logger.info(f"Video deleted successfully: {storage_path}")
                return True
            return False

        except Exception as e:
            logger.error(f"Error deleting video: {str(e)}")
            return False
