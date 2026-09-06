from django.contrib import admin

from .models import Invoice, InvoiceItem


class InvoiceItemInline(admin.TabularInline):
    model = InvoiceItem
    extra = 0
    can_delete = False
    readonly_fields = (
        'product',
        'product_name',
        'quantity',
        'unit_price',
        'total_price',
    )

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = (
        'number',
        'order',
        'user',
        'status',
        'total_amount',
        'issued_at',
    )
    list_filter = ('status', 'payment_gateway')
    search_fields = (
        'number',
        'order__id',
        'buyer_name',
        'buyer_phone',
        'payment_reference',
    )
    readonly_fields = (
        'number', 'order', 'payment', 'user', 'status', 'buyer_name',
        'buyer_phone', 'buyer_email', 'province', 'city', 'address',
        'postal_code', 'subtotal', 'tax_amount', 'shipping_cost', 'total_amount',
        'payment_gateway', 'payment_reference', 'issued_at', 'refunded_at',
    )
    inlines = (InvoiceItemInline,)

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
