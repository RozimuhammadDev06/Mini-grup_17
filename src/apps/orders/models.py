from django.conf import settings
from django.db import models


class Order(models.Model):
    """
    Order. Prices, name and article are snapshotted at checkout time so that
    the next price/nomenclature import from 1C cannot change a placed order.
    """

    class Status(models.TextChoices):
        NEW = 'new', 'New'
        AWAITING_PAYMENT = 'awaiting_payment', 'Awaiting payment'
        PROCESSING = 'processing', 'Processing'
        ASSEMBLED = 'assembled', 'Assembled'
        SHIPPED = 'shipped', 'Shipped'
        READY_FOR_PICKUP = 'ready_for_pickup', 'Ready for pickup'
        COMPLETED = 'completed', 'Completed'
        CANCELLED = 'cancelled', 'Cancelled'
        REFUNDED = 'refunded', 'Refunded'

    class DeliveryType(models.TextChoices):
        DELIVERY = 'delivery', 'Delivery'
        PICKUP = 'pickup', 'Pickup'

    class PaymentMethod(models.TextChoices):
        CARD = 'card', 'Card online'
        ON_DELIVERY = 'on_delivery', 'On delivery'
        INVOICE = 'invoice', 'Invoice'

    number = models.CharField(max_length=32, unique=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
        blank=True, related_name='orders')
    status = models.CharField(
        max_length=32, choices=Status.choices, default=Status.NEW)
    delivery_type = models.CharField(
        max_length=20, choices=DeliveryType.choices,
        default=DeliveryType.DELIVERY)
    address_snapshot = models.JSONField(default=dict, blank=True)
    payment_method = models.CharField(
        max_length=20, choices=PaymentMethod.choices,
        default=PaymentMethod.CARD)
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    cart_discount = models.DecimalField(
        max_digits=12, decimal_places=2, default=0)
    promo_discount = models.DecimalField(
        max_digits=12, decimal_places=2, default=0)
    delivery_cost = models.DecimalField(
        max_digits=12, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    paid_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'Order'
        verbose_name_plural = 'Orders'
        ordering = ('-created_at',)
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['user', '-created_at']),
        ]

    def __str__(self):
        return f'Order {self.number}'

    @property
    def is_paid(self):
        return self.paid_at is not None

    def recalculate_total(self):
        self.total = (self.subtotal
                      - self.cart_discount
                      - self.promo_discount
                      + self.delivery_cost)
        return self.total


class OrderItem(models.Model):
    order = models.ForeignKey(
        Order, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(
        'catalog.Product', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='order_items')
    name_snapshot = models.CharField(max_length=255)
    article_snapshot = models.CharField(max_length=64)
    price = models.DecimalField(max_digits=12, decimal_places=2)
    quantity = models.PositiveIntegerField(default=1)

    class Meta:
        verbose_name = 'Order item'
        verbose_name_plural = 'Order items'

    def __str__(self):
        return f'{self.article_snapshot} x {self.quantity}'

    @property
    def total(self):
        return self.price * self.quantity
