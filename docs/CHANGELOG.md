# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **Account switching at the OIDC provider** (L1–L3): the identity-provider half of MADFAM-wide account switching. Every platform inherits it through Janua's honored `prompt` values, except one vCTO client's portal (single-account by design). See [architecture/SILENT_SSO_SESSION.md](architecture/SILENT_SSO_SESSION.md) → *Account switching (L1–L3)*.
  - **POST form of the OIDC RP-initiated logout** (`end_session`) endpoint ([#622](https://github.com/madfam-org/janua/pull/622)) — same validation and row-revoke-then-clear-cookie sequence as the existing GET form.
  - **`prompt=login` and `prompt=select_account` honored at `/authorize`** ([#623](https://github.com/madfam-org/janua/pull/623)) — previously only `prompt=none` changed behaviour. `login` forces the login form (never auto-issues a code off a valid cookie); `select_account` renders a chooser over held accounts and degrades to `login` when none is held. MFA and consent gates preserved under every value.
  - **Multi-account estate sessions** ([#625](https://github.com/madfam-org/janua/pull/625)) — a `janua_sessions` companion cookie (signed, `type: "sso_session_set"`, session-id references only, no bearer) remembers the other accounts a browser holds so a second sign-in adds rather than evicts; `switch-session` / `sign-out-one` / `sign-out-all` endpoints re-point or clear the fronted account. Hold-many-front-one.
  - **Per-tab session focus** ([#626](https://github.com/madfam-org/janua/pull/626)) — the `X-Janua-Session` header lets one tab front a different held account than the browser-wide cookie. Non-escalating: honored only when its `sid` is both in the signed held-set and a live session row; otherwise ignored. No migration.
- **Auth Component Overhaul** (`@janua/ui`): Major UI SDK upgrade reaching feature parity with Clerk/Auth0/WorkOS
  - `JanuaThemeProvider` — React context for runtime theming with preset support (`default`, `madfam`, `solarpunk`), dark mode via `next-themes`, and granular color overrides
  - `JanuaAuthProvider` — Config-driven auth UI provider that fetches `JanuaAuthConfig` from API or accepts static config, enabling tenant customization from the Janua dashboard
  - Shared sub-components: `SocialButton` (branded Google/GitHub/Microsoft/Apple/Janua buttons), `AuthCard` (card/modal/page layouts), `AuthDivider`, `PasswordInput` (with strength meter)
  - SSO email domain detection (`SSOEmailDetector`) — email-first flow that checks domain against API and redirects to org IdP
  - Passkey/WebAuthn button (`PasskeyButton`) — auto-hides on unsupported browsers, calls `navigator.credentials.get()`
  - Magic link passwordless login (`MagicLinkForm`) — email input with success state and 60s resend cooldown
  - "Sign in with Janua" button (`JanuaSSOButton`) for MADFAM ecosystem cross-app auth
  - PIN-style MFA digit inputs (6 individual inputs with auto-advance, backspace navigation, paste support, success animation)
  - CSS animations (`janua-fade-in`, `janua-slide-up`, `janua-shake`, `janua-shimmer`, `janua-checkmark`) with `prefers-reduced-motion` support
  - Theme presets system (`packages/ui/src/tokens/presets.ts`) and auth config defaults (`packages/ui/src/config/`)
  - Runtime auth config type system (`JanuaAuthConfig`) covering branding, auth methods, social providers, SSO, MFA, flow settings, and locale strings

### Changed
- **Passkey registration accepts built-in authenticators** (owner decision 2026-10-04). `POST /api/v1/passkeys/register/options` defaulted `authenticatorSelection.authenticatorAttachment` to `cross-platform`, which excluded platform authenticators (Touch ID, Windows Hello, Android) whenever the client sent no preference, as the dashboard does. With no preference in the request the option is now omitted, so platform and roaming authenticators both work. A requested `platform` or `cross-platform` is still honoured; `residentKey: discouraged` and `userVerification: preferred` are unchanged.
- **Readiness is independent of Redis** (owner decision 2026-10-04). `GET /api/v1/health/ready`, the k8s readiness probe, no longer answers 503 when the pod cannot PING Redis. A Redis-wide outage used to take every replica out of the Service within about 30 s, and JWKS and OIDC discovery went down with them. It now answers 200 and reports `"redis"`, `"degraded"`, `"status": "degraded"` and `redis_circuit`. Redis-backed routes still answer 503 + Retry-After on their own. Other checks gate as before, and liveness is unchanged. Alerting must now watch the readiness body; see [runbooks/oauth-shared-state-redis.md](runbooks/oauth-shared-state-redis.md).

### Fixed
- **Readiness reports the database honestly, and does not gate on it** (owner decision 2026-10-04). The `database` readiness check could not fail: `get_database_health()` returns a dict and `HealthChecker` counted any non-empty result as healthy, so `GET /api/v1/health/ready` and `/health/detailed` said `healthy` through every database outage. A dict now counts only when its `healthy` is true. Readiness reports `"database": {"healthy": ..., "status": ...}` and lists it in `"degraded"`, and still answers 200, like Redis: the replicas share one database, and gating would take JWKS, discovery and health down while database-backed routes fail on their own anyway. Each readiness check is now bounded (2 s), so a hanging dependency cannot time out the 5 s probe. The database check also recovers when the database was down at pod startup. Alerting must read the readiness body for both Redis and the database; see [runbooks/oauth-shared-state-redis.md](runbooks/oauth-shared-state-redis.md).
- **A completed password reset signs the user out everywhere** (owner decision 2026-10-04). `POST /auth/password/reset` and the hosted reset form set the new password without revoking any session, so a session stolen before the reset kept refreshing after it. The reset now revokes every session of the user through `AuthService.revoke_sessions` (refresh family, refresh and access JTIs, row marked `password_reset`); unlike password change, no session is kept. The revocation is written first, strictly, and committed together with the new password: while Redis is unavailable the reset answers `503` + `Retry-After` and applies nothing (password, reset link and sessions unchanged), so the same link works once Redis answers. See [runbooks/oauth-shared-state-redis.md](runbooks/oauth-shared-state-redis.md).
- **Revocation actually revokes** (owner decision 2026-10-04). Sign-out, password change (other sessions only), session-limit eviction, `DELETE /sessions/{id}`, `DELETE /sessions` and per-account sign-out now revoke the session's refresh-token family, and `POST /auth/refresh` refuses it with the usual 401. Until now they wrote a revocation-list key `/auth/refresh` never read and set a column it never checked, so a signed-out refresh token kept refreshing. `/auth/refresh` now also refuses any refresh token whose session row is revoked, deactivated or expired, so a revocation holds even when its Redis write was lost. One implementation (`AuthService.revoke_sessions`) serves every path; readers check every key spelling (`app/services/token_revocation.py`).
- **`DELETE /sessions/{id}` revokes the session** (it was a placeholder that revoked nothing). Only the owner or a platform admin may revoke it; anyone else gets 404. The revoked session leaves the sessions list, the account chooser and account switching.
- **`POST /oauth/revoke` implements RFC 7009** (it acknowledged without revoking anything). Client authentication as at the token endpoint; `token_type_hint` honoured but optional; a refresh token revokes its family (the `refresh_token` grant then answers `invalid_grant`); an access token is blacklisted by `jti` until it expires (`/oauth/introspect` reports it inactive, `/oauth/userinfo` answers 401); unknown tokens and other clients' tokens answer 200 and change nothing; 503 when Redis cannot store the revocation. The `refresh_token` grant, introspection and userinfo read the revocation list strictly (503 while Redis is down).
- **Passkeys work on webauthn 3.x.** Registration options passed dicts where the library takes `AuthenticatorSelectionCriteria` and `PublicKeyCredentialDescriptor`, so building them raised `AttributeError`; authentication options had the same bug, and stored credential ids (base64url) were decoded as plain base64. Verification read a `verified` flag the library's result does not have, and a verified passkey sign-in called a method that does not exist. Registration options are now the library's own JSON (`options_to_json`), and passkey sign-in creates its session through `AuthService.create_session`, so it is revocable like any other. J2's strict challenge storage is unchanged.
- **Token revocation checks fail closed when Redis is unavailable** (owner decision 2026-10-04): the revocation list read by `AuthService.verify_token` (`blacklist:<jti>`, used by `POST /auth/refresh`, `GET /auth/session` and the sessions routes) and the refresh-token reuse check in `JWTManager.refresh_token_pair` (`blacklist:refresh:<jti>`) went through the Redis circuit breaker's fallback, whose answer while Redis was unreachable was "not revoked". A logged-out, rotated-away or replayed token was therefore accepted during a Redis outage. They now use strict Redis reads, and an outage answers `503` with `Retry-After` (JSON for API clients, the short page for browsers). With Redis healthy nothing changes. Sign-out, password change and the sessions list keep working during an outage, because they only use the token to find the current session. A blacklist write that Redis did not take is now logged as an error instead of passing silently. See [runbooks/oauth-shared-state-redis.md](runbooks/oauth-shared-state-redis.md).
- **`GET /auth/session` consulted no revocation list**: it called `AuthService.verify_token` without `await`, so the revocation check never ran and the route failed on the coroutine. It now awaits the check.
- **Passkey challenges and social-login state use strict Redis storage**: WebAuthn registration and authentication challenges, and the `oauth_state:*` values for social sign-in and account linking (including the on-behalf link), were written and read through the breaker's fallback. A write that did not reach Redis surfaced later as "challenge expired" or "invalid or expired state". These flows now answer `503` with `Retry-After` up front. Each value is consumed once across replicas, using the count from `DEL`.
- **Account chooser switches accounts again**: `prompt=select_account` rendered each held account as a form-encoded post to the JSON-only `/auth/switch-session`, so a click answered 422 and left the browser on a JSON page. The chooser now posts to `POST /api/v1/auth/switch-session/form`, which applies the same held-set and live-row guards plus an Origin check, then resumes the original authorization request. The chooser also lists each person once, showing their newest live session, instead of once per sign-in.
- **OAuth consent no longer depends on one pod's memory**: consent CSRF tokens, stored authorization requests and authorization codes now use strict Redis operations that never fall back to a default value or to the per-process cache. Previously, a write made while a replica's Redis circuit was open was stored nowhere, so pressing Allow failed with `403 Invalid or expired CSRF token`. A replica whose first Redis PING failed also lost its client for good, while its probes still reported Redis as healthy. Redis being unavailable now answers `503` with `Retry-After`; `403` means the token is really unknown, expired, mismatched or already used. The consent form submits once, and `/ready` plus the readiness probe report this pod's breaker state (`redis_circuit`). See [runbooks/oauth-shared-state-redis.md](runbooks/oauth-shared-state-redis.md).
- **Hosted magic-link login loop** ([#620](https://github.com/madfam-org/janua/pull/620)): the hosted sign-in form (`POST /login-form/magic-link`) emailed a link to `/oauth/authorize?…&token=`, which cannot redeem a one-time magic-link token — so passwordless users were bounced to the password form in an endless loop (found live 2026-09-17). The form now forces the hosted hop, so the link lands on `/magic-link/callback`, which spends the token and mints the session cookie before forwarding to `/authorize`. See [architecture/SILENT_SSO_SESSION.md](architecture/SILENT_SSO_SESSION.md) → *The hosted login form forces the hop*.
- **Production website rollout (2026-06-15):** Documented and remediated git-vs-cluster lag for `janua-website` — Kyverno PolicyException, ARC `sync-prod-gitops`, Enclii GHCR rotate. See [runbooks/incidents/2026-06-15-janua-website-prod-rollout.md](runbooks/incidents/2026-06-15-janua-website-prod-rollout.md).
- **Public marketing site (`janua.dev`):** Tailwind v4 CSS compilation + shared `(marketing)` nav/footer ([#419](https://github.com/madfam-org/janua/pull/419)).
- **Website Phase 2 UX:** Sora + DM Sans typography, brand gradient tokens, local legal pages, branded 404, footer/nav polish.
- **Website Phase 3 UX:** Honest blog page, careers copy, Enclii deploy wired in nav/footer, e2e footer/legal tests refreshed.
- **TypeScript strict mode** (`@janua/ui@0.1.4`): Resolved 17 strict mode errors across 15 source files that caused consumer build failures when `tsc` evaluated uncompiled `.tsx` sources
  - Added explicit `return undefined` in `useEffect` hooks with conditional early returns (email-verification, magic-link-form, mfa-challenge, phone-verification)
  - Added nullish fallbacks for array indexing (`split()[n]`) in audit-log, user-button, sso-email-detector, bulk-invite-upload
  - Added guards for `Record<string, T>` dynamic lookups in invitation-list, sso-provider-list
  - Added `if` guard for possibly-undefined array element mutation in saml-config-form
  - Removed unused `cn` imports from sign-in and sign-up
  - Removed unused `_code` variable from error-messages, prefixed unused destructured `organizationId` in sso-test-connection

### Changed
- **SignIn** component: replaced inline SVGs with `SocialButton` components, native checkbox with Radix `Checkbox`, added layout/SSO/passkey/magicLink/MFA props (all optional, backward compatible)
- **SignUp** component: replaced `alert()` with inline email verification success state, added layout/terms/privacy props, Radix `Checkbox` for terms
- **MFAChallenge** component: single text input replaced with 6 PIN-style digit inputs, added success checkmark animation, lucide icons replace inline SVGs
- **UserButton** component: inline SVGs replaced with lucide icons, added `activeOrganization` prop, dropdown open/close animations

- Initial package structure for PyPI distribution
- Comprehensive CLI interface with `janua` command
- Middleware stack for easy FastAPI integration
- Complete package documentation and examples
- MFA challenge verify endpoint (`POST /mfa/challenge/verify`) for completing MFA during sign-in

### Security
- **Browser-based auth audit** (2026-03-05): Comprehensive Playwright-driven audit of 12 surfaces across 8 domains — found 2 critical (tokens in URL on Enclii callback, missing headers on Tezca/Forgesight), 4 high (broken auth flows on Dhanam/Forgesight, logout 500, Enclii shell leak), 5 medium severity issues. Full report: `docs/internal/browser-audit-report.md`
- **CSP Swagger UI fix**: Added `cdn.jsdelivr.net` to `script-src` and `style-src` in security headers middleware so `/docs` endpoint renders correctly
- **CSP dynamic host**: Security headers middleware now accepts `api_host` parameter for environment-aware `connect-src` directives instead of hardcoded values
- **MFA before token issuance**: Sign-in now requires MFA verification before issuing session tokens for MFA-enabled users
- **Session invalidation on password change**: All active sessions (except current) are revoked when a user changes their password
- **Security headers for website and docs**: Full CSP, HSTS, Referrer-Policy, Permissions-Policy, X-Frame-Options, X-Content-Type-Options for all public-facing Next.js apps
- **Admin CSP hardened**: Removed `unsafe-eval` from production CSP in admin panel (kept for dev HMR only)
- **Admin next.config.js headers**: Added defense-in-depth security headers alongside middleware headers
- **CI security gates**: Removed `continue-on-error: true` from security-critical CI steps (Bandit, Safety, pip-audit, pnpm audit, Snyk, Trivy) so vulnerabilities block PRs
- **Explicit bcrypt rounds**: Wired `settings.BCRYPT_ROUNDS` into `pwd_context` for auditability
- **RS256 production guard**: RS256→HS256 silent fallback now raises `ValueError` in production; dev-only fallback logs a warning
- **Email verification grace period**: Reduced default from 24 hours to 1 hour to limit unverified email abuse window

### Fixed
- `reset_password` endpoint used non-existent `AuthService.validate_password()` — corrected to `validate_password_strength()`
- `X-XSS-Protection` header updated from deprecated `1; mode=block` to `0` across admin middleware and docs config (CSP replaces the legacy filter)
- Quarantine config test `test_default_settings` now disables `.env` file loading to test true defaults

## [0.1.0] - 2025-01-19

### Added
- Initial release of Janua authentication platform
- Core authentication services (AuthService, JWTService, CacheService)
- User and organization management models
- Multi-tenancy support with organization-based access
- JWT token authentication with refresh token support
- Password hashing with bcrypt
- Redis caching integration
- Database models with SQLAlchemy async support
- Rate limiting middleware
- Security headers middleware
- CORS middleware with configurable origins
- Audit logging system
- Comprehensive exception handling
- FastAPI integration utilities
- Settings management with Pydantic
- Multi-factor authentication (MFA) support
- WebAuthn/Passkey authentication
- OAuth provider integration
- SAML SSO support
- Session management
- User status and role management
- Email verification system
- Password reset functionality
- Comprehensive test suite with 95%+ coverage
- API documentation with OpenAPI/Swagger
- Development tooling (Black, Ruff, MyPy, Pytest)

### Security
- Secure password hashing with configurable rounds
- JWT signing with RS256/HS256 algorithms
- Rate limiting to prevent abuse
- Security headers for XSS/CSRF protection
- Input validation and sanitization
- Audit logging for security events
- Session security with proper expiration
- CORS protection with origin validation

### Performance
- Async/await support throughout
- Redis caching for session and user data
- Database connection pooling
- Optimized database queries
- Background task processing
- Response compression middleware

### Developer Experience
- Comprehensive CLI tools for management
- Easy FastAPI integration
- Extensive documentation
- Code examples and tutorials
- Type hints throughout
- Developer-friendly error messages
- Hot reload support in development
- Testing utilities and fixtures

### Enterprise Features
- Multi-tenancy with organization isolation
- Role-based access control (RBAC)
- SAML SSO integration
- OAuth provider support
- Audit logging and compliance
- Admin user management
- Bulk user operations
- Organization management
- Custom authentication flows

## Package Distribution Features

### Added in Package Release
- **PyPI Distribution**: Available via `pip install janua`
- **CLI Interface**: Complete command-line tools for deployment and management
- **Middleware Stack**: Pre-configured FastAPI middleware for easy integration
- **Optional Dependencies**: Modular installation with `janua[email]`, `janua[sso]`, `janua[dev]`
- **Entry Points**: Package scripts and FastAPI middleware entry points
- **Development Tools**: Integrated linting, formatting, and testing tools
- **Docker Support**: Container-ready deployment configuration
- **Production Ready**: Environment configuration and deployment guides

### Installation
```bash
pip install janua
```

### Quick Start
```python
from janua import create_app
app = create_app(title="My App")
```

### CLI Usage
```bash
janua server --host 0.0.0.0 --port 8000
janua migrate
janua create-user --email admin@example.com --admin
```

---

## Development Notes

### Version Numbering
- Major version (X.y.z): Breaking changes
- Minor version (x.Y.z): New features, backwards compatible
- Patch version (x.y.Z): Bug fixes, backwards compatible

### Release Process
1. Update version in `app/__init__.py`
2. Update CHANGELOG.md with new features and fixes
3. Create git tag with version number
4. Build and publish to PyPI
5. Create GitHub release with changelog

### Dependencies
- Python 3.9+ required
- FastAPI for web framework
- SQLAlchemy for database ORM
- Pydantic for data validation
- Redis for caching
- PostgreSQL for primary database
- See `pyproject.toml` for complete dependency list

### Support
- Documentation: https://docs.janua.dev
- Issues: https://github.com/madfam-org/janua/issues
- Community: https://discord.gg/janua
- Security: security@janua.dev