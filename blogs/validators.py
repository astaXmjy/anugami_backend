from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
import magic
from .constants import (
    MAX_UPLOAD_SIZE,
    ALLOWED_IMAGE_TYPES,
    META_TITLE_MAX_LENGTH,
    META_DESCRIPTION_MAX_LENGTH,
    META_KEYWORDS_MAX_LENGTH,
    COMMENT_MIN_LENGTH,
    MAX_COMMENT_LENGTH,
)


def validate_file_size(file):
    """Validate file size does not exceed maximum upload size"""
    if file.size > MAX_UPLOAD_SIZE:
        raise ValidationError(
            _(f"File size cannot exceed {MAX_UPLOAD_SIZE/1024/1024}MB")
        )


def validate_image_type(file):
    """Validate image file type using magic library"""
    try:
        mime_type = magic.from_buffer(file.read(1024), mime=True)
        file.seek(0)  # Reset file pointer

        if mime_type not in ALLOWED_IMAGE_TYPES:
            raise ValidationError(
                _(
                    f'Invalid file type. Allowed types are: {", ".join(ALLOWED_IMAGE_TYPES)}'
                )
            )
    except Exception as e:
        raise ValidationError(_("Error validating file type"))


def validate_meta_title(value):
    """Validate meta title length"""
    if len(value) > META_TITLE_MAX_LENGTH:
        raise ValidationError(
            _(f"Meta title cannot exceed {META_TITLE_MAX_LENGTH} characters")
        )


def validate_meta_description(value):
    """Validate meta description length"""
    if len(value) > META_DESCRIPTION_MAX_LENGTH:
        raise ValidationError(
            _(
                f"Meta description cannot exceed {META_DESCRIPTION_MAX_LENGTH} characters"
            )
        )


def validate_meta_keywords(value):
    """Validate meta keywords length"""
    if len(value) > META_KEYWORDS_MAX_LENGTH:
        raise ValidationError(
            _(f"Meta keywords cannot exceed {META_KEYWORDS_MAX_LENGTH} characters")
        )


def validate_comment_length(value):
    """Validate comment length"""
    if len(value) < COMMENT_MIN_LENGTH:
        raise ValidationError(
            _(f"Comment must be at least {COMMENT_MIN_LENGTH} characters long")
        )
    if len(value) > MAX_COMMENT_LENGTH:
        raise ValidationError(
            _(f"Comment cannot exceed {MAX_COMMENT_LENGTH} characters")
        )
