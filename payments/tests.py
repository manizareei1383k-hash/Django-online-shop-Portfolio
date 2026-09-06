from decimal import Decimal

from django.test import TestCase, override_settings
from django.urls import reverse

from account.models import Address, User, Wallet, WalletTransaction
from orders import selectors as order_selectors
from orders.models import Order, OrderItem, ShippingMethod
from shop.models import Category, Product

from . import selectors as payment_selectors
from .models import Payment


@override_settings(DEBUG=True)
class PaymentViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            phone_number='09124440000',
            password='safe-password-123',
        )
        self.address = Address.objects.create(
            user=self.user,
            recipient_name='Test User',
            recipient_phone=self.user.phone_number,
            province='Tehran',
            city='Tehran',
            address='Test address',
            postal_code='1234567890',
        )
        self.shipping = ShippingMethod.objects.create(
            name='Post',
            price='20.00',
        )
        self.category = Category.objects.create(
            name='Test category',
            image='category_images/test.jpg',
        )
        self.product = Product.objects.create(
            name='Test product',
            price='100.00',
            quantity=5,
            status='available',
            category=self.category,
        )
        self.order = Order.objects.create(
            user=self.user,
            address=self.address,
            shipping_method=self.shipping,
            shipping_cost='20.00',
        )
        OrderItem.objects.create(
            order=self.order,
            product=self.product,
            quantity=2,
            unit_price='100.00',
        )

    def test_payment_urls_require_login(self):
        token = '9bd1f251-2d0f-4f19-a770-da67e51c9033'
        urls = (
            reverse('payments:start', args=[self.order.pk]),
            reverse('payments:test_gateway', args=[token]),
            reverse('payments:test_gateway_callback', args=[token]),
        )
        for url in urls:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 302)
                self.assertTrue(response.url.startswith(reverse('account:login')))

    def test_amount_is_always_calculated_on_server(self):
        self.client.force_login(self.user)

        response = self.client.post(
            reverse('payments:start', args=[self.order.pk]),
            {'gateway': Payment.Gateway.TEST, 'amount': '1.00'},
        )

        payment = Payment.objects.get(order=self.order)
        self.assertRedirects(
            response,
            reverse('payments:test_gateway', args=[payment.token]),
        )
        self.assertEqual(payment.amount, Decimal('220.00'))

    def test_successful_test_payment_changes_order_status(self):
        self.client.force_login(self.user)
        self.client.post(
            reverse('payments:start', args=[self.order.pk]),
            {'gateway': Payment.Gateway.TEST},
        )
        payment = Payment.objects.get(order=self.order)

        response = self.client.post(
            reverse('payments:test_gateway_callback', args=[payment.token]),
            {'result': 'success'},
        )

        payment.refresh_from_db()
        self.order.refresh_from_db()
        self.assertRedirects(
            response,
            reverse('orders:detail', args=[self.order.pk]),
        )
        self.assertEqual(payment.status, Payment.Status.PAID)
        self.assertTrue(payment.gateway_reference.startswith('TEST-'))
        self.assertIsNotNone(payment.paid_at)
        self.assertEqual(self.order.status, Order.Status.PROCESSING)

    def test_test_callback_is_idempotent(self):
        self.client.force_login(self.user)
        self.client.post(
            reverse('payments:start', args=[self.order.pk]),
            {'gateway': Payment.Gateway.TEST},
        )
        payment = Payment.objects.get(order=self.order)
        callback_url = reverse(
            'payments:test_gateway_callback', args=[payment.token]
        )

        self.client.post(callback_url, {'result': 'success'})
        payment.refresh_from_db()
        first_reference = payment.gateway_reference
        self.client.post(callback_url, {'result': 'success'})

        payment.refresh_from_db()
        self.assertEqual(payment.status, Payment.Status.PAID)
        self.assertEqual(payment.gateway_reference, first_reference)
        self.assertEqual(Payment.objects.filter(order=self.order).count(), 1)

    def test_failed_test_payment_keeps_order_pending(self):
        self.client.force_login(self.user)
        self.client.post(
            reverse('payments:start', args=[self.order.pk]),
            {'gateway': Payment.Gateway.TEST},
        )
        payment = Payment.objects.get(order=self.order)

        self.client.post(
            reverse('payments:test_gateway_callback', args=[payment.token]),
            {'result': 'failed'},
        )

        payment.refresh_from_db()
        self.order.refresh_from_db()
        self.assertEqual(payment.status, Payment.Status.FAILED)
        self.assertEqual(self.order.status, Order.Status.PENDING)

    def test_other_user_cannot_open_or_complete_payment(self):
        other_user = User.objects.create_user(
            phone_number='09124440001',
            password='safe-password-123',
        )
        payment = Payment.objects.create(
            order=self.order,
            user=self.user,
            gateway=Payment.Gateway.TEST,
            amount='220.00',
        )
        self.client.force_login(other_user)

        gateway_response = self.client.get(
            reverse('payments:test_gateway', args=[payment.token])
        )
        callback_response = self.client.post(
            reverse('payments:test_gateway_callback', args=[payment.token]),
            {'result': 'success'},
        )

        self.assertEqual(gateway_response.status_code, 404)
        self.assertEqual(callback_response.status_code, 404)
        payment.refresh_from_db()
        self.assertEqual(payment.status, Payment.Status.PENDING)

    def test_wallet_payment_debits_balance_once(self):
        wallet = Wallet.objects.create(user=self.user)
        wallet.credit('1000')
        self.client.force_login(self.user)

        response = self.client.post(
            reverse('payments:start', args=[self.order.pk]),
            {'gateway': Payment.Gateway.WALLET},
        )

        payment = Payment.objects.get(order=self.order)
        wallet.refresh_from_db()
        self.order.refresh_from_db()
        self.assertRedirects(
            response,
            reverse('orders:detail', args=[self.order.pk]),
        )
        self.assertEqual(payment.status, Payment.Status.PAID)
        self.assertEqual(wallet.balance, Decimal('780'))
        self.assertEqual(self.order.status, Order.Status.PROCESSING)
        self.assertEqual(
            wallet.transactions.filter(kind='purchase').count(),
            1,
        )

    def test_insufficient_wallet_balance_fails_safely(self):
        wallet = Wallet.objects.create(user=self.user)
        wallet.credit('100')
        self.client.force_login(self.user)

        self.client.post(
            reverse('payments:start', args=[self.order.pk]),
            {'gateway': Payment.Gateway.WALLET},
        )

        payment = Payment.objects.get(order=self.order)
        wallet.refresh_from_db()
        self.order.refresh_from_db()
        self.assertEqual(payment.status, Payment.Status.FAILED)
        self.assertEqual(wallet.balance, Decimal('100'))
        self.assertEqual(self.order.status, Order.Status.PENDING)
        self.assertFalse(wallet.transactions.filter(kind='purchase').exists())

    def test_paid_order_cannot_be_paid_again(self):
        Wallet.objects.create(user=self.user).credit('1000')
        self.client.force_login(self.user)
        start_url = reverse('payments:start', args=[self.order.pk])

        self.client.post(start_url, {'gateway': Payment.Gateway.WALLET})
        self.client.post(start_url, {'gateway': Payment.Gateway.WALLET})

        self.assertEqual(Payment.objects.filter(order=self.order).count(), 1)

    def test_payment_actions_reject_get(self):
        payment = Payment.objects.create(
            order=self.order,
            user=self.user,
            gateway=Payment.Gateway.TEST,
            amount='220.00',
        )
        self.client.force_login(self.user)

        start_response = self.client.get(
            reverse('payments:start', args=[self.order.pk])
        )
        callback_response = self.client.get(
            reverse('payments:test_gateway_callback', args=[payment.token])
        )

        self.assertEqual(start_response.status_code, 405)
        self.assertEqual(callback_response.status_code, 405)

    @override_settings(DEBUG=False)
    def test_test_gateway_is_disabled_outside_development(self):
        self.client.force_login(self.user)

        response = self.client.post(
            reverse('payments:start', args=[self.order.pk]),
            {'gateway': Payment.Gateway.TEST},
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(Payment.objects.filter(order=self.order).exists())

    def test_admin_cancel_refunds_wallet_payment_only_once(self):
        wallet = Wallet.objects.create(user=self.user)
        wallet.credit('1000')
        self.client.force_login(self.user)
        self.client.post(
            reverse('payments:start', args=[self.order.pk]),
            {'gateway': Payment.Gateway.WALLET},
        )
        payment = Payment.objects.get(order=self.order)

        first_result = order_selectors.cancel_order_by_admin(self.order.pk)
        second_result = order_selectors.cancel_order_by_admin(self.order.pk)

        wallet.refresh_from_db()
        payment.refresh_from_db()
        self.order.refresh_from_db()
        self.assertTrue(first_result)
        self.assertFalse(second_result)
        self.assertEqual(wallet.balance, Decimal('1000'))
        self.assertEqual(payment.status, Payment.Status.REFUNDED)
        self.assertTrue(payment.refund_reference)
        self.assertIsNotNone(payment.refunded_at)
        self.assertEqual(self.order.status, Order.Status.CANCELED)
        self.assertEqual(
            wallet.transactions.filter(
                kind=WalletTransaction.Kind.REFUND
            ).count(),
            1,
        )

    def test_admin_cancel_marks_test_payment_as_refunded(self):
        self.client.force_login(self.user)
        self.client.post(
            reverse('payments:start', args=[self.order.pk]),
            {'gateway': Payment.Gateway.TEST},
        )
        payment = Payment.objects.get(order=self.order)
        self.client.post(
            reverse('payments:test_gateway_callback', args=[payment.token]),
            {'result': 'success'},
        )

        order_selectors.cancel_order_by_admin(self.order.pk)

        payment.refresh_from_db()
        self.assertEqual(payment.status, Payment.Status.REFUNDED)
        self.assertTrue(payment.refund_reference.startswith('TEST-REFUND-'))
        self.assertIsNotNone(payment.refunded_at)

    def test_cancel_order_cancels_its_pending_payments(self):
        payment = Payment.objects.create(
            order=self.order,
            user=self.user,
            gateway=Payment.Gateway.TEST,
            amount='220.00',
        )
        self.client.force_login(self.user)

        self.client.post(reverse('orders:cancel', args=[self.order.pk]))

        payment.refresh_from_db()
        self.assertEqual(payment.status, Payment.Status.CANCELED)

    def test_failed_refund_rolls_back_order_cancellation(self):
        self.order.status = Order.Status.PROCESSING
        self.order.save(update_fields=('status',))
        Payment.objects.create(
            order=self.order,
            user=self.user,
            gateway='unsupported',
            status=Payment.Status.PAID,
            amount='220.00',
        )
        original_quantity = self.product.quantity

        with self.assertRaises(payment_selectors.PaymentError):
            order_selectors.cancel_order_by_admin(self.order.pk)

        self.order.refresh_from_db()
        self.product.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.PROCESSING)
        self.assertEqual(self.product.quantity, original_quantity)
