from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone


class PromoCode(models.Model):
    class Type(models.TextChoices):
        PERCENT = 'percent', 'Percent'
        FIXED = 'fixed', 'Fixed amount'

    code = models.CharField(max_length=50, unique=True)
    type = models.CharField(
        max_length=20, choices=Type.choices, default=Type.PERCENT)
    value = models.DecimalField(max_digits=12, decimal_places=2)
    min_order = models.DecimalField(
        max_digits=12, decimal_places=2, default=0)
    valid_to = models.DateTimeField(null=True, blank=True)
    usage_limit = models.IntegerField(null=True, blank=True)
    used_count = models.IntegerField(default=0)

    class Meta:
        verbose_name = 'Promo code'
        verbose_name_plural = 'Promo codes'
        ordering = ('code',)

    def __str__(self):
        return self.code

    def is_expired(self):
        return bool(self.valid_to and self.valid_to < timezone.now())

    def is_exhausted(self):
        return bool(self.usage_limit and self.used_count >= self.usage_limit)

    def is_valid(self, subtotal):
        return (not self.is_expired()
                and not self.is_exhausted()
                and subtotal >= self.min_order)

    def discount_for(self, subtotal):
        if not self.is_valid(subtotal):
            return 0
        if self.type == self.Type.PERCENT:
            return subtotal * self.value / 100
        return min(self.value, subtotal)


class DiscountTier(models.Model):
    """Cart-total based discount: spend `threshold`, get `percent` off."""

    threshold = models.DecimalField(max_digits=12, decimal_places=2)
    percent = models.IntegerField(
        validators=[MinValueValidator(0), MaxValueValidator(100)])
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'Discount tier'
        verbose_name_plural = 'Discount tiers'
        ordering = ('threshold',)

    def __str__(self):
        return f'{self.threshold} -> {self.percent}%'
