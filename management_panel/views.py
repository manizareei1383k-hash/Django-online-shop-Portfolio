from django.contrib import messages
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from account.decorators import admin_required

from . import selectors


@admin_required
def dashboard(request):
    return render(request, 'management_panel/dashboard.html', selectors.get_dashboard_context())


@admin_required
def product_list(request):
    return render(request, 'management_panel/product_list.html', selectors.get_products_context(request.GET))


@admin_required
def product_create(request):
    data = request.POST if request.method == 'POST' else None
    files = request.FILES if request.method == 'POST' else None
    context = selectors.get_product_form_context(
        data=data,
        files=files,
        admin_user=request.user,
        request=request,
    )
    if context['saved']:
        messages.success(request, 'محصول و تخفیف آن ذخیره شد.')
        return redirect('management_panel:products')
    context['title'] = 'افزودن محصول'
    return render(request, 'management_panel/object_form.html', context)


@admin_required
def product_update(request, pk):
    data = request.POST if request.method == 'POST' else None
    files = request.FILES if request.method == 'POST' else None
    context = selectors.get_product_form_context(
        pk,
        data,
        files,
        admin_user=request.user,
        request=request,
    )
    if context['saved']:
        messages.success(request, 'محصول و تخفیف آن ویرایش شد.')
        return redirect('management_panel:products')
    context['title'] = 'ویرایش محصول'
    return render(request, 'management_panel/object_form.html', context)


@admin_required
@require_POST
def product_delete(request, pk):
    if selectors.delete_product(pk, request.user, request):
        messages.success(request, 'محصول حذف شد.')
    else:
        messages.error(request, 'این محصول در سفارش استفاده شده و قابل حذف نیست.')
    return redirect('management_panel:products')


@admin_required
def category_list(request):
    return render(request, 'management_panel/category_list.html', selectors.get_categories_context())


@admin_required
def category_create(request):
    data = request.POST if request.method == 'POST' else None
    files = request.FILES if request.method == 'POST' else None
    context = selectors.get_category_form_context(
        data=data,
        files=files,
        admin_user=request.user,
        request=request,
    )
    if context['saved']:
        messages.success(request, 'دسته‌بندی اضافه شد.')
        return redirect('management_panel:categories')
    context['title'] = 'افزودن دسته‌بندی'
    return render(request, 'management_panel/object_form.html', context)


@admin_required
def category_update(request, pk):
    data = request.POST if request.method == 'POST' else None
    files = request.FILES if request.method == 'POST' else None
    context = selectors.get_category_form_context(
        pk,
        data,
        files,
        admin_user=request.user,
        request=request,
    )
    if context['saved']:
        messages.success(request, 'دسته‌بندی ویرایش شد.')
        return redirect('management_panel:categories')
    context['title'] = 'ویرایش دسته‌بندی'
    return render(request, 'management_panel/object_form.html', context)


@admin_required
@require_POST
def category_delete(request, pk):
    if selectors.delete_category(pk, request.user, request):
        messages.success(request, 'دسته‌بندی حذف شد.')
    else:
        messages.error(request, 'دسته‌بندی دارای محصول است و قابل حذف نیست.')
    return redirect('management_panel:categories')


@admin_required
def shipping_list(request):
    return render(request, 'management_panel/shipping_list.html', selectors.get_shipping_methods_context())


@admin_required
def shipping_create(request):
    data = request.POST if request.method == 'POST' else None
    context = selectors.get_shipping_form_context(
        data=data,
        admin_user=request.user,
        request=request,
    )
    if context['saved']:
        messages.success(request, 'روش ارسال اضافه شد.')
        return redirect('management_panel:shipping_methods')
    context['title'] = 'افزودن روش ارسال'
    return render(request, 'management_panel/object_form.html', context)


@admin_required
def shipping_update(request, pk):
    data = request.POST if request.method == 'POST' else None
    context = selectors.get_shipping_form_context(
        pk,
        data,
        admin_user=request.user,
        request=request,
    )
    if context['saved']:
        messages.success(request, 'روش ارسال ویرایش شد.')
        return redirect('management_panel:shipping_methods')
    context['title'] = 'ویرایش روش ارسال'
    return render(request, 'management_panel/object_form.html', context)


@admin_required
@require_POST
def shipping_delete(request, pk):
    if selectors.delete_shipping_method(pk, request.user, request):
        messages.success(request, 'روش ارسال حذف شد.')
    else:
        messages.error(request, 'این روش در سفارش استفاده شده و قابل حذف نیست.')
    return redirect('management_panel:shipping_methods')


@admin_required
def order_list(request):
    return render(request, 'management_panel/order_list.html', selectors.get_orders_context(request.GET))


@admin_required
def order_detail(request, pk):
    data = request.POST if request.method == 'POST' else None
    context = selectors.get_order_context(
        pk,
        data,
        admin_user=request.user,
        request=request,
    )
    if context['changed']:
        messages.success(request, 'وضعیت سفارش تغییر کرد.')
        return redirect('management_panel:order_detail', pk=pk)
    return render(request, 'management_panel/order_detail.html', context)


@admin_required
@require_POST
def order_cancel(request, pk):
    if selectors.cancel_order(pk, request.user, request):
        messages.success(request, 'سفارش لغو و در صورت نیاز وجه بازگردانده شد.')
    else:
        messages.error(request, 'سفارش قبلاً لغو شده است.')
    return redirect('management_panel:order_detail', pk=pk)


@admin_required
def ticket_list(request):
    return render(request, 'management_panel/ticket_list.html', selectors.get_tickets_context(request.GET))


@admin_required
def ticket_detail(request, pk):
    action = request.POST.get('action') if request.method == 'POST' else None
    context = selectors.get_ticket_context(
        pk,
        request.user,
        action=action,
        data=request.POST if request.method == 'POST' else None,
        files=request.FILES if request.method == 'POST' else None,
        request=request,
    )
    if context['completed_action']:
        messages.success(request, 'تیکت به‌روزرسانی شد.')
        return redirect('management_panel:ticket_detail', pk=pk)
    return render(request, 'management_panel/ticket_detail.html', context)


@admin_required
def review_list(request):
    return render(request, 'management_panel/review_list.html', selectors.get_reviews_context())


@admin_required
def review_detail(request, pk):
    data = request.POST if request.method == 'POST' else None
    context = selectors.get_review_context(
        pk,
        request.user,
        data,
        request=request,
    )
    if context['saved']:
        messages.success(request, 'پاسخ نظر ذخیره شد.')
        return redirect('management_panel:review_detail', pk=pk)
    return render(request, 'management_panel/review_detail.html', context)


@admin_required
def payment_list(request):
    return render(request, 'management_panel/payment_list.html', selectors.get_payments_context(request.GET))


@admin_required
def payment_detail(request, pk):
    return render(request, 'management_panel/payment_detail.html', selectors.get_payment_context(pk))


@admin_required
def invoice_list(request):
    return render(request, 'management_panel/invoice_list.html', selectors.get_invoices_context())


@admin_required
def invoice_detail(request, pk):
    return render(request, 'management_panel/invoice_detail.html', selectors.get_invoice_context(pk))


@admin_required
def user_list(request):
    return render(request, 'management_panel/user_list.html', selectors.get_users_context(request.GET))


@admin_required
def user_detail(request, pk):
    return render(request, 'management_panel/user_detail.html', selectors.get_user_context(pk))


@admin_required
def activity_list(request):
    return render(
        request,
        'management_panel/activity_list.html',
        selectors.get_admin_activities_context(request.GET),
    )


@admin_required
def system_log_list(request):
    return render(
        request,
        'management_panel/system_log_list.html',
        selectors.get_system_logs_context(request.GET),
    )
