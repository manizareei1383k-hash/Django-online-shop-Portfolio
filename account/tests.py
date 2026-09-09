import uuid

from django.core import mail
from django.core.exceptions import ValidationError
from django.contrib.auth.tokens import default_token_generator
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from orders.models import Order

from .models import (
    Address,
    Ticket,
    TicketMessage,
    User,
    Wallet,
    WalletTransaction,
)


class UserModelTests(TestCase):
    def test_create_user_with_phone_number(self):
        user = User.objects.create_user(
            phone_number='09123456789',
            password='safe-password-123',
            first_name='Test',
        )

        self.assertEqual(user.phone_number, '09123456789')
        self.assertTrue(user.check_password('safe-password-123'))
        self.assertEqual(str(user), 'Test')
        self.assertTrue(
            self.client.login(
                phone_number='09123456789',
                password='safe-password-123',
            )
        )

    def test_create_superuser(self):
        user = User.objects.create_superuser(
            phone_number='09120000000',
            password='safe-password-123',
        )

        self.assertTrue(user.is_staff)
        self.assertTrue(user.is_superuser)

    def test_user_can_have_multiple_addresses(self):
        user = User.objects.create_user(
            phone_number='09121111111',
            password='safe-password-123',
        )
        Address.objects.create(
            user=user,
            title='خانه',
            recipient_name='Test User',
            recipient_phone='09121111111',
            province='تهران',
            city='تهران',
            address='آدرس آزمایشی اول',
            postal_code='1234567890',
            is_default=True,
        )
        Address.objects.create(
            user=user,
            title='محل کار',
            recipient_name='Test User',
            recipient_phone='09121111111',
            province='تهران',
            city='تهران',
            address='آدرس آزمایشی دوم',
            postal_code='0987654321',
        )

        self.assertEqual(user.addresses.count(), 2)
        self.assertEqual(user.addresses.first().title, 'خانه')

    def test_user_ticket_can_have_multiple_messages(self):
        user = User.objects.create_user(
            phone_number='09122222222',
            password='safe-password-123',
        )
        ticket = Ticket.objects.create(
            user=user,
            subject='پیگیری سفارش',
            priority=Ticket.Priority.HIGH,
        )
        TicketMessage.objects.create(
            ticket=ticket,
            sender=user,
            message='سفارش من چه زمانی ارسال می‌شود؟',
        )
        TicketMessage.objects.create(
            ticket=ticket,
            sender=user,
            message='لطفاً وضعیت را اطلاع دهید.',
        )

        self.assertEqual(user.tickets.count(), 1)
        self.assertEqual(ticket.messages.count(), 2)
        self.assertEqual(ticket.status, Ticket.Status.OPEN)

    def test_wallet_credit_and_debit_create_transaction_history(self):
        user = User.objects.create_user(
            phone_number='09123333333',
            password='safe-password-123',
        )
        wallet = Wallet.objects.create(user=user)

        wallet.credit(1000)
        wallet.debit(300)

        wallet.refresh_from_db()
        self.assertEqual(wallet.balance, 700)
        self.assertEqual(wallet.transactions.count(), 2)
        self.assertEqual(
            wallet.transactions.first().direction,
            WalletTransaction.Direction.DEBIT,
        )

    def test_wallet_rejects_insufficient_balance(self):
        user = User.objects.create_user(
            phone_number='09124444444',
            password='safe-password-123',
        )
        wallet = Wallet.objects.create(user=user)

        with self.assertRaises(ValidationError):
            wallet.debit(1)

        wallet.refresh_from_db()
        self.assertEqual(wallet.balance, 0)
        self.assertEqual(wallet.transactions.count(), 0)

    def test_wallet_reference_is_idempotent(self):
        user = User.objects.create_user(
            phone_number='09125555555',
            password='safe-password-123',
        )
        wallet = Wallet.objects.create(user=user)
        reference = uuid.uuid4()

        first = wallet.credit(500, reference=reference)
        second = wallet.credit(500, reference=reference)

        wallet.refresh_from_db()
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(wallet.balance, 500)
        self.assertEqual(wallet.transactions.count(), 1)


class AccountViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            phone_number='09126666666',
            password='safe-password-123',
        )

    def test_register_and_login_pages_are_public(self):
        self.assertEqual(self.client.get(reverse('account:register')).status_code, 200)
        self.assertEqual(self.client.get(reverse('account:login')).status_code, 200)

    def test_register_creates_and_logs_in_user(self):
        response = self.client.post(
            reverse('account:register'),
            {
                'phone_number': '09128888888',
                'email': 'new@example.com',
                'first_name': 'New',
                'last_name': 'User',
                'password1': 'A-safe-password-456',
                'password2': 'A-safe-password-456',
            },
        )

        self.assertRedirects(response, reverse('account:profile'))
        created_user = User.objects.get(phone_number='09128888888')
        self.assertEqual(int(self.client.session['_auth_user_id']), created_user.pk)
        self.assertFalse(created_user.is_staff)
        self.assertFalse(created_user.is_superuser)

    def test_login_and_logout_actions(self):
        response = self.client.post(
            reverse('account:login'),
            {
                'username': self.user.phone_number,
                'password': 'safe-password-123',
            },
        )
        self.assertRedirects(response, reverse('account:profile'))
        self.assertEqual(int(self.client.session['_auth_user_id']), self.user.pk)

        response = self.client.post(reverse('account:logout'))
        self.assertRedirects(response, reverse('shop:home'))
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_logout_rejects_get_request(self):
        self.assertEqual(self.client.get(reverse('account:logout')).status_code, 405)

    def test_login_does_not_redirect_to_external_site(self):
        response = self.client.post(
            f"{reverse('account:login')}?next=https://example.org/unsafe",
            {
                'username': self.user.phone_number,
                'password': 'safe-password-123',
            },
        )
        self.assertRedirects(response, reverse('account:profile'))

    def test_profile_requires_login(self):
        response = self.client.get(reverse('account:profile'))
        self.assertRedirects(
            response,
            f"{reverse('account:login')}?next={reverse('account:profile')}",
        )

    def test_all_private_views_redirect_anonymous_user_to_login(self):
        urls = (
            reverse('account:password_change'),
            reverse('account:password_change_done'),
            reverse('account:profile'),
            reverse('account:profile_edit'),
            reverse('account:address_list'),
            reverse('account:address_create'),
            reverse('account:address_update', args=[999]),
            reverse('account:address_delete', args=[999]),
            reverse('account:ticket_list'),
            reverse('account:ticket_create'),
            reverse('account:ticket_detail', args=[999]),
            reverse('account:wallet'),
        )
        for url in urls:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 302)
                self.assertTrue(response.url.startswith(reverse('account:login')))

    def test_account_pages_are_available_for_logged_in_user(self):
        self.client.force_login(self.user)
        urls = (
            reverse('account:profile'),
            reverse('account:profile_edit'),
            reverse('account:address_list'),
            reverse('account:address_create'),
            reverse('account:ticket_list'),
            reverse('account:ticket_create'),
            reverse('account:wallet'),
        )
        for url in urls:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)

    def test_profile_edit_updates_user(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse('account:profile_edit'),
            {
                'first_name': 'Updated',
                'last_name': 'Person',
                'email': 'updated@example.com',
                'current_password': 'safe-password-123',
                'phone_number': self.user.phone_number,
            },
        )

        self.assertRedirects(response, reverse('account:profile'))
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, 'Updated')
        self.assertEqual(self.user.email, 'updated@example.com')

    def test_address_create_update_and_delete_actions(self):
        self.client.force_login(self.user)
        create_response = self.client.post(
            reverse('account:address_create'),
            {
                'title': 'Home',
                'recipient_name': 'Test User',
                'recipient_phone': self.user.phone_number,
                'province': 'Tehran',
                'city': 'Tehran',
                'address': 'First address',
                'postal_code': '1234567890',
                'is_default': 'on',
            },
        )
        self.assertRedirects(create_response, reverse('account:address_list'))
        address = self.user.addresses.get()

        update_response = self.client.post(
            reverse('account:address_update', args=[address.pk]),
            {
                'title': 'Work',
                'recipient_name': 'Test User',
                'recipient_phone': self.user.phone_number,
                'province': 'Tehran',
                'city': 'Tehran',
                'address': 'Updated address',
                'postal_code': '1234567890',
                'is_default': 'on',
            },
        )
        self.assertRedirects(update_response, reverse('account:address_list'))
        address.refresh_from_db()
        self.assertEqual(address.title, 'Work')

        delete_response = self.client.post(
            reverse('account:address_delete', args=[address.pk])
        )
        self.assertRedirects(delete_response, reverse('account:address_list'))
        self.assertFalse(Address.objects.filter(pk=address.pk).exists())

    def test_selecting_new_default_address_unsets_previous_default(self):
        old_address = Address.objects.create(
            user=self.user,
            title='Old',
            recipient_name='Test User',
            recipient_phone=self.user.phone_number,
            province='Tehran',
            city='Tehran',
            address='Old address',
            postal_code='1234567890',
            is_default=True,
        )
        self.client.force_login(self.user)

        response = self.client.post(
            reverse('account:address_create'),
            {
                'title': 'New',
                'recipient_name': 'Test User',
                'recipient_phone': self.user.phone_number,
                'province': 'Tehran',
                'city': 'Tehran',
                'address': 'New address',
                'postal_code': '0987654321',
                'is_default': 'on',
            },
        )

        self.assertRedirects(response, reverse('account:address_list'))
        old_address.refresh_from_db()
        self.assertFalse(old_address.is_default)
        self.assertTrue(self.user.addresses.get(title='New').is_default)

    def test_user_cannot_edit_or_delete_another_users_address(self):
        other_user = User.objects.create_user(
            phone_number='09129999999',
            password='safe-password-123',
        )
        address = Address.objects.create(
            user=other_user,
            title='Private',
            recipient_name='Other User',
            recipient_phone=other_user.phone_number,
            province='Tehran',
            city='Tehran',
            address='Private address',
            postal_code='1234567890',
        )
        self.client.force_login(self.user)

        edit_response = self.client.get(
            reverse('account:address_update', args=[address.pk])
        )
        delete_response = self.client.post(
            reverse('account:address_delete', args=[address.pk])
        )

        self.assertEqual(edit_response.status_code, 404)
        self.assertEqual(delete_response.status_code, 404)
        self.assertTrue(Address.objects.filter(pk=address.pk).exists())

    def test_user_cannot_view_another_users_ticket(self):
        other_user = User.objects.create_user(
            phone_number='09127777777',
            password='safe-password-123',
        )
        ticket = Ticket.objects.create(user=other_user, subject='Private ticket')
        self.client.force_login(self.user)

        response = self.client.get(
            reverse('account:ticket_detail', args=[ticket.pk])
        )

        self.assertEqual(response.status_code, 404)

    def test_ticket_create_and_reply_actions(self):
        self.client.force_login(self.user)
        create_response = self.client.post(
            reverse('account:ticket_create'),
            {
                'subject': 'Order question',
                'priority': Ticket.Priority.HIGH,
            },
        )
        ticket = self.user.tickets.get()
        self.assertRedirects(
            create_response,
            reverse('account:ticket_detail', args=[ticket.pk]),
        )

        reply_response = self.client.post(
            reverse('account:ticket_detail', args=[ticket.pk]),
            {'message': 'Please check my order.'},
        )
        self.assertRedirects(
            reply_response,
            reverse('account:ticket_detail', args=[ticket.pk]),
        )
        ticket_message = ticket.messages.get()
        self.assertEqual(ticket_message.sender, self.user)

    def test_closed_ticket_rejects_new_message(self):
        ticket = Ticket.objects.create(
            user=self.user,
            subject='Closed ticket',
            status=Ticket.Status.CLOSED,
        )
        self.client.force_login(self.user)

        response = self.client.post(
            reverse('account:ticket_detail', args=[ticket.pk]),
            {'message': 'This should not be saved.'},
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(ticket.messages.exists())

    def test_wallet_view_creates_wallet_and_displays_transactions(self):
        self.client.force_login(self.user)
        first_response = self.client.get(reverse('account:wallet'))
        self.assertEqual(first_response.status_code, 200)
        wallet = Wallet.objects.get(user=self.user)

        wallet.credit(500)
        second_response = self.client.get(reverse('account:wallet'))

        self.assertEqual(second_response.status_code, 200)
        self.assertContains(second_response, '500')
        self.assertEqual(wallet.transactions.count(), 1)

    def test_address_used_by_order_cannot_be_deleted(self):
        address = Address.objects.create(
            user=self.user,
            title='Order address',
            recipient_name='Test User',
            recipient_phone=self.user.phone_number,
            province='Tehran',
            city='Tehran',
            address='Order address',
            postal_code='1234567890',
        )
        Order.objects.create(user=self.user, address=address)
        self.client.force_login(self.user)

        response = self.client.post(
            reverse('account:address_delete', args=[address.pk])
        )

        self.assertRedirects(response, reverse('account:address_list'))
        self.assertTrue(Address.objects.filter(pk=address.pk).exists())

    def test_logged_in_user_can_change_password(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse('account:password_change'),
            {
                'old_password': 'safe-password-123',
                'new_password1': 'New-safe-password-456',
                'new_password2': 'New-safe-password-456',
            },
        )

        self.assertRedirects(response, reverse('account:password_change_done'))
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('New-safe-password-456'))

    def test_wrong_current_password_does_not_change_password(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse('account:password_change'),
            {
                'old_password': 'wrong-password',
                'new_password1': 'New-safe-password-456',
                'new_password2': 'New-safe-password-456',
            },
        )

        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('safe-password-123'))

    @override_settings(
        EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend'
    )
    def test_password_reset_sends_email_for_matching_phone_and_email(self):
        self.user.email = 'customer@example.com'
        self.user.save(update_fields=('email',))

        response = self.client.post(
            reverse('account:password_reset'),
            {
                'phone_number': self.user.phone_number,
                'email': self.user.email,
            },
        )

        self.assertRedirects(response, reverse('account:password_reset_done'))
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('/account/password/reset/', mail.outbox[0].body)

    @override_settings(
        EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend'
    )
    def test_password_reset_does_not_email_for_wrong_phone(self):
        self.user.email = 'customer@example.com'
        self.user.save(update_fields=('email',))

        response = self.client.post(
            reverse('account:password_reset'),
            {
                'phone_number': '09120000001',
                'email': self.user.email,
            },
        )

        self.assertRedirects(response, reverse('account:password_reset_done'))
        self.assertEqual(len(mail.outbox), 0)

    def test_valid_reset_token_can_set_a_new_password(self):
        uidb64 = urlsafe_base64_encode(force_bytes(self.user.pk))
        token = default_token_generator.make_token(self.user)
        confirm_url = reverse(
            'account:password_reset_confirm',
            kwargs={'uidb64': uidb64, 'token': token},
        )

        response = self.client.get(confirm_url)
        set_password_url = reverse(
            'account:password_reset_confirm',
            kwargs={'uidb64': uidb64, 'token': 'set-password'},
        )
        self.assertRedirects(response, set_password_url)

        response = self.client.post(
            set_password_url,
            {
                'new_password1': 'Another-safe-password-789',
                'new_password2': 'Another-safe-password-789',
            },
        )

        self.assertRedirects(response, reverse('account:password_reset_complete'))
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('Another-safe-password-789'))

    def test_invalid_reset_token_is_rejected(self):
        uidb64 = urlsafe_base64_encode(force_bytes(self.user.pk))
        response = self.client.get(
            reverse(
                'account:password_reset_confirm',
                kwargs={'uidb64': uidb64, 'token': 'invalid-token'},
            )
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'لینک نامعتبر است')
