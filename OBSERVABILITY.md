# Logging and error monitoring

This project keeps observability infrastructure inside `config`; no Django app is
required.

## Logs

Application and Django logs are emitted as JSON to stdout. Every HTTP response has
an `X-Request-ID` header, and the same ID appears in logs generated during that
request. Configure the minimum level with `DJANGO_LOG_LEVEL`.

Error-level logs are also stored in `SystemLog` and the latest 20 are shown on the
management dashboard. Old database logs are removed after
`SYSTEM_LOG_RETENTION_DAYS` days (30 by default). Console logs remain the primary
complete log stream.

Do not put passwords, tokens, request bodies, or other secrets in log messages.

## Health checks

- `/health/live/` confirms the Django process is running.
- `/health/ready/` checks the database and Redis cache and returns HTTP 503 when a
  dependency is unavailable.

These endpoints are exempt from the application rate limiter so infrastructure can
poll them. Restrict direct public access at the reverse proxy if appropriate.

## Sentry

Set `SENTRY_DSN` to enable error reporting. `SENTRY_ENVIRONMENT` and
`SENTRY_RELEASE` identify the deployment. Performance tracing is disabled by
default; set `SENTRY_TRACES_SAMPLE_RATE` to a value from 0 to 1 to enable sampling.
Tests never initialize Sentry.
