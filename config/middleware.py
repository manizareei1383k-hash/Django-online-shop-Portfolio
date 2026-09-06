import hashlib
import time

from django.conf import settings
from django.core.cache import cache
from django.http import HttpResponse


class UserRateLimitMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not settings.RATE_LIMIT_ENABLED:
            return self.get_response(request)

        user = request.user
        if user.is_authenticated and user.is_staff:
            return self.get_response(request)

        limit = settings.RATE_LIMIT_REQUESTS
        window = settings.RATE_LIMIT_WINDOW_SECONDS
        current_time = int(time.time())
        bucket = current_time // window
        retry_after = window - (current_time % window)

        if user.is_authenticated:
            visitor = f'user:{user.pk}'
        else:
            visitor = f'ip:{request.META.get("REMOTE_ADDR", "unknown")}'

        raw_key = f'{visitor}:{request.path_info}:{bucket}'
        key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
        cache_key = f'user-rate-limit:{key_hash}'

        if cache.add(cache_key, 1, timeout=retry_after + 1):
            request_count = 1
        else:
            try:
                request_count = cache.incr(cache_key)
            except ValueError:
                cache.set(cache_key, 1, timeout=retry_after + 1)
                request_count = 1

        remaining = max(0, limit - request_count)
        if request_count > limit:
            response = HttpResponse(
                'تعداد درخواست‌های شما بیش از حد مجاز است. کمی بعد دوباره تلاش کنید.',
                status=429,
            )
            response.headers['Retry-After'] = str(retry_after)
        else:
            response = self.get_response(request)

        response.headers['X-RateLimit-Limit'] = str(limit)
        response.headers['X-RateLimit-Remaining'] = str(remaining)
        return response
