from django.conf import settings
from django.db import models


class AdminActivity(models.Model):
    class Action(models.TextChoices):
        CREATE = 'create', 'ایجاد'
        UPDATE = 'update', 'ویرایش'
        DELETE = 'delete', 'حذف'
        STATUS_CHANGE = 'status_change', 'تغییر وضعیت'
        CANCEL = 'cancel', 'لغو'
        REPLY = 'reply', 'پاسخ'

    admin = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name='admin_activities',
        null=True,
        editable=False,
    )
    action = models.CharField(
        max_length=20,
        choices=Action.choices,
        editable=False,
    )
    target_type = models.CharField(max_length=100, editable=False)
    target_id = models.CharField(max_length=64, blank=True, editable=False)
    target_label = models.CharField(max_length=255, blank=True, editable=False)
    description = models.TextField(blank=True, editable=False)
    changes = models.JSONField(default=dict, blank=True, editable=False)
    ip_address = models.GenericIPAddressField(null=True, blank=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True, editable=False)

    class Meta:
        ordering = ('-created_at', '-id')
        indexes = [
            models.Index(fields=('admin', 'created_at')),
            models.Index(fields=('action', 'created_at')),
        ]

    def __str__(self):
        return f'{self.get_action_display()} {self.target_type} #{self.target_id}'


class SystemLog(models.Model):
    level = models.CharField(max_length=20, db_index=True, editable=False)
    logger_name = models.CharField(max_length=150, editable=False)
    message = models.TextField(editable=False)
    request_id = models.CharField(max_length=32, blank=True, editable=False)
    method = models.CharField(max_length=10, blank=True, editable=False)
    path = models.CharField(max_length=500, blank=True, editable=False)
    status_code = models.PositiveSmallIntegerField(null=True, editable=False)
    traceback = models.TextField(blank=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True, editable=False)

    class Meta:
        ordering = ('-created_at', '-id')

    def __str__(self):
        return f'{self.level}: {self.message[:80]}'
