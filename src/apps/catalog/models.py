from django.db import models


class Attribute(models.Model):
    """Characteristic a product can be filtered / compared by ("Power, W")."""

    class Type(models.TextChoices):
        STRING = 'string', 'String'
        NUMBER = 'number', 'Number'
        BOOL = 'bool', 'Boolean'
        CHOICE = 'choice', 'Choice'

    code = models.SlugField(max_length=100, unique=True)
    name = models.CharField(max_length=150)
    unit = models.CharField(max_length=30, blank=True)
    type = models.CharField(
        max_length=20, choices=Type.choices, default=Type.STRING)
    is_filterable = models.BooleanField(default=True)
    is_comparable = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'Attribute'
        verbose_name_plural = 'Attributes'
        ordering = ('name',)

    def __str__(self):
        return f'{self.name}, {self.unit}' if self.unit else self.name


class AttributeValue(models.Model):
    """Predefined value of an attribute — the source of facet options."""

    attribute = models.ForeignKey(
        Attribute, on_delete=models.CASCADE, related_name='values')
    value_string = models.CharField(max_length=255, blank=True)
    value_number = models.DecimalField(
        max_digits=14, decimal_places=4, null=True, blank=True)

    class Meta:
        verbose_name = 'Attribute value'
        verbose_name_plural = 'Attribute values'
        ordering = ('attribute', 'value_number', 'value_string')
        unique_together = ('attribute', 'value_string', 'value_number')

    def __str__(self):
        return self.value_string or str(self.value_number)


class Category(models.Model):
    parent = models.ForeignKey(
        'self', on_delete=models.CASCADE, null=True, blank=True,
        related_name='children')
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=200, unique=True)
    sort = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'Category'
        verbose_name_plural = 'Categories'
        ordering = ('sort', 'name')

    def __str__(self):
        return self.name


class CategoryAttribute(models.Model):
    """Which attributes are shown as filters inside a category, and in what order."""

    category = models.ForeignKey(
        Category, on_delete=models.CASCADE, related_name='category_attributes')
    attribute = models.ForeignKey(
        Attribute, on_delete=models.CASCADE, related_name='category_attributes')
    sort = models.IntegerField(default=0)

    class Meta:
        verbose_name = 'Category attribute'
        verbose_name_plural = 'Category attributes'
        ordering = ('sort',)
        unique_together = ('category', 'attribute')

    def __str__(self):
        return f'{self.category} | {self.attribute}'


class Brand(models.Model):
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=200, unique=True)
    logo = models.ImageField(upload_to='brands/', null=True, blank=True)

    class Meta:
        verbose_name = 'Brand'
        verbose_name_plural = 'Brands'
        ordering = ('name',)

    def __str__(self):
        return self.name


class Product(models.Model):
    category = models.ForeignKey(
        Category, on_delete=models.PROTECT, related_name='products')
    brand = models.ForeignKey(
        Brand, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='products')
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, unique=True)
    article = models.CharField(max_length=64, unique=True)
    price = models.DecimalField(max_digits=12, decimal_places=2)
    old_price = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True)
    attrs_json = models.JSONField(default=dict, blank=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    is_featured = models.BooleanField(default=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Product'
        verbose_name_plural = 'Products'
        ordering = ('-created_at',)
        indexes = [
            models.Index(fields=['category', 'is_active']),
            models.Index(fields=['price']),
        ]

    def __str__(self):
        return f'{self.article} | {self.name}'

    @property
    def discount_percent(self):
        if not self.old_price or self.old_price <= self.price:
            return 0
        return round((self.old_price - self.price) / self.old_price * 100)


class ProductImage(models.Model):
    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(upload_to='products/')
    sort = models.IntegerField(default=0)
    is_main = models.BooleanField(default=False)

    class Meta:
        verbose_name = 'Product image'
        verbose_name_plural = 'Product images'
        ordering = ('-is_main', 'sort')

    def __str__(self):
        return f'{self.product} | {self.sort}'


class ProductAttribute(models.Model):
    """Value of an attribute for a concrete product."""

    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name='product_attributes')
    attribute = models.ForeignKey(
        Attribute, on_delete=models.CASCADE, related_name='product_attributes')
    value = models.ForeignKey(
        AttributeValue, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='product_attributes')
    value_number = models.DecimalField(
        max_digits=14, decimal_places=4, null=True, blank=True)

    class Meta:
        verbose_name = 'Product attribute'
        verbose_name_plural = 'Product attributes'
        unique_together = ('product', 'attribute', 'value')
        indexes = [
            models.Index(fields=['attribute', 'value']),
        ]

    def __str__(self):
        return f'{self.product} | {self.attribute}'


class Stock(models.Model):
    """Quantity synced from 1C. One row per product."""

    class Status(models.TextChoices):
        IN_STOCK = 'in_stock', 'In stock'
        LOW_STOCK = 'low_stock', 'Low stock'
        OUT_OF_STOCK = 'out_of_stock', 'Out of stock'
        ON_ORDER = 'on_order', 'On order'

    product = models.OneToOneField(
        Product, on_delete=models.CASCADE, related_name='stock')
    quantity = models.IntegerField(default=0)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.OUT_OF_STOCK)
    synced_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'Stock'
        verbose_name_plural = 'Stocks'

    def __str__(self):
        return f'{self.product} | {self.quantity}'
