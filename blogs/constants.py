from django.utils.translation import gettext_lazy as _

# File Upload Constants
MAX_UPLOAD_SIZE = 5 * 1024 * 1024  # 5MB in bytes
ALLOWED_IMAGE_TYPES = ['image/jpeg', 'image/png', 'image/gif', 'image/webp']

# Cache Keys and Timeouts
CACHE_TIMEOUT = 3600  # 1 hour
BLOG_CACHE_KEY = 'blog_{}'
BLOG_LIST_CACHE_KEY = 'blog_list_{}'
CATEGORY_BLOGS_CACHE_KEY = 'category_blogs_{}'

# Pagination Constants
DEFAULT_PAGE_SIZE = 10
MAX_PAGE_SIZE = 50

# Blog Status
BLOG_STATUS = [
    ('draft', _('Draft')),
    ('published', _('Published')),
    ('archived', _('Archived')),
]

# Featured Image Dimensions
FEATURED_IMAGE_WIDTH = 1200
FEATURED_IMAGE_HEIGHT = 630

# Comment Settings
MAX_COMMENT_LENGTH = 1000
COMMENT_MIN_LENGTH = 10

# SEO Constants
META_TITLE_MAX_LENGTH = 60
META_DESCRIPTION_MAX_LENGTH = 160
META_KEYWORDS_MAX_LENGTH = 255