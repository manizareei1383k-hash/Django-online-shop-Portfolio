from django.contrib import admin

from . import selectors
from .forms import ShippingMethodForm
from .models import Order, OrderItem, ShippingMethod


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ('product', 'quantity', 'unit_price')
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'user',
        'status',
        'shipping_method',
        'shipping_cost',
        'created_at',
    )
    list_filter = ('status', 'shipping_method')
    search_fields = ('id', 'user__phone_number')
    list_select_related = ('user', 'address', 'shipping_method')
    readonly_fields = ('shipping_cost', 'created_at', 'updated_at')
    inlines = (OrderItemInline,)
    actions = ('cancel_selected_orders',)

    @admin.action(description='لغو سفارش‌های انتخاب‌شده')
    def cancel_selected_orders(self, request, queryset):
        canceled_count = 0
        for order_id in queryset.values_list('pk', flat=True):
            if selectors.cancel_order_by_admin(order_id):
                canceled_count += 1
        self.message_user(request, f'{canceled_count} سفارش لغو شد.')

    def save_model(self, request, obj, form, change):
        should_cancel = False
        if change and obj.status == Order.Status.CANCELED:
            old_status = Order.objects.filter(pk=obj.pk).values_list(
                'status', flat=True
            ).first()
            should_cancel = old_status != Order.Status.CANCELED

        if should_cancel:
            selectors.cancel_order_by_admin(obj.pk)
        super().save_model(request, obj, form, change)


@admin.register(ShippingMethod)
class ShippingMethodAdmin(admin.ModelAdmin):
    form = ShippingMethodForm
    list_display = ('name', 'price', 'estimated_delivery_days', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('name',)
