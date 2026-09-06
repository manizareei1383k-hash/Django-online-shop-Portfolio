from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from . import selectors


@login_required
def invoice_detail(request, number):
    context = selectors.get_invoice_detail_context(request.user, number)
    return render(request, 'invoices/invoice_detail.html', context)

