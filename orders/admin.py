from django.contrib import admin

from . import selectors
from .forms import OrderAdminForm, ShippingMethodForm
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
    form = OrderAdminForm
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
    readonly_fields = ('shipping_cost', 'tax_amount', 'created_at', 'updated_at')
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
        if change and 'status' in form.changed_data:
            selectors.change_order_status_by_admin(obj.pk, obj.status)
        super().save_model(request, obj, form, change)


@admin.register(ShippingMethod)
class ShippingMethodAdmin(admin.ModelAdmin):
    form = ShippingMethodForm
    list_display = ('name', 'price', 'estimated_delivery_days', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('name',)
