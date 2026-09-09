from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth import login as auth_login
from django.contrib.auth import logout as auth_logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST
from django.views.decorators.http import require_safe
from django.views.decorators.debug import sensitive_post_parameters
from django.http import FileResponse

from . import selectors


@login_required
@require_safe
def ticket_attachment(request, name):
    attachment = selectors.get_ticket_attachment(request.user, name)
    return FileResponse(attachment, as_attachment=True, content_type='application/octet-stream')


@login_required
@sensitive_post_parameters('old_password', 'new_password1', 'new_password2')
def password_change(request):
    data = request.POST if request.method == 'POST' else None
    context = selectors.get_password_change_context(request.user, data=data)
    user = context.pop('changed_user')
    if user is not None:
        update_session_auth_hash(request, user)
        return redirect('account:password_change_done')
    return render(request, 'account/password_change_form.html', context)


@login_required
def password_change_done(request):
    return render(request, 'account/password_change_done.html')


def password_reset(request):
    data = request.POST if request.method == 'POST' else None
    context = selectors.get_password_reset_context(request, data=data)
    if context.pop('email_sent'):
        return redirect('account:password_reset_done')
    return render(request, 'account/password_reset_form.html', context)


def password_reset_done(request):
    return render(request, 'account/password_reset_done.html')


@sensitive_post_parameters('new_password1', 'new_password2')
def password_reset_confirm(request, uidb64, token):
    data = request.POST if request.method == 'POST' else None
    context = selectors.get_password_reset_confirm_context(
        uidb64,
        token,
        session_token=request.session.get(selectors.RESET_SESSION_TOKEN),
        data=data,
    )
    token_to_store = context.pop('token_to_store')
    if token_to_store is not None:
        request.session[selectors.RESET_SESSION_TOKEN] = token_to_store
        return redirect(
            'account:password_reset_confirm',
            uidb64=uidb64,
            token=selectors.RESET_URL_TOKEN,
        )
    if context.pop('password_changed'):
        request.session.pop(selectors.RESET_SESSION_TOKEN, None)
        return redirect('account:password_reset_complete')
    return render(request, 'account/password_reset_confirm.html', context)


def password_reset_complete(request):
    return render(request, 'account/password_reset_complete.html')


@sensitive_post_parameters('password1', 'password2')
def register(request):
    if request.user.is_authenticated:
        return redirect('account:profile')

    data = request.POST if request.method == 'POST' else None
    files = request.FILES if request.method == 'POST' else None
    context = selectors.get_register_context(data=data, files=files)
    user = context.pop('registered_user')

    if user is not None:
        auth_login(request, user)
        messages.success(request, 'حساب کاربری شما ساخته شد.')
        return redirect('account:profile')

    return render(request, 'account/register.html', context)


@sensitive_post_parameters('password')
def login(request):
    if request.user.is_authenticated:
        return redirect('account:profile')

    data = request.POST if request.method == 'POST' else None
    context = selectors.get_login_context(request, data=data)
    user = context.pop('authenticated_user')

    if user is not None:
        auth_login(request, user)
        next_url = selectors.get_safe_login_redirect(request)
        if next_url:
            return redirect(next_url)
        return redirect('account:profile')

    return render(request, 'account/login.html', context)


@require_POST
def logout(request):
    auth_logout(request)
    return redirect('shop:home')


@login_required
def profile(request):
    context = selectors.get_profile_context(request.user)
    return render(request, 'account/profile.html', context)


@login_required
@sensitive_post_parameters('current_password')
def profile_edit(request):
    data = request.POST if request.method == 'POST' else None
    files = request.FILES if request.method == 'POST' else None
    context = selectors.get_profile_form_context(
        request.user,
        data=data,
        files=files,
    )
    if context.pop('profile_saved'):
        messages.success(request, 'پروفایل شما ویرایش شد.')
        return redirect('account:profile')
    return render(request, 'account/profile_form.html', context)


@login_required
def address_list(request):
    context = selectors.get_addresses_context(request.user)
    return render(request, 'account/address_list.html', context)


@login_required
def address_create(request):
    data = request.POST if request.method == 'POST' else None
    context = selectors.get_address_form_context(request.user, data=data)
    if context.pop('address_saved'):
        messages.success(request, 'آدرس اضافه شد.')
        return redirect('account:address_list')
    return render(request, 'account/address_form.html', context)


@login_required
def address_update(request, pk):
    data = request.POST if request.method == 'POST' else None
    context = selectors.get_address_form_context(request.user, pk=pk, data=data)
    if context.pop('address_saved'):
        messages.success(request, 'آدرس ویرایش شد.')
        return redirect('account:address_list')
    return render(request, 'account/address_form.html', context)


@login_required
def address_delete(request, pk):
    if request.method == 'POST':
        if selectors.delete_address_for_user(request.user, pk):
            messages.success(request, 'آدرس حذف شد.')
        else:
            messages.error(request, 'این آدرس در یک سفارش استفاده شده و قابل حذف نیست.')
        return redirect('account:address_list')
    address = selectors.get_address_for_user(request.user, pk)
    return render(
        request,
        'account/address_confirm_delete.html',
        {'address': address},
    )


@login_required
def ticket_list(request):
    context = selectors.get_tickets_context(request.user)
    return render(request, 'account/ticket_list.html', context)


@login_required
def ticket_create(request):
    data = request.POST if request.method == 'POST' else None
    context = selectors.get_ticket_form_context(request.user, data=data)
    ticket = context.pop('created_ticket')
    if ticket is not None:
        messages.success(request, 'تیکت ساخته شد. حالا پیام خود را ارسال کنید.')
        return redirect('account:ticket_detail', pk=ticket.pk)
    return render(request, 'account/ticket_form.html', context)


@login_required
def ticket_detail(request, pk):
    data = request.POST if request.method == 'POST' else None
    files = request.FILES if request.method == 'POST' else None
    context = selectors.get_ticket_detail_context(
        request.user,
        pk,
        data=data,
        files=files,
    )
    if context.pop('message_saved'):
        messages.success(request, 'پیام شما ارسال شد.')
        return redirect('account:ticket_detail', pk=pk)
    return render(request, 'account/ticket_detail.html', context)


@login_required
def wallet(request):
    context = selectors.get_wallet_context(request.user)
    return render(request, 'account/wallet.html', context)
