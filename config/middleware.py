import hashlib
import ipaddress
import logging
import time
import unicodedata

from django.conf import settings
from django.core.cache import cache
from django.http import HttpResponse
from django.urls import Resolver404, resolve
from django.utils.cache import patch_cache_control


logger = logging.getLogger('django.security.rate_limit')


class RequestSecurityMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.sensitive_post_parameters = '__ALL__'
        request.get_host()
        length = request.META.get('CONTENT_LENGTH', '')
        try:
            too_large = bool(length) and int(length) > settings.MAX_REQUEST_BYTES
        except ValueError:
            return HttpResponse(status=400)
        if too_large:
            return HttpResponse('Request too large.', status=413)
        if request.path_info.startswith('/media/account/tickets/'):
            return HttpResponse(status=404)
        response = self.get_response(request)
        if getattr(request, 'upload_limit_exceeded', False):
            response = HttpResponse('Upload too large.', status=413)
        response.headers['Permissions-Policy'] = 'camera=(), microphone=(), geolocation=()'
        response.headers['Content-Security-Policy'] = (
            "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data:; font-src 'self'; connect-src 'self'; "
            "object-src 'none'; base-uri 'self'; frame-ancestors 'none'; form-action 'self'"
        )
        if (getattr(request, 'user', None) and request.user.is_authenticated) or request.path_info.startswith('/account/'):
            patch_cache_control(response, private=True, no_store=True, no_cache=True, must_revalidate=True)
        if request.path_info.startswith('/account/password/'):
            response.headers['Referrer-Policy'] = 'no-referrer'
        return response

    def process_view(self, request, view_func, view_args, view_kwargs):
        if request.method == 'POST':
            request.POST  # Parse uploads before a view can perform a mutation.
            if getattr(request, 'upload_limit_exceeded', False):
                return HttpResponse('Upload too large.', status=413)
        return None


class UserRateLimitMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    @staticmethod
    def _check(identities):
        window = settings.RATE_LIMIT_WINDOW_SECONDS
        now = int(time.time())
        retry_after = window - now % window
        remaining = settings.RATE_LIMIT_REQUESTS
        try:
            for identity, limit in identities:
                digest = hashlib.sha256(f'{identity}:{now // window}'.encode()).hexdigest()
                key = f'rate-limit:{digest}'
                if cache.add(key, 1, timeout=retry_after + 1):
                    count = 1
                else:
                    try:
                        count = cache.incr(key)
                    except ValueError:
                        return HttpResponse('Please retry shortly.', status=503), 0
                remaining = min(remaining, max(0, limit - count))
                if count > limit:
                    response = HttpResponse('تعداد درخواست‌ها بیش از حد مجاز است.', status=429)
                    response.headers['Retry-After'] = str(retry_after)
                    return response, 0
        except Exception:
            logger.error('Rate limiter backend unavailable')
            return HttpResponse('Please retry shortly.', status=503), 0
        return None, remaining

    def __call__(self, request):
        if not settings.RATE_LIMIT_ENABLED:
            return self.get_response(request)
        try:
            route = resolve(request.path_info).view_name
        except Resolver404:
            route = 'unmatched'
        raw_ip = request.META.get('REMOTE_ADDR', 'unknown')
        try:
            address = ipaddress.ip_address(raw_ip)
            ip = str(ipaddress.ip_network(f'{address}/64', strict=False)) if address.version == 6 else str(address)
        except ValueError:
            ip = 'unknown'
        # Never trust client-supplied X-Forwarded-For.
        identities = [
            (f'ip:{ip}:route:{route}', settings.RATE_LIMIT_REQUESTS),
            (f'ip:{ip}:global', settings.RATE_LIMIT_GLOBAL_REQUESTS),
        ]
        if request.user.is_authenticated:
            identities.append((f'user:{request.user.pk}:route:{route}', settings.RATE_LIMIT_REQUESTS))
        response, remaining = self._check(identities)
        if response is None:
            response = self.get_response(request)
        response.headers['X-RateLimit-Limit'] = str(settings.RATE_LIMIT_REQUESTS)
        response.headers['X-RateLimit-Remaining'] = str(0 if response.status_code == 429 else remaining)
        return response

    def process_view(self, request, view_func, view_args, view_kwargs):
        if not settings.RATE_LIMIT_ENABLED or request.method != 'POST':
            return None
        name = request.resolver_match.view_name
        fields = {
            'account:login': ('username', 'login'),
            'admin:login': ('username', 'login'),
            'account:password_reset': ('phone_number', 'password-reset'),
            'account:register': ('phone_number', 'register'),
        }
        if name not in fields:
            return None
        field, action = fields[name]
        identifier = unicodedata.normalize('NFKC', request.POST.get(field, '').strip())
        if not identifier:
            return None
        # Account limits survive changing IPs; cache keys contain only hashes.
        response, _ = self._check([(f'account:{action}:{identifier}', settings.RATE_LIMIT_REQUESTS)])
        return response
