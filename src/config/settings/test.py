"""
Settings for the automated test suite.

Rate limiting, Redis and the real broker are all disabled: they make tests
slow and non-deterministic without exercising any application logic.
"""

from .development import *  # noqa: F401,F403
from .development import REST_FRAMEWORK

DEBUG = False

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "test-cache",
    }
}

# Throttling would reject legitimate requests once a test class issues more
# than a handful of calls from the same "client".
REST_FRAMEWORK = {**REST_FRAMEWORK, "DEFAULT_THROTTLE_CLASSES": []}

EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"

CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True

PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

MEDIA_ROOT = "/tmp/stroyopttorg-test-media"

# Payment gateway test fixtures. These are NOT credentials — they exist so the
# payments configuration check passes under DEBUG=False and so signature tests
# have a deterministic secret. Real values come from the environment.
FINTECHHUB_MERCHANT_USER_ID = "TEST-MERCHANT"
FINTECHHUB_MERCHANT_SECRET_KEY = "test-merchant-secret"
FINTECHHUB_SERVICE_SECRET_KEY = "test-service-secret"
FINTECHHUB_SERVICE_ID = 1
FINTECHHUB_VERIFY_SIGNATURE = True
# Off by default here too, so the default PCI posture is what gets tested.
FINTECHHUB_ENABLE_CARD_TOKENIZATION = False
