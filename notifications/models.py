from django.db import models


class Notification(models.Model):
    class Kind(models.TextChoices):
        ORDER_STATUS = 'order_status', 'وضعیت سفارش'
        PAYMENT_SUCCESS = 'payment_success', 'پرداخت موفق'
        PAYMENT_FAILED = 'payment_failed', 'پرداخت ناموفق'
        PAYMENT_REFUNDED = 'payment_refunded', 'بازگشت وجه'
        INVOICE_ISSUED = 'invoice_issued', 'صدور فاکتور'
        TICKET_REPLY = 'ticket_reply', 'پاسخ تیکت'
        REVIEW_REPLY = 'review_reply', 'پاسخ نظر'
        SYSTEM = 'system', 'سیستمی'

    recipient = models.ForeignKey(
        'account.User',
        on_delete=models.CASCADE,
        related_name='notifications',
    )
    kind = models.CharField(max_length=30, choices=Kind.choices, db_index=True)
    title = models.CharField(max_length=150)
    message = models.TextField()
    target_url = models.CharField(max_length=300, blank=True)
    data = models.JSONField(default=dict, blank=True)
    unique_key = models.CharField(
        max_length=150,
        unique=True,
        null=True,
        blank=True,
        editable=False,
    )
    is_read = models.BooleanField(default=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ('-created_at',)

    def __str__(self):
        return f'{self.recipient} - {self.title}'

