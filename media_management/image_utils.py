from PIL import Image
import io
import logging

logger = logging.getLogger(__name__)

class ImageOptimizer:
    """Handles image optimization while maintaining quality"""
    
    @staticmethod
    def optimize_image(image_file, max_size_bytes=2*1024*1024):  # 2MB
        """
        Optimize image while maintaining quality and respecting size limit
        
        Args:
            image_file: InMemoryUploadedFile or similar file object
            max_size_bytes: Maximum allowed file size in bytes
            
        Returns:
            tuple: (optimized_file: BytesIO, content_type: str)
        """
        try:
            # Open image using Pillow
            img = Image.open(image_file)
            
            # Convert RGBA to RGB if necessary
            if img.mode == 'RGBA':
                bg = Image.new('RGB', img.size, (255, 255, 255))
                bg.paste(img, mask=img.split()[3])
                img = bg
            
            # Initial quality
            quality = 95
            output = io.BytesIO()
            
            # Save with optimization
            img.save(output, format=img.format or 'JPEG', 
                    quality=quality, optimize=True)
            
            # Reduce quality until file size is under limit
            while output.tell() > max_size_bytes and quality > 30:
                output.seek(0)
                output.truncate()
                quality -= 5
                img.save(output, format=img.format or 'JPEG', 
                        quality=quality, optimize=True)
            
            # Check final size
            if output.tell() > max_size_bytes:
                raise ValueError("Cannot optimize image to under 2MB while maintaining acceptable quality")
            
            # Prepare file for return
            output.seek(0)
            return output, f"image/{img.format.lower()}" if img.format else "image/jpeg"
            
        except Exception as e:
            logger.error(f"Image optimization failed: {str(e)}")
            raise ValueError(f"Image optimization failed: {str(e)}")

    @staticmethod
    def create_thumbnail(image_file, size=(300, 300)):
        """
        Create thumbnail of specified size
        
        Args:
            image_file: Original image file
            size: Tuple of (width, height)
            
        Returns:
            BytesIO: Thumbnail image file
        """
        try:
            img = Image.open(image_file)
            img.thumbnail(size)
            
            output = io.BytesIO()
            img.save(output, format=img.format or 'JPEG', quality=85, optimize=True)
            output.seek(0)
            
            return output
            
        except Exception as e:
            logger.error(f"Thumbnail creation failed: {str(e)}")
            raise ValueError(f"Thumbnail creation failed: {str(e)}")