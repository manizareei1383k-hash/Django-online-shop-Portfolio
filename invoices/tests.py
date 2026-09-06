from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from account.models import Address, User, Wallet
from orders import selectors as order_selectors
from orders.models import Order, OrderItem, ShippingMethod
from payments import selectors as payment_selectors
from payments.models import Payment
from shop.models import Category, Product

from .models import Invoice
from .selectors import InvoiceError, issue_invoice_for_payment


class InvoiceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            phone_number='09125550000',
            password='safe-password-123',
            email='buyer@example.com',
        )
        self.address = Address.objects.create(
            user=self.user,
            recipient_name='Original Buyer',
            recipient_phone=self.user.phone_number,
            province='Tehran',
            city='Tehran',
            address='Original address',
            postal_code='1234567890',
        )
        self.shipping = ShippingMethod.objects.create(
            name='Post',
            price='20.00',
        )
        self.category = Category.objects.create(
            name='Category',
            image='category_images/test.jpg',
        )
        self.product = Product.objects.create(
            name='Original product',
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

    def pay_with_wallet(self):
        Wallet.objects.create(user=self.user).credit('1000')
        return payment_selectors.create_payment(
            self.user,
            self.order.pk,
            Payment.Gateway.WALLET,
        )

    def test_successful_payment_automatically_issues_invoice(self):
        payment = self.pay_with_wallet()

        invoice = Invoice.objects.get(order=self.order)
        line = invoice.items.get()
        self.assertEqual(invoice.payment, payment)
        self.assertEqual(invoice.user, self.user)
        self.assertEqual(invoice.status, Invoice.Status.ISSUED)
        self.assertEqual(invoice.subtotal, Decimal('200.00'))
        self.assertEqual(invoice.shipping_cost, Decimal('20.00'))
        self.assertEqual(invoice.total_amount, Decimal('220.00'))
        self.assertEqual(line.product_name, 'Original product')
        self.assertEqual(line.total_price, Decimal('200.00'))

    def test_invoice_data_is_a_snapshot(self):
        self.pay_with_wallet()
        invoice = Invoice.objects.get(order=self.order)

        self.address.recipient_name = 'Changed Buyer'
        self.address.address = 'Changed address'
        self.address.save(update_fields=('recipient_name', 'address'))
        self.product.name = 'Changed product'
        self.product.save(update_fields=('name',))

        invoice.refresh_from_db()
        self.assertEqual(invoice.buyer_name, 'Original Buyer')
        self.assertEqual(invoice.address, 'Original address')
        self.assertEqual(invoice.items.get().product_name, 'Original product')

    def test_unpaid_payment_cannot_issue_invoice(self):
        payment = Payment.objects.create(
            order=self.order,
            user=self.user,
            gateway=Payment.Gateway.TEST,
            amount='220.00',
        )

        with self.assertRaises(InvoiceError):
            issue_invoice_for_payment(payment)

        self.assertFalse(Invoice.objects.filter(order=self.order).exists())

    def test_invoice_issuance_is_idempotent(self):
        payment = self.pay_with_wallet()
        first_invoice = issue_invoice_for_payment(payment)
        second_invoice = issue_invoice_for_payment(payment)

        self.assertEqual(first_invoice.pk, second_invoice.pk)
        self.assertEqual(Invoice.objects.filter(order=self.order).count(), 1)

    def test_user_can_only_view_own_invoice(self):
        self.pay_with_wallet()
        invoice = Invoice.objects.get(order=self.order)
        other_user = User.objects.create_user(
            phone_number='09125550001',
            password='safe-password-123',
        )

        anonymous_response = self.client.get(
            reverse('invoices:detail', args=[invoice.number])
        )
        self.client.force_login(other_user)
        other_response = self.client.get(
            reverse('invoices:detail', args=[invoice.number])
        )
        self.client.force_login(self.user)
        owner_response = self.client.get(
            reverse('invoices:detail', args=[invoice.number])
        )

        self.assertEqual(anonymous_response.status_code, 302)
        self.assertEqual(other_response.status_code, 404)
        self.assertEqual(owner_response.status_code, 200)
        self.assertContains(owner_response, invoice.number)

    def test_refund_updates_invoice_status(self):
        self.pay_with_wallet()

        order_selectors.cancel_order_by_admin(self.order.pk)

        invoice = Invoice.objects.get(order=self.order)
        self.assertEqual(invoice.status, Invoice.Status.REFUNDED)
        self.assertIsNotNone(invoice.refunded_at)

