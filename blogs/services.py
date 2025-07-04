from typing import BinaryIO, Tuple, Dict, Any, List
from django.core.exceptions import ValidationError
from django.db import transaction, models
from django.utils.timezone import now
from firebase_admin import storage
from PIL import Image
from io import BytesIO
import magic
import logging
from datetime import datetime
from .models import BlogPost, BlogImage, BlogComment
from .constants import ALLOWED_IMAGE_TYPES, MAX_UPLOAD_SIZE
from django.utils.text import slugify
import re
from bs4 import BeautifulSoup
from django.conf import settings

logger = logging.getLogger(__name__)


class BlogImageService:
    """Service for handling blog image processing and storage"""

    def __init__(self):
        self.bucket = storage.bucket()

    def optimize_image(self, image_file: BinaryIO, max_width: int = 1200) -> BytesIO:
        """Optimize image for storage"""
        img = Image.open(image_file)

        if img.mode in ("RGBA", "LA"):
            background = Image.new("RGB", img.size, (255, 255, 255))
            background.paste(img, mask=img.split()[-1])
            img = background

        if img.width > max_width:
            ratio = max_width / img.width
            height = int(img.height * ratio)
            img = img.resize((max_width, height), Image.Resampling.LANCZOS)

        output = BytesIO()
        img.save(output, format="JPEG", quality=85, optimize=True)
        output.seek(0)
        return output

    def upload_image(self, file: BinaryIO, blog_id: str) -> Tuple[str, str]:
        """Upload image to Firebase Storage"""
        try:
            # Read first 1024 bytes to determine MIME type
            file_start = file.read(1024)
            file.seek(0)

            mime_type = magic.from_buffer(file_start, mime=True)

            if mime_type not in ALLOWED_IMAGE_TYPES:
                raise ValidationError(
                    f"Invalid file type: {mime_type}. Allowed types: {', '.join(ALLOWED_IMAGE_TYPES)}"
                )

            # Check file size
            file.seek(0, 2)  # Seek to end
            file_size = file.tell()
            file.seek(0)  # Reset to beginning

            if file_size > MAX_UPLOAD_SIZE:
                raise ValidationError(
                    f"File size cannot exceed {MAX_UPLOAD_SIZE/1024/1024}MB"
                )

            optimized = self.optimize_image(file)
            filename = f"blog_images/{blog_id}/{datetime.now().timestamp()}.jpg"

            blob = self.bucket.blob(filename)
            blob.upload_from_file(optimized, content_type="image/jpeg")
            blob.make_public()

            return filename, blob.public_url

        except Exception as e:
            logger.error(f"Error uploading image: {str(e)}")
            raise ValidationError(f"Failed to upload image: {str(e)}")

    def delete_image(self, file_path: str) -> bool:
        """Delete image from Firebase Storage"""
        try:
            blob = self.bucket.blob(file_path)
            if blob.exists():
                blob.delete()
                return True
            return False
        except Exception as e:
            logger.error(f"Error deleting image {file_path}: {str(e)}")
            return False


class BlogCleanupService:
    """Service for cleaning up blog-related resources"""

    def __init__(self):
        self.bucket = storage.bucket()

    def extract_image_urls(self, content: str) -> List[str]:
        """Extract all image URLs from blog content"""
        soup = BeautifulSoup(content, "html.parser")
        images = soup.find_all("img")
        return [img.get("src") for img in images if img.get("src")]

    def extract_firebase_paths(self, urls: List[str]) -> List[str]:
        """Convert Firebase URLs to storage paths"""
        paths = []
        for url in urls:
            match = re.search(r"blog_content_[^?]+", url)
            if match:
                paths.append(match.group(0))
        return paths

    def delete_unused_images(self, blog_post) -> None:
        """Delete images that are no longer used in the blog post"""
        try:
            current_images = self.extract_image_urls(blog_post.content)
            current_paths = self.extract_firebase_paths(current_images)

            if blog_post.featured_image_storage_path:
                current_paths.append(blog_post.featured_image_storage_path)

            prefix = f"blog_content_{blog_post.id}"
            blobs = self.bucket.list_blobs(prefix=prefix)

            for blob in blobs:
                if blob.name not in current_paths:
                    blob.delete()

        except Exception as e:
            logger.error(f"Error cleaning up blog images: {str(e)}")

    def delete_all_blog_images(self, blog_post) -> None:
        """Delete all images associated with a blog post"""
        try:
            if blog_post.featured_image_storage_path:
                blob = self.bucket.blob(blog_post.featured_image_storage_path)
                if blob.exists():
                    blob.delete()

            prefix = f"blog_content_{blog_post.id}"
            blobs = self.bucket.list_blobs(prefix=prefix)

            for blob in blobs:
                blob.delete()

        except Exception as e:
            logger.error(f"Error deleting blog images: {str(e)}")


class BlogService:
    """Main service for blog management"""

    def __init__(self):
        self.image_service = BlogImageService()
        self.cleanup_service = BlogCleanupService()

    @transaction.atomic
    def create_blog_post(self, data: dict, author: object) -> BlogPost:
        """Create a new blog post with images"""
        # Extract many-to-many fields
        images_data = data.pop("images", [])
        featured_image = data.pop("featured_image", None)
        tag_ids = data.pop("tag_ids", [])  # Extract tag_ids
        tags_data = data.pop("tags", [])  # Extract tags if present

        # Create the blog post without many-to-many fields
        blog_post = BlogPost.objects.create(
            author=author, created_by=author, updated_by=author, **data
        )

        # Set many-to-many relationships after creation
        if tag_ids:
            blog_post.tags.set(tag_ids)
        elif tags_data:
            # If tags_data is provided instead of tag_ids
            tag_ids = [tag.id if hasattr(tag, "id") else tag for tag in tags_data]
            blog_post.tags.set(tag_ids)

        # Handle featured image upload
        if featured_image:
            try:
                file_path, file_url = self.image_service.upload_image(
                    featured_image, str(blog_post.id)
                )
                blog_post.featured_image_url = file_url
                blog_post.featured_image_storage_path = file_path
                blog_post.save()
            except Exception as e:
                logger.error(f"Error uploading featured image: {str(e)}")
                # Continue without featured image

        # Handle additional images
        for img_data in images_data:
            if "file" in img_data:
                try:
                    file_path, file_url = self.image_service.upload_image(
                        img_data["file"], str(blog_post.id)
                    )
                    BlogImage.objects.create(
                        blog_post=blog_post,
                        image_url=file_url,
                        storage_path=file_path,
                        alt_text=img_data.get("alt_text", ""),
                        caption=img_data.get("caption", ""),
                        sort_order=img_data.get("sort_order", 0),
                    )
                except Exception as e:
                    logger.error(f"Error uploading additional image: {str(e)}")
                    # Continue with other images

        return blog_post

    @transaction.atomic
    def update_blog_post(
        self, blog_post: BlogPost, data: dict, user: object
    ) -> BlogPost:
        """Update blog post and related data"""
        # Extract many-to-many fields
        images_data = data.pop("images", None)
        featured_image = data.pop("featured_image", None)
        tag_ids = data.pop("tag_ids", None)
        tags_data = data.pop("tags", None)

        # Update basic fields
        for attr, value in data.items():
            setattr(blog_post, attr, value)

        blog_post.updated_by = user
        blog_post.save()

        # Update many-to-many relationships
        if tag_ids is not None:
            blog_post.tags.set(tag_ids)
        elif tags_data is not None:
            tag_ids = [tag.id if hasattr(tag, "id") else tag for tag in tags_data]
            blog_post.tags.set(tag_ids)

        # Handle featured image update
        if featured_image:
            try:
                # Delete old featured image if exists
                if blog_post.featured_image_storage_path:
                    self.image_service.delete_image(
                        blog_post.featured_image_storage_path
                    )

                file_path, file_url = self.image_service.upload_image(
                    featured_image, str(blog_post.id)
                )
                blog_post.featured_image_url = file_url
                blog_post.featured_image_storage_path = file_path
                blog_post.save()
            except Exception as e:
                logger.error(f"Error updating featured image: {str(e)}")

        # Handle additional images update
        if images_data is not None:
            # Delete existing images
            for img in blog_post.images.all():
                if img.storage_path:
                    self.image_service.delete_image(img.storage_path)
            blog_post.images.all().delete()

            # Create new images
            for img_data in images_data:
                if "file" in img_data:
                    try:
                        file_path, file_url = self.image_service.upload_image(
                            img_data["file"], str(blog_post.id)
                        )
                        BlogImage.objects.create(
                            blog_post=blog_post,
                            image_url=file_url,
                            storage_path=file_path,
                            alt_text=img_data.get("alt_text", ""),
                            caption=img_data.get("caption", ""),
                            sort_order=img_data.get("sort_order", 0),
                        )
                    except Exception as e:
                        logger.error(f"Error uploading image during update: {str(e)}")

        return blog_post

    def increment_view_count(self, blog_post: BlogPost) -> None:
        """Increment blog post view count"""
        BlogPost.objects.filter(id=blog_post.id).update(
            views_count=models.F("views_count") + 1
        )

    @transaction.atomic
    def delete_blog_post(self, blog_post: BlogPost) -> bool:
        """Delete blog post and all associated images"""
        try:
            self.cleanup_service.delete_all_blog_images(blog_post)
            blog_post.delete()
            return True
        except Exception as e:
            logger.error(f"Error deleting blog post: {str(e)}")
            return False


class BlogCommentService:
    """Service for managing blog comments"""

    @staticmethod
    def add_comment(
        blog_post: BlogPost,
        author: object,
        content: str,
        parent_comment: BlogComment = None,
    ) -> BlogComment:
        """Add a new comment to a blog post"""
        comment = BlogComment.objects.create(
            blog_post=blog_post, author=author, content=content, parent=parent_comment
        )
        return comment

    @staticmethod
    def approve_comment(comment: BlogComment) -> bool:
        """Approve a blog comment"""
        try:
            comment.is_approved = True
            comment.save()
            return True
        except Exception as e:
            logger.error(f"Error approving comment: {str(e)}")
            return False


class BlogSEOService:
    """Service for managing blog SEO"""

    @staticmethod
    def generate_meta_tags(blog_post) -> Dict[str, str]:
        """Generate SEO meta tags for a blog post"""
        return {
            "title": blog_post.meta_title or blog_post.title,
            "description": blog_post.meta_description
            or blog_post.excerpt
            or blog_post.content[:160],
            "keywords": blog_post.meta_keywords
            or ", ".join([tag.name for tag in blog_post.tags.all()]),
            "author": blog_post.author.name,
            "og:title": blog_post.meta_title or blog_post.title,
            "og:description": blog_post.meta_description
            or blog_post.excerpt
            or blog_post.content[:160],
            "og:type": "article",
            "og:url": f"{settings.SITE_URL}/blog/{blog_post.slug}",
            "og:image": (
                blog_post.featured_image_url if blog_post.featured_image_url else ""
            ),
            "article:published_time": (
                blog_post.published_at.isoformat() if blog_post.published_at else ""
            ),
            "article:modified_time": blog_post.updated_at.isoformat(),
            "article:author": blog_post.author.name,
            "article:section": blog_post.category.name if blog_post.category else "",
            "article:tag": ", ".join([tag.name for tag in blog_post.tags.all()]),
            "twitter:card": "summary_large_image",
            "twitter:title": blog_post.meta_title or blog_post.title,
            "twitter:description": blog_post.meta_description
            or blog_post.excerpt
            or blog_post.content[:160],
            "twitter:image": (
                blog_post.featured_image_url if blog_post.featured_image_url else ""
            ),
        }

    @staticmethod
    def generate_schema_markup(blog_post) -> Dict[str, Any]:
        """Generate schema.org markup for a blog post"""
        return {
            "@context": "https://schema.org",
            "@type": "BlogPosting",
            "headline": blog_post.title,
            "description": blog_post.meta_description
            or blog_post.excerpt
            or blog_post.content[:160],
            "author": {"@type": "Person", "name": blog_post.author.name},
            "datePublished": (
                blog_post.published_at.isoformat() if blog_post.published_at else ""
            ),
            "dateModified": blog_post.updated_at.isoformat(),
            "mainEntityOfPage": {
                "@type": "WebPage",
                "@id": f"{settings.SITE_URL}/blog/{blog_post.slug}",
            },
            "publisher": {
                "@type": "Organization",
                "name": settings.SITE_NAME,
                "logo": {"@type": "ImageObject", "url": settings.SITE_LOGO},
            },
            "image": {
                "@type": "ImageObject",
                "url": (
                    blog_post.featured_image_url if blog_post.featured_image_url else ""
                ),
                "width": "1200",
                "height": "630",
            },
            "articleSection": blog_post.category.name if blog_post.category else "",
            "keywords": blog_post.meta_keywords
            or ", ".join([tag.name for tag in blog_post.tags.all()]),
        }

    @staticmethod
    def generate_sitemap_data(blog_post) -> Dict[str, Any]:
        """Generate sitemap data for a blog post"""
        return {
            "loc": f"{settings.SITE_URL}/blog/{blog_post.slug}",
            "lastmod": blog_post.updated_at.isoformat(),
            "changefreq": "weekly",
            "priority": 0.8 if blog_post.is_featured else 0.6,
            "image:image": (
                [
                    {
                        "image:loc": blog_post.featured_image_url,
                        "image:title": blog_post.title,
                        "image:caption": blog_post.excerpt if blog_post.excerpt else "",
                    }
                ]
                if blog_post.featured_image_url
                else []
            ),
        }

    @staticmethod
    def generate_canonical_url(blog_post) -> str:
        """Generate canonical URL for a blog post"""
        return f"{settings.SITE_URL}/blog/{blog_post.slug}"

    @staticmethod
    def generate_robots_data(blog_post) -> str:
        """Generate robots meta tag content"""
        if blog_post.status == "published":
            return "index, follow"
        return "noindex, nofollow"
