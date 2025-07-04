# products/validators.py
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.utils.translation import gettext_lazy as _
import magic
import re

from .constants import (
    MAX_UPLOAD_SIZE,
    ALLOWED_IMAGE_TYPES,
    ALLOWED_VIDEO_TYPES,
    MAX_STOCK_QUANTITY,
    COLORS,
    SIZE_CHOICES,
    AGE_GROUP_CHOICES,
    GENDER_CHOICES,
)


def validate_file_size(file):
    """Validate file size does not exceed maximum upload size."""
    if file.size > MAX_UPLOAD_SIZE:
        raise ValidationError(
            _(f"File size cannot exceed {MAX_UPLOAD_SIZE/1024/1024:.2f}MB")
        )


def validate_image_type(file):
    """Validate image file type using magic library."""
    mime_type = magic.from_buffer(file.read(1024), mime=True)
    file.seek(0)  # Reset file pointer

    if mime_type not in ALLOWED_IMAGE_TYPES:
        raise ValidationError(
            _(f'Invalid file type. Allowed types are: {", ".join(ALLOWED_IMAGE_TYPES)}')
        )


def validate_video_type(file):
    """Validate video file type using magic library."""
    mime_type = magic.from_buffer(file.read(1024), mime=True)
    file.seek(0)  # Reset file pointer

    if mime_type not in ALLOWED_VIDEO_TYPES:
        raise ValidationError(
            _(
                f'Invalid video type. Allowed types are: {", ".join(ALLOWED_VIDEO_TYPES)}'
            )
        )


def validate_hsn_code(value):
    """Validate HSN (Harmonized System of Nomenclature) code."""
    hsn_validator = RegexValidator(
        regex=r"^\d{8}$", message=_("HSN code must be an 8-digit number")
    )
    hsn_validator(value)


def validate_sac_code(value):
    """Validate SAC (Service Accounting Code) code."""
    sac_validator = RegexValidator(
        regex=r"^\d{6}$", message=_("SAC code must be a 6-digit number")
    )
    sac_validator(value)


def validate_price(value):
    """Validate product pricing."""
    if value is None or value <= 0:
        raise ValidationError(_("Price must be greater than zero"))

    # Ensure no more than 2 decimal places
    if len(str(value).split(".")[-1]) > 2:
        raise ValidationError(_("Price cannot have more than 2 decimal places"))


def validate_stock_quantity(value):
    """Validate stock quantity."""
    if value is None or value < 0:
        raise ValidationError(_("Stock quantity cannot be negative"))

    if value > MAX_STOCK_QUANTITY:
        raise ValidationError(_(f"Stock quantity cannot exceed {MAX_STOCK_QUANTITY}"))


def validate_color(value):
    """Validate color choice."""
    valid_colors = [color[0] for color in COLORS]
    if value not in valid_colors:
        raise ValidationError(
            _(f'Invalid color. Must be one of: {", ".join(valid_colors)}')
        )


def validate_size(value):
    """Validate size choice - Updated to include shoe sizes."""
    valid_sizes = [size[0] for size in SIZE_CHOICES]
    if value not in valid_sizes:
        # Create a more user-friendly error message
        clothing_sizes = ["XS", "S", "M", "L", "XL", "2XL", "3XL", "4XL", "5XL", "6XL"]
        shoe_sizes = [s for s in valid_sizes if s.startswith(("UK", "US", "EU"))]
        pant_sizes = [s for s in valid_sizes if s.isdigit()]

        error_msg = f'Invalid size "{value}". Valid options are:\n'
        error_msg += f'Clothing: {", ".join(clothing_sizes)}\n'
        error_msg += f'Shoes: {", ".join(shoe_sizes[:10])}... (and more)\n'
        error_msg += f'Pants: {", ".join(pant_sizes)}'

        raise ValidationError(_(error_msg))
    return value


def validate_age_group(value):
    """Validate age group choice."""
    valid_age_groups = [group[0] for group in AGE_GROUP_CHOICES]
    if value not in valid_age_groups:
        raise ValidationError(
            _(f'Invalid age group. Must be one of: {", ".join(valid_age_groups)}')
        )


def validate_gender(value):
    """Validate gender choice."""
    valid_genders = [gender[0] for gender in GENDER_CHOICES]
    if value not in valid_genders:
        raise ValidationError(
            _(f'Invalid gender. Must be one of: {", ".join(valid_genders)}')
        )


def validate_slug(value):
    """Validate slug format."""
    slug_validator = RegexValidator(
        regex=r"^[-a-zA-Z0-9_]+$",
        message=_(
            "Enter a valid slug. Use only letters, numbers, underscores, or hyphens."
        ),
    )
    slug_validator(value)


def validate_sku(value):
    """Validate SKU (Stock Keeping Unit) format."""
    sku_validator = RegexValidator(
        regex=r"^[A-Z]{3}-[0-9a-f]{8}$",
        message=_(
            "SKU must be in format: PRD-xxxxxxxx (3 uppercase letters, hyphen, 8 hex characters)"
        ),
    )
    sku_validator(value)
