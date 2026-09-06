import uuid

from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.db import models, transaction

from .managers import UserManager


phone_number_validator = RegexValidator(
    regex=r'^\+?\d{10,15}$',
    message='شماره تلفن باید بین ۱۰ تا ۱۵ رقم باشد.',
)


class User(AbstractUser):
    username = None
    email = models.EmailField(blank=True)
    phone_number = models.CharField(
        max_length=15,
        unique=True,
        validators=[phone_number_validator],
    )
    avatar = models.ImageField(
        upload_to='account/avatars/',
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    USERNAME_FIELD = 'phone_number'
    REQUIRED_FIELDS = []

    objects = UserManager()

    def __str__(self):
        return self.get_full_name() or self.phone_number


class Address(models.Model):
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='addresses',
    )
    title = models.CharField(max_length=100, default='آدرس من')
    recipient_name = models.CharField(max_length=150)
    recipient_phone = models.CharField(
        max_length=15,
        validators=[phone_number_validator],
    )
    province = models.CharField(max_length=100)
    city = models.CharField(max_length=100)
    address = models.TextField()
    postal_code = models.CharField(
        max_length=10,
        validators=[
            RegexValidator(
                regex=r'^\d{10}$',
                message='کدپستی باید دقیقاً ۱۰ رقم باشد.',
            )
        ],
    )
    is_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('-is_default', '-created_at')
        constraints = [
            models.UniqueConstraint(
                fields=('user',),
                condition=models.Q(is_default=True),
                name='one_default_address_per_user',
            )
        ]

    def __str__(self):
        return f'{self.title} - {self.user}'


class Ticket(models.Model):
    class Status(models.TextChoices):
        OPEN = 'open', 'باز'
        IN_PROGRESS = 'in_progress', 'در حال بررسی'
        ANSWERED = 'answered', 'پاسخ داده‌شده'
        CLOSED = 'closed', 'بسته‌شده'

    class Priority(models.TextChoices):
        LOW = 'low', 'کم'
        NORMAL = 'normal', 'عادی'
        HIGH = 'high', 'زیاد'

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='tickets',
    )
    subject = models.CharField(max_length=200)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.OPEN,
        db_index=True,
    )
    priority = models.CharField(
        max_length=10,
        choices=Priority.choices,
        default=Priority.NORMAL,
        db_index=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('-updated_at',)

    def __str__(self):
        return f'#{self.pk} - {self.subject}'


class TicketMessage(models.Model):
    ticket = models.ForeignKey(
        Ticket,
        on_delete=models.CASCADE,
        related_name='messages',
    )
    sender = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        related_name='ticket_messages',
        null=True,
    )
    message = models.TextField()
    attachment = models.FileField(
        upload_to='account/tickets/',
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ('created_at',)

    def __str__(self):
        return f'پیام تیکت #{self.ticket_id}'


class Wallet(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='wallet',
    )
    balance = models.DecimalField(
        max_digits=14,
        decimal_places=0,
        default=0,
        editable=False,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(balance__gte=0),
                name='wallet_balance_is_not_negative',
            )
        ]

    def __str__(self):
        return f'کیف پول {self.user}'

    @staticmethod
    def _validate_amount(amount):
        try:
            amount = models.DecimalField().to_python(amount)
        except (TypeError, ValueError):
            raise ValidationError('مبلغ واردشده معتبر نیست.')

        if amount is None or amount <= 0 or amount != amount.to_integral_value():
            raise ValidationError('مبلغ باید یک عدد صحیح و بیشتر از صفر باشد.')
        return amount

    @staticmethod
    def _get_existing_transaction(reference, wallet_id, direction, kind, amount):
        existing = WalletTransaction.objects.filter(reference=reference).first()
        if not existing:
            return None
        if (
            existing.wallet_id != wallet_id
            or existing.direction != direction
            or existing.kind != kind
            or existing.amount != amount
        ):
            raise ValidationError('شماره مرجع با اطلاعات متفاوت قبلاً استفاده شده است.')
        return existing

    def credit(self, amount, kind='deposit', description='', reference=None):
        amount = self._validate_amount(amount)
        reference = reference or uuid.uuid4()
        allowed_kinds = {
            WalletTransaction.Kind.DEPOSIT,
            WalletTransaction.Kind.REFUND,
            WalletTransaction.Kind.MANUAL,
        }
        if kind not in allowed_kinds:
            raise ValidationError('نوع تراکنش برای افزایش موجودی معتبر نیست.')

        with transaction.atomic():
            existing = self._get_existing_transaction(
                reference,
                self.pk,
                WalletTransaction.Direction.CREDIT,
                kind,
                amount,
            )
            if existing:
                return existing

            Wallet.objects.filter(pk=self.pk).update(
                balance=models.F('balance') + amount,
            )
            self.refresh_from_db(fields=('balance', 'updated_at'))
            return WalletTransaction.objects.create(
                wallet=self,
                direction=WalletTransaction.Direction.CREDIT,
                kind=kind,
                amount=amount,
                balance_after=self.balance,
                reference=reference,
                description=description,
            )

    def debit(self, amount, kind='purchase', description='', reference=None):
        amount = self._validate_amount(amount)
        reference = reference or uuid.uuid4()
        allowed_kinds = {
            WalletTransaction.Kind.PURCHASE,
            WalletTransaction.Kind.MANUAL,
        }
        if kind not in allowed_kinds:
            raise ValidationError('نوع تراکنش برای کاهش موجودی معتبر نیست.')

        with transaction.atomic():
            existing = self._get_existing_transaction(
                reference,
                self.pk,
                WalletTransaction.Direction.DEBIT,
                kind,
                amount,
            )
            if existing:
                return existing

            updated = Wallet.objects.filter(
                pk=self.pk,
                balance__gte=amount,
            ).update(balance=models.F('balance') - amount)
            if not updated:
                raise ValidationError('موجودی کیف پول کافی نیست.')

            self.refresh_from_db(fields=('balance', 'updated_at'))
            return WalletTransaction.objects.create(
                wallet=self,
                direction=WalletTransaction.Direction.DEBIT,
                kind=kind,
                amount=amount,
                balance_after=self.balance,
                reference=reference,
                description=description,
            )


class WalletTransaction(models.Model):
    class Direction(models.TextChoices):
        CREDIT = 'credit', 'افزایش موجودی'
        DEBIT = 'debit', 'کاهش موجودی'

    class Kind(models.TextChoices):
        DEPOSIT = 'deposit', 'واریز'
        PURCHASE = 'purchase', 'خرید'
        REFUND = 'refund', 'بازگشت وجه'
        MANUAL = 'manual', 'اصلاح دستی'

    wallet = models.ForeignKey(
        Wallet,
        on_delete=models.PROTECT,
        related_name='transactions',
    )
    direction = models.CharField(max_length=10, choices=Direction.choices)
    kind = models.CharField(max_length=20, choices=Kind.choices)
    amount = models.DecimalField(max_digits=14, decimal_places=0)
    balance_after = models.DecimalField(max_digits=14, decimal_places=0)
    reference = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    description = models.CharField(max_length=250, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ('-created_at',)
        constraints = [
            models.CheckConstraint(
                condition=models.Q(amount__gt=0),
                name='wallet_transaction_amount_is_positive',
            )
        ]

    def __str__(self):
        return f'{self.get_direction_display()} - {self.amount}'
