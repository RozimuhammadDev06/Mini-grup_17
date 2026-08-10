from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class Review(models.Model):
    """
    A rating with a comment. ``product`` is null for site-wide testimonials,
    which is what the original ERD modelled; product reviews set it.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
        blank=True, related_name='reviews')
    product = models.ForeignKey(
        'catalog.Product', on_delete=models.CASCADE, null=True, blank=True,
        related_name='reviews')
    author_name = models.CharField(max_length=150)
    rating = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)])
    comment = models.TextField(blank=True)
    is_published = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Review'
        verbose_name_plural = 'Reviews'
        ordering = ('-created_at',)
        constraints = [
            models.UniqueConstraint(
                fields=('user', 'product'),
                condition=models.Q(user__isnull=False,
                                   product__isnull=False),
                name='unique_review_per_user_and_product',
            ),
        ]
        indexes = [
            models.Index(fields=['product', 'is_published']),
        ]

    def __str__(self):
        return f'{self.author_name} | {self.rating}'
