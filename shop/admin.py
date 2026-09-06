from django.contrib import admin

from .forms import CategoryForm, ProductDiscountForm, ProductForm
from .models import Category, Message, Product, ProductDiscount, Review


class ProductDiscountInline(admin.TabularInline):
    model = ProductDiscount
    extra = 0
    fields = ('title', 'percent', 'starts_at', 'ends_at', 'is_active')


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    form = CategoryForm
    list_display = ('name',)
    search_fields = ('name',)


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    form = ProductForm
    list_display = ('name', 'category', 'price', 'quantity', 'status')
    list_filter = ('status', 'category')
    search_fields = ('name', 'description')
    list_select_related = ('category',)
    inlines = (ProductDiscountInline,)


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ('name', 'email', 'product')
    search_fields = ('name', 'email', 'review', 'product__name')
    list_select_related = ('product',)


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ('name', 'email')
    search_fields = ('name', 'email', 'message')


@admin.register(ProductDiscount)
class ProductDiscountAdmin(admin.ModelAdmin):
    form = ProductDiscountForm
    list_display = (
        'product',
        'title',
        'percent',
        'is_active',
        'is_current',
        'starts_at',
        'ends_at',
    )
    list_filter = ('is_active',)
    search_fields = ('product__name', 'title')
    list_select_related = ('product',)
    readonly_fields = ('created_at', 'updated_at', 'is_current')
