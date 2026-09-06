from django import forms

from .models import Order, OrderItem, ShippingMethod


class OrderForm(forms.ModelForm):
    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if user is None:
            self.fields['address'].queryset = self.fields['address'].queryset.none()
        else:
            self.fields['address'].queryset = user.addresses.all()
        self.fields['shipping_method'].queryset = ShippingMethod.objects.filter(
            is_active=True
        )
        self.fields['shipping_method'].required = True

    class Meta:
        model = Order
        fields = ('address', 'shipping_method', 'description')


class OrderItemForm(forms.ModelForm):
    class Meta:
        model = OrderItem
        fields = ('product', 'quantity')


class OrderStatusForm(forms.ModelForm):
    class Meta:
        model = Order
        fields = ('status',)


class ShippingMethodForm(forms.ModelForm):
    class Meta:
        model = ShippingMethod
        fields = ('name', 'price', 'estimated_delivery_days', 'is_active')

    def clean_price(self):
        price = self.cleaned_data['price']
        if price < 0:
            raise forms.ValidationError('هزینه ارسال نمی‌تواند منفی باشد.')
        return price

    def clean_estimated_delivery_days(self):
        days = self.cleaned_data['estimated_delivery_days']
        if days < 1:
            raise forms.ValidationError('زمان تحویل باید حداقل یک روز باشد.')
        return days
