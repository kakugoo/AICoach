# Architecture

The browser talks to FastAPI over HTTP. FastAPI owns business logic and database access; the browser never connects directly to PostgreSQL. PostgreSQL runs locally through Compose. Health and readiness are separate: `/health` checks the API process; `/ready` executes a database query and returns 503 if unavailable.

Later, a separate worker can claim durable database jobs and call an isolated parser adapter and versioned analysis module. Match facts, heuristic assessments, and future model interpretations must remain distinguishable. A repeated analysis creates a new versioned run; no FACEIT profile is required for manual demo analysis. These are design intentions, not implemented features.

This development setup binds the database to localhost. Example credentials are local-only. The upload and worker design below is for local use and needs hardening before public deployment.

## Accounts and sessions

Users have normalized unique email addresses and Argon2id password hashes. An opaque 256-bit random session token is held in an HttpOnly, SameSite=Strict cookie; only its SHA-256 digest is stored in PostgreSQL. Sessions expire after seven days; logout deletes the server-side row, and authentication replaces an existing session. Authentication and domain access are separate: `/auth/me` resolves the current user from the session, never from a client-supplied user ID.

Mutating auth endpoints require a configured exact Origin and a custom header; CORS allows credentials only for configured origins. Cookies use Secure and the `__Host-` prefix when `COOKIE_SECURE=true`; configure HTTPS and allowed origins explicitly before deployment. These protections apply to future mutating endpoints too. Local HTTP uses an unprefixed cookie.

A PostgreSQL-backed 15-minute rate limit is enforced independently per client IP and normalized email on login and registration; transaction locks coordinate workers. All attempts count, including successful ones (five per email, thirty per IP). This is deliberately conservative and can temporarily prevent legitimate access, especially on shared IPs. It is not a complete public anti-abuse solution: before deployment design trusted proxy/IP handling, distributed attack defenses, monitoring, retention and cleanup, session idle expiry, email verification, recovery, and deployment hardening. Client IP is taken from the direct connection, never from untrusted forwarding headers. Argon2 consumes CPU and memory, so capacity must be assessed under load.



## FACEIT profiles

The backend alone uses the FACEIT Data API server key as a Bearer token. `GET /players?nickname=...` performs exact nickname lookup, and `GET /players/{player_id}` obtains fresh data before adding or refreshing a profile. No unverified client-supplied profile fields are stored. External response errors and timeouts map to generic safe errors. Local rate limits share the existing PostgreSQL-backed mechanism, applied separately to IP and user for all external FACEIT operations. A missing key disables those operations, but not listing or removing previously tracked profiles. The status reports configuration only, not key validity.

`faceit_profiles` stores global player information, uniquely identified by FACEIT Player ID. `tracked_profiles` stores a unique user/profile pair and the addition time. Users may independently track the same profile. Deleting a tracking relationship never deletes the global record. Updates to a shared profile are visible to all trackers. Steam ID64 is stored only when FACEIT returns a valid 17-digit `steam_id_64`; it is a future matching hint, not proof of ownership or an implemented demo association. CS2 ELO and level come only from `games.cs2` and remain null when missing. A profile URL is built from the validated nickname rather than trusting arbitrary URLs returned by the API. Profile ownership is never asserted.

All endpoints require the existing user session; state-changing requests use the existing Origin and custom-header CSRF checks. FACEIT requests have a timeout and use a fixed host with redirects disabled. Data from the external service is not logged. Before public deployment, review quota, proxy/IP trust, retention and cleanup of orphaned profile records, and abuse protection; current limits are intentionally conservative.

## Demos and worker

The browser streams a raw `.dem` request with a declared Content-Length and the existing session/Origin/CSRF checks. The API reserves the declared length in PostgreSQL under a transaction lock, enforces file and global quotas and available disk space, streams into a randomized `.part` file while hashing, checks the `PBDEMS2` signature, and atomically renames it. No submitted filename is used as a path. Failed or interrupted requests remove temporary files and their reservation. The worker handles stale uploads at startup. Uploads are stored outside the frontend under a private local directory.

`demo_uploads` is owned by a site user. API reads and modifications always filter by owner, even when file checksums match. A single worker holds a session-scoped PostgreSQL advisory lock. It claims queued work with row locks, changes state to processing, invokes a separate parser process with a timeout, then saves the match, players, rounds and event facts in one transaction before setting completed. On startup it requeues jobs left in processing and removes stale result files. A crashed worker can leave its child process alive temporarily; process supervision and stronger isolation are needed before multi-host production deployment. Retry creates a new run by replacing the previous materialized result only when the new transaction succeeds; results carry parser and analysis versions.

The parser reads CS2 headers, documented player info, player-death and round-end events. Its event counters cover the entire recording, including potential warmup and friendly fire. Missing event columns yield unknown values; no score, permanent team assignment, competitive-round boundaries or derived ratings are inferred. Events include ticks and are explicitly marked as raw recording facts, not player mistakes. The parser has not yet been verified on a real CS2 demo in this environment. The API keeps the demo as evidence; parsed event output is bounded and records truncation.
