from decimal import Decimal

from django.shortcuts import get_object_or_404

from shop.models import Product

from .forms import CartItemQuantityForm
from .models import Cart, CartItem


def get_user_cart(user):
    cart, _ = Cart.objects.get_or_create(user=user)
    return cart


def get_cart_context(user):
    cart = get_user_cart(user)
    items = cart.items.select_related(
        'product',
        'product__category',
    ).prefetch_related('product__discounts')

    lines = []
    total_items = 0
    total_price = Decimal('0')

    for item in items:
        unit_price = item.product.price_after_discount
        line_total = unit_price * item.quantity
        lines.append(
            {
                'item': item,
                'unit_price': unit_price,
                'total_price': line_total,
            }
        )
        total_items += item.quantity
        total_price += line_total

    return {
        'cart': cart,
        'lines': lines,
        'total_items': total_items,
        'total_price': total_price,
    }


def add_product_to_cart(user, product_id, data):
    product = get_object_or_404(Product, pk=product_id)
    form = CartItemQuantityForm(data=data)

    if not form.is_valid():
        return 'invalid'

    quantity = form.cleaned_data['quantity']
    if product.quantity < quantity:
        return 'insufficient_stock'

    cart = get_user_cart(user)
    item = CartItem.objects.filter(cart=cart, product=product).first()

    if item is None:
        CartItem.objects.create(
            cart=cart,
            product=product,
            quantity=quantity,
        )
    else:
        new_quantity = item.quantity + quantity
        if product.quantity < new_quantity:
            return 'insufficient_stock'
        item.quantity = new_quantity
        item.save(update_fields=('quantity', 'updated_at'))

    cart.save(update_fields=('updated_at',))
    return 'added'


def update_cart_item(user, item_id, data):
    item = get_object_or_404(
        CartItem.objects.select_related('product'),
        pk=item_id,
        cart__user=user,
    )
    form = CartItemQuantityForm(data=data, instance=item)

    if not form.is_valid():
        return 'invalid'

    if item.product.quantity < form.cleaned_data['quantity']:
        return 'insufficient_stock'

    form.save()
    item.cart.save(update_fields=('updated_at',))
    return 'updated'


def remove_cart_item(user, item_id):
    item = get_object_or_404(CartItem, pk=item_id, cart__user=user)
    item.delete()


def clear_user_cart(user):
    cart = get_user_cart(user)
    cart.items.all().delete()
