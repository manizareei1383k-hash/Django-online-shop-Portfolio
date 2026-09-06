from django.contrib import admin

from .models import Payment


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ('id', 'order', 'user', 'gateway', 'amount', 'status', 'created_at')
    list_filter = ('gateway', 'status')
    search_fields = ('id', 'order__id', 'user__phone_number', 'gateway_reference')
    readonly_fields = (
        'order', 'user', 'gateway', 'amount', 'status', 'token',
        'gateway_reference', 'refund_reference', 'failure_reason',
        'created_at', 'paid_at', 'refunded_at', 'updated_at',
    )

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
