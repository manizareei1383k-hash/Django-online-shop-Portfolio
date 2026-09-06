from django import forms

from .models import Payment


class PaymentStartForm(forms.Form):
    gateway = forms.ChoiceField(choices=Payment.Gateway.choices)

