from django.db import models


class Region(models.Model):
    name = models.CharField(max_length=150, unique=True)

    class Meta:
        verbose_name = 'Region'
        verbose_name_plural = 'Regions'
        ordering = ('name',)

    def __str__(self):
        return self.name


class DeliveryZone(models.Model):
    name = models.CharField(max_length=150)
    base_cost = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    per_kg = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    class Meta:
        verbose_name = 'Delivery zone'
        verbose_name_plural = 'Delivery zones'
        ordering = ('name',)

    def __str__(self):
        return self.name

    def cost_for(self, weight_kg):
        return self.base_cost + self.per_kg * weight_kg


class City(models.Model):
    region = models.ForeignKey(
        Region, on_delete=models.CASCADE, related_name='cities')
    name = models.CharField(max_length=150)
    delivery_zone = models.ForeignKey(
        DeliveryZone, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='cities')

    class Meta:
        verbose_name = 'City'
        verbose_name_plural = 'Cities'
        ordering = ('name',)
        unique_together = ('region', 'name')

    def __str__(self):
        return f'{self.name} ({self.region.name})'
