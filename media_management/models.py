from django.db import models
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _

User = get_user_model()

class FirestoreMedia(models.Model):
    """
    Model to store Firestore media metadata and relationships
    """
    firestore_id = models.CharField(_('Firestore ID'), max_length=255, unique=True)
    original_name = models.CharField(_('Original Filename'), max_length=255)
    storage_path = models.CharField(_('Storage Path'), max_length=512)
    content_type = models.CharField(_('Content Type'), max_length=100)
    size = models.PositiveIntegerField(_('File Size'))
    directory = models.CharField(_('Directory'), max_length=100)
    user = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL,
        null=True,
        related_name='firestore_media_files'
    )
    created_at = models.DateTimeField(_('Created At'), auto_now_add=True)
    updated_at = models.DateTimeField(_('Updated At'), auto_now=True)
    
    # Optional thumbnail path for images
    thumbnail_path = models.CharField(
        _('Thumbnail Path'),
        max_length=512,
        null=True,
        blank=True
    )

    class Meta:
        verbose_name = _('Media File')
        verbose_name_plural = _('Media Files')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['content_type']),
            models.Index(fields=['directory']),
        ]

    def __str__(self):
        return f"{self.original_name} ({self.firestore_id})"

    @property
    def file_size_display(self):
        """Return human-readable file size"""
        size = self.size
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024.0:
                return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} TB"

class FirestoreProductImage(models.Model):
    """
    Model to associate media with products
    """
    product = models.ForeignKey(
        'products.Product',
        on_delete=models.CASCADE,
        related_name='firestore_images'
    )
    media = models.ForeignKey(
        FirestoreMedia,
        on_delete=models.CASCADE,
        related_name='product_images'
    )
    is_primary = models.BooleanField(_('Is Primary Image'), default=False)
    position = models.PositiveIntegerField(_('Display Position'), default=0)

    class Meta:
        ordering = ['position']
        unique_together = [['product', 'media']]
        verbose_name = _('Product Image')
        verbose_name_plural = _('Product Images')

    def save(self, *args, **kwargs):
        # Ensure only one primary image per product
        if self.is_primary:
            FirestoreProductImage.objects.filter(
                product=self.product,
                is_primary=True
            ).exclude(id=self.id).update(is_primary=False)
        super().save(*args, **kwargs)