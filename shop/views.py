from django.contrib import messages
from django.shortcuts import redirect, render

from account.decorators import admin_required

from . import selectors


def home(request):
    context = selectors.get_home_context()
    return render(request, 'shop/home.html', context)


def shop(request):
    context = selectors.get_shop_context(request.GET)
    return render(request, 'shop/shop.html', context)


def product_detail(request, pk):
    data = request.POST if request.method == 'POST' else None
    context = selectors.get_product_detail_context(pk, data)

    if context.pop('review_saved'):
        messages.success(request, 'نظر شما با موفقیت ثبت شد.')
        return redirect('shop:product_detail', pk=pk)

    return render(request, 'shop/product_detail.html', context)


def contact_us(request):
    data = request.POST if request.method == 'POST' else None
    context = selectors.get_contact_context(data)

    if context.pop('message_saved'):
        messages.success(request, 'پیام شما با موفقیت ارسال شد.')
        return redirect('shop:contact_us')

    return render(request, 'shop/contact_us.html', context)


def rules(request):
    return render(request, 'shop/rules.html')


def about_us(request):
    return render(request, 'shop/about_us.html')


@admin_required
def product_management(request):
    context = selectors.get_management_context()
    return render(request, 'shop/management/product_list.html', context)


@admin_required
def product_create(request):
    data = request.POST if request.method == 'POST' else None
    files = request.FILES if request.method == 'POST' else None
    context = selectors.get_product_form_context(data=data, files=files)

    if context.pop('product_saved'):
        messages.success(request, 'محصول با موفقیت افزوده شد.')
        return redirect('shop:product_management')

    context['page_title'] = 'افزودن محصول'
    return render(request, 'shop/management/product_form.html', context)


@admin_required
def product_update(request, pk):
    data = request.POST if request.method == 'POST' else None
    files = request.FILES if request.method == 'POST' else None
    context = selectors.get_product_form_context(
        pk=pk,
        data=data,
        files=files,
    )

    if context.pop('product_saved'):
        messages.success(request, 'محصول با موفقیت ویرایش شد.')
        return redirect('shop:product_management')

    context['page_title'] = 'ویرایش محصول'
    return render(request, 'shop/management/product_form.html', context)


@admin_required
def product_delete(request, pk):
    product = selectors.get_product_for_delete(pk)

    if request.method == 'POST':
        selectors.delete_product(product)
        messages.success(request, 'محصول با موفقیت حذف شد.')
        return redirect('shop:product_management')

    return render(
        request,
        'shop/management/product_confirm_delete.html',
        {'product': product},
    )
