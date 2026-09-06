from django import forms
from django.utils import timezone

from account.models import Ticket
from account.forms import TicketMessageForm
from orders.forms import OrderStatusForm, ShippingMethodForm
from shop.forms import CategoryForm, ProductForm
from shop.models import ReviewReply


class ProductManagementForm(ProductForm):
    discount_title = forms.CharField(max_length=100, required=False)
    discount_percent = forms.DecimalField(
        max_digits=5,
        decimal_places=2,
        min_value=0.01,
        max_value=100,
        required=False,
    )
    discount_starts_at = forms.DateTimeField(required=False)
    discount_ends_at = forms.DateTimeField(required=False)
    discount_is_active = forms.BooleanField(required=False, initial=True)
    remove_discount = forms.BooleanField(required=False)

    def __init__(self, *args, discount=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.discount = discount
        if discount is not None and not self.is_bound:
            self.initial.update(
                {
                    'discount_title': discount.title,
                    'discount_percent': discount.percent,
                    'discount_starts_at': discount.starts_at,
                    'discount_ends_at': discount.ends_at,
                    'discount_is_active': discount.is_active,
                }
            )

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get('remove_discount'):
            return cleaned_data

        percent = cleaned_data.get('discount_percent')
        starts_at = cleaned_data.get('discount_starts_at')
        ends_at = cleaned_data.get('discount_ends_at')
        has_discount_data = any(
            (
                percent is not None,
                starts_at is not None,
                ends_at is not None,
                cleaned_data.get('discount_title'),
            )
        )
        if not has_discount_data:
            return cleaned_data
        if percent is None:
            self.add_error('discount_percent', 'درصد تخفیف را وارد کنید.')
        if ends_at is None:
            self.add_error('discount_ends_at', 'زمان پایان تخفیف را وارد کنید.')
        starts_at = starts_at or timezone.now()
        cleaned_data['discount_starts_at'] = starts_at
        if ends_at is not None and ends_at <= starts_at:
            self.add_error('discount_ends_at', 'پایان تخفیف باید بعد از شروع باشد.')
        return cleaned_data


class TicketManagementForm(forms.ModelForm):
    class Meta:
        model = Ticket
        fields = ('status', 'priority')


class ReviewReplyForm(forms.ModelForm):
    class Meta:
        model = ReviewReply
        fields = ('message',)


__all__ = (
    'CategoryForm',
    'OrderStatusForm',
    'ProductManagementForm',
    'ReviewReplyForm',
    'ShippingMethodForm',
    'TicketManagementForm',
    'TicketMessageForm',
)

