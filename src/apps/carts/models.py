from django.conf import settings
from django.db import models


class Cart(models.Model):
    """Cart of a logged-in user, or of a guest identified by `session_key`."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True,
        blank=True, related_name='carts')
    session_key = models.CharField(max_length=64, null=True, blank=True)
    promo_code = models.ForeignKey(
        'discounts.PromoCode', on_delete=models.SET_NULL, null=True,
        blank=True, related_name='carts')
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Cart'
        verbose_name_plural = 'Carts'
        ordering = ('-updated_at',)
        indexes = [
            models.Index(fields=['session_key']),
        ]

    def __str__(self):
        return f'Cart #{self.id} | {self.user or self.session_key}'

    @property
    def subtotal(self):
        return sum((item.total for item in self.items.all()), 0)


class CartItem(models.Model):
    cart = models.ForeignKey(
        Cart, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(
        'catalog.Product', on_delete=models.CASCADE, related_name='cart_items')
    quantity = models.PositiveIntegerField(default=1)
    price = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        verbose_name = 'Cart item'
        verbose_name_plural = 'Cart items'
        unique_together = ('cart', 'product')

    def __str__(self):
        return f'{self.product} x {self.quantity}'

    @property
    def total(self):
        return self.price * self.quantity


class Wishlist(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='wishlist')
    product = models.ForeignKey(
        'catalog.Product', on_delete=models.CASCADE, related_name='wishlisted')

    class Meta:
        verbose_name = 'Wishlist item'
        verbose_name_plural = 'Wishlist items'
        unique_together = ('user', 'product')

    def __str__(self):
        return f'{self.user} | {self.product}'


class Compare(models.Model):
    """Comparison list. Products are compared within one category."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True,
        blank=True, related_name='compares')
    session_key = models.CharField(max_length=64, null=True, blank=True)
    product = models.ForeignKey(
        'catalog.Product', on_delete=models.CASCADE, related_name='compares')
    category = models.ForeignKey(
        'catalog.Category', on_delete=models.CASCADE, related_name='compares')

    class Meta:
        verbose_name = 'Compare item'
        verbose_name_plural = 'Compare items'
        unique_together = ('user', 'session_key', 'product')
        indexes = [
            models.Index(fields=['session_key']),
        ]

    def __str__(self):
        return f'{self.user or self.session_key} | {self.product}'
