from django.core.exceptions import ValidationError
from django.core.cache import cache
from django.db import transaction
from django.db.models import Count, Q, Sum
from django.db.models.deletion import ProtectedError
from django.shortcuts import get_object_or_404
from django.utils import timezone

from account.models import Ticket, TicketMessage, User
from invoices.models import Invoice
from notifications.models import Notification
from orders import selectors as order_selectors
from orders.models import Order, ShippingMethod
from payments.models import Payment
from shop.models import Category, Product, ProductDiscount, Review, ReviewReply
from shop.signals import invalidate_public_shop_cache

from .models import AdminActivity
from .forms import (
    CategoryForm,
    OrderStatusForm,
    ProductManagementForm,
    ReviewReplyForm,
    ShippingMethodForm,
    TicketManagementForm,
    TicketMessageForm,
)


MANAGEMENT_DASHBOARD_STATS_CACHE_KEY = 'management_panel:dashboard:stats'
MANAGEMENT_DASHBOARD_STATS_CACHE_TIMEOUT = 30


def record_admin_activity(
    admin_user,
    action,
    target,
    *,
    request=None,
    description='',
    changes=None,
):
    return AdminActivity.objects.create(
        admin=admin_user,
        action=action,
        target_type=target._meta.label,
        target_id=str(target.pk),
        target_label=str(target)[:255],
        description=description,
        changes=changes or {},
        ip_address=request.META.get('REMOTE_ADDR') if request else None,
    )


def get_dashboard_stats(use_cache=True):
    stats = (
        cache.get(MANAGEMENT_DASHBOARD_STATS_CACHE_KEY)
        if use_cache
        else None
    )
    if stats is not None:
        return stats

    stats = {
        'products_count': Product.objects.count(),
        'users_count': User.objects.filter(is_staff=False).count(),
        'pending_orders_count': Order.objects.filter(
            status=Order.Status.PENDING
        ).count(),
        'open_tickets_count': Ticket.objects.exclude(
            status=Ticket.Status.CLOSED
        ).count(),
        'unread_notifications_count': Notification.objects.filter(
            is_read=False
        ).count(),
        'paid_total': Payment.objects.filter(status=Payment.Status.PAID).aggregate(
            total=Sum('amount')
        )['total'] or 0,
    }
    if use_cache:
        cache.set(
            MANAGEMENT_DASHBOARD_STATS_CACHE_KEY,
            stats,
            MANAGEMENT_DASHBOARD_STATS_CACHE_TIMEOUT,
        )
    return stats


def get_dashboard_context(use_cache=True):
    return {
        **get_dashboard_stats(use_cache=use_cache),
        'recent_orders': Order.objects.select_related('user')[:8],
    }


def get_products_context(params):
    query = params.get('q', '').strip()
    products = Product.objects.select_related('category').prefetch_related(
        'discounts'
    ).order_by('-id')
    if query:
        products = products.filter(
            Q(name__icontains=query) | Q(category__name__icontains=query)
        )
    return {'products': products, 'query': query}


def get_product_form_context(
    pk=None,
    data=None,
    files=None,
    admin_user=None,
    request=None,
):
    product = get_object_or_404(Product, pk=pk) if pk is not None else None
    is_create = product is None
    discount = None
    if product is not None:
        discount = product.discounts.order_by('-starts_at').first()
    form = ProductManagementForm(
        data=data,
        files=files,
        instance=product,
        discount=discount,
    )
    saved = False
    if data is not None and form.is_valid():
        try:
            with transaction.atomic():
                product = form.save()
                if form.cleaned_data.get('remove_discount'):
                    product.discounts.filter(is_active=True).update(is_active=False)
                    invalidate_public_shop_cache()
                elif form.cleaned_data.get('discount_percent') is not None:
                    discount = discount or ProductDiscount(product=product)
                    discount.title = form.cleaned_data.get('discount_title', '')
                    discount.percent = form.cleaned_data['discount_percent']
                    discount.starts_at = form.cleaned_data['discount_starts_at']
                    discount.ends_at = form.cleaned_data['discount_ends_at']
                    discount.is_active = form.cleaned_data['discount_is_active']
                    discount.full_clean()
                    discount.save()
                record_admin_activity(
                    admin_user,
                    (
                        AdminActivity.Action.CREATE
                        if is_create
                        else AdminActivity.Action.UPDATE
                    ),
                    product,
                    request=request,
                    changes={'fields': list(form.changed_data)},
                )
            saved = True
        except ValidationError as error:
            form.add_error(None, error)
    return {'form': form, 'product': product, 'saved': saved}


def delete_product(pk, admin_user, request=None):
    product = get_object_or_404(Product, pk=pk)
    try:
        with transaction.atomic():
            record_admin_activity(
                admin_user,
                AdminActivity.Action.DELETE,
                product,
                request=request,
            )
            product.delete()
    except ProtectedError:
        return False
    return True


def get_categories_context():
    return {
        'categories': Category.objects.annotate(
            products_count=Count('products')
        ).order_by('name')
    }


def get_category_form_context(
    pk=None,
    data=None,
    files=None,
    admin_user=None,
    request=None,
):
    category = get_object_or_404(Category, pk=pk) if pk is not None else None
    is_create = category is None
    form = CategoryForm(data=data, files=files, instance=category)
    saved = data is not None and form.is_valid()
    if saved:
        with transaction.atomic():
            category = form.save()
            record_admin_activity(
                admin_user,
                (
                    AdminActivity.Action.CREATE
                    if is_create
                    else AdminActivity.Action.UPDATE
                ),
                category,
                request=request,
                changes={'fields': list(form.changed_data)},
            )
    return {'form': form, 'category': category, 'saved': saved}


def delete_category(pk, admin_user, request=None):
    category = get_object_or_404(Category, pk=pk)
    if category.products.exists():
        return False
    with transaction.atomic():
        record_admin_activity(
            admin_user,
            AdminActivity.Action.DELETE,
            category,
            request=request,
        )
        category.delete()
    return True


def get_shipping_methods_context():
    return {'shipping_methods': ShippingMethod.objects.order_by('name')}


def get_shipping_form_context(
    pk=None,
    data=None,
    admin_user=None,
    request=None,
):
    shipping = get_object_or_404(ShippingMethod, pk=pk) if pk else None
    is_create = shipping is None
    form = ShippingMethodForm(data=data, instance=shipping)
    saved = data is not None and form.is_valid()
    if saved:
        with transaction.atomic():
            shipping = form.save()
            record_admin_activity(
                admin_user,
                (
                    AdminActivity.Action.CREATE
                    if is_create
                    else AdminActivity.Action.UPDATE
                ),
                shipping,
                request=request,
                changes={'fields': list(form.changed_data)},
            )
    return {'form': form, 'shipping': shipping, 'saved': saved}


def delete_shipping_method(pk, admin_user, request=None):
    shipping = get_object_or_404(ShippingMethod, pk=pk)
    try:
        with transaction.atomic():
            record_admin_activity(
                admin_user,
                AdminActivity.Action.DELETE,
                shipping,
                request=request,
            )
            shipping.delete()
    except ProtectedError:
        return False
    return True


def get_orders_context(params):
    status = params.get('status', '').strip()
    orders = Order.objects.select_related('user', 'shipping_method').prefetch_related(
        'items'
    )
    if status in {choice[0] for choice in Order.Status.choices}:
        orders = orders.filter(status=status)
    return {'orders': orders, 'statuses': Order.Status.choices, 'selected_status': status}


def get_order_context(pk, data=None, admin_user=None, request=None):
    order = get_object_or_404(
        Order.objects.select_related('user', 'address', 'shipping_method')
        .prefetch_related('items__product', 'payments'),
        pk=pk,
    )
    form = OrderStatusForm(data=data, instance=order)
    old_status = order.status
    changed = False
    if data is not None and form.is_valid():
        with transaction.atomic():
            changed = order_selectors.change_order_status_by_admin(
                order.pk,
                form.cleaned_data['status'],
            )
            if changed:
                record_admin_activity(
                    admin_user,
                    AdminActivity.Action.STATUS_CHANGE,
                    order,
                    request=request,
                    changes={
                        'status': {
                            'from': old_status,
                            'to': form.cleaned_data['status'],
                        }
                    },
                )
        order.refresh_from_db()
    return {
        'order': order,
        'form': form,
        'totals': order_selectors.calculate_order_totals(order),
        'changed': changed,
    }


def cancel_order(pk, admin_user, request=None):
    with transaction.atomic():
        canceled = order_selectors.cancel_order_by_admin(pk)
        if canceled:
            order = Order.objects.get(pk=pk)
            record_admin_activity(
                admin_user,
                AdminActivity.Action.CANCEL,
                order,
                request=request,
                changes={'status': {'to': Order.Status.CANCELED}},
            )
        return canceled


def get_tickets_context(params):
    status = params.get('status', '').strip()
    tickets = Ticket.objects.select_related('user').annotate(
        messages_count=Count('messages')
    )
    if status in {choice[0] for choice in Ticket.Status.choices}:
        tickets = tickets.filter(status=status)
    return {'tickets': tickets, 'statuses': Ticket.Status.choices, 'selected_status': status}


def get_ticket_context(
    pk,
    admin_user,
    action=None,
    data=None,
    files=None,
    request=None,
):
    ticket = get_object_or_404(
        Ticket.objects.select_related('user').prefetch_related('messages__sender'),
        pk=pk,
    )
    manage_form = TicketManagementForm(
        data=data if action == 'update' else None,
        instance=ticket,
    )
    reply_form = TicketMessageForm(
        data=data if action == 'reply' else None,
        files=files if action == 'reply' else None,
    )
    completed_action = None
    if action == 'update' and manage_form.is_valid():
        with transaction.atomic():
            ticket = manage_form.save()
            record_admin_activity(
                admin_user,
                AdminActivity.Action.UPDATE,
                ticket,
                request=request,
                changes={'fields': list(manage_form.changed_data)},
            )
        completed_action = 'updated'
    elif action == 'reply':
        if ticket.status == Ticket.Status.CLOSED:
            reply_form.add_error(None, 'تیکت بسته است و نمی‌توان به آن پاسخ داد.')
        elif reply_form.is_valid():
            with transaction.atomic():
                message = reply_form.save(commit=False)
                message.ticket = ticket
                message.sender = admin_user
                message.save()
                ticket.status = Ticket.Status.ANSWERED
                ticket.save(update_fields=('status', 'updated_at'))
                record_admin_activity(
                    admin_user,
                    AdminActivity.Action.REPLY,
                    ticket,
                    request=request,
                    description=f'پیام #{message.pk}',
                )
            completed_action = 'replied'
    return {
        'ticket': ticket,
        'manage_form': manage_form,
        'reply_form': reply_form,
        'completed_action': completed_action,
    }


def get_reviews_context():
    return {
        'reviews': Review.objects.select_related(
            'product', 'user'
        ).select_related('reply').order_by('-id')
    }


def get_review_context(pk, admin_user, data=None, request=None):
    review = get_object_or_404(
        Review.objects.select_related('product', 'user'),
        pk=pk,
    )
    reply = ReviewReply.objects.filter(review=review).first()
    form = ReviewReplyForm(data=data, instance=reply)
    saved = False
    if data is not None and form.is_valid():
        with transaction.atomic():
            reply = form.save(commit=False)
            reply.review = review
            reply.responder = admin_user
            reply.save()
            record_admin_activity(
                admin_user,
                AdminActivity.Action.REPLY,
                review,
                request=request,
                description=f'پاسخ #{reply.pk}',
                changes={'fields': list(form.changed_data)},
            )
            from notifications.selectors import notify_review_reply

            notify_review_reply(reply)
        saved = True
    return {'review': review, 'reply': reply, 'form': form, 'saved': saved}


def get_payments_context(params):
    status = params.get('status', '').strip()
    payments = Payment.objects.select_related('user', 'order')
    if status in {choice[0] for choice in Payment.Status.choices}:
        payments = payments.filter(status=status)
    return {'payments': payments, 'statuses': Payment.Status.choices, 'selected_status': status}


def get_payment_context(pk):
    return {
        'payment': get_object_or_404(
            Payment.objects.select_related('user', 'order'), pk=pk
        )
    }


def get_invoices_context():
    return {'invoices': Invoice.objects.select_related('user', 'order', 'payment')}


def get_invoice_context(pk):
    return {
        'invoice': get_object_or_404(
            Invoice.objects.select_related('user', 'order', 'payment')
            .prefetch_related('items'),
            pk=pk,
        )
    }


def get_users_context(params):
    query = params.get('q', '').strip()
    users = User.objects.annotate(orders_count=Count('orders')).order_by('-date_joined')
    if query:
        users = users.filter(
            Q(phone_number__icontains=query)
            | Q(email__icontains=query)
            | Q(first_name__icontains=query)
            | Q(last_name__icontains=query)
        )
    return {'users': users, 'query': query}


def get_user_context(pk):
    user = get_object_or_404(User, pk=pk)
    return {
        'managed_user': user,
        'orders': user.orders.all()[:20],
        'tickets': user.tickets.all()[:20],
        'payments': user.payments.all()[:20],
    }


def get_admin_activities_context(params):
    action = params.get('action', '').strip()
    activities = AdminActivity.objects.select_related('admin')
    if action in {choice[0] for choice in AdminActivity.Action.choices}:
        activities = activities.filter(action=action)
    return {
        'activities': activities[:200],
        'actions': AdminActivity.Action.choices,
        'selected_action': action,
    }
