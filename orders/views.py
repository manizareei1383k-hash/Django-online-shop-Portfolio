from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from . import selectors


@login_required
def checkout(request):
    data = request.POST if request.method == 'POST' else None
    context = selectors.get_checkout_context(request.user, data=data)
    order = context.pop('created_order')
    if order is not None:
        messages.success(request, 'سفارش شما با موفقیت ثبت شد.')
        return redirect('orders:detail', pk=order.pk)
    return render(request, 'orders/checkout.html', context)


@login_required
def order_list(request):
    context = selectors.get_orders_context(request.user)
    return render(request, 'orders/order_list.html', context)


@login_required
def order_detail(request, pk):
    context = selectors.get_order_detail_context(request.user, pk)
    return render(request, 'orders/order_detail.html', context)


@login_required
@require_POST
def order_cancel(request, pk):
    if selectors.cancel_user_order(request.user, pk):
        messages.success(request, 'سفارش لغو شد و موجودی محصولات بازگردانده شد.')
    else:
        messages.error(request, 'این سفارش دیگر قابل لغو نیست.')
    return redirect('orders:detail', pk=pk)
