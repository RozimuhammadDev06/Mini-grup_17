"""
Redis/Celery configuration.

Production once shipped a cache pointed at localhost:6379, which made DRF
throttling raise on every request. These tests pin the rules that prevent it.
"""

import importlib

from django.test import SimpleTestCase

from config.settings import base as base_settings


class RedisUrlBuildingTests(SimpleTestCase):
    def _build(self, **env):
        """Rebuild the URL with a patched environment reader."""
        original = base_settings.env_str
        base_settings.env_str = lambda key, default="": env.get(key, default)
        try:
            return base_settings._build_redis_url()
        finally:
            base_settings.env_str = original

    def test_no_configuration_yields_empty_not_localhost(self):
        """The bug: an implicit localhost default became a live cache."""
        self.assertEqual(self._build(), "")

    def test_redis_url_wins(self):
        self.assertEqual(
            self._build(REDIS_URL="rediss://u:p@example.com:6380/1"),
            "rediss://u:p@example.com:6380/1")

    def test_built_from_parts(self):
        self.assertEqual(
            self._build(REDIS_HOST="cache.internal", REDIS_PORT="6380",
                        REDIS_PASSWORD="secret", REDIS_DB="2"),
            "redis://:secret@cache.internal:6380/2")


class MaskUrlTests(SimpleTestCase):
    def test_password_is_hidden(self):
        masked = base_settings.mask_url(
            "rediss://default:SuperSecret@host:6380/0")
        self.assertNotIn("SuperSecret", masked)
        self.assertIn("default:***@host", masked)

    def test_empty_is_reported_not_crashed(self):
        self.assertEqual(base_settings.mask_url(""), "(not configured)")

    def test_url_without_credentials_is_unchanged(self):
        self.assertEqual(base_settings.mask_url("redis://host:6379/0"),
                         "redis://host:6379/0")


class ProductionGuardTests(SimpleTestCase):
    """Production must refuse to start rather than fall back to localhost."""

    def _load_production(self, monkey):
        import os
        saved = {k: os.environ.get(k) for k in monkey}
        os.environ.update({k: v for k, v in monkey.items() if v is not None})
        for k, v in monkey.items():
            if v is None:
                os.environ.pop(k, None)
        try:
            module = importlib.import_module("config.settings.production")
            importlib.reload(module)
            return module
        finally:
            for k, v in saved.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v

    def test_missing_redis_url_raises(self):
        from django.core.exceptions import ImproperlyConfigured
        with self.assertRaises(ImproperlyConfigured) as ctx:
            self._load_production({
                "REDIS_URL": None, "REDIS_HOST": None,
                "REDIS_REQUIRED": "True",
                "SECRET_KEY": "x" * 50, "ALLOWED_HOSTS": "example.com",
            })
        self.assertIn("REDIS_URL", str(ctx.exception))

    def test_explicit_opt_out_is_allowed(self):
        module = self._load_production({
            "REDIS_URL": None, "REDIS_HOST": None,
            "REDIS_REQUIRED": "False",
            "SECRET_KEY": "x" * 50, "ALLOWED_HOSTS": "example.com",
        })
        self.assertFalse(module.REDIS_REQUIRED)
