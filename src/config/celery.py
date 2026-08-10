import os

from celery import Celery

# Points at the dispatch package, not a concrete module, so the worker honours
# the same development/production selection as the web process.
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

app = Celery("stroyopttorg")

# Every CELERY_-prefixed Django setting becomes a Celery setting.
app.config_from_object("django.conf:settings", namespace="CELERY")

app.autodiscover_tasks()
# The API layer is not an installed app, so its tasks module needs naming.
app.autodiscover_tasks(["api.auth"])
