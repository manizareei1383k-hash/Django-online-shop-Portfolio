from django.contrib import admin

from .models import Notification


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('recipient', 'kind', 'title', 'is_read', 'created_at')
    list_filter = ('kind', 'is_read', 'created_at')
    search_fields = ('recipient__phone_number', 'title', 'message')
    readonly_fields = ('unique_key', 'created_at', 'read_at')
    list_select_related = ('recipient',)

