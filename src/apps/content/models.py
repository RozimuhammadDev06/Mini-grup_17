from django.db import models


class Article(models.Model):
    class Type(models.TextChoices):
        NEWS = 'news', 'News'
        ARTICLE = 'article', 'Article'
        BLOG = 'blog', 'Blog'

    type = models.CharField(
        max_length=20, choices=Type.choices, default=Type.NEWS)
    title = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, unique=True)
    body = models.TextField(blank=True)
    image = models.ImageField(upload_to='articles/', null=True, blank=True)
    published_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'Article'
        verbose_name_plural = 'Articles'
        ordering = ('-published_at',)

    def __str__(self):
        return self.title

    @property
    def is_published(self):
        return self.published_at is not None


class Promotion(models.Model):
    title = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, unique=True)
    body = models.TextField(blank=True)
    image = models.ImageField(upload_to='promotions/', null=True, blank=True)
    discount_label = models.CharField(max_length=50, blank=True)
    valid_until = models.DateField(null=True, blank=True)
    category = models.ForeignKey(
        'catalog.Category', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='promotions')

    class Meta:
        verbose_name = 'Promotion'
        verbose_name_plural = 'Promotions'
        ordering = ('-valid_until',)

    def __str__(self):
        return self.title


class Banner(models.Model):
    title = models.CharField(max_length=255, blank=True)
    image = models.ImageField(upload_to='banners/')
    link = models.CharField(max_length=500, blank=True)
    sort = models.IntegerField(default=0)

    class Meta:
        verbose_name = 'Banner'
        verbose_name_plural = 'Banners'
        ordering = ('sort',)

    def __str__(self):
        return self.title or f'Banner #{self.id}'


class Faq(models.Model):
    question = models.TextField()
    answer = models.TextField()
    sort = models.IntegerField(default=0)

    class Meta:
        verbose_name = 'FAQ'
        verbose_name_plural = 'FAQ'
        ordering = ('sort',)

    def __str__(self):
        return self.question[:80]


class StaticPage(models.Model):
    """Delivery, payment, contacts, privacy policy and other flat pages."""

    slug = models.SlugField(max_length=200, unique=True)
    title = models.CharField(max_length=255)
    body = models.TextField(blank=True)

    class Meta:
        verbose_name = 'Static page'
        verbose_name_plural = 'Static pages'
        ordering = ('title',)

    def __str__(self):
        return self.title
