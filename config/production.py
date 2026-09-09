"""Fail-closed production settings. Supply values using the process environment."""
from .settings import *  # noqa: F403
from .settings import redis_database_url
from django.core.exceptions import ImproperlyConfigured


def required(name):
    value = os.environ.get(name, '').strip()
    if not value:
        raise ImproperlyConfigured(f'{name} is required in production.')
    return value


DEBUG = False
SECRET_KEY = required('DJANGO_SECRET_KEY')
if len(SECRET_KEY) < 50 or len(set(SECRET_KEY)) < 5 or SECRET_KEY.startswith('django-insecure-'):
    raise ImproperlyConfigured('Use a new, random DJANGO_SECRET_KEY of at least 50 characters.')
ALLOWED_HOSTS = [host.strip() for host in required('DJANGO_ALLOWED_HOSTS').split(',')]
if any(not host or '*' in host or host.startswith('.') for host in ALLOWED_HOSTS):
    raise ImproperlyConfigured('DJANGO_ALLOWED_HOSTS must contain exact hostnames.')
CSRF_TRUSTED_ORIGINS = [f'https://{host}' for host in ALLOWED_HOSTS]
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
# Only enable if the trusted proxy strips incoming X-Forwarded-Proto and sets it itself.
if os.environ.get('DJANGO_TRUST_PROXY_HTTPS') == 'true':
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

ENABLE_TEST_GATEWAY = False
RATE_LIMIT_ENABLED = True
REDIS_URL = required('REDIS_URL')
CACHES['default']['BACKEND'] = 'django_redis.cache.RedisCache'
CACHES['default']['LOCATION'] = REDIS_URL
CACHES['default']['OPTIONS'] = {
    'CLIENT_CLASS': 'django_redis.client.DefaultClient',
    'SOCKET_CONNECT_TIMEOUT': 2,
    'SOCKET_TIMEOUT': 2,
}
CELERY_BROKER_URL = os.environ.get('CELERY_BROKER_URL', redis_database_url(REDIS_URL, 2))
CELERY_RESULT_BACKEND = os.environ.get('CELERY_RESULT_BACKEND', redis_database_url(REDIS_URL, 3))
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': required('POSTGRES_DB'),
        'USER': required('POSTGRES_USER'),
        'PASSWORD': required('POSTGRES_PASSWORD'),
        'HOST': required('POSTGRES_HOST'),
        'PORT': os.environ.get('POSTGRES_PORT', '5432'),
        'OPTIONS': {'sslmode': os.environ.get('POSTGRES_SSLMODE', 'verify-full')},
    },
}
STATIC_ROOT = BASE_DIR / 'staticfiles'
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = required('EMAIL_HOST')
EMAIL_PORT = int(os.environ.get('EMAIL_PORT', '587'))
EMAIL_HOST_USER = required('EMAIL_HOST_USER')
EMAIL_HOST_PASSWORD = required('EMAIL_HOST_PASSWORD')
EMAIL_USE_TLS = True
EMAIL_TIMEOUT = 10
DEFAULT_FROM_EMAIL = required('DEFAULT_FROM_EMAIL')
