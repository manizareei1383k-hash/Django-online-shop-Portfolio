from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import (
    Address,
    Ticket,
    TicketMessage,
    User,
    Wallet,
    WalletTransaction,
)


class AddressInline(admin.TabularInline):
    model = Address
    extra = 0


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    inlines = (AddressInline,)
    ordering = ('phone_number',)
    list_display = (
        'phone_number',
        'email',
        'first_name',
        'last_name',
        'is_staff',
        'is_active',
    )
    search_fields = ('phone_number', 'email', 'first_name', 'last_name')
    fieldsets = (
        (None, {'fields': ('phone_number', 'password')}),
        (
            'اطلاعات شخصی',
            {
                'fields': (
                    'first_name',
                    'last_name',
                    'email',
                    'avatar',
                )
            },
        ),
        (
            'دسترسی‌ها',
            {
                'fields': (
                    'is_active',
                    'is_staff',
                    'is_superuser',
                    'groups',
                    'user_permissions',
                )
            },
        ),
        ('تاریخ‌ها', {'fields': ('last_login', 'date_joined')}),
    )
    add_fieldsets = (
        (
            None,
            {
                'classes': ('wide',),
                'fields': (
                    'phone_number',
                    'email',
                    'password1',
                    'password2',
                    'is_staff',
                    'is_active',
                ),
            },
        ),
    )


@admin.register(Address)
class AddressAdmin(admin.ModelAdmin):
    list_display = ('title', 'user', 'province', 'city', 'is_default')
    list_filter = ('province', 'city', 'is_default')
    search_fields = (
        'title',
        'recipient_name',
        'recipient_phone',
        'postal_code',
        'user__phone_number',
    )
    list_select_related = ('user',)


class TicketMessageInline(admin.TabularInline):
    model = TicketMessage
    extra = 0
    readonly_fields = ('created_at',)


@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = ('id', 'subject', 'user', 'status', 'priority', 'updated_at')
    list_filter = ('status', 'priority')
    search_fields = ('subject', 'user__phone_number', 'messages__message')
    list_select_related = ('user',)
    inlines = (TicketMessageInline,)


@admin.register(TicketMessage)
class TicketMessageAdmin(admin.ModelAdmin):
    list_display = ('ticket', 'sender', 'created_at')
    search_fields = ('message', 'ticket__subject', 'sender__phone_number')
    list_select_related = ('ticket', 'sender')


@admin.register(Wallet)
class WalletAdmin(admin.ModelAdmin):
    list_display = ('user', 'balance', 'updated_at')
    search_fields = ('user__phone_number', 'user__first_name', 'user__last_name')
    readonly_fields = ('balance', 'created_at', 'updated_at')
    list_select_related = ('user',)


@admin.register(WalletTransaction)
class WalletTransactionAdmin(admin.ModelAdmin):
    list_display = (
        'reference',
        'wallet',
        'direction',
        'kind',
        'amount',
        'balance_after',
        'created_at',
    )
    list_filter = ('direction', 'kind')
    search_fields = ('reference', 'wallet__user__phone_number', 'description')
    readonly_fields = (
        'wallet',
        'direction',
        'kind',
        'amount',
        'balance_after',
        'reference',
        'description',
        'created_at',
    )
    list_select_related = ('wallet__user',)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
