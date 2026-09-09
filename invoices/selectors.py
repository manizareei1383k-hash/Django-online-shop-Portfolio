from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone

from orders.models import Order
from payments.models import Payment

from .models import Invoice, InvoiceItem


class InvoiceError(Exception):
    pass


@transaction.atomic
def issue_invoice_for_payment(payment):
    order_id = Payment.objects.values_list('order_id', flat=True).get(pk=payment.pk)
    Order.objects.select_for_update().get(pk=order_id)
    payment = Payment.objects.select_for_update().select_related(
        'order',
        'user',
        'order__address',
    ).get(pk=payment.pk)

    if payment.status != Payment.Status.PAID:
        raise InvoiceError('فاکتور فقط برای پرداخت موفق صادر می‌شود.')

    existing_invoice = Invoice.objects.filter(order=payment.order).first()
    if existing_invoice is not None:
        return existing_invoice

    order = Order.objects.select_for_update().prefetch_related(
        'items__product'
    ).get(pk=payment.order_id)
    order_items = list(order.items.all())
    if not order_items:
        raise InvoiceError('سفارش بدون محصول قابل صدور نیست.')

    subtotal = sum(
        (item.unit_price * item.quantity for item in order_items),
        start=payment.amount * 0,
    )
    total_amount = subtotal + order.tax_amount + order.shipping_cost
    if total_amount != payment.amount:
        raise InvoiceError('مبلغ پرداخت با مبلغ سفارش یکسان نیست.')

    issued_at = timezone.now()
    address = order.address
    invoice = Invoice.objects.create(
        number=f'INV-{issued_at:%Y}-{order.pk:08d}',
        order=order,
        payment=payment,
        user=order.user,
        buyer_name=address.recipient_name,
        buyer_phone=address.recipient_phone,
        buyer_email=order.user.email,
        province=address.province,
        city=address.city,
        address=address.address,
        postal_code=address.postal_code,
        subtotal=subtotal,
        tax_amount=order.tax_amount,
        shipping_cost=order.shipping_cost,
        total_amount=total_amount,
        payment_gateway=payment.gateway,
        payment_reference=payment.gateway_reference,
        issued_at=issued_at,
    )
    InvoiceItem.objects.bulk_create(
        [
            InvoiceItem(
                invoice=invoice,
                product=item.product,
                product_name=item.product.name,
                quantity=item.quantity,
                unit_price=item.unit_price,
                total_price=item.unit_price * item.quantity,
            )
            for item in order_items
        ]
    )

    from notifications.selectors import notify_invoice_issued

    notify_invoice_issued(invoice)
    return invoice


def get_invoice_detail_context(user, number):
    invoice = get_object_or_404(
        Invoice.objects.select_related(
            'order',
            'payment',
        ).prefetch_related('items'),
        number=number,
        user=user,
    )
    return {'invoice': invoice, 'lines': invoice.items.all()}


def mark_invoice_as_refunded(payment):
    return Invoice.objects.filter(
        payment=payment,
        status=Invoice.Status.ISSUED,
    ).update(
        status=Invoice.Status.REFUNDED,
        refunded_at=payment.refunded_at,
    )
