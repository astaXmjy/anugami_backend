from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

def validate_file_size(file):
    """
    Validate file size is under 2MB
    """
    max_size = 2 * 1024 * 1024  # 2MB in bytes
    if file.size > max_size:
        raise ValidationError(_(
            f'File size must be no more than 2MB - current size is {file.size / (1024*1024):.1f}MB'
        ))

def validate_image_type(file):
    """
    Validate image file type
    """
    valid_types = {'image/jpeg', 'image/png', 'image/gif', 'image/webp'}
    if file.content_type not in valid_types:
        raise ValidationError(_(
            f'Invalid image type. Supported types are: {", ".join(valid_types)}'
        ))

def validate_video_type(file):
    """
    Validate video file type
    """
    valid_types = {'video/mp4', 'video/mpeg', 'video/webm'}
    if file.content_type not in valid_types:
        raise ValidationError(_(
            f'Invalid video type. Supported types are: {", ".join(valid_types)}'
        ))