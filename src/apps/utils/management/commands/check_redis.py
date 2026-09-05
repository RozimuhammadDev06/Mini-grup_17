"""
Verify the configured cache/broker end to end.

Prints the resolved configuration with credentials masked, then performs a
real cache round-trip. Intended to be run on the deployment host, where the
answer to "is Redis reachable from here?" is the whole question.
"""

from django.conf import settings
from django.core.cache import cache
from django.core.management.base import BaseCommand

from config.settings.base import mask_url


class Command(BaseCommand):
    help = "Report the cache/Celery configuration and test Redis connectivity."

    def add_arguments(self, parser):
        parser.add_argument(
            "--fail", action="store_true",
            help="Exit non-zero when the cache round-trip fails (for CI).")

    def handle(self, *args, **options):
        backend = settings.CACHES["default"]["BACKEND"]
        self.stdout.write(self.style.MIGRATE_HEADING("Configuration"))
        self.stdout.write(f"  DEBUG            : {settings.DEBUG}")
        self.stdout.write(f"  REDIS_URL        : {mask_url(settings.REDIS_URL)}")
        self.stdout.write(
            f"  CELERY_BROKER    : {mask_url(settings.CELERY_BROKER_URL)}")
        self.stdout.write(
            f"  CELERY_RESULT    : "
            f"{mask_url(settings.CELERY_RESULT_BACKEND)}")
        self.stdout.write(f"  CACHE BACKEND    : {backend}")
        self.stdout.write(
            f"  TLS (rediss://)  : {getattr(settings, 'REDIS_IS_TLS', False)}")

        if "locmem" in backend:
            self.stdout.write(self.style.WARNING(
                "\nUsing LocMemCache — throttle counters live in one process "
                "only and are lost on restart. Acceptable for local "
                "development; not for production."))

        self.stdout.write(self.style.MIGRATE_HEADING("\nCache round-trip"))
        try:
            cache.set("healthcheck:redis", "ok", 30)
            value = cache.get("healthcheck:redis")
            cache.delete("healthcheck:redis")
        except Exception as exc:
            # The message can embed the connection string, so mask it.
            self.stdout.write(self.style.ERROR(
                f"  FAILED: {type(exc).__name__}: {mask_url(str(exc))}"))
            if options["fail"]:
                raise SystemExit(1)
            return

        if value == "ok":
            self.stdout.write(self.style.SUCCESS("  set/get/delete: OK"))
        else:
            self.stdout.write(self.style.ERROR(
                f"  set/get returned {value!r}, expected 'ok'"))
            if options["fail"]:
                raise SystemExit(1)
