from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from account.models import User
from shop.models import Category, Product, ProductDiscount

from .models import Cart, CartItem


class CartViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            phone_number='09121110000',
            password='safe-password-123',
        )
        self.category = Category.objects.create(
            name='Test category',
            image='category_images/test.jpg',
        )
        self.product = Product.objects.create(
            name='Test product',
            price='100.00',
            status='available',
            quantity=5,
            category=self.category,
        )

    def test_cart_requires_login(self):
        response = self.client.get(reverse('cart:detail'))
        self.assertRedirects(
            response,
            f"{reverse('account:login')}?next={reverse('cart:detail')}",
        )

    def test_cart_detail_creates_cart_for_user(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse('cart:detail'))

        self.assertEqual(response.status_code, 200)
        self.assertTrue(Cart.objects.filter(user=self.user).exists())

    def test_add_product_and_add_again_increases_quantity(self):
        self.client.force_login(self.user)
        add_url = reverse('cart:add', args=[self.product.pk])

        first_response = self.client.post(add_url, {'quantity': 2})
        second_response = self.client.post(add_url, {'quantity': 2})

        self.assertRedirects(first_response, reverse('cart:detail'))
        self.assertRedirects(second_response, reverse('cart:detail'))
        item = CartItem.objects.get(cart__user=self.user, product=self.product)
        self.assertEqual(item.quantity, 4)

    def test_add_rejects_quantity_above_stock(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse('cart:add', args=[self.product.pk]),
            {'quantity': 6},
        )

        self.assertRedirects(response, reverse('cart:detail'))
        self.assertFalse(CartItem.objects.filter(cart__user=self.user).exists())

    def test_update_cart_item_quantity(self):
        cart = Cart.objects.create(user=self.user)
        item = CartItem.objects.create(
            cart=cart,
            product=self.product,
            quantity=1,
        )
        self.client.force_login(self.user)

        response = self.client.post(
            reverse('cart:item_update', args=[item.pk]),
            {'quantity': 3},
        )

        self.assertRedirects(response, reverse('cart:detail'))
        item.refresh_from_db()
        self.assertEqual(item.quantity, 3)

    def test_update_rejects_zero_and_quantity_above_stock(self):
        cart = Cart.objects.create(user=self.user)
        item = CartItem.objects.create(
            cart=cart,
            product=self.product,
            quantity=2,
        )
        self.client.force_login(self.user)
        update_url = reverse('cart:item_update', args=[item.pk])

        self.client.post(update_url, {'quantity': 0})
        item.refresh_from_db()
        self.assertEqual(item.quantity, 2)

        self.client.post(update_url, {'quantity': 6})
        item.refresh_from_db()
        self.assertEqual(item.quantity, 2)

    def test_remove_cart_item(self):
        cart = Cart.objects.create(user=self.user)
        item = CartItem.objects.create(
            cart=cart,
            product=self.product,
            quantity=1,
        )
        self.client.force_login(self.user)

        response = self.client.post(
            reverse('cart:item_remove', args=[item.pk])
        )

        self.assertRedirects(response, reverse('cart:detail'))
        self.assertFalse(CartItem.objects.filter(pk=item.pk).exists())

    def test_clear_cart(self):
        cart = Cart.objects.create(user=self.user)
        CartItem.objects.create(cart=cart, product=self.product, quantity=1)
        self.client.force_login(self.user)

        response = self.client.post(reverse('cart:clear'))

        self.assertRedirects(response, reverse('cart:detail'))
        self.assertFalse(cart.items.exists())

    def test_user_cannot_change_another_users_cart_item(self):
        other_user = User.objects.create_user(
            phone_number='09121110001',
            password='safe-password-123',
        )
        other_cart = Cart.objects.create(user=other_user)
        item = CartItem.objects.create(
            cart=other_cart,
            product=self.product,
            quantity=1,
        )
        self.client.force_login(self.user)

        update_response = self.client.post(
            reverse('cart:item_update', args=[item.pk]),
            {'quantity': 2},
        )
        remove_response = self.client.post(
            reverse('cart:item_remove', args=[item.pk])
        )

        self.assertEqual(update_response.status_code, 404)
        self.assertEqual(remove_response.status_code, 404)
        item.refresh_from_db()
        self.assertEqual(item.quantity, 1)

    def test_cart_total_uses_active_discount(self):
        ProductDiscount.objects.create(
            product=self.product,
            percent=20,
            ends_at=timezone.now() + timedelta(days=1),
        )
        cart = Cart.objects.create(user=self.user)
        CartItem.objects.create(cart=cart, product=self.product, quantity=2)
        self.client.force_login(self.user)

        response = self.client.get(reverse('cart:detail'))

        self.assertEqual(response.context['total_items'], 2)
        self.assertEqual(response.context['total_price'], 160)

    def test_cart_actions_only_accept_post(self):
        cart = Cart.objects.create(user=self.user)
        item = CartItem.objects.create(
            cart=cart,
            product=self.product,
            quantity=1,
        )
        self.client.force_login(self.user)
        urls = (
            reverse('cart:add', args=[self.product.pk]),
            reverse('cart:item_update', args=[item.pk]),
            reverse('cart:item_remove', args=[item.pk]),
            reverse('cart:clear'),
        )

        for url in urls:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 405)
