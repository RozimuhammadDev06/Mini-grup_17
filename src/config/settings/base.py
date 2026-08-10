"""
Settings shared by every environment.

Everything environment-specific or secret is read from environment variables
(see ``.env.example``). Nothing secret is hardcoded here.

Environment selection happens in ``config/settings/__init__.py``: ``DEBUG``
picks ``development`` or ``production``.
"""

import os
from datetime import timedelta

import environ

env = environ.Env()

BASE_DIR = os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))))
environ.Env.read_env(os.path.join(BASE_DIR, ".env"))


def env_str(key: str, default: str = "") -> str:
    """
    Read a string setting, treating a present-but-empty variable as unset.

    ``.env`` files in this project ship with blank placeholders
    (``REDIS_HOST=``), and plain ``env(key, default=...)`` would return the
    empty string for those instead of falling back to the default.
    """
    return env(key, default="").strip() or default


# ---------------------------------------------------------------------------
# Core
# ---------------------------------------------------------------------------

SECRET_KEY = env("SECRET_KEY")
DEBUG = env.bool("DEBUG", default=False)
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=["127.0.0.1", "localhost"])

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

AUTH_USER_MODEL = "users.User"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Public base URL of this service, used to build links sent by email.
BASE_URL = env_str("BASE_URL", "http://127.0.0.1:8000")
BASE_URL_LINK = env_str(
    "BASE_URL_LINK",
    f"{BASE_URL}/api/v1/auth/register/confirmations/",
)


# ---------------------------------------------------------------------------
# Applications
# ---------------------------------------------------------------------------

DJANGO_APPS = [
    "jazzmin",  # must precede django.contrib.admin to override its templates
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
]

THIRD_PARTY_APPS = [
    "corsheaders",
    "rest_framework",
    "rest_framework_simplejwt",
    "rest_framework_simplejwt.token_blacklist",
    "django_filters",
    "drf_spectacular",
]

LOCAL_APPS = [
    "apps.utils",
    "apps.users",
    "apps.geo",
    "apps.catalog",
    "apps.discounts",
    "apps.carts",
    "apps.orders",
    "apps.payments",
    "apps.reviews",
    "apps.leads",
    "apps.content",
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [os.path.join(BASE_DIR, "templates")],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ]
        },
    }
]


# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------
# POSTGRES_* are the documented variable names. DB_* are the names this project
# shipped with and are still honoured so existing .env files keep working.

def _db_value(key: str, legacy_key: str, default: str = "") -> str:
    return env_str(key) or env_str(legacy_key, default)


DB_TYPE = env_str("DB_TYPE", "psql")
_USE_POSTGRES = DB_TYPE in ("psql", "postgres", "postgresql") or bool(
    env_str("POSTGRES_DB"))

if _USE_POSTGRES:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": _db_value("POSTGRES_DB", "DB_NAME"),
            "USER": _db_value("POSTGRES_USER", "DB_USER"),
            "PASSWORD": _db_value("POSTGRES_PASSWORD", "DB_PASSWORD"),
            "HOST": _db_value("POSTGRES_HOST", "DB_HOST", "localhost"),
            "PORT": _db_value("POSTGRES_PORT", "DB_PORT", "5432"),
            "CONN_MAX_AGE": env.int("DB_CONN_MAX_AGE", default=60),
            "CONN_HEALTH_CHECKS": True,
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": os.path.join(BASE_DIR, "db.sqlite3"),
        }
    }


# ---------------------------------------------------------------------------
# Redis: cache, Celery broker and result backend
# ---------------------------------------------------------------------------

def _build_redis_url() -> str:
    """Assemble a Redis URL from REDIS_URL, or from REDIS_HOST/PORT/PASSWORD."""
    url = env_str("REDIS_URL")
    if url:
        return url
    host = env_str("REDIS_HOST")
    if not host:
        return ""
    port = env_str("REDIS_PORT", "6379")
    password = env_str("REDIS_PASSWORD")
    db = env_str("REDIS_DB", "0")
    credentials = f":{password}@" if password else ""
    return f"redis://{credentials}{host}:{port}/{db}"


REDIS_URL = _build_redis_url()

if REDIS_URL:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.redis.RedisCache",
            "LOCATION": REDIS_URL,
            "KEY_PREFIX": env_str("CACHE_KEY_PREFIX", "stroyopttorg"),
        }
    }
else:
    # No Redis configured (plain local run) — an in-process cache keeps every
    # cache-aware code path working without a broker.
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "stroyopttorg-locmem",
        }
    }

CACHE_TTL_SHORT = env.int("CACHE_TTL_SHORT", default=60)
CACHE_TTL_MEDIUM = env.int("CACHE_TTL_MEDIUM", default=300)
CACHE_TTL_LONG = env.int("CACHE_TTL_LONG", default=3600)

CELERY_BROKER_URL = env_str(
    "CELERY_BROKER_URL", REDIS_URL or "redis://localhost:6379/0")
CELERY_RESULT_BACKEND = env_str(
    "CELERY_RESULT_BACKEND", CELERY_BROKER_URL)
CELERY_ACCEPT_CONTENT = ["application/json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TASK_SOFT_TIME_LIMIT = env.int(
    "CELERY_TASK_SOFT_TIME_LIMIT", default=60)
CELERY_TASK_TIME_LIMIT = env.int("CELERY_TASK_TIME_LIMIT", default=120)
CELERY_TASK_ALWAYS_EAGER = env.bool("CELERY_TASK_ALWAYS_EAGER", default=False)
CELERY_TASK_EAGER_PROPAGATES = True
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True
CELERY_TIMEZONE = env_str("TIME_ZONE", "Asia/Tashkent")


# ---------------------------------------------------------------------------
# Authentication / passwords
# ---------------------------------------------------------------------------

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation."
             "UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
     "OPTIONS": {"min_length": 8}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation."
             "NumericPasswordValidator"},
]

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(
        minutes=env.int("JWT_ACCESS_TOKEN_LIFETIME", default=60)),
    "REFRESH_TOKEN_LIFETIME": timedelta(
        days=env.int("JWT_REFRESH_TOKEN_LIFETIME", default=7)),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "UPDATE_LAST_LOGIN": True,
    "ALGORITHM": "HS256",
    "SIGNING_KEY": SECRET_KEY,
    "VERIFYING_KEY": None,
    "AUDIENCE": None,
    "ISSUER": None,
    "AUTH_HEADER_TYPES": ("Bearer",),
    "USER_ID_FIELD": "id",
    "USER_ID_CLAIM": "user_id",
    "AUTH_TOKEN_CLASSES": ("rest_framework_simplejwt.tokens.AccessToken",),
    "TOKEN_TYPE_CLAIM": "token_type",
    "JTI_CLAIM": "jti",
}


# ---------------------------------------------------------------------------
# Django REST Framework
# ---------------------------------------------------------------------------
# Permissions are deny-by-default: every public endpoint opts in explicitly
# with AllowAny. That way a new view cannot leak data by omission.

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_PAGINATION_CLASS": "api.pagination.CustomPagination",
    "PAGE_SIZE": env.int("PAGE_SIZE", default=20),
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ],
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
        "rest_framework.throttling.ScopedRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "anon": env_str("THROTTLE_ANON", "300/hour"),
        "user": env_str("THROTTLE_USER", "1000/hour"),
        # Scoped rates guarding credential and one-time-code abuse.
        "login": env_str("THROTTLE_LOGIN", "10/hour"),
        "register": env_str("THROTTLE_REGISTER", "10/hour"),
        "otp": env_str("THROTTLE_OTP", "5/hour"),
        "password_reset": env_str("THROTTLE_PASSWORD_RESET", "5/hour"),
    },
    "EXCEPTION_HANDLER": "api.exceptions.api_exception_handler",
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
}

SPECTACULAR_SETTINGS = {
    "TITLE": "Stroyopttorg API",
    "DESCRIPTION": "REST API for the Stroyopttorg store/marketplace backend.",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "SCHEMA_PATH_PREFIX": "/api/v1",
    "COMPONENT_SPLIT_REQUEST": True,
    "SORT_OPERATIONS": False,
    "TAGS": [
        {"name": "auth", "description": "Registration, verification, login, "
                                        "logout and password reset."},
        {"name": "user", "description": "The signed-in user's own profile, "
                                        "addresses, orders, wishlist and "
                                        "reviews."},
        {"name": "catalog", "description": "Public categories, brands, "
                                           "products and comparison."},
        {"name": "cart", "description": "Cart for guests and signed-in "
                                        "users."},
        {"name": "content", "description": "Home page, news, promotions, "
                                           "banners, FAQ, pages and leads."},
        {"name": "admin", "description": "Staff-only management API."},
        {"name": "ops", "description": "Health checks."},
    ],
}


# ---------------------------------------------------------------------------
# Internationalisation
# ---------------------------------------------------------------------------

LANGUAGE_CODE = env_str("LANGUAGE_CODE", "en-us")
TIME_ZONE = env_str("TIME_ZONE", "Asia/Tashkent")
USE_I18N = True
USE_TZ = True


# ---------------------------------------------------------------------------
# Static and media files
# ---------------------------------------------------------------------------
# STATIC_ROOT is the collectstatic *output* and must never be the same
# directory as the checked-in source assets in STATICFILES_DIRS.

STATIC_URL = "/static/"
STATIC_ROOT = os.path.join(BASE_DIR, "staticfiles")
STATICFILES_DIRS = [os.path.join(BASE_DIR, "static")]

MEDIA_URL = "/media/"
MEDIA_ROOT = os.path.join(BASE_DIR, "media")


# ---------------------------------------------------------------------------
# Email
# ---------------------------------------------------------------------------
# Standard Django semantics: EMAIL_HOST is the SMTP server. Older .env files in
# this project stored the sender address there instead, so a value containing
# "@" is migrated to EMAIL_HOST_USER rather than silently breaking delivery.

_email_host = env_str("EMAIL_HOST")
if "@" in _email_host:
    _legacy_email_user = _email_host
    _email_host = ""
else:
    _legacy_email_user = ""

EMAIL_HOST = _email_host or env_str("EMAIL_SMTP_HOST", "smtp.gmail.com")
EMAIL_PORT = env.int("EMAIL_PORT", default=587)
EMAIL_USE_TLS = env.bool("EMAIL_USE_TLS", default=True)
EMAIL_USE_SSL = env.bool("EMAIL_USE_SSL", default=False)
EMAIL_HOST_USER = env_str("EMAIL_HOST_USER", _legacy_email_user)
EMAIL_HOST_PASSWORD = env_str("EMAIL_HOST_PASSWORD") or env_str(
    "EMAIL_PASSWORD")
DEFAULT_FROM_EMAIL = env_str(
    "DEFAULT_FROM_EMAIL", EMAIL_HOST_USER or "no-reply@localhost")
EMAIL_TIMEOUT = env.int("EMAIL_TIMEOUT", default=10)

# One-time code policy, shared by registration, resend and password reset.
OTP_CODE_TTL_MINUTES = env.int("OTP_CODE_TTL_MINUTES", default=3)
OTP_MAX_ATTEMPTS = env.int("OTP_MAX_ATTEMPTS", default=6)
OTP_RESEND_COOLDOWN_SECONDS = env.int(
    "OTP_RESEND_COOLDOWN_SECONDS", default=60)


# ---------------------------------------------------------------------------
# Security defaults (production tightens these further)
# ---------------------------------------------------------------------------

X_FRAME_OPTIONS = "DENY"
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
SECURE_CROSS_ORIGIN_OPENER_POLICY = "same-origin"

CORS_ALLOWED_ORIGINS = env.list("CORS_ALLOWED_ORIGINS", default=[])
CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS", default=[])
CORS_ALLOW_CREDENTIALS = env.bool("CORS_ALLOW_CREDENTIALS", default=True)


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

LOG_LEVEL = env_str("LOG_LEVEL", "INFO").upper()

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "[{asctime}] {levelname} {name} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
    },
    "root": {"handlers": ["console"], "level": LOG_LEVEL},
    "loggers": {
        "django.request": {
            "handlers": ["console"],
            "level": "WARNING",
            "propagate": False,
        },
        "celery": {
            "handlers": ["console"],
            "level": LOG_LEVEL,
            "propagate": False,
        },
    },
}
