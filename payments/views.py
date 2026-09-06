from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from . import selectors
from .models import Payment


@login_required
@require_POST
def payment_start(request, order_id):
    context = selectors.get_payment_start_context(
        request.user,
        order_id,
        data=request.POST,
    )
    form = context['form']
    if not form.is_valid():
        return render(request, 'payments/payment_start.html', context)

    try:
        payment = selectors.create_payment(
            request.user,
            order_id,
            form.cleaned_data['gateway'],
        )
    except selectors.PaymentError as error:
        messages.error(request, str(error))
        return redirect('orders:detail', pk=order_id)

    if payment.gateway == Payment.Gateway.TEST:
        return redirect('payments:test_gateway', token=payment.token)
    if payment.status == Payment.Status.PAID:
        messages.success(request, 'پرداخت با موفقیت انجام شد.')
    else:
        messages.error(request, payment.failure_reason)
    return redirect('orders:detail', pk=order_id)


@login_required
def test_gateway(request, token):
    try:
        context = selectors.get_test_gateway_context(request.user, token)
    except selectors.PaymentError as error:
        messages.error(request, str(error))
        return redirect('orders:list')
    return render(request, 'payments/test_gateway.html', context)


@login_required
@require_POST
def test_gateway_callback(request, token):
    successful = request.POST.get('result') == 'success'
    try:
        payment = selectors.complete_test_payment(
            request.user,
            token,
            successful,
        )
    except selectors.PaymentError as error:
        messages.error(request, str(error))
        return redirect('orders:list')

    if payment.status == Payment.Status.PAID:
        messages.success(request, 'پرداخت با موفقیت تأیید شد.')
    else:
        messages.error(request, payment.failure_reason)
    return redirect('orders:detail', pk=payment.order_id)

