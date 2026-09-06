from decimal import Decimal, ROUND_HALF_UP

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import F
from django.shortcuts import get_object_or_404

from cart.models import CartItem
from shop.models import Product

from .forms import OrderForm
from .models import Order, OrderItem


def calculate_tax(subtotal):
    return (subtotal * settings.TAX_PERCENT / Decimal('100')).quantize(
        Decimal('0.01'),
        rounding=ROUND_HALF_UP,
    )


ADMIN_STATUS_TRANSITIONS = {
    Order.Status.PENDING: {
        Order.Status.PROCESSING,
        Order.Status.CANCELED,
    },
    Order.Status.PROCESSING: {
        Order.Status.SHIPPED,
        Order.Status.CANCELED,
    },
    Order.Status.SHIPPED: {
        Order.Status.DELIVERED,
        Order.Status.CANCELED,
    },
    Order.Status.DELIVERED: {
        Order.Status.CANCELED,
    },
    Order.Status.CANCELED: set(),
}


def validate_admin_status_transition(order, new_status):
    valid_statuses = {choice[0] for choice in Order.Status.choices}
    if new_status not in valid_statuses:
        raise ValidationError('وضعیت سفارش معتبر نیست.')

    if new_status == order.status:
        return

    allowed_statuses = ADMIN_STATUS_TRANSITIONS.get(order.status, set())
    if new_status not in allowed_statuses:
        raise ValidationError(
            'تغییر وضعیت سفارش از «{}» به «{}» مجاز نیست.'.format(
                order.get_status_display(),
                dict(Order.Status.choices)[new_status],
            )
        )

    if new_status == Order.Status.PROCESSING:
        has_successful_payment = order.payments.filter(status='paid').exists()
        if not has_successful_payment:
            raise ValidationError(
                'سفارش فقط بعد از پرداخت موفق می‌تواند وارد مرحله پردازش شود.'
            )


def change_order_status_by_admin(order_id, new_status):
    with transaction.atomic():
        order = get_object_or_404(
            Order.objects.select_for_update(),
            pk=order_id,
        )
        validate_admin_status_transition(order, new_status)
        if order.status == new_status:
            return False
        if new_status == Order.Status.CANCELED:
            return cancel_order_by_admin(order_id)

        order.status = new_status
        order.save(update_fields=('status', 'updated_at'))

        from notifications.selectors import notify_order_status

        notify_order_status(order)
        return True


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
        'tax_amount': order.tax_amount,
        'shipping_cost': order.shipping_cost,
        'total_price': subtotal + order.tax_amount + order.shipping_cost,
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

    tax_amount = calculate_tax(subtotal)

    return {
        'form': form,
        'lines': lines,
        'subtotal': subtotal,
        'tax_amount': tax_amount,
        'shipping_cost': shipping_cost,
        'total_price': subtotal + tax_amount + shipping_cost,
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
        subtotal = sum(
            (
                locked_products[item.product_id].price_after_discount
                * item.quantity
                for item in cart_items
            ),
            start=Decimal('0'),
        )
        order.tax_amount = calculate_tax(subtotal)
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
    return {
        'order': order,
        'latest_payment': order.payments.first(),
        'invoice': getattr(order, 'invoice', None),
        'test_gateway_enabled': settings.DEBUG,
        **calculate_order_totals(order),
    }


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

        from payments.selectors import cancel_pending_order_payments

        cancel_pending_order_payments(order.pk)

        for item in order.items.all():
            Product.objects.filter(pk=item.product_id).update(
                quantity=F('quantity') + item.quantity
            )
        order.status = Order.Status.CANCELED
        order.save(update_fields=('status', 'updated_at'))

        from notifications.selectors import notify_order_status

        notify_order_status(order)
        return True


def cancel_order_by_admin(order_id):
    with transaction.atomic():
        order = get_object_or_404(
            Order.objects.select_for_update().prefetch_related('items'),
            pk=order_id,
        )
        if order.status == Order.Status.CANCELED:
            return False

        from payments.selectors import (
            cancel_pending_order_payments,
            refund_paid_order,
        )

        refund_paid_order(order.pk)
        cancel_pending_order_payments(order.pk)

        for item in order.items.all():
            Product.objects.filter(pk=item.product_id).update(
                quantity=F('quantity') + item.quantity
            )
        order.status = Order.Status.CANCELED
        order.save(update_fields=('status', 'updated_at'))

        from notifications.selectors import notify_order_status

        notify_order_status(order)
        return True
