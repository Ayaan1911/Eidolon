# Eidolon threat model

Scope: the current React/FastAPI application, its decoy endpoints and its configured hosted deployment. Reviewed November 17, 2026. This describes code behavior and deployment assumptions; it is not a penetration-test certificate. Historical implementation notes are in [the learning log](../learning/eidolon-notes.md).

## Assets and actors

Protect admin authority, database credentials, signing secrets, notification topics, stored trap/visitor records, uploaded photos, email queries and result integrity. Keep a public request from exhausting resources or silently producing a misleading clean result.

Actors include an anonymous Mirror user, a single trusted admin, a decoy visitor (benign or hostile), a caller crafting abusive requests and the operators of infrastructure/upstream services. A public repository owner can intentionally supply misleading or expensive content. There is no multi-user account ownership or tenant isolation model.

## Trust boundaries and controls

| Boundary / threat | Implemented control | Assumption or remaining exposure |
|---|---|---|
| Browser → admin API: unauthorized reads or mutation | Passphrase login, rate limits, signed 24-hour bearer token, admin dependencies on alert/mint/create/delete routes; signatures checked with constant-time comparison. | One shared admin credential; no MFA. Token in localStorage is readable by same-origin script. A stolen token works until expiry or global secret rotation. |
| Browser → exposure API: malicious uploads and expensive queries | Input schemas; body caps/timeouts before multipart parsing; bounded photo reads and worker-thread parsing; per-IP limits. | Limits are per process. Ingress must bound slow connections/headers. Pillow and other parser dependencies still need maintenance. |
| Backend → GitHub: hostile source text or excessive download | Fixed GitHub origins, repository/file/byte/time/concurrency limits, counted skips, bounded regexes and line lengths, masked findings. | Six patterns and file filters miss some secrets and can raise false positives. Private repos/history are outside scope. Coverage warnings must be retained in the UI. |
| Browser → Pwned Passwords | Browser computes SHA-1, sends only five hex characters with padded responses, compares suffixes locally. No password route through Eidolon's backend. | The provider sees a prefix bucket and connection metadata. Compromised browser code/extensions can read input. No match is not a password-strength guarantee. |
| Backend → email provider | HTTPS, encoded email, generic failure text, suppressed HTTP client request logs. | XposedOrNot receives the full email. The application cannot guarantee the provider's collection or retention policy. |
| Public visitor → trap page/form | Known trap IDs only; rate limits; bounded/sanitized fields; stored hit before background work. Password contents are not submitted by the provided decoy form. | Username/email and full IP are retained. Automated previews can generate hits. An attacker can intentionally create noise or submit false metadata. |
| Public visitor → decoy-key verifier | HMAC-signed nonce/finding context; uniform `401` response for valid and invalid keys; rate limits; background enrichment/push. | No per-key expiry or revocation and no persistent key-event log. Global signing-secret rotation invalidates all keys. Response timing is not a formal indistinguishability guarantee. |
| Ingress → client-IP decision | Render validates its overwritten Cloudflare header; other hosts use configured rightmost trusted hops; invalid input falls back to peer. Uvicorn proxy rewriting disabled. | A header is trustworthy only through the intended ingress. Direct origin access, incorrect hop counts, VPNs and shared networks undermine attribution and rate-limit accuracy. |
| Backend → Postgres | Shared validated configuration, remote SSL required, Alembic schema ownership, parameterized ORM/SQL, atomic hit increments and a unique non-NULL finding index. | TLS `require` encrypts but is weaker than verified certificate/hostname modes. A database credential compromise exposes stored visitor records. Least privilege and provider access controls are operator responsibilities. |
| Backend → ipwho.is / ntfy | HTTPS, bounded request fields, sanitized titles/context, background work, five-minute per-trap notification suppression. | External providers receive visitor information. Topic knowledge permits reading/publishing in the current ntfy integration. No durable queue, retries or delivery guarantee. |
| Browser → rendered content | React text escaping; bounded fields; production CSP, framing restrictions, nosniff/referrer/permission headers; frontend API-origin build guard. | CSP still permits inline styles and selected Google Fonts resources. It reduces script injection impact but does not prove XSS absence. Headers are deployment-dependent. |
| Application → logs | Production JSON, validated request IDs, visitor-IP masking, secret/bearer/URL redaction; HTTP client loggers suppressed. | Application controls do not cover hosting, database, upstream or browser logs. Do not enable verbose request logging containing sensitive URLs or bodies. |
| Developer → destructive integration tests | Separate `EIDOLON_TEST_DATABASE_URL`, loopback host and dedicated database-name allowlist, no URL query overrides. App `DATABASE_URL` alone does not enable the suite. | Names and loopback do not prove disposability; never forward a production database onto the local test port. Neon rehearsal uses a separately pinned branch endpoint. |

## Data lifecycle

Email/photo/repository findings are held in the current browser session's React memory. The app does not persist the photo or Mirror dossier in Postgres; multipart processing can spool temporary files. Breach metadata and operational counters are held in server memory.

Traps retain their name, source/context and optional finding identifier. Alert records include timestamp, IP, rough geography/network details, browser/device, referrer and any typed username/email. Decoy forms send password presence/length, not the password. Treat these records as personal information and deploy only within an authorized, documented scope.

Old alerts are pruned at startup using `RETENTION_DAYS` (default 90), at most 5,000 per startup; this is not a strict daily deletion guarantee. Traps are not automatically pruned. Admin deletion of a trap also deletes its linked alerts. Provider storage and checkpoint copies have separate retention; deleting an app row does not remove those copies.

Signed admin sessions last 24 hours. Logout removes localStorage, not an already-copied token. Rotating `ADMIN_KEY` invalidates all admin sessions. Rotating `HONEYTOKEN_SECRET` invalidates all admin sessions and existing decoy keys. Tokens are signed, not encrypted; finding context carried inside a decoy key is not confidential.

## Deployment assumptions

- Keep `EIDOLON_ENV=dev` out of production. Startup rejects missing/weak secrets, invalid canonical URL configuration and a missing or unencrypted remote database URL outside development.
- Store secrets in the hosting secret manager and keep them out of source, screenshots and chat. Limit the GitHub token to required reads. Set `PUBLIC_BASE_URL` to the canonical HTTPS origin instead of deriving links from a caller's Host header.
- Configure exact allowed frontend origins. CORS does not stop non-browser callers and is not an authorization check.
- Use the repository's migration-before-start command, `--no-proxy-headers` and `/ready` health check. A successful readiness probe verifies database/schema availability, not upstream services or push delivery.
- Preserve and test a recovery copy before schema changes. Migration `0002` refuses duplicate finding associations; investigate them explicitly without discarding deployed URLs or history. Follow the [recovery runbook](../operations/database-recovery.md), not a production downgrade or `alembic stamp` shortcut.
- For multiple workers/replicas, design shared rate limits, durable jobs and notification suppression before assuming the current per-process limits are global. Free-host cold starts and provider quotas remain availability limits.

## Outside the current guarantees

Eidolon does not establish who a person is, whether a visit was hostile, whether an account is uncompromised, or whether a repository is free of secrets. `Contained` can label an informational partial-scan finding; it is not proof of remediation. Real leaked credentials require owner-led revocation and rotation before considering deception.

No continuous scheduled monitoring, complete Git history scan, automatic repository edits, strong tenant separation, per-session revocation, authenticated ntfy integration, durable notification retry queue or independent off-site backup is implemented. A compromised admin browser, hosting account, dependency, signing secret or database is outside the protection of request-level controls.

## Verification and open work

CI covers input limits, auth gating, signature behavior, scan truncation/regex safety, trusted-proxy decisions, security headers, migrations and frontend result handling. PostgreSQL CI uses a throwaway container; migration rehearsal on a Neon child branch preserved row fingerprints and deployed URLs through up/down/up. See the runbook for exact rehearsal scope.

Operator-reported live checks on November 16–17, 2026 covered security headers, disabled docs, readiness, IP resolution, unauthorized alert rejection, admin refresh/logout, oversized upload rejection and partial-scan warnings. These checks are a dated observation, not continuous assurance.

Remaining release verification includes current end-to-end notification delivery and the full mobile/keyboard/browser walkthrough. Recovery does not yet demonstrate an independent dump/restore, recovery after provider-account loss, or an automated backup schedule. Record any future verification with its environment and scope; do not treat older learning-log claims as current evidence.
