from django.db import models


class Invoice(models.Model):
    class Status(models.TextChoices):
        ISSUED = 'issued', 'صادرشده'
        REFUNDED = 'refunded', 'بازگشت وجه'

    number = models.CharField(max_length=30, unique=True, editable=False)
    order = models.OneToOneField(
        'orders.Order',
        on_delete=models.PROTECT,
        related_name='invoice',
    )
    payment = models.OneToOneField(
        'payments.Payment',
        on_delete=models.PROTECT,
        related_name='invoice',
    )
    user = models.ForeignKey(
        'account.User',
        on_delete=models.PROTECT,
        related_name='invoices',
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.ISSUED,
        editable=False,
    )

    buyer_name = models.CharField(max_length=150, editable=False)
    buyer_phone = models.CharField(max_length=15, editable=False)
    buyer_email = models.EmailField(blank=True, editable=False)
    province = models.CharField(max_length=100, editable=False)
    city = models.CharField(max_length=100, editable=False)
    address = models.TextField(editable=False)
    postal_code = models.CharField(max_length=10, editable=False)

    subtotal = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        editable=False,
    )
    shipping_cost = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        editable=False,
    )
    tax_amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=0,
        editable=False,
    )
    total_amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        editable=False,
    )
    payment_gateway = models.CharField(max_length=20, editable=False)
    payment_reference = models.CharField(max_length=100, editable=False)
    issued_at = models.DateTimeField(editable=False)
    refunded_at = models.DateTimeField(null=True, blank=True, editable=False)

    class Meta:
        ordering = ('-issued_at',)
        constraints = [
            models.CheckConstraint(
                condition=models.Q(subtotal__gte=0),
                name='invoice_subtotal_is_not_negative',
            ),
            models.CheckConstraint(
                condition=models.Q(shipping_cost__gte=0),
                name='invoice_shipping_cost_is_not_negative',
            ),
            models.CheckConstraint(
                condition=models.Q(tax_amount__gte=0),
                name='invoice_tax_amount_is_not_negative',
            ),
            models.CheckConstraint(
                condition=models.Q(total_amount__gt=0),
                name='invoice_total_amount_is_positive',
            ),
        ]

    def __str__(self):
        return self.number


class InvoiceItem(models.Model):
    invoice = models.ForeignKey(
        Invoice,
        on_delete=models.CASCADE,
        related_name='items',
    )
    product = models.ForeignKey(
        'shop.Product',
        on_delete=models.SET_NULL,
        related_name='invoice_items',
        null=True,
        blank=True,
    )
    product_name = models.CharField(max_length=200, editable=False)
    quantity = models.PositiveIntegerField(editable=False)
    unit_price = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        editable=False,
    )
    total_price = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        editable=False,
    )

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(quantity__gt=0),
                name='invoice_item_quantity_is_positive',
            ),
            models.CheckConstraint(
                condition=models.Q(unit_price__gte=0),
                name='invoice_item_unit_price_is_not_negative',
            ),
            models.CheckConstraint(
                condition=models.Q(total_price__gte=0),
                name='invoice_item_total_price_is_not_negative',
            ),
        ]

    def __str__(self):
        return f'{self.product_name} x {self.quantity}'
