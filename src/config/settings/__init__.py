"""
Environment dispatch.

``DJANGO_SETTINGS_MODULE`` points at this package; the ``DEBUG`` variable
decides whether development or production settings are loaded.
"""

import os

import environ

BASE_DIR = os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))))
environ.Env.read_env(os.path.join(BASE_DIR, ".env"))

_TRUTHY = ("1", "true", "yes", "on")
DEBUG = os.environ.get("DEBUG", "1").strip().lower() in _TRUTHY

if DEBUG:
    from .development import *  # noqa: F401,F403
else:
    from .production import *  # noqa: F401,F403
