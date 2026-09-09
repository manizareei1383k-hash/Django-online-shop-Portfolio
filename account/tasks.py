from celery import shared_task

from .forms import AccountPasswordResetForm


@shared_task(autoretry_for=(Exception,), retry_backoff=True, retry_kwargs={'max_retries': 3})
def send_password_reset_email(email, phone_number, domain, use_https=False):
    form = AccountPasswordResetForm(
        data={'email': email, 'phone_number': phone_number},
    )
    if not form.is_valid():
        return False
    form.save(
        domain_override=domain,
        use_https=use_https,
        email_template_name='account/password_reset_email.txt',
        subject_template_name='account/password_reset_subject.txt',
    )
    return True
