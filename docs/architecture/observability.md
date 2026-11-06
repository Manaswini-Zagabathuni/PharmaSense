# API observability and operational metadata

## Scope

Phase 4B adds dependency-free operational visibility at the HTTP and application-service
boundaries. It does not alter FAERS source data, analytics queries, statistical calculations,
ranking, or response values.

## Request correlation

Every HTTP response includes `X-Request-ID`. A client-provided identifier is preserved only when
it is 1–128 characters, begins with an ASCII letter or digit, and otherwise contains only ASCII
letters, digits, `.`, `_`, or `-`. Missing or invalid values are replaced with a random UUID4 hex
identifier. This validation prevents control characters, unbounded identifiers, and log injection.

The request-completion event is a compact JSON object with only:

- `event=http_request_completed`
- request ID
- HTTP method
- matched route path template without query strings or path-parameter values
- response status code
- monotonic duration in milliseconds

Durations are operational measurements and are not API response fields. Unexpected route
exceptions return a generic HTTP 500 response, retain the request ID, and produce a sanitized
event without the exception message.

## Analytics operation timing

The application service times the four existing operations using stable names:

- `signal_list_retrieval`
- `signal_detail_retrieval`
- `drug_list_retrieval`
- `drug_reaction_retrieval`

Each `analytics_operation_completed` JSON event contains the operation, `success` or `error`, and
duration in milliseconds. It contains no drug names, reaction terms, thresholds, SQL, source
records, or result values. Database readiness and analytics database failures also use fixed JSON
events without driver exception text.

The implementation uses Python's standard `logging`, `json`, and monotonic `perf_counter` APIs.
It adds no telemetry vendor, agent, exporter, or external dependency. Deployment platforms may
collect stdout/stderr according to their own retention and access policies. Local startup uses a
message-only formatter; an existing deployment logging handler is never replaced.

## Safe metadata

`GET /api/v1/info` returns exactly:

- `application_name`
- `environment`
- `version`

The version defaults to the centralized package version and can be set with `APP_VERSION` for a
build or release. The endpoint never returns database configuration, credentials, filesystem
paths, hostnames, ports, or infrastructure details.

## Privacy and logging rules

Application events must be constructed from explicit allowlists. The following are prohibited:

- request or response bodies
- authorization, cookie, or other credential-bearing headers
- query strings
- database URLs, usernames, or passwords
- raw SQL or database-driver exception text
- raw FAERS records, drug names, reaction terms, or patient/report fields

Request IDs are correlation values, not authentication or authorization tokens. Clients should
not place personal data or secrets in them even though the server validates their syntax and
length.
