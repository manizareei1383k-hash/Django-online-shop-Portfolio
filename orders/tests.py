from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from account.models import Address, User
from cart.models import Cart, CartItem
from shop.models import Category, Product
from payments.models import Payment

from . import selectors
from .models import Order, OrderItem, ShippingMethod


class OrderViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            phone_number='09123330000',
            password='safe-password-123',
        )
        self.address = Address.objects.create(
            user=self.user,
            title='Home',
            recipient_name='Test User',
            recipient_phone=self.user.phone_number,
            province='Tehran',
            city='Tehran',
            address='Test address',
            postal_code='1234567890',
            is_default=True,
        )
        self.shipping_method = ShippingMethod.objects.create(
            name='Express post',
            price='20.00',
            estimated_delivery_days=2,
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

    def add_product_to_cart(self, quantity=2):
        cart, _ = Cart.objects.get_or_create(user=self.user)
        return CartItem.objects.create(
            cart=cart,
            product=self.product,
            quantity=quantity,
        )

    def checkout_data(self, **overrides):
        data = {
            'address': self.address.pk,
            'shipping_method': self.shipping_method.pk,
            'description': 'Test order',
        }
        data.update(overrides)
        return data

    def test_tax_uses_financial_half_up_rounding(self):
        self.assertEqual(
            selectors.calculate_tax(Decimal('0.05')),
            Decimal('0.01'),
        )

    def test_order_views_require_login(self):
        urls = (
            reverse('orders:list'),
            reverse('orders:checkout'),
            reverse('orders:detail', args=[999]),
            reverse('orders:cancel', args=[999]),
        )
        for url in urls:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 302)
                self.assertTrue(response.url.startswith(reverse('account:login')))

    def test_checkout_creates_order_reduces_stock_and_clears_cart(self):
        self.add_product_to_cart(quantity=2)
        self.client.force_login(self.user)

        response = self.client.post(
            reverse('orders:checkout'),
            self.checkout_data(),
        )

        order = Order.objects.get(user=self.user)
        self.assertRedirects(
            response,
            reverse('orders:detail', args=[order.pk]),
        )
        item = order.items.get()
        self.assertEqual(item.product, self.product)
        self.assertEqual(item.quantity, 2)
        self.assertEqual(item.unit_price, Decimal('100.00'))
        self.assertEqual(order.shipping_cost, Decimal('20.00'))
        self.product.refresh_from_db()
        self.assertEqual(self.product.quantity, 3)
        self.assertFalse(CartItem.objects.filter(cart__user=self.user).exists())

    def test_checkout_ignores_prices_sent_by_user(self):
        self.add_product_to_cart(quantity=2)
        self.client.force_login(self.user)
        data = self.checkout_data()
        data.update(
            {
                'unit_price': '1.00',
                'shipping_cost': '1.00',
                'subtotal': '1.00',
                'total_price': '1.00',
            }
        )

        response = self.client.post(reverse('orders:checkout'), data)

        order = Order.objects.get(user=self.user)
        self.assertRedirects(
            response,
            reverse('orders:detail', args=[order.pk]),
        )
        self.assertEqual(order.items.get().unit_price, Decimal('100.00'))
        self.assertEqual(order.shipping_cost, Decimal('20.00'))
        self.assertEqual(order.tax_amount, Decimal('20.00'))
        self.assertEqual(
            order.items.get().unit_price * order.items.get().quantity
            + order.tax_amount
            + order.shipping_cost,
            Decimal('240.00'),
        )
        self.assertEqual(
            selectors.get_order_payable_amount(self.user, order.pk),
            Decimal('240.00'),
        )

    def test_empty_cart_does_not_create_order(self):
        self.client.force_login(self.user)

        response = self.client.post(
            reverse('orders:checkout'),
            self.checkout_data(),
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(Order.objects.filter(user=self.user).exists())

    def test_checkout_rejects_insufficient_stock_and_keeps_cart(self):
        cart_item = self.add_product_to_cart(quantity=6)
        self.client.force_login(self.user)

        response = self.client.post(
            reverse('orders:checkout'),
            self.checkout_data(),
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(Order.objects.filter(user=self.user).exists())
        self.assertTrue(CartItem.objects.filter(pk=cart_item.pk).exists())
        self.product.refresh_from_db()
        self.assertEqual(self.product.quantity, 5)

    def test_checkout_rejects_another_users_address(self):
        other_user = User.objects.create_user(
            phone_number='09123330001',
            password='safe-password-123',
        )
        other_address = Address.objects.create(
            user=other_user,
            title='Other',
            recipient_name='Other User',
            recipient_phone=other_user.phone_number,
            province='Tehran',
            city='Tehran',
            address='Other address',
            postal_code='0987654321',
        )
        self.add_product_to_cart()
        self.client.force_login(self.user)

        response = self.client.post(
            reverse('orders:checkout'),
            self.checkout_data(address=other_address.pk),
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(Order.objects.filter(user=self.user).exists())

    def test_checkout_rejects_inactive_shipping_method(self):
        self.shipping_method.is_active = False
        self.shipping_method.save(update_fields=('is_active',))
        self.add_product_to_cart()
        self.client.force_login(self.user)

        response = self.client.post(
            reverse('orders:checkout'),
            self.checkout_data(),
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(Order.objects.filter(user=self.user).exists())

    def test_order_list_and_detail_only_show_users_orders(self):
        own_order = Order.objects.create(
            user=self.user,
            address=self.address,
            shipping_method=self.shipping_method,
            shipping_cost=self.shipping_method.price,
        )
        OrderItem.objects.create(
            order=own_order,
            product=self.product,
            quantity=2,
            unit_price='100.00',
        )
        other_user = User.objects.create_user(
            phone_number='09123330002',
            password='safe-password-123',
        )
        other_address = Address.objects.create(
            user=other_user,
            title='Other',
            recipient_name='Other User',
            recipient_phone=other_user.phone_number,
            province='Tehran',
            city='Tehran',
            address='Other address',
            postal_code='0987654321',
        )
        other_order = Order.objects.create(user=other_user, address=other_address)
        self.client.force_login(self.user)

        list_response = self.client.get(reverse('orders:list'))
        own_response = self.client.get(
            reverse('orders:detail', args=[own_order.pk])
        )
        other_response = self.client.get(
            reverse('orders:detail', args=[other_order.pk])
        )

        self.assertEqual(list_response.status_code, 200)
        listed_orders = [row['order'] for row in list_response.context['order_rows']]
        self.assertIn(own_order, listed_orders)
        self.assertNotIn(other_order, listed_orders)
        self.assertEqual(own_response.status_code, 200)
        self.assertEqual(own_response.context['total_price'], Decimal('220.00'))
        self.assertEqual(other_response.status_code, 404)

    def test_cancel_pending_order_restores_stock(self):
        order = Order.objects.create(
            user=self.user,
            address=self.address,
            shipping_method=self.shipping_method,
            shipping_cost=self.shipping_method.price,
        )
        OrderItem.objects.create(
            order=order,
            product=self.product,
            quantity=2,
            unit_price='100.00',
        )
        self.product.quantity = 3
        self.product.save(update_fields=('quantity',))
        self.client.force_login(self.user)

        response = self.client.post(
            reverse('orders:cancel', args=[order.pk])
        )

        self.assertRedirects(response, reverse('orders:detail', args=[order.pk]))
        order.refresh_from_db()
        self.product.refresh_from_db()
        self.assertEqual(order.status, Order.Status.CANCELED)
        self.assertEqual(self.product.quantity, 5)

    def test_non_pending_orders_cannot_be_canceled(self):
        self.client.force_login(self.user)
        statuses = (
            Order.Status.PROCESSING,
            Order.Status.SHIPPED,
            Order.Status.DELIVERED,
            Order.Status.CANCELED,
        )

        for status in statuses:
            with self.subTest(status=status):
                order = Order.objects.create(
                    user=self.user,
                    address=self.address,
                    status=status,
                )
                response = self.client.post(
                    reverse('orders:cancel', args=[order.pk])
                )

                self.assertRedirects(
                    response,
                    reverse('orders:detail', args=[order.pk]),
                )
                order.refresh_from_db()
                self.assertEqual(order.status, status)

    def test_admin_can_cancel_order_in_any_status_only_once(self):
        admin_user = User.objects.create_superuser(
            phone_number='09123330003',
            password='safe-password-123',
        )
        order = Order.objects.create(
            user=self.user,
            address=self.address,
            status=Order.Status.DELIVERED,
        )
        OrderItem.objects.create(
            order=order,
            product=self.product,
            quantity=2,
            unit_price='100.00',
        )
        self.product.quantity = 3
        self.product.save(update_fields=('quantity',))
        self.client.force_login(admin_user)
        action_url = reverse('admin:orders_order_changelist')
        action_data = {
            'action': 'cancel_selected_orders',
            '_selected_action': order.pk,
            'select_across': '0',
        }

        first_response = self.client.post(action_url, action_data)
        second_response = self.client.post(action_url, action_data)

        self.assertEqual(first_response.status_code, 302)
        self.assertEqual(second_response.status_code, 302)
        order.refresh_from_db()
        self.product.refresh_from_db()
        self.assertEqual(order.status, Order.Status.CANCELED)
        self.assertEqual(self.product.quantity, 5)

    def test_cancel_action_only_accepts_post(self):
        order = Order.objects.create(user=self.user, address=self.address)
        self.client.force_login(self.user)

        response = self.client.get(
            reverse('orders:cancel', args=[order.pk])
        )

        self.assertEqual(response.status_code, 405)

    def test_order_cannot_process_before_successful_payment(self):
        order = Order.objects.create(user=self.user, address=self.address)

        with self.assertRaises(ValidationError):
            selectors.change_order_status_by_admin(
                order.pk,
                Order.Status.PROCESSING,
            )

        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.PENDING)

    def test_order_follows_the_valid_status_path(self):
        order = Order.objects.create(user=self.user, address=self.address)
        Payment.objects.create(
            order=order,
            user=self.user,
            gateway=Payment.Gateway.TEST,
            status=Payment.Status.PAID,
            amount='100.00',
        )

        selectors.change_order_status_by_admin(
            order.pk,
            Order.Status.PROCESSING,
        )
        selectors.change_order_status_by_admin(
            order.pk,
            Order.Status.SHIPPED,
        )
        selectors.change_order_status_by_admin(
            order.pk,
            Order.Status.DELIVERED,
        )

        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.DELIVERED)

    def test_order_cannot_skip_or_move_back_between_statuses(self):
        order = Order.objects.create(user=self.user, address=self.address)

        with self.assertRaises(ValidationError):
            selectors.change_order_status_by_admin(
                order.pk,
                Order.Status.SHIPPED,
            )

        order.status = Order.Status.SHIPPED
        order.save(update_fields=('status',))
        with self.assertRaises(ValidationError):
            selectors.change_order_status_by_admin(
                order.pk,
                Order.Status.PROCESSING,
            )

    def test_canceled_order_is_a_terminal_status(self):
        order = Order.objects.create(
            user=self.user,
            address=self.address,
            status=Order.Status.CANCELED,
        )

        with self.assertRaises(ValidationError):
            selectors.change_order_status_by_admin(
                order.pk,
                Order.Status.PROCESSING,
            )

        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.CANCELED)
