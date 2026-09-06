from django.db import models


class ShippingMethod(models.Model):
    name = models.CharField(max_length=100)
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    estimated_delivery_days = models.PositiveSmallIntegerField(default=1)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name


class Order(models.Model):
    class Status(models.TextChoices):
        PENDING = 'pending', 'در انتظار بررسی'
        PROCESSING = 'processing', 'در حال پردازش'
        SHIPPED = 'shipped', 'ارسال شده'
        DELIVERED = 'delivered', 'تحویل داده شده'
        CANCELED = 'canceled', 'لغو شده'

    user = models.ForeignKey(
        'account.User',
        on_delete=models.PROTECT,
        related_name='orders',
    )
    address = models.ForeignKey(
        'account.Address',
        on_delete=models.PROTECT,
        related_name='orders',
    )
    shipping_method = models.ForeignKey(
        ShippingMethod,
        on_delete=models.PROTECT,
        related_name='orders',
        null=True,
        blank=True,
    )
    shipping_cost = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        editable=False,
    )
    tax_amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=0,
        editable=False,
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('-created_at',)
        constraints = [
            models.CheckConstraint(
                condition=models.Q(tax_amount__gte=0),
                name='order_tax_amount_is_not_negative',
            ),
        ]

    def __str__(self):
        return f'Order #{self.pk}'


class OrderItem(models.Model):
    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name='items',
    )
    product = models.ForeignKey(
        'shop.Product',
        on_delete=models.PROTECT,
        related_name='order_items',
    )
    quantity = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        editable=False,
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=('order', 'product'),
                name='one_order_item_per_product',
            ),
            models.CheckConstraint(
                condition=models.Q(quantity__gt=0),
                name='order_item_quantity_must_be_positive',
            ),
        ]

    def __str__(self):
        return f'{self.product} x {self.quantity}'
