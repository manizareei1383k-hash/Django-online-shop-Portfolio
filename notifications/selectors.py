from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils import timezone

from .models import Notification


def create_notification(
    recipient,
    kind,
    title,
    message,
    target_url='',
    data=None,
    unique_key=None,
):
    values = {
        'recipient': recipient,
        'kind': kind,
        'title': title,
        'message': message,
        'target_url': target_url,
        'data': data or {},
    }
    if unique_key:
        notification, _ = Notification.objects.get_or_create(
            unique_key=unique_key,
            defaults=values,
        )
        return notification
    return Notification.objects.create(**values)


def get_user_notifications(user, unread_only=False):
    notifications = user.notifications.all()
    if unread_only:
        notifications = notifications.filter(is_read=False)
    return notifications


def get_user_notification_summary(user):
    notifications = get_user_notifications(user)
    return {
        'notifications': notifications,
        'unread_count': notifications.filter(is_read=False).count(),
    }


def mark_notification_as_read(user, notification_id):
    notification = get_object_or_404(
        Notification,
        pk=notification_id,
        recipient=user,
    )
    if not notification.is_read:
        notification.is_read = True
        notification.read_at = timezone.now()
        notification.save(update_fields=('is_read', 'read_at'))
    return notification


def mark_all_notifications_as_read(user):
    updated = user.notifications.filter(is_read=False).update(
        is_read=True,
        read_at=timezone.now(),
    )
    if updated:
        from management_panel.cache import invalidate_dashboard_stats_cache

        invalidate_dashboard_stats_cache()
    return updated


def notify_payment_success(payment):
    return create_notification(
        recipient=payment.user,
        kind=Notification.Kind.PAYMENT_SUCCESS,
        title='پرداخت موفق',
        message=f'پرداخت سفارش شماره {payment.order_id} با موفقیت انجام شد.',
        target_url=reverse('orders:detail', args=[payment.order_id]),
        data={'order_id': payment.order_id, 'payment_id': payment.pk},
        unique_key=f'payment:{payment.pk}:paid',
    )


def notify_payment_failed(payment):
    return create_notification(
        recipient=payment.user,
        kind=Notification.Kind.PAYMENT_FAILED,
        title='پرداخت ناموفق',
        message=f'پرداخت سفارش شماره {payment.order_id} ناموفق بود.',
        target_url=reverse('orders:detail', args=[payment.order_id]),
        data={'order_id': payment.order_id, 'payment_id': payment.pk},
        unique_key=f'payment:{payment.pk}:failed',
    )


def notify_payment_refunded(payment):
    return create_notification(
        recipient=payment.user,
        kind=Notification.Kind.PAYMENT_REFUNDED,
        title='بازگشت وجه',
        message=f'مبلغ سفارش شماره {payment.order_id} بازگردانده شد.',
        target_url=reverse('orders:detail', args=[payment.order_id]),
        data={
            'order_id': payment.order_id,
            'payment_id': payment.pk,
            'refund_reference': payment.refund_reference,
        },
        unique_key=f'payment:{payment.pk}:refunded',
    )


def notify_invoice_issued(invoice):
    return create_notification(
        recipient=invoice.user,
        kind=Notification.Kind.INVOICE_ISSUED,
        title='فاکتور صادر شد',
        message=f'فاکتور {invoice.number} برای سفارش شما صادر شد.',
        target_url=reverse('invoices:detail', args=[invoice.number]),
        data={'order_id': invoice.order_id, 'invoice_id': invoice.pk},
        unique_key=f'invoice:{invoice.pk}:issued',
    )


def notify_order_status(order):
    return create_notification(
        recipient=order.user,
        kind=Notification.Kind.ORDER_STATUS,
        title='تغییر وضعیت سفارش',
        message=(
            f'وضعیت سفارش شماره {order.pk} به '
            f'«{order.get_status_display()}» تغییر کرد.'
        ),
        target_url=reverse('orders:detail', args=[order.pk]),
        data={'order_id': order.pk, 'status': order.status},
        unique_key=f'order:{order.pk}:status:{order.status}',
    )


def notify_ticket_reply(ticket_message):
    ticket = ticket_message.ticket
    return create_notification(
        recipient=ticket.user,
        kind=Notification.Kind.TICKET_REPLY,
        title='پاسخ جدید به تیکت',
        message=f'برای تیکت «{ticket.subject}» پاسخ جدیدی ثبت شد.',
        target_url=reverse('account:ticket_detail', args=[ticket.pk]),
        data={'ticket_id': ticket.pk, 'message_id': ticket_message.pk},
        unique_key=f'ticket-message:{ticket_message.pk}',
    )


def notify_review_reply(review_reply):
    review = review_reply.review
    if review.user_id is None:
        return None
    return create_notification(
        recipient=review.user,
        kind=Notification.Kind.REVIEW_REPLY,
        title='پاسخ به نظر شما',
        message=f'فروشگاه به نظر شما درباره «{review.product.name}» پاسخ داد.',
        target_url=reverse('shop:product_detail', args=[review.product_id]),
        data={'review_id': review.pk, 'reply_id': review_reply.pk},
        unique_key=f'review-reply:{review_reply.pk}',
    )
