from django import forms
from django.contrib.auth.forms import (
    AuthenticationForm,
    PasswordChangeForm,
    PasswordResetForm,
    SetPasswordForm,
    UserCreationForm,
)

from .models import Address, Ticket, TicketMessage, User


class RegisterForm(UserCreationForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['phone_number'].label = 'شماره تلفن'
        self.fields['password1'].label = 'رمز عبور'
        self.fields['password2'].label = 'تکرار رمز عبور'

    class Meta:
        model = User
        fields = (
            'phone_number',
            'email',
            'first_name',
            'last_name',
            'avatar',
        )


class LoginForm(AuthenticationForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['username'].label = 'شماره تلفن'
        self.fields['password'].label = 'رمز عبور'


class AccountPasswordChangeForm(PasswordChangeForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['old_password'].label = 'رمز عبور فعلی'
        self.fields['new_password1'].label = 'رمز عبور جدید'
        self.fields['new_password2'].label = 'تکرار رمز عبور جدید'


class AccountPasswordResetForm(PasswordResetForm):
    phone_number = forms.CharField(max_length=15, label='شماره تلفن')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['email'].label = 'ایمیل ثبت‌شده'

    def get_users(self, email):
        users = User.objects.filter(
            phone_number=self.cleaned_data['phone_number'],
            email__iexact=email,
            is_active=True,
        )
        return (user for user in users if user.has_usable_password())


class AccountSetPasswordForm(SetPasswordForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['new_password1'].label = 'رمز عبور جدید'
        self.fields['new_password2'].label = 'تکرار رمز عبور جدید'


class UserProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = (
            'first_name',
            'last_name',
            'email',
            'phone_number',
            'avatar',
        )


class AddressForm(forms.ModelForm):
    class Meta:
        model = Address
        fields = (
            'title',
            'recipient_name',
            'recipient_phone',
            'province',
            'city',
            'address',
            'postal_code',
            'is_default',
        )


class TicketForm(forms.ModelForm):
    class Meta:
        model = Ticket
        fields = ('subject', 'priority')


class TicketMessageForm(forms.ModelForm):
    class Meta:
        model = TicketMessage
        fields = ('message', 'attachment')


class WalletOperationForm(forms.Form):
    amount = forms.DecimalField(
        min_value=1,
        decimal_places=0,
        max_digits=14,
        label='مبلغ',
    )
    description = forms.CharField(
        required=False,
        max_length=250,
        label='توضیحات',
    )
