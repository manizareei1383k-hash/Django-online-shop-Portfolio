import logging
import uuid

from django.core.cache import cache
from django.db import connection
from django.http import JsonResponse
from django.views.decorators.http import require_GET


logger = logging.getLogger('shop.health')


@require_GET
def live(request):
    return JsonResponse({'status': 'ok'})


@require_GET
def ready(request):
    cache_key = f'health:{uuid.uuid4().hex}'
    try:
        with connection.cursor() as cursor:
            cursor.execute('SELECT 1')
            cursor.fetchone()
        cache.set(cache_key, 'ok', 10)
        if cache.get(cache_key) != 'ok':
            raise RuntimeError('Cache health check failed.')
        cache.delete(cache_key)
    except Exception:
        logger.exception('Readiness check failed')
        return JsonResponse({'status': 'unavailable'}, status=503)
    return JsonResponse({'status': 'ok'})
