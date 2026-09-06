from django.db import models


class Cart(models.Model):
    """سبد خریدِ فعلی هر کاربر."""

    user = models.OneToOneField(
        'account.User',
        on_delete=models.CASCADE,
        related_name='cart',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('-updated_at',)

    def __str__(self):
        return f'Cart for {self.user}'


class CartItem(models.Model):
    """یک محصول درون سبد خرید."""

    cart = models.ForeignKey(
        Cart,
        on_delete=models.CASCADE,
        related_name='items',
    )
    product = models.ForeignKey(
        'shop.Product',
        on_delete=models.CASCADE,
        related_name='cart_items',
    )
    quantity = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('-updated_at',)
        constraints = [
            models.UniqueConstraint(
                fields=('cart', 'product'),
                name='one_cart_item_per_product',
            ),
            models.CheckConstraint(
                condition=models.Q(quantity__gt=0),
                name='cart_item_quantity_must_be_positive',
            ),
        ]

    def __str__(self):
        return f'{self.product} x {self.quantity}'
