# categories/signals.py
from django.db.models.signals import post_save, post_delete, pre_delete
from django.dispatch import receiver
from django.core.cache import cache
from django.utils.text import slugify
from .models import Category, CategoryImage
from .services import CategoryService
import logging

logger = logging.getLogger(__name__)

@receiver(post_save, sender=Category)
def handle_category_save(sender, instance, created, **kwargs):
    """Handle category post-save operations"""
    try:
        # Clear cache
        cache.delete('category_tree')
        
        # Generate slug if not exists
        if not instance.slug:
            instance.slug = slugify(instance.name)
            instance.save()
        
        # Update parent's subcategory count
        if instance.parent:
            instance.parent.subcategory_count = instance.parent.get_children().count()
            instance.parent.save()
            
        if created:
            logger.info(f"Category created: {instance.name}")
        else:
            logger.info(f"Category updated: {instance.name}")
            
    except Exception as e:
        logger.error(f"Error in category post-save signal: {str(e)}")

@receiver(pre_delete, sender=Category)
def handle_category_pre_delete(sender, instance, **kwargs):
    """Handle category pre-delete operations"""
    try:
        # Store parent reference for post-delete
        instance._parent = instance.parent
        
        # Delete associated images from Firebase
        service = CategoryService()
        for image in instance.images.all():
            service.delete_category_image(image.image_url)
            
    except Exception as e:
        logger.error(f"Error in category pre-delete signal: {str(e)}")

@receiver(post_delete, sender=Category)
def handle_category_post_delete(sender, instance, **kwargs):
    """Handle category post-delete operations"""
    try:
        # Clear cache
        cache.delete('category_tree')
        
        # Update parent's subcategory count
        if hasattr(instance, '_parent') and instance._parent:
            instance._parent.subcategory_count = instance._parent.get_children().count()
            instance._parent.save()
            
        logger.info(f"Category deleted: {instance.name}")
        
    except Exception as e:
        logger.error(f"Error in category post-delete signal: {str(e)}")

@receiver(post_save, sender=CategoryImage)
def handle_image_save(sender, instance, created, **kwargs):
    """Handle image post-save operations"""
    try:
        # Update primary image logic
        if instance.is_primary:
            CategoryImage.objects.filter(
                category=instance.category,
                is_primary=True
            ).exclude(id=instance.id).update(is_primary=False)
            
    except Exception as e:
        logger.error(f"Error in image post-save signal: {str(e)}")