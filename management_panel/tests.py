from datetime import timedelta
import logging

from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from account.models import Address, Ticket, User, Wallet
from invoices.models import Invoice
from management_panel.models import AdminActivity, SystemLog
from config.observability import DatabaseErrorHandler
from notifications.models import Notification
from orders.models import Order, OrderItem, ShippingMethod
from payments import selectors as payment_selectors
from payments.models import Payment
from shop.models import Category, Product, ProductDiscount, Review, ReviewReply

from . import selectors
from .cache import DASHBOARD_STATS_CACHE_KEY


class ManagementPanelTests(TestCase):
    def setUp(self):
        self.admin_user = User.objects.create_superuser(
            phone_number='09128880000',
            password='safe-password-123',
        )
        self.user = User.objects.create_user(
            phone_number='09128880001',
            password='safe-password-123',
            email='user@example.com',
        )
        self.category = Category.objects.create(
            name='Category',
            image='category_images/test.jpg',
        )
        self.product = Product.objects.create(
            name='Product',
            price='100.00',
            status='available',
            quantity=10,
            category=self.category,
        )
        self.shipping = ShippingMethod.objects.create(
            name='Post',
            price='20.00',
            estimated_delivery_days=2,
        )
        self.address = Address.objects.create(
            user=self.user,
            recipient_name='User',
            recipient_phone=self.user.phone_number,
            province='Tehran',
            city='Tehran',
            address='Address',
            postal_code='1234567890',
        )

    def test_dashboard_summary_is_cached(self):
        cache.clear()

        with self.assertNumQueries(6):
            first_stats = selectors.get_dashboard_stats()
        with self.assertNumQueries(0):
            cached_stats = selectors.get_dashboard_stats()

        self.assertEqual(cached_stats, first_stats)

    def test_dashboard_cache_is_invalidated_after_related_change(self):
        cache.clear()
        old_stats = selectors.get_dashboard_stats()
        self.assertIsNotNone(cache.get(DASHBOARD_STATS_CACHE_KEY))

        with self.captureOnCommitCallbacks(execute=True):
            Product.objects.create(
                name='Second product',
                price='50.00',
                status='available',
                quantity=1,
                category=self.category,
            )

        self.assertIsNone(cache.get(DASHBOARD_STATS_CACHE_KEY))
        new_stats = selectors.get_dashboard_stats()
        self.assertEqual(
            new_stats['products_count'],
            old_stats['products_count'] + 1,
        )

    def test_error_log_is_saved_and_shown_on_system_logs_page(self):
        record = logging.LogRecord(
            'shop.test',
            logging.ERROR,
            __file__,
            1,
            'Test dashboard error',
            (),
            None,
        )
        record.request_id = 'a' * 32
        record.method = 'GET'
        record.path = '/broken/'
        record.status_code = 500
        DatabaseErrorHandler().emit(record)

        self.client.force_login(self.admin_user)
        response = self.client.get(reverse('management_panel:system_logs'))

        self.assertEqual(SystemLog.objects.count(), 1)
        self.assertContains(response, 'Test dashboard error')

    def test_panel_requires_staff_access(self):
        panel_urls = (
            reverse('management_panel:dashboard'),
            reverse('management_panel:products'),
            reverse('management_panel:categories'),
            reverse('management_panel:shipping_methods'),
            reverse('management_panel:orders'),
            reverse('management_panel:tickets'),
            reverse('management_panel:reviews'),
            reverse('management_panel:payments'),
            reverse('management_panel:invoices'),
            reverse('management_panel:users'),
            reverse('management_panel:activities'),
            reverse('management_panel:system_logs'),
        )
        for url in panel_urls:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 302)

        self.client.force_login(self.user)
        for url in panel_urls:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 403)

    def test_staff_can_open_all_panel_sections(self):
        self.client.force_login(self.admin_user)
        urls = (
            reverse('management_panel:dashboard'),
            reverse('management_panel:products'),
            reverse('management_panel:categories'),
            reverse('management_panel:shipping_methods'),
            reverse('management_panel:orders'),
            reverse('management_panel:tickets'),
            reverse('management_panel:reviews'),
            reverse('management_panel:payments'),
            reverse('management_panel:invoices'),
            reverse('management_panel:users'),
            reverse('management_panel:activities'),
            reverse('management_panel:system_logs'),
        )
        for url in urls:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)

    def test_admin_can_create_category_and_shipping_method(self):
        self.client.force_login(self.admin_user)
        image = SimpleUploadedFile(
            'category.gif',
            b'GIF87a\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00\xff\xff\xff!\xf9\x04\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;',
            content_type='image/gif',
        )

        category_response = self.client.post(
            reverse('management_panel:category_create'),
            {'name': 'New category', 'image': image},
        )
        shipping_response = self.client.post(
            reverse('management_panel:shipping_create'),
            {
                'name': 'Express',
                'price': '40.00',
                'estimated_delivery_days': 1,
                'is_active': 'on',
            },
        )

        self.assertEqual(category_response.status_code, 302)
        self.assertEqual(shipping_response.status_code, 302)
        self.assertTrue(Category.objects.filter(name='New category').exists())
        self.assertTrue(ShippingMethod.objects.filter(name='Express').exists())
        self.assertEqual(
            AdminActivity.objects.filter(
                admin=self.admin_user,
                action=AdminActivity.Action.CREATE,
            ).count(),
            2,
        )

    def test_admin_can_create_and_edit_product_with_discount(self):
        self.client.force_login(self.admin_user)
        starts_at = timezone.now() + timedelta(hours=1)
        ends_at = starts_at + timedelta(days=2)
        create_data = {
            'name': 'Discounted product',
            'price': '500.00',
            'status': 'available',
            'description': 'Description',
            'quantity': 7,
            'category': self.category.pk,
            'discount_title': 'Launch sale',
            'discount_percent': '10.00',
            'discount_starts_at': starts_at.strftime('%Y-%m-%d %H:%M:%S'),
            'discount_ends_at': ends_at.strftime('%Y-%m-%d %H:%M:%S'),
            'discount_is_active': 'on',
        }

        response = self.client.post(
            reverse('management_panel:product_create'),
            create_data,
        )

        self.assertEqual(response.status_code, 302)
        product = Product.objects.get(name='Discounted product')
        discount = product.discounts.get()
        self.assertEqual(discount.percent, 10)

        create_data['name'] = 'Edited product'
        create_data['discount_percent'] = '20.00'
        response = self.client.post(
            reverse('management_panel:product_update', args=[product.pk]),
            create_data,
        )
        product.refresh_from_db()
        discount.refresh_from_db()
        self.assertEqual(response.status_code, 302)
        self.assertEqual(product.name, 'Edited product')
        self.assertEqual(discount.percent, 20)
        self.assertTrue(
            AdminActivity.objects.filter(
                admin=self.admin_user,
                action=AdminActivity.Action.UPDATE,
                target_type='shop.Product',
                target_id=str(product.pk),
            ).exists()
        )

    def test_admin_can_change_and_cancel_order_from_custom_panel(self):
        order = Order.objects.create(
            user=self.user,
            address=self.address,
            shipping_method=self.shipping,
            shipping_cost=self.shipping.price,
        )
        OrderItem.objects.create(
            order=order,
            product=self.product,
            quantity=2,
            unit_price='100.00',
        )
        Payment.objects.create(
            order=order,
            user=self.user,
            gateway=Payment.Gateway.TEST,
            status=Payment.Status.PAID,
            amount='220.00',
        )
        self.client.force_login(self.admin_user)

        status_response = self.client.post(
            reverse('management_panel:order_detail', args=[order.pk]),
            {'status': Order.Status.PROCESSING},
        )
        cancel_response = self.client.post(
            reverse('management_panel:order_cancel', args=[order.pk]),
        )

        order.refresh_from_db()
        self.assertEqual(status_response.status_code, 302)
        self.assertEqual(cancel_response.status_code, 302)
        self.assertEqual(order.status, Order.Status.CANCELED)
        self.assertTrue(
            AdminActivity.objects.filter(
                admin=self.admin_user,
                action=AdminActivity.Action.STATUS_CHANGE,
                target_id=str(order.pk),
            ).exists()
        )
        self.assertTrue(
            AdminActivity.objects.filter(
                admin=self.admin_user,
                action=AdminActivity.Action.CANCEL,
                target_id=str(order.pk),
            ).exists()
        )

    def test_admin_can_reply_to_ticket_and_review(self):
        ticket = Ticket.objects.create(user=self.user, subject='Help')
        review = Review.objects.create(
            user=self.user,
            product=self.product,
            name='User',
            email='user@example.com',
            review='Good product',
        )
        self.client.force_login(self.admin_user)

        ticket_response = self.client.post(
            reverse('management_panel:ticket_detail', args=[ticket.pk]),
            {'action': 'reply', 'message': 'Ticket answer'},
        )
        review_response = self.client.post(
            reverse('management_panel:review_detail', args=[review.pk]),
            {'message': 'Review answer'},
        )

        ticket.refresh_from_db()
        self.assertEqual(ticket_response.status_code, 302)
        self.assertEqual(review_response.status_code, 302)
        self.assertEqual(ticket.status, Ticket.Status.ANSWERED)
        self.assertTrue(ticket.messages.filter(sender=self.admin_user).exists())
        self.assertTrue(ReviewReply.objects.filter(review=review).exists())
        self.assertTrue(
            Notification.objects.filter(
                recipient=self.user,
                kind=Notification.Kind.REVIEW_REPLY,
            ).exists()
        )
        self.assertEqual(
            AdminActivity.objects.filter(
                admin=self.admin_user,
                action=AdminActivity.Action.REPLY,
            ).count(),
            2,
        )

    def test_panel_lists_users_payments_and_invoices(self):
        order = Order.objects.create(
            user=self.user,
            address=self.address,
            shipping_method=self.shipping,
            shipping_cost=self.shipping.price,
        )
        OrderItem.objects.create(
            order=order,
            product=self.product,
            quantity=2,
            unit_price='100.00',
        )
        Wallet.objects.create(user=self.user).credit('1000')
        payment_selectors.create_payment(
            self.user,
            order.pk,
            Payment.Gateway.WALLET,
        )
        self.client.force_login(self.admin_user)

        users_response = self.client.get(reverse('management_panel:users'))
        payments_response = self.client.get(reverse('management_panel:payments'))
        invoices_response = self.client.get(reverse('management_panel:invoices'))

        self.assertContains(users_response, self.user.phone_number)
        self.assertContains(payments_response, '220.00')
        self.assertContains(invoices_response, Invoice.objects.get(order=order).number)

    def test_delete_actions_only_accept_post(self):
        self.client.force_login(self.admin_user)
        urls = (
            reverse('management_panel:product_delete', args=[self.product.pk]),
            reverse('management_panel:category_delete', args=[self.category.pk]),
            reverse('management_panel:shipping_delete', args=[self.shipping.pk]),
        )
        for url in urls:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 405)

    def test_successful_delete_is_logged_with_snapshot_and_ip(self):
        self.client.force_login(self.admin_user)

        response = self.client.post(
            reverse('management_panel:product_delete', args=[self.product.pk]),
            REMOTE_ADDR='192.0.2.10',
        )

        self.assertEqual(response.status_code, 302)
        activity = AdminActivity.objects.get(
            action=AdminActivity.Action.DELETE,
            target_type='shop.Product',
        )
        self.assertEqual(activity.admin, self.admin_user)
        self.assertEqual(activity.target_id, str(self.product.pk))
        self.assertEqual(activity.target_label, 'Product')
        self.assertEqual(str(activity.ip_address), '192.0.2.10')

        page = self.client.get(reverse('management_panel:activities'))
        self.assertContains(page, 'Product')
