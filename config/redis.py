from contextlib import nullcontext

from django.conf import settings


def redis_lock(name, timeout=30, blocking_timeout=3):
    if settings.IS_TESTING:
        return nullcontext()
    from django_redis import get_redis_connection

    return get_redis_connection('default').lock(
        f'lock:{name}',
        timeout=timeout,
        blocking_timeout=blocking_timeout,
    )
