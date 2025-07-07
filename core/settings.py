"""
Django settings for core project.
"""

from pathlib import Path
import os
import sys
from decouple import config
from datetime import timedelta
import firebase_admin
from firebase_admin import credentials, initialize_app

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Security and Environment Configuration
SECRET_KEY = config("SECRET_KEY", default="your-secret-key-for-development")
DEBUG = config("DEBUG", default=False, cast=bool)


def parse_csv_config(v):
    """Helper function to parse comma-separated configuration values."""
    return [s.strip() for s in v.split(",")]


ALLOWED_HOSTS = parse_csv_config(config("ALLOWED_HOSTS", default="*"))

# Application Definition
INSTALLED_APPS = [
    "daphne",
    # Django Built-in Apps
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # 'django_quill',
    # Third-Party Apps
    "rest_framework",
    "rest_framework.authtoken",
    "rest_framework_simplejwt",
    "drf_spectacular",
    "corsheaders",
    "django_extensions",
    "mptt",
    "django_filters",
    "channels",
    # Custom Apps
    "system_users.apps.SystemUsersConfig",
    "categories.apps.CategoriesConfig",
    "products.apps.ProductsConfig",
    "sellers",
    "shipping_policies",
    "returns",
    "payments",
    # "django_extensions",
    "blogs",
    "orders",
    "customers",
    "media_management",
    "chat",
    "faq",
    "email_template",
    "support_tickets",
    "reports",
    "system_settings",
    "promo_codes",
    "offers",
    "contact",
]

ASGI_APPLICATION = "core.asgi.application"

# User Model Configuration
AUTH_USER_MODEL = "system_users.CustomUser"

# Caching
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": config("REDIS_URL", default="redis://localhost:6379/1"),
    }
}

# Channels layer configuration
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            "hosts": [("localhost", 6379)],
        },
    },
}

# REST Framework Configuration
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
        "rest_framework.authentication.SessionAuthentication",
        "rest_framework.authentication.TokenAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.IsAuthenticatedOrReadOnly",
    ),
    "DEFAULT_FILTER_BACKENDS": (
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ),
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 20,
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {"anon": "10000/day", "user": "100000/day"},
}

# JWT Configuration
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=60),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=1),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "UPDATE_LAST_LOGIN": True,
    "ALGORITHM": "HS256",
    "SIGNING_KEY": SECRET_KEY,
    "VERIFYING_KEY": None,
    "AUTH_HEADER_TYPES": ("Bearer",),
    "USER_ID_FIELD": "id",
    "USER_ID_CLAIM": "user_id",
}

QUILL_CONFIGS = {
    "default": {
        "theme": "snow",
        "modules": {
            "syntax": True,
            "toolbar": [
                [
                    {"font": []},
                    {"header": []},
                    {"align": []},
                    "bold",
                    "italic",
                    "underline",
                    "strike",
                    "blockquote",
                    {"color": []},
                    {"background": []},
                ],
                ["code-block", "link"],
                ["clean"],
            ],
        },
    }
}

# API Documentation
SPECTACULAR_SETTINGS = {
    "TITLE": "Anugami E-commerce API",
    "DESCRIPTION": "Comprehensive API for Anugami Multivendor E-commerce Platform",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "COMPONENT_SPLIT_REQUEST": True,
    "SCHEMA_PATH_PREFIX": r"/api/v1/",
    "SERVE_PERMISSIONS": ["rest_framework.permissions.IsAdminUser"],
    "SWAGGER_UI_SETTINGS": {
        "deepLinking": True,
        "persistAuthorization": True,
        "displayOperationId": True,
    },
}

# Authentication Configuration
AUTHENTICATION_BACKENDS = [
    "system_users.backends.EmailBackend",
    "django.contrib.auth.backends.ModelBackend",
]

# Database Configuration
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": config("POSTGRES_DB", default="anugami_db"),
        "USER": config("POSTGRES_USER", default="anugami_user"),
        "PASSWORD": config("POSTGRES_PASSWORD"),
        "HOST": config("POSTGRES_HOST", default="localhost"),
        "PORT": config("POSTGRES_PORT", default="5432"),
        "OPTIONS": {
            "client_encoding": "UTF8",
        },
        "TEST": {
            "NAME": f'test_{config("POSTGRES_DB", default="anugami_db")}',
        },
    }
}

# Firebase Configuration
FIREBASE_CREDENTIALS_PATH = config("FIREBASE_CREDENTIALS_PATH")
try:
    if os.path.exists(FIREBASE_CREDENTIALS_PATH):
        # Initialize the Firebase application with the credentials
        cred = credentials.Certificate(FIREBASE_CREDENTIALS_PATH)
        firebase_app = initialize_app(
            cred,
            {
                "storageBucket": config("FIREBASE_STORAGE_BUCKET"),
                "projectId": config("FIREBASE_PROJECT_ID"),
            },
        )
        print("Firebase initialized successfully.")
    else:
        print("Firebase credentials not found.")
        firebase_app = None
except Exception as e:
    print(f"Firebase initialization error: {e}")
    firebase_app

FIREBASE_CONFIG = {
    "apiKey": config("FIREBASE_API_KEY"),
    "authDomain": config("FIREBASE_AUTH_DOMAIN"),
    "projectId": config("FIREBASE_PROJECT_ID"),
    "storageBucket": config("FIREBASE_STORAGE_BUCKET"),
    "messagingSenderId": config("FIREBASE_MESSAGING_SENDER_ID"),
    "appId": config("FIREBASE_APP_ID"),
}

# Email Configuration
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = config("EMAIL_HOST", default="smtp.gmail.com")
EMAIL_PORT = config("EMAIL_PORT", default=587, cast=int)
EMAIL_USE_TLS = config("EMAIL_USE_TLS", default=True, cast=bool)
EMAIL_HOST_USER = config("EMAIL_HOST_USER")
EMAIL_HOST_PASSWORD = config("EMAIL_HOST_PASSWORD")
DEFAULT_FROM_EMAIL = config("DEFAULT_FROM_EMAIL")

# Contact Configuration
CONTACT_EMAIL = config("CONTACT_EMAIL", default="support@anugami.com")
ADMIN_EMAIL = config("ADMIN_EMAIL", default="admin@anugami.com")

# Middleware
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "customers.middlewares.CartMergeMiddleware",
    "customers.middlewares.WishlistMergeMiddleware",
]

# CORS Configuration
CORS_ALLOWED_ORIGINS = parse_csv_config(
    config(
        "CORS_ALLOWED_ORIGINS",
        default="http://localhost:3000,http://localhost:3001,http://65.1.8.148:3001,http://65.1.8.148:3000,http://65.1.88.148:8000,https://stgadmin.anugami.com,https://stg.anugami.com",
    )
)

CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_METHODS = ["DELETE", "GET", "OPTIONS", "PATCH", "POST", "PUT"]

# Application Configuration
ROOT_URLCONF = "core.urls"
WSGI_APPLICATION = "core.wsgi.application"

# Template Configuration
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    }
]

# Internationalization
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

# Static and Media Files
STATIC_URL = "/qrcodes/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "qrcodes"]
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# Logging
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{levelname} {asctime} {module} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "file": {
            "level": "ERROR",
            "class": "logging.FileHandler",
            "filename": BASE_DIR / "logs/error.log",
            "formatter": "verbose",
        },
        "console": {
            "level": "INFO",
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
    },
    "loggers": {
        "django": {
            "handlers": ["file", "console"],
            "level": "ERROR",
            "propagate": False,
        },
        "application": {
            "handlers": ["file", "console"],
            "level": "DEBUG",
            "propagate": False,
        },
    },
}

PHONEPE_SALT_KEY = config("PHONEPE_SALT_KEY")
PHONEPE_SALT_INDEX = config("PHONEPE_SALT_INDEX")
PHONEPE_MERCHANT_ID = config("PHONEPE_MERCHANT_ID")
PHONEPE_ENVIRONMENT = "production"
PHONEPE_CALLBACK_URL = (
    "https://49cc-106-219-87-60.ngrok-free.app/api/v1/orders/webhooks/phonepe/"
)
PHONEPE_REDIRECT_URL = (
    "https://b6e2-106-219-87-60.ngrok-free.app/api/v1/order/payment/callback"
)
PHONEPE_REFUND_CALLBACK_URL = (
    "https://b6e2-106-219-87-60.ngrok-free.app/api/v1/orders/webhooks/phonepe/refund/"
)


SHIPMOJO_PUBLIC_KEY=config("SHIPMOJO_PUBLIC_KEY")
SHIPMOJO_PRIVATE_KEY=config("SHIPMOJO_PRIVATE_KEY")


# Security Settings (Production)
if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ("HTTP_x_FORWARDED_PROTO", "https")
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_BROWSER_XSS_FILTER = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    X_FRAME_OPTIONS = "DENY"
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    USE_X_FORWARDED_HOST = True
    USE_X_FORWARDED_PORT = True
