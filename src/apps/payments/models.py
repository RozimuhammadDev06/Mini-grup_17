from django.db import models


class Payment(models.Model):
    """Payment attempt at an external gateway. Webhooks update `status`."""

    class Provider(models.TextChoices):
        YOOKASSA = 'yookassa', 'YooKassa'
        TINKOFF = 'tinkoff', 'Tinkoff'
        MANUAL = 'manual', 'Manual'

    class PaymentType(models.TextChoices):
        CARD = 'card', 'Card'
        SBP = 'sbp', 'SBP'
        CASH = 'cash', 'Cash'
        INVOICE = 'invoice', 'Invoice'

    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        SUCCEEDED = 'succeeded', 'Succeeded'
        CANCELLED = 'cancelled', 'Cancelled'
        FAILED = 'failed', 'Failed'
        REFUNDED = 'refunded', 'Refunded'

    order = models.ForeignKey(
        'orders.Order', on_delete=models.CASCADE, related_name='payments')
    provider = models.CharField(
        max_length=30, choices=Provider.choices, default=Provider.YOOKASSA)
    provider_id = models.CharField(max_length=128, blank=True)
    payment_type = models.CharField(
        max_length=20, choices=PaymentType.choices, default=PaymentType.CARD)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING)
    amount = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        verbose_name = 'Payment'
        verbose_name_plural = 'Payments'
        unique_together = ('provider', 'provider_id')
        indexes = [
            models.Index(fields=['status']),
        ]

    def __str__(self):
        return f'{self.order} | {self.provider} | {self.status}'
