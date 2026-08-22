from django.db import models


class Payment(models.Model):
    """Payment attempt at an external gateway. Webhooks update `status`."""

    class Provider(models.TextChoices):
        FINTECHHUB = 'fintechhub', 'Fintechhub'
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
        max_length=30, choices=Provider.choices, default=Provider.FINTECHHUB)
    provider_id = models.CharField(max_length=128, blank=True)
    payment_type = models.CharField(
        max_length=20, choices=PaymentType.choices, default=PaymentType.CARD)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING)
    amount = models.DecimalField(max_digits=12, decimal_places=2)

    # Shop API correlation ids. The gateway replays prepare/complete, so these
    # are what make the callbacks idempotent: once set, they are returned
    # unchanged instead of the work being done twice.
    merchant_prepare_id = models.BigIntegerField(null=True, blank=True)
    merchant_confirm_id = models.BigIntegerField(null=True, blank=True)
    # Last raw callback/response payload, kept for reconciliation disputes.
    raw_response = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Payment'
        verbose_name_plural = 'Payments'
        ordering = ('-created_at',)
        constraints = [
            # provider_id is blank until the gateway assigns one, so the
            # uniqueness guarantee must skip those rows.
            models.UniqueConstraint(
                fields=('provider', 'provider_id'),
                condition=~models.Q(provider_id=''),
                name='unique_provider_payment_id',
            ),
        ]
        indexes = [
            models.Index(fields=['status']),
        ]

    def __str__(self):
        return f'{self.order} | {self.provider} | {self.status}'
