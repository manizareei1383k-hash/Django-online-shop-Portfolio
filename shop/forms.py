from decimal import Decimal

from django import forms

from .models import Category, Message, Product, ProductDiscount, Review


class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ('name', 'image')


class ProductForm(forms.ModelForm):
    name = forms.CharField(
        min_length=3,
        max_length=200,
    )
    price = forms.DecimalField(
        min_value=Decimal('0.01'),
        max_digits=10,
        decimal_places=2,
    )

    class Meta:
        model = Product
        fields = (
            'name',
            'price',
            'status',
            'description',
            'quantity',
            'category',
            'image',
        )

    def clean_image(self):
        image = self.cleaned_data.get('image')
        if image and getattr(image, 'size', 0) > 5 * 1024 * 1024:
            raise forms.ValidationError('حجم تصویر نباید بیشتر از ۵ مگابایت باشد.')
        return image


class MessageForm(forms.ModelForm):
    class Meta:
        model = Message
        fields = ('name', 'email', 'message')
        labels = {
            'name': 'نام',
            'email': 'ایمیل',
            'message': 'پیام',
        }


class ReviewForm(forms.ModelForm):
    class Meta:
        model = Review
        fields = ('name', 'email', 'review')
        labels = {
            'name': 'نام',
            'email': 'ایمیل',
            'review': 'متن نظر',
        }


class ProductDiscountForm(forms.ModelForm):
    class Meta:
        model = ProductDiscount
        fields = (
            'product',
            'title',
            'percent',
            'starts_at',
            'ends_at',
            'is_active',
        )
