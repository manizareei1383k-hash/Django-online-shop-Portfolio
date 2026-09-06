from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from . import selectors


@login_required
def cart_detail(request):
    context = selectors.get_cart_context(request.user)
    return render(request, 'cart/cart_detail.html', context)


@login_required
@require_POST
def cart_add(request, product_id):
    result = selectors.add_product_to_cart(
        request.user,
        product_id,
        request.POST,
    )
    if result == 'added':
        messages.success(request, 'محصول به سبد خرید اضافه شد.')
    elif result == 'insufficient_stock':
        messages.error(request, 'تعداد درخواستی بیشتر از موجودی محصول است.')
    else:
        messages.error(request, 'تعداد واردشده معتبر نیست.')
    return redirect('cart:detail')


@login_required
@require_POST
def cart_item_update(request, item_id):
    result = selectors.update_cart_item(request.user, item_id, request.POST)
    if result == 'updated':
        messages.success(request, 'تعداد محصول تغییر کرد.')
    elif result == 'insufficient_stock':
        messages.error(request, 'تعداد درخواستی بیشتر از موجودی محصول است.')
    else:
        messages.error(request, 'تعداد واردشده معتبر نیست.')
    return redirect('cart:detail')


@login_required
@require_POST
def cart_item_remove(request, item_id):
    selectors.remove_cart_item(request.user, item_id)
    messages.success(request, 'محصول از سبد خرید حذف شد.')
    return redirect('cart:detail')


@login_required
@require_POST
def cart_clear(request):
    selectors.clear_user_cart(request.user)
    messages.success(request, 'سبد خرید خالی شد.')
    return redirect('cart:detail')
