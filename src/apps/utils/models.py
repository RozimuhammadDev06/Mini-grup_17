from django.conf import settings
from django.db import models


class TimeStampedModel(models.Model):
    """Creation and modification timestamps, without audit columns."""

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class BaseModel(TimeStampedModel):
    """Timestamps plus who created/updated/deleted the row, and soft deletion."""

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        related_name='%(app_label)s_%(class)s_created', null=True, blank=True)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        related_name='%(app_label)s_%(class)s_updated', null=True, blank=True)
    deleted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        related_name='%(app_label)s_%(class)s_deleted', null=True, blank=True)
    is_deleted = models.BooleanField(default=False, db_index=True)

    class Meta:
        abstract = True
