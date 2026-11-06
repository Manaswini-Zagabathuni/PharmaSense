# Security hardening and deployment readiness

## Scope and assumptions

Phase 4C hardens the existing local-first, read-only analytics application. It does not add user
accounts, authentication, authorization, public-internet rate limiting, or a managed edge. The
API still assumes deployment behind an operator-controlled TLS reverse proxy or load balancer.

The public data source does not remove the need to protect database credentials, operational
configuration, logs, and deployment infrastructure. Application logs remain governed by the
privacy allowlist in [the observability design](observability.md).

## HTTP response headers

The API applies these headers to successful responses, validation/errors, trusted-host
rejections, health/readiness responses, and sanitized unexpected 500 responses:

| Header | Value | Purpose |
| --- | --- | --- |
| `X-Content-Type-Options` | `nosniff` | Prevent MIME-type sniffing. |
| `X-Frame-Options` | `DENY` | Prevent framing and clickjacking. |
| `Referrer-Policy` | `no-referrer` | Avoid sending request URLs as referrers. |
| `Permissions-Policy` | `camera=(), microphone=(), geolocation=()` | Disable unused browser capabilities. |

`X-Request-ID` remains present and independent of these headers. No successful response body or
schema changes.

A Content Security Policy is intentionally deferred: the API development documentation and the
current Vite-based local frontend have different asset requirements, and an incorrect shared
policy would be misleading or disruptive. Production static hosting should define a tested CSP
for its exact asset origins. HSTS is also an HTTPS edge responsibility and must only be enabled
after TLS is enforced for the intended domain.

## Trusted hosts and production validation

`APP_TRUSTED_HOSTS` is a comma-separated allowlist consumed by Starlette's trusted-host
middleware. Values are hostnames or `*.example.org` patterns without schemes, paths, or ports.
Local Python defaults allow `localhost`, `127.0.0.1`, `testserver`, and the Compose service name
`api`.

Production settings fail validation when:

- `APP_TRUSTED_HOSTS` was not explicitly supplied;
- the allowlist contains the unrestricted `*` entry; or
- `APP_LOG_LEVEL=DEBUG`.

For example:

```dotenv
APP_ENVIRONMENT=production
APP_LOG_LEVEL=INFO
APP_TRUSTED_HOSTS=api.pharmasense.example
```

Trusted-host validation is not CORS, authentication, or proxy trust configuration. PharmaSense
does not currently enable cross-origin browser access. Operators must separately configure their
reverse proxy, forwarded-header trust, TLS certificates, DNS, and network policy.

## Error handling

Known analytics availability and execution failures retain their existing sanitized API
responses. Unexpected exceptions retain the existing plain-text HTTP 500 contract, include the
request ID and security headers, and log only the request ID, method, matched route template, and
fixed event name. Exception messages, stack traces, SQL, driver text, credentials, and database
URLs are not sent to clients or added to application events.

## Container posture

The API image runs as UID/GID `10001`; the web image runs as the upstream `node` user. Compose
keeps MySQL on an internal network, binds API/web ports to loopback, enables
`no-new-privileges`, drops all Linux capabilities from API and web, uses init processes for signal
forwarding, and defines graceful stop windows. The API continues to apply Alembic migrations
before starting Uvicorn.

Compose is a development and verification topology, not a complete public deployment. In
particular, the web container runs Vite's development server. A public deployment should build
the static frontend and serve it from a hardened static server or CDN, terminate TLS at a trusted
edge, define CSP/HSTS there, keep MySQL private, manage secrets outside environment files, add
rate limiting, and define backup, recovery, log retention, and vulnerability-patching procedures.

## Verification boundary

Unit tests cover headers, request-ID coexistence, host acceptance/rejection, unchanged successful
responses, sanitized unexpected errors, and production configuration validation. CI continues to
exercise migrations and the full frontend-to-MySQL demonstration path. Local checks do not prove
the security of a future cloud or public deployment.
