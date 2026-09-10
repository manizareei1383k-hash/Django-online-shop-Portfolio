import contextvars
import json
import logging
import os
from datetime import datetime, timedelta, timezone


request_id_context = contextvars.ContextVar('request_id', default='-')


def bind_request_id(request_id):
    return request_id_context.set(request_id)


def reset_request_id(token):
    request_id_context.reset(token)


class RequestIdFilter(logging.Filter):
    def filter(self, record):
        request = getattr(record, 'request', None)
        record.request_id = getattr(
            request,
            'request_id',
            request_id_context.get(),
        )
        return True


class JsonFormatter(logging.Formatter):
    def format(self, record):
        payload = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'request_id': getattr(record, 'request_id', '-'),
        }
        for field in ('method', 'path', 'status_code', 'duration_ms'):
            value = getattr(record, field, None)
            if value is not None:
                payload[field] = value
        if record.exc_info:
            payload['exception'] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False, default=str)


class DatabaseErrorHandler(logging.Handler):
    def emit(self, record):
        try:
            from django.conf import settings
            from django.utils import timezone as django_timezone
            from management_panel.models import SystemLog

            request = getattr(record, 'request', None)
            traceback_text = (
                logging.Formatter().formatException(record.exc_info)
                if record.exc_info
                else ''
            )
            SystemLog.objects.create(
                level=record.levelname[:20],
                logger_name=record.name[:150],
                message=record.getMessage()[:5000],
                request_id=getattr(record, 'request_id', request_id_context.get())[:32],
                method=getattr(record, 'method', getattr(request, 'method', ''))[:10],
                path=getattr(record, 'path', getattr(request, 'path_info', ''))[:500],
                status_code=getattr(record, 'status_code', None),
                traceback=traceback_text[:20000],
            )
            cutoff = django_timezone.now() - timedelta(
                days=settings.SYSTEM_LOG_RETENTION_DAYS
            )
            SystemLog.objects.filter(created_at__lt=cutoff).delete()
        except Exception:
            self.handleError(record)


def configure_sentry():
    dsn = os.environ.get('SENTRY_DSN', '').strip()
    if not dsn:
        return False

    import sentry_sdk

    sentry_sdk.init(
        dsn=dsn,
        environment=os.environ.get('SENTRY_ENVIRONMENT', 'production'),
        release=os.environ.get('SENTRY_RELEASE') or None,
        traces_sample_rate=float(os.environ.get('SENTRY_TRACES_SAMPLE_RATE', '0')),
        send_default_pii=False,
    )
    return True
