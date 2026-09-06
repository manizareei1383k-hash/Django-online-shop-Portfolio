from decimal import Decimal

from django.db import transaction
from django.db.models import F
from django.shortcuts import get_object_or_404

from cart.models import CartItem
from shop.models import Product

from .forms import OrderForm
from .models import Order, OrderItem


def calculate_order_totals(order):
    lines = []
    subtotal = Decimal('0')
    for item in order.items.all():
        line_total = item.unit_price * item.quantity
        lines.append({'item': item, 'total_price': line_total})
        subtotal += line_total
    return {
        'lines': lines,
        'subtotal': subtotal,
        'shipping_cost': order.shipping_cost,
        'total_price': subtotal + order.shipping_cost,
    }


def get_checkout_context(user, data=None):
    form = OrderForm(data=data, user=user)
    cart_items = list(
        CartItem.objects.filter(cart__user=user)
        .select_related('product')
        .prefetch_related('product__discounts')
    )

    lines = []
    subtotal = Decimal('0')
    for item in cart_items:
        unit_price = item.product.price_after_discount
        line_total = unit_price * item.quantity
        lines.append(
            {
                'item': item,
                'unit_price': unit_price,
                'total_price': line_total,
            }
        )
        subtotal += line_total

    order = None
    if data is not None and form.is_valid():
        if not cart_items:
            form.add_error(None, 'سبد خرید شما خالی است.')
        else:
            order = create_order_from_cart(user, form)
            if order is None:
                form.add_error(
                    None,
                    'موجودی یکی از محصولات کافی نیست. سبد خرید را بررسی کنید.',
                )

    shipping_cost = Decimal('0')
    if form.is_bound and form.is_valid():
        shipping_method = form.cleaned_data.get('shipping_method')
        if shipping_method is not None:
            shipping_cost = shipping_method.price

    return {
        'form': form,
        'lines': lines,
        'subtotal': subtotal,
        'shipping_cost': shipping_cost,
        'total_price': subtotal + shipping_cost,
        'created_order': order,
    }


def create_order_from_cart(user, form):
    with transaction.atomic():
        cart_items = list(
            CartItem.objects.select_for_update()
            .filter(cart__user=user)
            .select_related('product')
        )
        if not cart_items:
            return None

        locked_products = {}
        for cart_item in cart_items:
            product = Product.objects.select_for_update().get(
                pk=cart_item.product_id
            )
            if product.quantity < cart_item.quantity:
                return None
            locked_products[product.pk] = product

        order = form.save(commit=False)
        order.user = user
        order.shipping_cost = order.shipping_method.price
        order.save()

        order_items = []
        for cart_item in cart_items:
            product = locked_products[cart_item.product_id]
            order_items.append(
                OrderItem(
                    order=order,
                    product=product,
                    quantity=cart_item.quantity,
                    unit_price=product.price_after_discount,
                )
            )
            Product.objects.filter(pk=product.pk).update(
                quantity=F('quantity') - cart_item.quantity
            )

        OrderItem.objects.bulk_create(order_items)
        CartItem.objects.filter(pk__in=[item.pk for item in cart_items]).delete()
        return order


def get_orders_context(user):
    orders = user.orders.select_related(
        'address',
        'shipping_method',
    ).prefetch_related('items')
    order_rows = []
    for order in orders:
        totals = calculate_order_totals(order)
        totals.pop('lines')
        order_rows.append({'order': order, **totals})
    return {'order_rows': order_rows}


def get_order_detail_context(user, pk):
    order = get_object_or_404(
        Order.objects.select_related(
            'address',
            'shipping_method',
        ).prefetch_related('items__product'),
        pk=pk,
        user=user,
    )
    return {'order': order, **calculate_order_totals(order)}


def get_order_payable_amount(user, pk):
    order = get_object_or_404(
        Order.objects.prefetch_related('items'),
        pk=pk,
        user=user,
    )
    return calculate_order_totals(order)['total_price']


def cancel_user_order(user, pk):
    with transaction.atomic():
        order = get_object_or_404(
            Order.objects.select_for_update().prefetch_related('items'),
            pk=pk,
            user=user,
        )
        if order.status != Order.Status.PENDING:
            return False

        for item in order.items.all():
            Product.objects.filter(pk=item.product_id).update(
                quantity=F('quantity') + item.quantity
            )
        order.status = Order.Status.CANCELED
        order.save(update_fields=('status', 'updated_at'))
        return True


def cancel_order_by_admin(order_id):
    with transaction.atomic():
        order = get_object_or_404(
            Order.objects.select_for_update().prefetch_related('items'),
            pk=order_id,
        )
        if order.status == Order.Status.CANCELED:
            return False

        for item in order.items.all():
            Product.objects.filter(pk=item.product_id).update(
                quantity=F('quantity') + item.quantity
            )
        order.status = Order.Status.CANCELED
        order.save(update_fields=('status', 'updated_at'))
        return True
