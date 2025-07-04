# products/constants.py
from django.utils.translation import gettext_lazy as _

# Attribute Types
ATTRIBUTE_TYPES = [
    ("size", "Size"),
    ("color", "Color"),
    ("age_group", "Age Group"),
    ("gender", "Gender"),
    ("custom", "Custom"),
]

# Tax Constants
GST_RATE_CHOICES = [
    (0, "0%"),
    (5, "5%"),
    (12, "12%"),
    (18, "18%"),
]

GST_CATEGORIES = [
    ("exempt", _("GST Exempt")),
    ("regular", _("Regular GST")),
    ("zero_rated", _("Zero Rated")),
]

# Product Status
PRODUCT_STATUS = [
    ("draft", _("Draft")),
    ("published", _("Published")),
    ("archived", _("Archived")),
]

# Attribute Constants - Color choices
COLORS = [
    ("black", _("Black")),
    ("white", _("White")),
    ("red", _("Red")),
    ("blue", _("Blue")),
    ("green", _("Green")),
    ("yellow", _("Yellow")),
    ("purple", _("Purple")),
    ("pink", _("Pink")),
    ("orange", _("Orange")),
    ("brown", _("Brown")),
    ("gray", _("Gray")),
    ("navy", _("Navy Blue")),
    ("teal", _("Teal")),
]

# Size Choices
# products/constants.py - REPLACE the SIZE_CHOICES with this expanded version

# Size Choices - Updated to include all size types
SIZE_CHOICES = [
    # General clothing sizes
    ("XS", _("Extra Small")),
    ("S", _("Small")),
    ("M", _("Medium")),
    ("L", _("Large")),
    ("XL", _("Extra Large")),
    ("2XL", _("2X Large")),
    ("3XL", _("3X Large")),
    ("4XL", _("4X Large")),
    ("5XL", _("5X Large")),
    ("6XL", _("6X Large")),
    # UK Shoe Sizes
    ("UK5", _("UK Size 5")),
    ("UK5.5", _("UK Size 5.5")),
    ("UK6", _("UK Size 6")),
    ("UK6.5", _("UK Size 6.5")),
    ("UK7", _("UK Size 7")),
    ("UK7.5", _("UK Size 7.5")),
    ("UK8", _("UK Size 8")),
    ("UK8.5", _("UK Size 8.5")),
    ("UK9", _("UK Size 9")),
    ("UK9.5", _("UK Size 9.5")),
    ("UK10", _("UK Size 10")),
    ("UK10.5", _("UK Size 10.5")),
    ("UK11", _("UK Size 11")),
    ("UK11.5", _("UK Size 11.5")),
    ("UK12", _("UK Size 12")),
    # US Shoe Sizes
    ("US6", _("US Size 6")),
    ("US6.5", _("US Size 6.5")),
    ("US7", _("US Size 7")),
    ("US7.5", _("US Size 7.5")),
    ("US8", _("US Size 8")),
    ("US8.5", _("US Size 8.5")),
    ("US9", _("US Size 9")),
    ("US9.5", _("US Size 9.5")),
    ("US10", _("US Size 10")),
    ("US10.5", _("US Size 10.5")),
    ("US11", _("US Size 11")),
    ("US11.5", _("US Size 11.5")),
    ("US12", _("US Size 12")),
    ("US12.5", _("US Size 12.5")),
    ("US13", _("US Size 13")),
    # EU Shoe Sizes
    ("EU38", _("EU 38")),
    ("EU38.5", _("EU 38.5")),
    ("EU39", _("EU 39")),
    ("EU39.5", _("EU 39.5")),
    ("EU40", _("EU 40")),
    ("EU40.5", _("EU 40.5")),
    ("EU41", _("EU 41")),
    ("EU41.5", _("EU 41.5")),
    ("EU42", _("EU 42")),
    ("EU42.5", _("EU 42.5")),
    ("EU43", _("EU 43")),
    ("EU43.5", _("EU 43.5")),
    ("EU44", _("EU 44")),
    ("EU44.5", _("EU 44.5")),
    ("EU45", _("EU 45")),
    ("EU45.5", _("EU 45.5")),
    ("EU46", _("EU 46")),
    # Indian Shoe Sizes
    ("IN5", _("Indian Size 5")),
    ("IN6", _("Indian Size 6")),
    ("IN7", _("Indian Size 7")),
    ("IN8", _("Indian Size 8")),
    ("IN9", _("Indian Size 9")),
    ("IN10", _("Indian Size 10")),
    ("IN11", _("Indian Size 11")),
    ("IN12", _("Indian Size 12")),
    ("IN13", _("Indian Size 13")),
    ("IN14", _("Indian Size 14")),
    ("IN15", _("Indian Size 15")),
    # Pant/Waist Sizes (inches)
    ("26", _("26 inches")),
    ("28", _("28 inches")),
    ("30", _("30 inches")),
    ("32", _("32 inches")),
    ("34", _("34 inches")),
    ("36", _("36 inches")),
    ("38", _("38 inches")),
    ("40", _("40 inches")),
    ("42", _("42 inches")),
    ("44", _("44 inches")),
]

# Gender Choices
GENDER_CHOICES = [
    ("M", _("Male")),
    ("F", _("Female")),
    ("U", _("Unisex")),
]

# Age Group Choices
AGE_GROUP_CHOICES = [
    ("infant", _("0-2 years")),
    ("toddler", _("2-4 years")),
    ("kids", _("4-12 years")),
    ("teen", _("13-19 years")),
    ("adult", _("20+ years")),
]

# File Upload Constants
MAX_UPLOAD_SIZE = 10 * 1024 * 1024  # 10MB in bytes
ALLOWED_IMAGE_TYPES = ["image/jpeg", "image/png", "image/gif", "image/webp"]
ALLOWED_VIDEO_TYPES = ["video/mp4", "video/mpeg", "video/quicktime"]

# Pagination Constants
DEFAULT_PAGE_SIZE = 10
MAX_PAGE_SIZE = 100

# Cache Settings
CACHE_TIMEOUT = 3600  # 1 hour
PRODUCT_CACHE_KEY = "product_{}"
BRAND_CACHE_KEY = "brand_{}"
CATEGORY_PRODUCTS_CACHE_KEY = "category_products_{}"

# Rating Constants
MIN_RATING = 1
MAX_RATING = 5

# Stock Constants
LOW_STOCK_THRESHOLD = 10
MAX_STOCK_QUANTITY = 9999
