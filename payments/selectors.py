import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone

from account.models import Wallet, WalletTransaction
from orders.models import Order
from orders.selectors import calculate_order_totals

from .forms import PaymentStartForm
from .models import Payment
from config.redis import redis_lock


class PaymentError(Exception):
    pass


def test_gateway_enabled():
    return settings.DEBUG and settings.ENABLE_TEST_GATEWAY


def get_payment_start_context(user, order_id, data=None):
    order = get_object_or_404(Order, pk=order_id, user=user)
    form = PaymentStartForm(data=data)
    if not test_gateway_enabled():
        form.fields['gateway'].choices = [
            choice
            for choice in Payment.Gateway.choices
            if choice[0] != Payment.Gateway.TEST
        ]
    return {
        'order': order,
        'amount': calculate_order_totals(order)['total_price'],
        'form': form,
        'latest_payment': order.payments.first(),
    }


def create_payment(user, order_id, gateway):
    valid_gateways = {choice[0] for choice in Payment.Gateway.choices}
    if gateway not in valid_gateways:
        raise PaymentError('روش پرداخت معتبر نیست.')
    if gateway == Payment.Gateway.TEST and not test_gateway_enabled():
        raise PaymentError('درگاه آزمایشی در محیط اصلی فعال نیست.')

    with redis_lock(f'payment:create:{user.pk}:{order_id}'), transaction.atomic():
        order = get_object_or_404(
            Order.objects.select_for_update().prefetch_related('items'),
            pk=order_id,
            user=user,
        )
        if order.status != Order.Status.PENDING:
            raise PaymentError('این سفارش قابل پرداخت نیست.')
        if order.payments.filter(status=Payment.Status.PAID).exists():
            raise PaymentError('این سفارش قبلاً پرداخت شده است.')

        amount = calculate_order_totals(order)['total_price']
        if amount <= 0:
            raise PaymentError('مبلغ سفارش معتبر نیست.')

        payment = Payment.objects.create(
            order=order,
            user=user,
            gateway=gateway,
            amount=amount,
        )
        if gateway == Payment.Gateway.WALLET:
            _pay_with_wallet(payment)
        return payment


def _pay_with_wallet(payment):
    wallet, _ = Wallet.objects.select_for_update().get_or_create(
        user=payment.user
    )
    try:
        transaction_record = wallet.debit(
            payment.amount,
            kind=WalletTransaction.Kind.PURCHASE,
            description=f'پرداخت سفارش شماره {payment.order_id}',
            reference=payment.token,
        )
    except ValidationError as error:
        payment.status = Payment.Status.FAILED
        payment.failure_reason = error.messages[0]
        payment.save(update_fields=('status', 'failure_reason', 'updated_at'))

        from notifications.selectors import notify_payment_failed

        notify_payment_failed(payment)
        return

    _mark_as_paid(payment, str(transaction_record.reference))


def _mark_as_paid(payment, gateway_reference):
    order = Order.objects.select_for_update().get(pk=payment.order_id)
    if order.status != Order.Status.PENDING:
        raise PaymentError('وضعیت سفارش برای پرداخت معتبر نیست.')

    payment.status = Payment.Status.PAID
    payment.gateway_reference = gateway_reference
    payment.paid_at = timezone.now()
    payment.failure_reason = ''
    payment.save(
        update_fields=(
            'status',
            'gateway_reference',
            'paid_at',
            'failure_reason',
            'updated_at',
        )
    )
    order.status = Order.Status.PROCESSING
    order.save(update_fields=('status', 'updated_at'))

    from invoices.selectors import issue_invoice_for_payment
    from notifications.selectors import (
        notify_order_status,
        notify_payment_success,
    )

    issue_invoice_for_payment(payment)
    notify_payment_success(payment)
    notify_order_status(order)


def get_test_gateway_context(user, token):
    if not test_gateway_enabled():
        raise PaymentError('درگاه آزمایشی غیرفعال است.')
    payment = get_object_or_404(
        Payment.objects.select_related('order'),
        token=token,
        user=user,
        gateway=Payment.Gateway.TEST,
    )
    return {'payment': payment}


def complete_test_payment(user, token, successful):
    if not test_gateway_enabled():
        raise PaymentError('درگاه آزمایشی غیرفعال است.')

    with redis_lock(f'payment:complete:{token}'), transaction.atomic():
        # Always lock order before payment, as cancellation and wallet payment do.
        order_id = get_object_or_404(
            Payment, token=token, user=user, gateway=Payment.Gateway.TEST,
        ).order_id
        Order.objects.select_for_update().get(pk=order_id)
        payment = get_object_or_404(
            Payment.objects.select_for_update(),
            token=token,
            user=user,
            gateway=Payment.Gateway.TEST,
        )
        if payment.status != Payment.Status.PENDING:
            return payment

        if not successful:
            payment.status = Payment.Status.FAILED
            payment.failure_reason = 'پرداخت آزمایشی توسط کاربر ناموفق شد.'
            payment.save(
                update_fields=('status', 'failure_reason', 'updated_at')
            )

            from notifications.selectors import notify_payment_failed

            notify_payment_failed(payment)
            return payment

        reference = f'TEST-{uuid.uuid4().hex}'
        _mark_as_paid(payment, reference)
        return payment


@transaction.atomic
def refund_paid_order(order_id):
    Order.objects.select_for_update().get(pk=order_id)
    payment = (
        Payment.objects.select_for_update()
        .filter(order_id=order_id, status=Payment.Status.PAID)
        .first()
    )
    if payment is None:
        return False

    if payment.gateway == Payment.Gateway.WALLET:
        wallet = Wallet.objects.select_for_update().get(user=payment.user)
        refund_token = uuid.uuid5(
            uuid.NAMESPACE_URL,
            f'payment-refund:{payment.token}',
        )
        transaction_record = wallet.credit(
            payment.amount,
            kind=WalletTransaction.Kind.REFUND,
            description=f'بازگشت وجه سفارش شماره {payment.order_id}',
            reference=refund_token,
        )
        refund_reference = str(transaction_record.reference)
    elif payment.gateway == Payment.Gateway.TEST:
        refund_reference = f'TEST-REFUND-{uuid.uuid4().hex}'
    else:
        raise PaymentError('بازگشت وجه برای این درگاه پیاده‌سازی نشده است.')

    payment.status = Payment.Status.REFUNDED
    payment.refund_reference = refund_reference
    payment.refunded_at = timezone.now()
    payment.save(
        update_fields=(
            'status',
            'refund_reference',
            'refunded_at',
            'updated_at',
        )
    )

    from invoices.selectors import mark_invoice_as_refunded
    from notifications.selectors import notify_payment_refunded

    mark_invoice_as_refunded(payment)
    notify_payment_refunded(payment)
    return True


def cancel_pending_order_payments(order_id):
    return Payment.objects.filter(
        order_id=order_id,
        status=Payment.Status.PENDING,
    ).update(status=Payment.Status.CANCELED, updated_at=timezone.now())
