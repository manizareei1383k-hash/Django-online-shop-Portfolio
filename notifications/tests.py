from django.http import Http404
from django.test import TestCase

from account.models import Address, Ticket, TicketMessage, User, Wallet
from orders import selectors as order_selectors
from orders.models import Order, OrderItem, ShippingMethod
from payments import selectors as payment_selectors
from payments.models import Payment
from shop.models import Category, Product

from . import selectors
from .models import Notification


class NotificationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            phone_number='09126660000',
            password='safe-password-123',
        )
        self.other_user = User.objects.create_user(
            phone_number='09126660001',
            password='safe-password-123',
        )

    def test_unique_key_prevents_duplicate_notifications(self):
        first = selectors.create_notification(
            self.user,
            Notification.Kind.SYSTEM,
            'Title',
            'Message',
            unique_key='same-event',
        )
        second = selectors.create_notification(
            self.user,
            Notification.Kind.SYSTEM,
            'Different title',
            'Different message',
            unique_key='same-event',
        )

        self.assertEqual(first.pk, second.pk)
        self.assertEqual(Notification.objects.count(), 1)

    def test_user_can_only_mark_own_notification_as_read(self):
        notification = selectors.create_notification(
            self.user,
            Notification.Kind.SYSTEM,
            'Title',
            'Message',
        )

        with self.assertRaises(Http404):
            selectors.mark_notification_as_read(
                self.other_user,
                notification.pk,
            )

        notification.refresh_from_db()
        self.assertFalse(notification.is_read)
        selectors.mark_notification_as_read(self.user, notification.pk)
        notification.refresh_from_db()
        self.assertTrue(notification.is_read)
        self.assertIsNotNone(notification.read_at)

    def test_mark_all_only_changes_current_users_notifications(self):
        own = selectors.create_notification(
            self.user,
            Notification.Kind.SYSTEM,
            'Own',
            'Message',
        )
        other = selectors.create_notification(
            self.other_user,
            Notification.Kind.SYSTEM,
            'Other',
            'Message',
        )

        updated_count = selectors.mark_all_notifications_as_read(self.user)

        own.refresh_from_db()
        other.refresh_from_db()
        self.assertEqual(updated_count, 1)
        self.assertTrue(own.is_read)
        self.assertFalse(other.is_read)


class AutomaticNotificationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            phone_number='09127770000',
            password='safe-password-123',
        )
        self.address = Address.objects.create(
            user=self.user,
            recipient_name='Buyer',
            recipient_phone=self.user.phone_number,
            province='Tehran',
            city='Tehran',
            address='Address',
            postal_code='1234567890',
        )
        self.shipping = ShippingMethod.objects.create(
            name='Post',
            price='20.00',
        )
        category = Category.objects.create(
            name='Category',
            image='category_images/test.jpg',
        )
        self.product = Product.objects.create(
            name='Product',
            price='100.00',
            quantity=5,
            status='available',
            category=category,
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

    def test_successful_payment_creates_payment_invoice_and_status_notifications(self):
        Wallet.objects.create(user=self.user).credit('1000')

        payment_selectors.create_payment(
            self.user,
            self.order.pk,
            Payment.Gateway.WALLET,
        )

        kinds = set(self.user.notifications.values_list('kind', flat=True))
        self.assertIn(Notification.Kind.PAYMENT_SUCCESS, kinds)
        self.assertIn(Notification.Kind.INVOICE_ISSUED, kinds)
        self.assertIn(Notification.Kind.ORDER_STATUS, kinds)

    def test_failed_payment_creates_failure_notification(self):
        Wallet.objects.create(user=self.user).credit('10')

        payment_selectors.create_payment(
            self.user,
            self.order.pk,
            Payment.Gateway.WALLET,
        )

        self.assertTrue(
            self.user.notifications.filter(
                kind=Notification.Kind.PAYMENT_FAILED
            ).exists()
        )

    def test_refund_creates_refund_and_cancellation_notifications(self):
        Wallet.objects.create(user=self.user).credit('1000')
        payment_selectors.create_payment(
            self.user,
            self.order.pk,
            Payment.Gateway.WALLET,
        )

        order_selectors.cancel_order_by_admin(self.order.pk)

        self.assertTrue(
            self.user.notifications.filter(
                kind=Notification.Kind.PAYMENT_REFUNDED
            ).exists()
        )
        self.assertTrue(
            self.user.notifications.filter(
                kind=Notification.Kind.ORDER_STATUS,
                data__status=Order.Status.CANCELED,
            ).exists()
        )

    def test_admin_ticket_reply_notifies_user_but_users_own_message_does_not(self):
        admin_user = User.objects.create_superuser(
            phone_number='09127770001',
            password='safe-password-123',
        )
        ticket = Ticket.objects.create(user=self.user, subject='Question')

        TicketMessage.objects.create(
            ticket=ticket,
            sender=self.user,
            message='User message',
        )
        self.assertFalse(
            self.user.notifications.filter(
                kind=Notification.Kind.TICKET_REPLY
            ).exists()
        )

        TicketMessage.objects.create(
            ticket=ticket,
            sender=admin_user,
            message='Admin reply',
        )

        self.assertEqual(
            self.user.notifications.filter(
                kind=Notification.Kind.TICKET_REPLY
            ).count(),
            1,
        )
