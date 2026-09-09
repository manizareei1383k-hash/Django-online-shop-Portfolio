import hashlib

from django.core.paginator import Paginator
from django.core.cache import cache
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.db import transaction

from .forms import MessageForm, ProductForm, ReviewForm
from .models import Category, Product


PRODUCT_DETAIL_CACHE_TIMEOUT = 300
SHOP_LIST_CACHE_TIMEOUT = 120


def get_home_context(use_cache=True):
    products = cache.get('shop:home:products') if use_cache else None
    categories = cache.get('shop:home:categories') if use_cache else None
    if products is None:
        products = list(
            Product.objects.select_related('category')
            .prefetch_related('discounts').order_by('-id')[:8]
        )
        cache.set('shop:home:products', products, 300)
    if categories is None:
        categories = list(Category.objects.all().order_by('name'))
        cache.set('shop:home:categories', categories, 300)
    return {'products': products, 'categories': categories}


def get_shop_list_cache_key(filters, page_number):
    cache_parts = '|'.join(
        (
            filters['category'],
            '1' if filters['in_stock'] else '0',
            filters['sort'],
            str(page_number),
        )
    )
    digest = hashlib.sha256(cache_parts.encode()).hexdigest()
    return f'shop:catalog:{digest}'


def get_shop_context(params, use_cache=True):
    filters = {
        'q': params.get('q', '').strip(),
        'category': params.get('category', '').strip(),
        'in_stock': params.get('in_stock') == '1',
        'sort': params.get('sort', 'newest'),
    }
    valid_sorts = {
        'newest',
        'oldest',
        'price_asc',
        'price_desc',
        'name',
    }
    if filters['sort'] not in valid_sorts:
        filters['sort'] = 'newest'

    raw_page = params.get('page', '1')
    valid_page = (
        raw_page.isascii()
        and raw_page.isdecimal()
        and len(raw_page) <= 7
        and int(raw_page) > 0
    )
    requested_page = int(raw_page) if valid_page else 1
    can_cache = use_cache and not filters['q'] and valid_page
    cache_key = get_shop_list_cache_key(filters, requested_page)
    cached_page = cache.get(cache_key) if can_cache else None

    if cached_page is not None:
        paginator = Paginator(range(cached_page['count']), 12)
        page = paginator.page(cached_page['number'])
        page.object_list = cached_page['products']
        categories = cache.get('shop:home:categories')
        if categories is None:
            categories = list(Category.objects.all().order_by('name'))
            cache.set('shop:home:categories', categories, 300)
        page_query = params.copy()
        page_query.pop('page', None)
        return {
            'page': page,
            'categories': categories,
            'filters': filters,
            'page_query': page_query.urlencode(),
        }

    products = Product.objects.select_related('category').prefetch_related('discounts')

    if filters['q']:
        products = products.filter(
            Q(name__icontains=filters['q'])
            | Q(description__icontains=filters['q'])
        )

    category_id = filters['category']
    if category_id.isascii() and category_id.isdecimal() and len(category_id) <= 10:
        products = products.filter(category_id=category_id)

    if filters['in_stock']:
        products = products.filter(quantity__gt=0)

    order_by = {
        'oldest': 'id',
        'price_asc': 'price',
        'price_desc': '-price',
        'name': 'name',
    }.get(filters['sort'], '-id')
    products = products.order_by(order_by)

    paginator = Paginator(products, 12)
    page = paginator.get_page(params.get('page'))
    if can_cache:
        page.object_list = list(page.object_list)
        cache.set(
            cache_key,
            {
                'products': page.object_list,
                'count': paginator.count,
                'number': page.number,
            },
            SHOP_LIST_CACHE_TIMEOUT,
        )

    categories = cache.get('shop:home:categories')
    if categories is None:
        categories = list(Category.objects.all().order_by('name'))
        cache.set('shop:home:categories', categories, 300)
    page_query = params.copy()
    page_query.pop('page', None)

    return {
        'page': page,
        'categories': categories,
        'filters': filters,
        'page_query': page_query.urlencode(),
    }


def get_product_detail_cache_key(pk):
    return f'shop:product_detail:{pk}'


def get_product_detail_data(pk, use_cache=True):
    cache_key = get_product_detail_cache_key(pk)
    detail_data = cache.get(cache_key) if use_cache else None

    if detail_data is None:
        product = get_object_or_404(
            Product.objects.select_related('category').prefetch_related(
                'reviews__reply',
                'discounts',
            ),
            pk=pk,
        )
        related_products = list(
            Product.objects.filter(category=product.category)
            .exclude(pk=product.pk)
            .select_related('category')
            .prefetch_related('discounts')[:4]
        )
        detail_data = {
            'product': product,
            'related_products': related_products,
        }
        if use_cache:
            cache.set(cache_key, detail_data, PRODUCT_DETAIL_CACHE_TIMEOUT)

    return detail_data


def get_product_detail_context(pk, user=None, data=None, use_cache=True):
    detail_data = get_product_detail_data(pk, use_cache=use_cache and data is None)
    product = detail_data['product']
    review_form = ReviewForm(data)
    review_saved = False

    if data is not None and review_form.is_valid():
        review = review_form.save(commit=False)
        review.product = product
        review.user = user
        review.save()
        review_saved = True

    return {
        'product': product,
        'review_form': review_form,
        'review_saved': review_saved,
        'related_products': detail_data['related_products'],
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


def get_product_form_context(pk=None, data=None, files=None, admin_user=None, request=None):
    product = get_object_or_404(Product, pk=pk) if pk is not None else None
    form = ProductForm(data=data, files=files, instance=product)
    product_saved = False

    if data is not None and form.is_valid():
        from management_panel.models import AdminActivity
        from management_panel.selectors import record_admin_activity
        with transaction.atomic():
            product = form.save()
            record_admin_activity(
                admin_user,
                AdminActivity.Action.CREATE if pk is None else AdminActivity.Action.UPDATE,
                product,
                request=request,
                changes={'fields': list(form.changed_data)},
            )
        product_saved = True

    return {
        'form': form,
        'product': product,
        'product_saved': product_saved,
    }


def get_product_for_delete(pk):
    return get_object_or_404(Product, pk=pk)


def delete_product(product, admin_user, request=None):
    from management_panel.selectors import delete_product as delete_with_audit
    return delete_with_audit(product.pk, admin_user, request)
