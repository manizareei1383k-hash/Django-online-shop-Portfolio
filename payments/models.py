import uuid

from django.db import models


class Payment(models.Model):
    class Gateway(models.TextChoices):
        WALLET = 'wallet', 'کیف پول'
        TEST = 'test', 'درگاه آزمایشی'

    class Status(models.TextChoices):
        PENDING = 'pending', 'در انتظار پرداخت'
        PAID = 'paid', 'پرداخت‌شده'
        FAILED = 'failed', 'ناموفق'
        CANCELED = 'canceled', 'لغوشده'
        REFUNDED = 'refunded', 'بازگشت داده‌شده'

    order = models.ForeignKey(
        'orders.Order',
        on_delete=models.PROTECT,
        related_name='payments',
    )
    user = models.ForeignKey(
        'account.User',
        on_delete=models.PROTECT,
        related_name='payments',
    )
    gateway = models.CharField(max_length=20, choices=Gateway.choices)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )
    amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        editable=False,
    )
    token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    gateway_reference = models.CharField(max_length=100, blank=True)
    refund_reference = models.CharField(max_length=100, blank=True)
    failure_reason = models.CharField(max_length=250, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    refunded_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('-created_at',)
        constraints = [
            models.CheckConstraint(
                condition=models.Q(amount__gt=0),
                name='payment_amount_must_be_positive',
            ),
            models.UniqueConstraint(
                fields=('order',),
                condition=models.Q(status='paid'),
                name='one_successful_payment_per_order',
            ),
        ]

    def __str__(self):
        return f'Payment #{self.pk} - Order #{self.order_id}'
