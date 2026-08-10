"""Development settings: permissive CORS, no TLS enforcement, loud errors."""

from .base import *  # noqa: F401,F403
from .base import EMAIL_HOST_PASSWORD, EMAIL_HOST_USER, env, env_str

DEBUG = True

# Development is never exposed, and the test client uses the "testserver"
# host, so this stays open regardless of ALLOWED_HOSTS in .env.
ALLOWED_HOSTS = ["*"]

CORS_ALLOW_ALL_ORIGINS = env.bool("CORS_ALLOW_ALL_ORIGINS", default=True)
CORS_ALLOW_CREDENTIALS = True

# Real SMTP is used when credentials are present, so an existing local .env
# keeps sending mail; otherwise messages are printed to the console.
EMAIL_BACKEND = env_str("EMAIL_BACKEND") or (
    "django.core.mail.backends.smtp.EmailBackend"
    if EMAIL_HOST_USER and EMAIL_HOST_PASSWORD
    else "django.core.mail.backends.console.EmailBackend"
)
