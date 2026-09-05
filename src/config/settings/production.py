"""
Production settings.

TLS-dependent hardening is toggled by ``SECURE_SSL_ENABLED`` so the stack can
also run behind a TLS-terminating proxy or in a staging environment without
HTTPS, without editing code.
"""

from django.core.exceptions import ImproperlyConfigured

from .base import *  # noqa: F401,F403
from .base import REDIS_URL, env, env_str

DEBUG = False

ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=[])

# ---------------------------------------------------------------------------
# Redis is mandatory in production
# ---------------------------------------------------------------------------
# DRF throttling writes to the cache on *every* request, so a cache pointed at
# a Redis that is not there turns every endpoint into a 500. Refuse to start
# rather than fall back to localhost or to a per-process LocMemCache that would
# silently break rate limiting and the home-page cache across workers.
REDIS_REQUIRED = env.bool("REDIS_REQUIRED", default=True)

if REDIS_REQUIRED and not REDIS_URL:
    raise ImproperlyConfigured(
        "REDIS_URL is not configured. Production uses Redis for the cache, "
        "DRF throttling and the Celery broker.\n"
        "Set REDIS_URL (for example rediss://default:<password>@<host>:<port>/0) "
        "in the deployment environment.\n"
        "To run without Redis on purpose — accepting per-process throttling "
        "and no shared cache — set REDIS_REQUIRED=False explicitly."
    )

EMAIL_BACKEND = env_str(
    "EMAIL_BACKEND", "django.core.mail.backends.smtp.EmailBackend")

# Behind Nginx/Traefik the original scheme arrives in this header.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
USE_X_FORWARDED_HOST = True

SECURE_SSL_ENABLED = env.bool("SECURE_SSL_ENABLED", default=True)

SECURE_SSL_REDIRECT = SECURE_SSL_ENABLED
SESSION_COOKIE_SECURE = SECURE_SSL_ENABLED
CSRF_COOKIE_SECURE = SECURE_SSL_ENABLED

SECURE_HSTS_SECONDS = env.int(
    "SECURE_HSTS_SECONDS", default=31536000) if SECURE_SSL_ENABLED else 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = SECURE_SSL_ENABLED
SECURE_HSTS_PRELOAD = SECURE_SSL_ENABLED

SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = False  # the SPA must read the token to send it back
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"

# Deliberately no CORS_ALLOW_ALL_ORIGINS here: origins come from
# CORS_ALLOWED_ORIGINS in the environment.
