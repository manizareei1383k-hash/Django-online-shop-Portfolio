# Security and deployment

Local development uses `config.settings`; WSGI/ASGI default to `config.production`.
Do not deploy `runserver` or override production with development settings.
Production refuses startup without a fresh secret, exact allowed hosts, PostgreSQL,
Redis and SMTP configuration. Environment variables are documented in `.env.example`;
that file is a template, not an automatically loaded configuration file.

## Running locally

Install `requirements-dev.txt`, run `python manage.py migrate`, then
`python manage.py test --noinput`. Set a random `DJANGO_SECRET_KEY` in the process
environment for stable local sessions. Without it, development generates a temporary
key and restarting the process invalidates sessions and reset links.
The former committed secret must never be reused in deployment or as a fallback.
Default Django `/admin/` is disabled; use `/management-panel/`.

## Production requirements

- Provision PostgreSQL and Redis privately, with authentication, a dedicated database
  user, backups and tested restore procedures. PostgreSQL SSL defaults to `verify-full`;
  configure the server CA. SQLite cannot validate the row-locking concurrency guarantees.
- Set environment variables from `.env.example`, install `requirements.txt`, and run
  `python manage.py check --deploy --settings=config.production` and migrations with
  the same settings before starting the service. Redis should use `noeviction` and
  enough memory; do not expose its port publicly or use read replicas for rate counters.
- Terminate HTTPS at a trusted proxy, reject unknown hosts, set a 6 MiB request body
  limit, connection/read timeouts and edge-level traffic limits. Set the real client
  REMOTE_ADDR through a trusted server integration. The app deliberately ignores
  user-supplied X-Forwarded-For. Only trust forwarded HTTPS after the proxy strips and
  overwrites that header; block direct access to the application port.
- HSTS lasts a year and includes subdomains; ensure every subdomain supports HTTPS.
  The preload header does not register the domain in a browser preload list.
- Serve only public images from public media. Deny `/media/account/tickets/` at the
  reverse proxy, never map `private_media/` to a public URL, and never serve the repo,
  `.git`, database files, backups or environment files. Prefer a separate media origin
  without cookies if adding user-generated file types; adapt CSP explicitly if needed.
- Ticket files are stored outside public media, with random names, and served only
  after owner/admin authorization as `application/octet-stream` attachments. Existing
  legacy ticket files on another installation must be moved from
  `media/account/tickets/` to `private_media/account/tickets/`, preserving names,
  with verified backups and the old public location denied before deployment.
  This workspace had no legacy attachment records during inspection.
- PDF validation checks extension/header and forces download; it is not malware
  scanning. Add an antivirus/sandbox scan before distributing files in deployments
  that accept untrusted documents. Images are decoded, size checked and re-encoded.
- Configure SMTP credentials; password reset must not print tokens into production logs.
  Add error monitoring and restricted, externally retained administrative audit logs.

## Application controls

CSRF stays enabled. State-changing endpoints require POST or process mutations only
on POST. Private objects are scoped to their owner; admin routes require active staff.
Forms whitelist editable fields. Changing email/phone requires the current password.
Passwords are masked in error reports, private responses use no-store, and reset
pages use no-referrer. CSP, clickjacking, MIME sniffing and cookie protections apply.

Rate limits are five requests per route/IP and authenticated user per 60-second fixed
window, including staff; the global IP limit is 60. Login/reset/register have additional
per-identifier limits across IPs. Object IDs and IPv6 addresses within /64 do not create
fresh buckets. Cache outages fail closed with 503. Local cache is process-local;
production uses shared Redis. Fixed windows can allow a boundary burst. This is not
DDoS protection, and distributed attacks across many accounts require edge controls.

Redis database 1 stores cache, rate-limit counters, short locks and the cached copy of
database-backed sessions. Celery uses database 2 as broker and database 3 for results.
Run `start_redis.ps1` and `start_worker.ps1` for local development. Production must run
Redis and the Celery worker as supervised services. Password-reset email is queued in
Celery; public home data is cached for five minutes and invalidated after product,
category or discount writes. Database rows remain the source of truth.
The local Redis-compatible server binds only to loopback, enables protected mode and
AOF persistence, uses a 256 MiB ceiling and `noeviction` so security counters aren't
silently discarded. Production needs authentication/TLS or a private socket/network.

Financial changes retain server-calculated price snapshots, stock checks and payment
idempotency. Wallet changes lock the wallet before checking the reference; cart
mutations and checkout lock the cart; payment completion/refund lock order before
payment to align lock ordering. Tax and order lines reuse the same price snapshot.
Real concurrency must also be tested against the production PostgreSQL deployment.
The test gateway has a separate disable switch and is always off in production.

## Verification and remaining work

Verified on 2026-09-09: all 135 tests passed on local SQLite, including 24 added
security regression tests. The production deployment check passed without warnings
using isolated example environment values (no live service connectivity tested).
Migration 0006 was applied locally; no model changes remain without migrations.
`pip check` passed. The installed environment audit initially found
PYSEC-2026-3721 in pip 26.1.2; pip was upgraded to 26.2.1 and the repeated audit
reported no known vulnerabilities. Django was updated from 6.1 to 6.1.1.

Run `python manage.py test --noinput`, `python manage.py makemigrations --check --dry-run`,
`python -m pip check` and `python -m pip_audit -r requirements.txt --no-deps --disable-pip`.
Repeat dependency auditing after upgrades and review security announcements.

An application-code review is not a penetration test of a deployed server. TLS,
proxy behavior, network ACLs, production Redis/PostgreSQL, backups, malware scanning,
account contact verification, admin MFA and operational monitoring need deployment
configuration and validation. No live server or external accounts were changed.

Reference: https://docs.djangoproject.com/en/6.1/howto/deployment/checklist/
