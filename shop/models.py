from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


class Category(models.Model):
    name = models.CharField(max_length=100)
    image = models.ImageField(upload_to='category_images/')

    def __str__(self):
        return self.name


class Product(models.Model):
    name = models.CharField(max_length=200)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=100)
    description = models.TextField(null=True, blank=True)
    quantity = models.PositiveIntegerField(default=0)
    category = models.ForeignKey(
        Category,
        on_delete=models.CASCADE,
        related_name='products',
    )
    image = models.ImageField(upload_to='product_images/', null=True, blank=True)

    @property
    def active_discount(self):
        now = timezone.now()
        return self.discounts.filter(
            is_active=True,
            starts_at__lte=now,
            ends_at__gt=now,
        ).order_by('starts_at').first()

    @property
    def price_after_discount(self):
        discount = self.active_discount
        if not discount:
            return self.price

        multiplier = (Decimal('100') - discount.percent) / Decimal('100')
        price = Decimal(str(self.price))
        return (price * multiplier).quantize(Decimal('0.01'))

    def __str__(self):
        return self.name


class Message(models.Model):
    name = models.CharField(max_length=100)
    email = models.EmailField()
    message = models.TextField(null=False, blank=False)

    def __str__(self):
        return self.name


class Review(models.Model):
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='reviews',
    )
    name = models.CharField(max_length=100)
    email = models.EmailField()
    review = models.TextField(null=False, blank=False)

    def __str__(self):
        return f'{self.name} - {self.product.name}'


class ProductDiscount(models.Model):
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='discounts',
    )
    title = models.CharField(max_length=100, blank=True)
    percent = models.DecimalField(max_digits=5, decimal_places=2)
    starts_at = models.DateTimeField(default=timezone.now)
    ends_at = models.DateTimeField()
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('-starts_at',)
        constraints = [
            models.CheckConstraint(
                condition=models.Q(percent__gt=0, percent__lte=100),
                name='product_discount_percent_between_1_and_100',
            ),
            models.CheckConstraint(
                condition=models.Q(ends_at__gt=models.F('starts_at')),
                name='product_discount_ends_after_start',
            ),
        ]

    def clean(self):
        if self.ends_at and self.starts_at and self.ends_at <= self.starts_at:
            raise ValidationError({'ends_at': 'پایان تخفیف باید بعد از زمان شروع باشد.'})

        if self.percent is not None and not 0 < self.percent <= 100:
            raise ValidationError({'percent': 'درصد تخفیف باید بین ۱ تا ۱۰۰ باشد.'})

        if self.product_id and self.starts_at and self.ends_at:
            overlaps = ProductDiscount.objects.filter(
                product_id=self.product_id,
                is_active=True,
                starts_at__lt=self.ends_at,
                ends_at__gt=self.starts_at,
            ).exclude(pk=self.pk)
            if overlaps.exists():
                raise ValidationError(
                    'برای این محصول در این بازه، یک تخفیف فعال دیگر وجود دارد.'
                )

    @property
    def is_current(self):
        now = timezone.now()
        return self.is_active and self.starts_at <= now < self.ends_at

    def __str__(self):
        return f'{self.product.name} - {self.percent}%'
