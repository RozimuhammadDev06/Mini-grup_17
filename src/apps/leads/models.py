from django.db import models


class Lead(models.Model):
    """Request from a site form: callback, price request, one-click buy."""

    class Type(models.TextChoices):
        CALLBACK = 'callback', 'Callback'
        PRICE_REQUEST = 'price_request', 'Price request'
        CONSULTATION = 'consultation', 'Consultation'
        ONE_CLICK = 'one_click', 'One-click buy'

    class Status(models.TextChoices):
        NEW = 'new', 'New'
        IN_PROGRESS = 'in_progress', 'In progress'
        DONE = 'done', 'Done'
        REJECTED = 'rejected', 'Rejected'

    type = models.CharField(
        max_length=30, choices=Type.choices, default=Type.CALLBACK)
    name = models.CharField(max_length=150)
    phone = models.CharField(max_length=20)
    product = models.ForeignKey(
        'catalog.Product', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='leads')
    consent = models.BooleanField(default=False)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.NEW)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Lead'
        verbose_name_plural = 'Leads'
        ordering = ('-created_at',)
        indexes = [
            models.Index(fields=['status']),
        ]

    def __str__(self):
        return f'{self.get_type_display()} | {self.name} | {self.phone}'
