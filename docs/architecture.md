# Architecture

The browser talks to FastAPI over HTTP. FastAPI owns business logic and database access; the browser never connects directly to PostgreSQL. PostgreSQL runs locally through Compose. Health and readiness are separate: `/health` checks the API process; `/ready` executes a database query and returns 503 if unavailable.

Later, a separate worker can claim durable database jobs and call an isolated parser adapter and versioned analysis module. Match facts, heuristic assessments, and future model interpretations must remain distinguishable. A repeated analysis creates a new versioned run; no FACEIT profile is required for manual demo analysis. These are design intentions, not implemented features.

This development setup binds the database to localhost. Example credentials are local-only. Upload handling and job recovery must be designed and verified before exposing the application to other users.

## Accounts and sessions

Users have normalized unique email addresses and Argon2id password hashes. An opaque 256-bit random session token is held in an HttpOnly, SameSite=Strict cookie; only its SHA-256 digest is stored in PostgreSQL. Sessions expire after seven days; logout deletes the server-side row, and authentication replaces an existing session. Authentication and domain access are separate: `/auth/me` resolves the current user from the session, never from a client-supplied user ID.

Mutating auth endpoints require a configured exact Origin and a custom header; CORS allows credentials only for configured origins. Cookies use Secure and the `__Host-` prefix when `COOKIE_SECURE=true`; configure HTTPS and allowed origins explicitly before deployment. These protections apply to future mutating endpoints too. Local HTTP uses an unprefixed cookie.

A PostgreSQL-backed 15-minute rate limit is enforced independently per client IP and normalized email on login and registration; transaction locks coordinate workers. All attempts count, including successful ones (five per email, thirty per IP). This is deliberately conservative and can temporarily prevent legitimate access, especially on shared IPs. It is not a complete public anti-abuse solution: before deployment design trusted proxy/IP handling, distributed attack defenses, monitoring, retention and cleanup, session idle expiry, email verification, recovery, and deployment hardening. Client IP is taken from the direct connection, never from untrusted forwarding headers. Argon2 consumes CPU and memory, so capacity must be assessed under load.

No FACEIT integration is implemented. A future tracked profile should be linked to an account through a separate association and must not imply ownership.
