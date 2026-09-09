from io import BytesIO
import os
import runpy
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, SimpleTestCase, TestCase, override_settings
from django.core.exceptions import ImproperlyConfigured
from django.urls import reverse
from PIL import Image

from account.forms import RegisterForm, TicketMessageForm, UserProfileForm
from account.models import Address, Ticket, TicketMessage, User, Wallet
from cart.models import Cart, CartItem
from orders.models import Order, OrderItem, ShippingMethod
from payments.models import Payment
from payments import selectors as payment_selectors
from shop.models import Category, Message, Product


class SecurityTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user('09121110000', 'Correct-pass-123!')
        cls.other = User.objects.create_user('09121110001', 'Correct-pass-123!')
        cls.admin = User.objects.create_superuser('09121110002', 'Correct-pass-123!')
        cls.category = Category.objects.create(name='Category', image='test.jpg')
        cls.product = Product.objects.create(name='Product', price=100, category=cls.category, quantity=10)
        cls.address = Address.objects.create(user=cls.user, recipient_name='Owner', recipient_phone=cls.user.phone_number,
                                            province='Tehran', city='Tehran', address='Address', postal_code='1234567890')
        cls.shipping = ShippingMethod.objects.create(name='Post', price=20)
        cls.order = Order.objects.create(user=cls.user, address=cls.address, shipping_method=cls.shipping)
        OrderItem.objects.create(order=cls.order, product=cls.product, unit_price=100, quantity=1)
        cls.cart = Cart.objects.create(user=cls.user)
        cls.item = CartItem.objects.create(cart=cls.cart, product=cls.product, quantity=1)
        cls.ticket = Ticket.objects.create(user=cls.user, subject='Private')

    def test_other_user_cannot_mutate_private_objects(self):
        self.client.force_login(self.other)
        paths = [
            reverse('account:address_update', args=[self.address.pk]),
            reverse('account:address_delete', args=[self.address.pk]),
            reverse('account:ticket_detail', args=[self.ticket.pk]),
            reverse('orders:cancel', args=[self.order.pk]),
            reverse('payments:start', args=[self.order.pk]),
        ]
        for path in paths:
            with self.subTest(path=path):
                self.assertEqual(self.client.post(path, {'message': 'attack', 'gateway': 'wallet'}).status_code, 404)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.PENDING)
        self.assertEqual(self.ticket.messages.count(), 0)

    def test_admin_mutations_reject_regular_user(self):
        self.client.force_login(self.other)
        for name, args in [
            ('product_create', []), ('product_update', [self.product.pk]), ('product_delete', [self.product.pk]),
            ('category_create', []), ('category_delete', [self.category.pk]),
            ('shipping_create', []), ('shipping_delete', [self.shipping.pk]),
            ('order_cancel', [self.order.pk]), ('order_detail', [self.order.pk]),
            ('ticket_detail', [self.ticket.pk]),
        ]:
            with self.subTest(name=name):
                url = reverse(f'management_panel:{name}', args=args)
                self.assertEqual(self.client.post(url, {'status': 'canceled'}).status_code, 403)
        self.assertTrue(Product.objects.filter(pk=self.product.pk).exists())

    def test_csrf_required_for_login_contact_and_authenticated_mutations(self):
        client = Client(enforce_csrf_checks=True)
        for name in ['account:login', 'shop:contact_us']:
            self.assertEqual(client.post(reverse(name), {}).status_code, 403)
        client.force_login(self.admin)
        self.assertEqual(client.post(reverse('management_panel:product_delete', args=[self.product.pk])).status_code, 403)
        self.assertTrue(Product.objects.filter(pk=self.product.pk).exists())

    def test_get_does_not_cancel_or_delete(self):
        self.client.force_login(self.admin)
        url = reverse('management_panel:order_cancel', args=[self.order.pk])
        self.assertEqual(self.client.get(url).status_code, 405)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.PENDING)

    def test_profile_requires_password_for_recovery_identity_changes(self):
        data = {'email': 'attacker@example.com', 'phone_number': self.user.phone_number}
        form = UserProfileForm(data=data, instance=self.user)
        self.assertFalse(form.is_valid())
        self.assertIn('current_password', form.errors)
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, '')

    def test_profile_cannot_set_privileges_or_balance(self):
        self.client.force_login(self.user)
        self.client.post(reverse('account:profile_edit'), {
            'phone_number': self.user.phone_number, 'email': '',
            'is_staff': True, 'is_superuser': True, 'balance': '999999',
        })
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_staff)
        self.assertFalse(self.user.is_superuser)
        self.assertFalse(Wallet.objects.filter(user=self.user, balance__gt=0).exists())

    def test_security_headers_and_private_cache(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse('account:profile'))
        self.assertIn('no-store', response['Cache-Control'])
        self.assertIn("frame-ancestors 'none'", response['Content-Security-Policy'])
        self.assertEqual(response['X-Content-Type-Options'], 'nosniff')
        self.assertEqual(response['X-Frame-Options'], 'DENY')

    def test_invalid_host_and_large_request_rejected(self):
        self.assertEqual(self.client.get('/', HTTP_HOST='evil.example').status_code, 400)
        response = self.client.post(reverse('shop:contact_us'), {}, CONTENT_LENGTH=str(7 * 1024 * 1024))
        self.assertEqual(response.status_code, 413)
        self.assertEqual(Message.objects.count(), 0)

    def test_django_admin_disabled(self):
        self.assertEqual(self.client.get('/admin/').status_code, 404)

    def test_invalid_category_filters_do_not_crash(self):
        for category in ['²', '9' * 200, "1 OR 1=1"]:
            self.assertEqual(self.client.get(reverse('shop:shop'), {'category': category}).status_code, 200)

    def test_search_input_is_escaped_and_not_executed(self):
        response = self.client.get(reverse('shop:shop'), {'q': '<script>alert(1)</script>'})
        self.assertNotContains(response, '<script>alert(1)</script>')
        self.assertEqual(Product.objects.count(), 1)

    @override_settings(DEBUG=True, ENABLE_TEST_GATEWAY=False)
    def test_test_gateway_stays_disabled_even_if_debug_accidentally_enabled(self):
        with self.assertRaises(payment_selectors.PaymentError):
            payment_selectors.create_payment(self.user, self.order.pk, Payment.Gateway.TEST)
        self.assertEqual(Payment.objects.count(), 0)

    def test_ticket_attachment_is_private_and_forced_download(self):
        with TemporaryDirectory() as directory, override_settings(PRIVATE_MEDIA_ROOT=directory):
            message = TicketMessage.objects.create(ticket=self.ticket, sender=self.user, message='File',
                attachment=SimpleUploadedFile('file.pdf', b'%PDF-1.4\nexample', content_type='application/pdf'))
            url = message.attachment.url
            self.assertEqual(self.client.get(url).status_code, 302)
            self.client.force_login(self.other)
            self.assertEqual(self.client.get(url).status_code, 404)
            for user in [self.user, self.admin]:
                self.client.force_login(user)
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200)
                self.assertIn('attachment;', response['Content-Disposition'])
                self.assertEqual(response['Content-Type'], 'application/octet-stream')
                response.close()
            self.assertEqual(self.client.get('/media/account/tickets/file.pdf').status_code, 404)

    def test_reject_executable_and_disguised_ticket_uploads(self):
        for filename in ['attack.html', 'attack.svg', 'attack.pdf', 'attack.jpg']:
            form = TicketMessageForm(data={'message': 'x'}, files={
                'attachment': SimpleUploadedFile(filename, b'<script>alert(1)</script>')})
            with self.subTest(filename=filename):
                self.assertFalse(form.is_valid())
                self.assertIn('attachment', form.errors)

    def test_uploaded_image_payload_is_removed(self):
        raw = BytesIO()
        Image.new('RGB', (2, 2)).save(raw, format='PNG')
        payload = raw.getvalue() + b'<script>evil()</script>'
        form = RegisterForm(data={'phone_number': '09129998888', 'password1': 'Stronger-pass-123!',
                                 'password2': 'Stronger-pass-123!'}, files={
            'avatar': SimpleUploadedFile('image.png', payload, content_type='image/png')})
        self.assertTrue(form.is_valid(), form.errors)
        self.assertNotIn(b'<script>', form.cleaned_data['avatar'].read())

    @override_settings(MAX_UPLOAD_BYTES=16)
    def test_oversized_optional_upload_cannot_still_create_message(self):
        self.client.force_login(self.user)
        response = self.client.post(reverse('account:ticket_detail', args=[self.ticket.pk]), {
            'message': 'must not save', 'attachment': SimpleUploadedFile('big.pdf', b'%PDF-' + b'x' * 50)})
        self.assertEqual(response.status_code, 413)
        self.assertEqual(self.ticket.messages.count(), 0)


@override_settings(RATE_LIMIT_ENABLED=True)
class RateLimitSecurityTests(TestCase):
    def setUp(self):
        cache.clear()
        timer = patch('config.middleware.time.time', return_value=120)
        timer.start()
        self.addCleanup(timer.stop)

    def test_changing_forwarded_ip_does_not_bypass_limit(self):
        for i in range(5):
            self.assertEqual(self.client.get('/', HTTP_X_FORWARDED_FOR=f'192.0.2.{i}').status_code, 200)
        self.assertEqual(self.client.get('/', HTTP_X_FORWARDED_FOR='203.0.113.1').status_code, 429)

    def test_login_account_limit_survives_actual_ip_change(self):
        for i in range(5):
            response = self.client.post(reverse('account:login'), {'username': '09121110000', 'password': 'bad'}, REMOTE_ADDR=f'192.0.2.{i}')
            self.assertEqual(response.status_code, 200)
        response = self.client.post(reverse('account:login'), {'username': '09121110000', 'password': 'bad'}, REMOTE_ADDR='203.0.113.1')
        self.assertEqual(response.status_code, 429)

    def test_rotating_object_id_does_not_bypass_route_limit(self):
        for i in range(5):
            self.assertEqual(self.client.get(f'/product/{i + 1}/').status_code, 404)
        self.assertEqual(self.client.get('/product/999/').status_code, 429)

    def test_ipv6_address_rotation_within_subnet_is_limited(self):
        for i in range(5):
            self.assertEqual(self.client.get('/', REMOTE_ADDR=f'2001:db8::{i + 1}').status_code, 200)
        self.assertEqual(self.client.get('/', REMOTE_ADDR='2001:db8::ff').status_code, 429)

    def test_cache_outage_fails_closed(self):
        with patch('config.middleware.cache.add', side_effect=ConnectionError):
            self.assertEqual(self.client.get('/').status_code, 503)


class ProductionConfigurationTests(SimpleTestCase):
    def environment(self):
        return {
            'DJANGO_SECRET_KEY': 'test-only-production-configuration-key-' * 2,
            'DJANGO_ALLOWED_HOSTS': 'shop.example.com',
            'REDIS_URL': 'redis://127.0.0.1:6379/1',
            'POSTGRES_DB': 'test', 'POSTGRES_USER': 'test',
            'POSTGRES_PASSWORD': 'test', 'POSTGRES_HOST': '127.0.0.1',
            'EMAIL_HOST': 'smtp.example.com', 'EMAIL_HOST_USER': 'test',
            'EMAIL_HOST_PASSWORD': 'test', 'DEFAULT_FROM_EMAIL': 'test@example.com',
        }

    def test_missing_configuration_refuses_startup(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(ImproperlyConfigured):
                runpy.run_module('config.production')

    def test_production_rejects_weak_secret_and_wildcard_host(self):
        for field, value in [('DJANGO_SECRET_KEY', 'weak'), ('DJANGO_ALLOWED_HOSTS', '*')]:
            env = self.environment()
            env[field] = value
            with self.subTest(field=field), patch.dict(os.environ, env, clear=True):
                with self.assertRaises(ImproperlyConfigured):
                    runpy.run_module('config.production')

    def test_production_cannot_enable_debug_or_test_gateway(self):
        env = self.environment()
        env['DJANGO_DEBUG'] = 'true'
        with patch.dict(os.environ, env, clear=True):
            config = runpy.run_module('config.production')
        self.assertFalse(config['DEBUG'])
        self.assertFalse(config['ENABLE_TEST_GATEWAY'])
        self.assertTrue(config['RATE_LIMIT_ENABLED'])
        self.assertTrue(config['SECURE_SSL_REDIRECT'])
        self.assertTrue(config['SESSION_COOKIE_SECURE'])
        self.assertEqual(config['CACHES']['default']['BACKEND'], 'django_redis.cache.RedisCache')
        self.assertEqual(config['DATABASES']['default']['ENGINE'], 'django.db.backends.postgresql')
        self.assertEqual(config['CELERY_BROKER_URL'], 'redis://127.0.0.1:6379/2')
        self.assertEqual(config['CELERY_RESULT_BACKEND'], 'redis://127.0.0.1:6379/3')
