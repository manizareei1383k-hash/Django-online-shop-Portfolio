from celery import shared_task


@shared_task(autoretry_for=(Exception,), retry_backoff=True, retry_kwargs={'max_retries': 3})
def warm_public_shop_cache():
    from .selectors import get_home_context

    get_home_context(use_cache=True)
    return True
