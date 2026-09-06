from django.contrib.auth.tokens import default_token_generator
from django.db.models.deletion import ProtectedError
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils.encoding import force_str
from django.utils.http import url_has_allowed_host_and_scheme, urlsafe_base64_decode
from django.utils import timezone

from .forms import (
    AccountPasswordChangeForm,
    AccountPasswordResetForm,
    AccountSetPasswordForm,
    AddressForm,
    LoginForm,
    RegisterForm,
    TicketForm,
    TicketMessageForm,
    UserProfileForm,
)
from .models import Address, Ticket, User, Wallet


RESET_SESSION_TOKEN = '_password_reset_token'
RESET_URL_TOKEN = 'set-password'


def get_password_change_context(user, data=None):
    form = AccountPasswordChangeForm(user, data=data)
    changed_user = None
    if data is not None and form.is_valid():
        changed_user = form.save()
    return {'form': form, 'changed_user': changed_user}


def get_password_reset_context(request, data=None):
    form = AccountPasswordResetForm(data=data)
    email_sent = False
    if data is not None and form.is_valid():
        form.save(
            request=request,
            use_https=request.is_secure(),
            email_template_name='account/password_reset_email.txt',
            subject_template_name='account/password_reset_subject.txt',
        )
        email_sent = True
    return {'form': form, 'email_sent': email_sent}


def get_password_reset_confirm_context(
    uidb64,
    token,
    session_token=None,
    data=None,
):
    try:
        user_id = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=user_id)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None

    token_to_store = None
    if (
        user is not None
        and token != RESET_URL_TOKEN
        and default_token_generator.check_token(user, token)
    ):
        token_to_store = token

    validlink = bool(
        user is not None
        and token == RESET_URL_TOKEN
        and session_token
        and default_token_generator.check_token(user, session_token)
    )
    form = AccountSetPasswordForm(user, data=data) if validlink else None
    password_changed = False

    if data is not None and form is not None and form.is_valid():
        form.save()
        password_changed = True

    return {
        'form': form,
        'validlink': validlink,
        'token_to_store': token_to_store,
        'password_changed': password_changed,
    }


def get_safe_login_redirect(request):
    next_url = request.GET.get('next')
    if next_url and url_has_allowed_host_and_scheme(
        next_url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return next_url
    return None


def get_register_context(data=None, files=None):
    form = RegisterForm(data=data, files=files)
    user = form.save() if data is not None and form.is_valid() else None
    return {'form': form, 'registered_user': user}


def get_login_context(request, data=None):
    form = LoginForm(request=request, data=data)
    user = form.get_user() if data is not None and form.is_valid() else None
    return {'form': form, 'authenticated_user': user}


def get_profile_context(user):
    return {
        'addresses_count': user.addresses.count(),
        'tickets_count': user.tickets.count(),
        'recent_tickets': user.tickets.all()[:5],
    }


def get_profile_form_context(user, data=None, files=None):
    form = UserProfileForm(data=data, files=files, instance=user)
    saved = False
    if data is not None and form.is_valid():
        form.save()
        saved = True
    return {'form': form, 'profile_saved': saved}


def get_addresses_context(user):
    return {'addresses': user.addresses.all()}


def get_address_form_context(user, pk=None, data=None):
    address = (
        get_object_or_404(Address, pk=pk, user=user) if pk is not None else None
    )
    form = AddressForm(data=data, instance=address)
    form.instance.user = user
    saved = False

    if data is not None and form.is_valid():
        with transaction.atomic():
            address = form.save(commit=False)
            address.user = user
            if address.is_default:
                user.addresses.filter(is_default=True).exclude(
                    pk=address.pk
                ).update(is_default=False)
            address.save()
        saved = True

    return {
        'form': form,
        'address': address,
        'address_saved': saved,
        'page_title': 'ویرایش آدرس' if pk is not None else 'افزودن آدرس',
    }


def get_address_for_user(user, pk):
    return get_object_or_404(Address, pk=pk, user=user)


def delete_address_for_user(user, pk):
    address = get_address_for_user(user, pk)
    try:
        address.delete()
    except ProtectedError:
        return False
    return True


def get_tickets_context(user):
    tickets = user.tickets.prefetch_related('messages')
    return {'tickets': tickets}


def get_ticket_form_context(user, data=None):
    form = TicketForm(data=data)
    ticket = None

    if data is not None and form.is_valid():
        ticket = form.save(commit=False)
        ticket.user = user
        ticket.save()

    return {'form': form, 'created_ticket': ticket}


def get_ticket_detail_context(user, pk, data=None, files=None):
    ticket = get_object_or_404(
        Ticket.objects.prefetch_related('messages__sender'),
        pk=pk,
        user=user,
    )
    form = TicketMessageForm(data=data, files=files)
    message_saved = False

    if data is not None and ticket.status != Ticket.Status.CLOSED and form.is_valid():
        ticket_message = form.save(commit=False)
        ticket_message.ticket = ticket
        ticket_message.sender = user
        ticket_message.save()
        Ticket.objects.filter(pk=ticket.pk).update(updated_at=timezone.now())
        message_saved = True

    return {
        'ticket': ticket,
        'form': form,
        'message_saved': message_saved,
    }


def get_wallet_context(user):
    wallet, _ = Wallet.objects.get_or_create(user=user)
    transactions = wallet.transactions.all()[:30]
    return {'wallet': wallet, 'transactions': transactions}
