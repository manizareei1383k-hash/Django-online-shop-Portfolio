from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404

from .forms import MessageForm, ProductForm, ReviewForm
from .models import Category, Product


def get_home_context():
    products = (
        Product.objects.select_related('category')
        .prefetch_related('discounts')
        .order_by('-id')[:8]
    )
    categories = Category.objects.all().order_by('name')
    return {'products': products, 'categories': categories}


def get_shop_context(params=None):
    params = params or {}
    search = params.get('q', '').strip()
    category = params.get('category', '').strip()
    in_stock = params.get('in_stock', '') == '1'
    sort = params.get('sort', 'newest')

    products = Product.objects.select_related('category').prefetch_related(
        'discounts'
    )

    if search:
        products = products.filter(
            Q(name__icontains=search)
            | Q(description__icontains=search)
            | Q(category__name__icontains=search)
        )

    if category.isdigit():
        products = products.filter(category_id=category)

    if in_stock:
        products = products.filter(quantity__gt=0)

    ordering = {
        'newest': '-id',
        'oldest': 'id',
        'price_asc': 'price',
        'price_desc': '-price',
        'name': 'name',
    }
    products = products.order_by(ordering.get(sort, '-id'))

    page = Paginator(products, 12).get_page(params.get('page'))
    query_params = params.copy()
    if hasattr(query_params, 'pop'):
        query_params.pop('page', None)
    page_query = (
        query_params.urlencode() if hasattr(query_params, 'urlencode') else ''
    )

    return {
        'page': page,
        'categories': Category.objects.order_by('name'),
        'filters': {
            'q': search,
            'category': category,
            'in_stock': in_stock,
            'sort': sort,
        },
        'page_query': page_query,
    }


def get_product_detail_context(pk, data=None):
    product = get_object_or_404(
        Product.objects.select_related('category').prefetch_related(
            'reviews',
            'discounts',
        ),
        pk=pk,
    )
    related_products = (
        Product.objects.filter(category=product.category)
        .exclude(pk=product.pk)
        .select_related('category')
        .prefetch_related('discounts')[:4]
    )
    review_form = ReviewForm(data)
    review_saved = False

    if data is not None and review_form.is_valid():
        review = review_form.save(commit=False)
        review.product = product
        review.save()
        review_saved = True

    return {
        'product': product,
        'review_form': review_form,
        'review_saved': review_saved,
        'related_products': related_products,
    }


def get_contact_context(data=None):
    form = MessageForm(data)
    message_saved = False

    if data is not None and form.is_valid():
        form.save()
        message_saved = True

    return {'form': form, 'message_saved': message_saved}


def get_management_context():
    products = Product.objects.select_related('category').order_by('-id')
    return {'products': products}


def get_product_form_context(pk=None, data=None, files=None):
    product = get_object_or_404(Product, pk=pk) if pk is not None else None
    form = ProductForm(data=data, files=files, instance=product)
    product_saved = False

    if data is not None and form.is_valid():
        product = form.save()
        product_saved = True

    return {
        'form': form,
        'product': product,
        'product_saved': product_saved,
    }


def get_product_for_delete(pk):
    return get_object_or_404(Product, pk=pk)


def delete_product(product):
    product.delete()
