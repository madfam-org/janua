# Silent SSO: where the browser session comes from

**Status**: B1, B2, B6, R1, J9 and J6 landed in Janua; B3/B4 are operator steps;
B5 lives in nauta and B7 in crea-map. **R1 chose option 3 of the security note
below** — a separate HttpOnly estate cookie, `janua_sso`; see "R1 — the
`janua_sso` estate cookie". **J9 makes that cookie outrank a stale
`janua_access_token` at `/authorize`**; see "J9 — the estate session outranks a
stale hosted-login cookie", which is the section to read first if silent SSO ever
authenticates the wrong person again. **J6 reaches the hosts that cookie can
never be relayed to** — the client's own `creatumundo.mx` zone — by moving where
the emailed link lands; see "J6 — the hosted hop".
**Related**: `ADR-001_AUTH_FLOW.md`, ADR `2026-05-04-selva-unified-sso` (Phase 1
= `prompt=none`, delivered earlier), `docs/guides/SSO_INTEGRATION_GUIDE.md`.

## The problem this closes

Janua has implemented OIDC `prompt=none` at `/authorize` since Phase 1 of the
unified-SSO ADR. It resolves the person from the `janua_access_token` cookie.

That cookie had exactly two writers, both on the hosted password form
(`login_form` and `login_form_mfa` in `apps/api/app/routers/v1/auth.py`, via
`_set_session_cookies`). But the products that actually needed silent SSO — the
MAP and the nauta ERP portal (`map.creatumundo.mx` / `erp.creatumundo.mx`
today; `crea-map.madfam.io` / `crea-erp.madfam.io` when this was written, now
301 aliases) — sign people in by **magic link**, and their users have no password at all. So no
browser ever held the cookie `/authorize` reads, and `prompt=none` could only
ever answer `login_required`.

Nothing logged an error. The silent path simply never succeeded.

## Order of operations

Each step is useless without the ones before it. This is the order things must
land, not a menu.

| Step | What | Where | State |
|---|---|---|---|
| **B1** | Both magic-link paths set the issuer session cookies | Janua `routers/v1/auth.py` | landed |
| **B2** | `/authorize` accepts every audience Janua mints | Janua `routers/v1/oauth_provider.py` | landed |
| **B6** | First-party clients are pre-consented | Janua `routers/v1/oauth_provider.py` | landed |
| **B3** | `COOKIE_DOMAIN=.madfam.io` so the cookie is readable estate-wide | `k8s/base/deployments/janua-api.yaml` | landed |
| **B4** | `madfam:silent_auth` on the `crea-map` and nauta OIDC clients | operator (admin API / data) | landed (client rows; not verifiable from this repo) |
| **B5** | nauta sends `prompt=none` and falls back to interactive login | nauta `sso-launch.ts`, `auth.ts` | landed |
| **B7** | The MAP links to `crea-erp` (optionally sends `prompt`) | crea-map | landed |
| **R1** | `janua_sso`: an HttpOnly estate cookie the SDK can relay to the browser | Janua `auth/sso_cookie.py`, `routers/v1/auth.py`, `routers/v1/oauth_provider.py` | landed |
| **R1s** | `@madfam/janua-next` relays `janua_sso` (and its deletion) | madfam-js `@madfam/janua-next@0.2.0` | landed |
| **R1n** | nauta adds the same relay | nauta | landed |
| **J9** | `janua_sso` outranks `janua_access_token` at `/authorize` | Janua `routers/v1/oauth_provider.py` | landed |
| **J6** | Magic links land on Janua first for hosts outside `COOKIE_DOMAIN`; the callback GET stops spending the token | Janua `auth/hosted_hop.py`, `services/email_service.py`, `routers/v1/auth.py` | landed |

**B2 is a silent prerequisite of B1.** A magic-link session carries the audience
of the product the link forwards to (`_session_audience_for_redirect`) —
`crea-map`, `nauta-portal` — not the platform `JWT_AUDIENCE`. Before B2,
`/authorize` validated against the platform audience only, so the cookie B1
writes would have been rejected with nothing visibly wrong in the happy path.

### B1 — who writes the cookie

- `GET /api/v1/auth/magic-link/callback`: the browser is on the issuer for this
  hop, which is the one moment Janua can set its own cookie on a magic-link
  login. The redirect still goes to `<destination>?token=<access_token>`; the
  contract products read is unchanged.
- `POST /api/v1/auth/magic-link/verify`: the `SignInResponse` body is unchanged
  — `@madfam/janua-next` and nauta's integration package depend on it — with the
  cookies added on the injected `Response`. When a **server** calls this (which
  is how both products call it today), Node keeps the `Set-Cookie` and drops it;
  the cookie only matters when a browser posts here directly.

An MFA interrupt mints no session and therefore sets no cookie. A destination
the allowlist rejects at redemption returns the HTML page with no cookie.

### B2 — audience tolerance

`get_user_from_cookie_or_header` now verifies through
`_verify_own_access_token`, which retries once with audience verification off
and still requires a usable `aud` claim. Signature, issuer, expiry and token
type stay enforced on both passes. This is the tolerance
`AuthService.verify_token` already had; Janua is the **issuer** reading a token
it minted itself, and audience restriction is a rule for *resource servers*
deciding which tokens to accept.

`JWTManager.verify_token` gained an additive `verify_audience` flag, default
`True`, so every other caller keeps strict validation.

### B6 — pre-consent

Consent exists so a person can refuse a **third party** access to their account.
It communicates nothing when the client is MADFAM itself, and on the silent path
it cannot even be asked: `prompt=none` renders no screen, so a missing consent
row became `consent_required` for a client nobody would have refused.

The predicate is `_is_silent_auth_allowed` itself, not a looser copy — exactly
the clients trusted to authenticate silently are treated as pre-consented, so
widening one can never quietly widen the other. Third-party clients still see
the consent screen.

Consequence: `consent_required` is now unreachable on the silent path by
construction. The branch is kept as defense in depth in case the two predicates
ever diverge.

## Security note: the cookie is readable by JavaScript

`janua_access_token` is set with `httponly=False` on purpose — the browser SDK
reads it to make API calls. `janua_refresh_token` is HttpOnly.

B1 does not change that, and **does not change `COOKIE_DOMAIN`**, which defaults
to `None` (`apps/api/app/config.py`): the cookie is scoped to the issuer host
only. That default is deliberate here.

**B3 must be ratified before it is deployed.** Setting `COOKIE_DOMAIN=.madfam.io`
extends a JS-readable bearer token to every host in the estate; an XSS anywhere
under `madfam.io` would then be able to read a live Janua access token. Options
worth weighing before flipping it:

1. Set `COOKIE_DOMAIN=.madfam.io` as is, accepting the widened blast radius.
2. Mark the wide-domain access cookie HttpOnly and let the browser SDK obtain
   tokens another way (this would break SDK consumers that read the cookie
   directly, so it needs its own migration).
3. Issue a **separate** HttpOnly SSO cookie for the wide domain and leave
   `janua_access_token` host-scoped as it is today. `/authorize` would read the
   SSO cookie; the SDK keeps reading the host-scoped one. This keeps the
   JS-readable token narrow and is the option this note recommends — but it is a
   design decision, not a mechanical change, and it was deliberately not made
   unilaterally.

**Option 3 was ratified and is what shipped** — the cookie is `janua_sso`; see
"R1 — the `janua_sso` estate cookie" below. `janua_access_token` is unchanged.

Silent SSO does **not** work across hosts until one of these is chosen. B1/B2/B6
make the mechanism correct; B3 is what makes it reach.

## R1 — the `janua_sso` estate cookie

### What B1 could not reach

B1 made all four session-establishing paths call `_set_session_cookies`. That is
correct, and it is not enough. The MAP and the nauta ERP portal exchange the
magic link **server-to-server**: their Next process calls
`POST /api/v1/auth/magic-link/verify` and reads the JSON. Node keeps the
`Set-Cookie` headers on that fetch response and drops them. Nothing ever reaches
a browser, so a person signed into the MAP was still asked for a second email at
`crea-erp.madfam.io`.

`@madfam/janua-next@0.2.0` closes the gap by relaying, **byte for byte**, any
`Set-Cookie` line whose cookie is named exactly `janua_sso` and whose `Domain`
covers the app's public host, appending it to the 303 it returns to the browser
after the verify exchange. It relays the `Max-Age=0` deletion from
`POST /api/v1/auth/logout` the same way. nauta adds the same relay (R1n). R1 is
the Janua half: minting what the relay carries.

> **Current package contract: `@madfam/janua-next@0.3.0`.** 0.2.0 is where the
> relay above landed and is still the correct attribution for it. 0.3.0 adds the
> **hop landing** J6 requires: a POST that accepts an `?token=<access_token>`
> forwarded by janua's interstitial, rather than only the one-time magic-link
> token 0.2.0 expects. This is not cosmetic — a product still on 0.2.0 answers
> a hop-forwarded link with "El enlace ya no es válido", which is exactly what
> `map.creatumundo.mx` did on 2026-09-07 at 03:07 CDMX before crea-map #347/#350
> shipped. A brand host therefore needs 0.3.0 **and** a route to land it on.

### Why a separate cookie (option 3, ratified)

The security note above listed three ways to make silent SSO reach across hosts
and recommended the third. R1 implements it. `janua_access_token` stays exactly
as it is — host-scoped by default, JS-readable because the browser SDK reads it
— and the estate-wide cookie is a new, HttpOnly one that no script can read and
that is useless as a bearer credential. Widening the access cookie (option 1)
would have put a live bearer token within reach of an XSS on any host under
`madfam.io`; option 2 would have broken every SDK consumer that reads the cookie.

### The cookie

```
janua_sso=<signed reference>; Path=/; Domain=.madfam.io; HttpOnly; Secure; SameSite=Lax; Max-Age=604800
```

- **HttpOnly** — it is readable on every host in the estate, so no script
  anywhere in the estate may read it.
- **Secure**, **SameSite=Lax** — Lax because every silent hop arrives as a
  top-level GET navigation to `/authorize`, which Lax sends.
- **`Domain`** is `settings.COOKIE_DOMAIN` when set, host-only otherwise. **The
  relay refuses a host-only cookie**, so estate SSO requires
  `COOKIE_DOMAIN=.madfam.io` (B3 — already set in prod). Without it Janua still
  emits the cookie and it still works on the issuer host; it just does not
  travel, and the estate silently keeps two sessions.
- **`Max-Age`** is the refresh-session lifetime
  (`JWT_REFRESH_TOKEN_EXPIRE_DAYS`), because the row it references expires then.

### Value, and why it is revocable without a migration

The value is a signed JWT carrying `sub` and `sid` — the id of the `sessions`
row `AuthService.create_session` already writes — with `type: "sso_session"`.

That type is the security boundary. Every bearer path in Janua verifies
`token_type="access"` (`get_current_user`, and `_verify_own_access_token` on the
`/authorize` seam), so the cookie's value presented as `Authorization: Bearer …`
fails verification everywhere. It is a **session reference**, not a credential.

Resolution re-reads the `sessions` row on **every** use and refuses it when the
row is revoked (`revoked = True`, which `/signout` and `invalidate_user_sessions`
set), deactivated (`is_active = False`, which `revoke_token_family` sets on
refresh-token theft detection), past `expires_at`, or owned by a non-active user.
That is what makes the cookie revocable — and it means every revocation path
Janua already has revokes this cookie too, for free. That includes the ones that
are not "logout": the concurrent-session-limit eviction in
`AuthService.create_session` sets `revoked = True` on the oldest row, so a session
pushed out by the limit stops authenticating its cookie as well. **No new table, no new
column, no alembic revision**, which matters while production is frozen behind
the migration-drift guard.

Refresh rotation mutates `refresh_token_jti` on that same row and leaves
`session.id` alone, so a rotation does not invalidate the cookie and nothing has
to be re-issued on the `/authorize` response.

### Where it is accepted — and where it is not

`janua_sso` is read in exactly one function,
`get_user_from_cookie_or_header` (`routers/v1/oauth_provider.py`), whose only
callers are `GET /authorize` and its consent continuation `POST /consent`. It is
**not** accepted at `/api/v1/auth/me` or any other API — those use
`get_current_user`, which never reads it, and the token-type gate would refuse it
anyway. A unit test pins both the reader count and the caller set, so widening
the acceptance scope has to be a deliberate edit rather than a side effect.

`POST /consent` accepts it for the same reason — it is the screen the interactive
`/authorize` renders — and adding a cookie there widens nothing: that endpoint
already requires a CSRF token bound to the person's own id **and** a server-side
`auth_request_id` held in Redis, and `SameSite=Lax` means the cookie is not sent
on a cross-site POST at all. Three independent reasons a `janua_sso` cookie alone
cannot forge a consent grant.

Within `/authorize` the cookie authenticates the person for **both** `prompt=none`
and the interactive flow — a valid estate session skipping the login page is what
SSO means. It resolves *who* the person is and never *whether they may proceed*:
email verification, MFA and third-party consent are enforced exactly as before.

## J9 — the estate session outranks a stale hosted-login cookie

### The failure (production, 2026-09-07)

A person signed into the MAP by magic link. The MAP's verify exchange is
server-to-server, so the only browser-visible trace of that login was the relayed
`janua_sso` on `.madfam.io`. The ERP then ran its silent hop
(`/oauth/authorize?…&prompt=none`) and Janua issued a code for **a different
person**: the same browser still held a `janua_access_token` from an unrelated
hosted login on `auth.madfam.io` — an operator's `enclii login` 43 minutes
earlier — and resolution read that cookie **before** `janua_sso`. nauta logged
`portal.silent_sso not_a_member` twice. Membership data was correct; the identity
was not.

This defeats R1 outright. Any prior hosted login on `auth.madfam.io` in the same
browser silently changed who the ERP saw, with nothing wrong anywhere in the
happy path.

### Why precedence is the fix, and not cookie hygiene

The obvious-looking repairs do not close it:

- **crea-map cannot clear the stale cookie.** `janua_access_token` is scoped to
  the issuer host; a subdomain app cannot delete a cookie on `auth.madfam.io`.
- **Re-setting `janua_access_token` whenever `janua_sso` is set does not help
  either.** The login that establishes the estate session is a server-to-server
  verify call, and the SDK relays only the cookie *named* `janua_sso` — a hosted
  cookie minted on that response is dropped by Node like every other header, so
  it never reaches the browser to overwrite anything.
- **`/signout` does not clear it.** Only the OIDC `end_session` endpoint clears
  `janua_access_token`; a person who signs out through the SDK's logout route
  keeps it.

Ordering at the one seam that reads both cookies is the only fix that does not
depend on a cookie one origin cannot reach.

### The rule

`get_user_from_cookie_or_header` (`routers/v1/oauth_provider.py`), whose only
callers are `GET /authorize` and `POST /consent`, resolves in this order:

1. **`Authorization: Bearer`** — unchanged, still first. An API client attaching
   a token is naming the identity it means to act as, explicitly, per request;
   nothing ambient can be staler than that.
2. **`janua_sso`** — the estate session. Preferred because it is by construction
   the most recent estate login (the only way it reaches a browser is a relay
   from a login that just happened) and because it is the only one of the three
   whose validity is re-read from `sessions` on every use, hence revocable — a
   `janua_access_token` stays valid until its own `exp` no matter what happens to
   its session.
3. **`janua_access_token`** — the hosted-login session, used when no valid estate
   session exists. The hosted password form is unaffected.

**Both valid, different people → the newer session wins.** The estate row's
`created_at` comes back with resolution; the hosted cookie's row is looked up by
`sessions.access_token_jti == jti`. That column is rotated by
`AuthService.refresh_tokens`, so the row may legitimately not be found — an
undatable hosted session cannot be shown to be newer, so the estate session keeps
precedence, as it does on an exact tie. The disagreement is logged at `info` with
both user ids **redacted to an 8-character prefix** and both session start times,
so an operator can see it happened without full ids entering a log line. Same
user in both cookies: no contest, nothing logged.

Recency is read from `created_at`, falling back to `last_activity` only when a
row carries no `created_at` — deliberately not the other way round, since a
background token refresh on an old session must not be able to make it look newer
than a login that just happened.

### What J9 does not change

Every security property of R1 stands. `janua_sso` is still resolved in exactly
one function with exactly two callers; the `sso_session` token type still makes
its value useless as a bearer credential everywhere; a forged cookie still cannot
revoke someone else's session, because the signature is verified before anything
is revoked; and precedence is still only about *who* the person is — email
verification, MFA and third-party consent are enforced downstream exactly as
before, which is why a revoked estate session falls back to the hosted cookie
rather than short-circuiting the request.

**No migration.** J9 adds no table, no column and no alembic revision; it reads
`sessions.created_at`, which has always been there.

### Logout

Deleting the cookie is the cosmetic half; a copy taken before logout must stop
working. Both `POST /api/v1/auth/logout` (and `/signout`) and the OIDC
`end_session` endpoint therefore **revoke the `sessions` row** the cookie
references and **then** delete the cookie with the same `Domain` and `Path` it was
set with — a deletion differing on either attribute addresses a different cookie
and leaves the live one in place. The cookie's signature is verified before
anything is revoked, so a forged value cannot end someone else's session.

### Which paths emit it, and which deliberately do not

The cookie is emitted from `_set_session_cookies`, so all four paths that
establish a **browser** session get it: `login_form`, `login_form_mfa`,
`magic_link_callback` and `verify_magic_link` (`routers/v1/auth.py`). The other
session-minting paths were reviewed and deliberately excluded:

| Path | Why not |
|---|---|
| `POST /auth/signin` (`app/auth/router.py`) | JSON API returning `TokenResponse`. Its cookies are the legacy `access_token` / `refresh_token` names, which `/authorize` does not read — it establishes no `/authorize`-visible session today, with or without R1. |
| `POST /mfa/challenge/verify` (`routers/v1/mfa.py`) | JSON API returning tokens in the body; sets **no** cookies at all, not even `janua_access_token`. Nothing to be estate-wide about. |
| Social OAuth callback (`routers/v1/oauth.py`) | Calls `AuthService.create_user_session`, **which does not exist anywhere in the codebase** — that path raises `AttributeError` the moment a social provider is configured. It is masked in production only because the social-provider env vars are unset (`/auth/oauth/providers` returns `[]`). Fixing it is out of R1's scope and tracked separately; when it is fixed it should emit `janua_sso` (and the `janua_*` cookie pair) too. |

Each of these becomes a one-line change (`user=` / `session=` on the helper, or
`set_sso_cookie`) if it later becomes a real browser-session door.

### A failed exchange sets nothing

An invalid or expired magic link, a wrong password, an MFA interrupt, or a
destination the allowlist rejects at redemption all emit no `janua_sso` — there
is no session, so there is nothing to reference.

## Operator steps

- **B3**: set `COOKIE_DOMAIN` in Janua's environment — after ratifying the above.
- **B4**: add `madfam:silent_auth` to `allowed_scopes` on the `crea-map` and
  nauta OIDC clients. Their names ("MAP · Crea Tu Mundo") do not match the
  `selva-office*` / `madfam-*` prefixes, so the scope is the only way they
  qualify — for `prompt=none` and, since B6, for pre-consent.
- **R1**: nothing beyond B3. `COOKIE_DOMAIN=.madfam.io` is the single
  prerequisite for `janua_sso` to travel, and it is already set in production.
  Without it the cookie is emitted host-only, the relay refuses it, and the
  estate keeps two sessions — working, but not shared.
- **No migration.** B1/B2/B6 and R1 add no tables or columns, and promote runs no
  alembic; nothing here waits on a schema change. R1 deliberately reuses the
  existing `sessions` row rather than adding storage, because production is
  frozen behind the migration-drift guard.

## Brand hosts: the three allowlists a new host must enter

The MAP and the ERP portal will also serve on the client's own zone —
`map.creatumundo.mx` and `erp.creatumundo.mx`. Three janua allowlists gate a
host like that, and each fails *silently* in a different way, so all three move
together (J7, 2026-09-06):

| List | Where | What breaks without the host |
|---|---|---|
| `CORS_ORIGINS` | `k8s/base/deployments/janua-api.yaml` (static env of `janua-api`) | **No magic link can be issued for the host.** `app/core/url_security.py` derives `get_allowed_redirect_hosts()` from `settings.cors_origins_list`, so the request 400s with "add it to CORS_ORIGINS before requesting links for it". Note the dynamic CORS middleware (`app/middleware/dynamic_cors.py`) derives origins from OAuth clients' `redirect_uris` — a **separate** list that does *not* feed `url_security`. |
| `CTM_HOSTS` | `app/services/email_branding.py` | Sign-in email silently reverts to MADFAM branding. `_host_matches` is a dot-boundary suffix match, so the single entry `creatumundo.mx` covers `map.` and `erp.` (and never `notcreatumundo.mx`). |
| CSP `form-action` | `app/middleware/security_headers.py` | After a hosted-login POST, browsers that apply `form-action` to the whole post-submit redirect chain block the 302 to the brand host — the "Sign In does nothing" bug class. |

These are *prerequisites for the login path*, not for session sharing. The
`janua_sso` estate cookie cannot be relayed onto `creatumundo.mx` hosts at all:
it is scoped by `COOKIE_DOMAIN=.madfam.io` and a cookie cannot cross a
registrable-domain boundary. A brand host therefore establishes its session the
browser-visited way — the `magic_link_callback` path (lane J6) — and not by
reading an estate cookie.

Adding a brand host is a deploy-only change (no migration): edit the three
lists, then the normal staging → prod promote.

## J6 — the hosted hop: SSO on a host outside the cookie domain

R1 gave the estate one browser session. The section above states the limit it
could not pass: `janua_sso` is scoped by `COOKIE_DOMAIN=.madfam.io`, and a
cookie cannot cross a registrable-domain boundary, so on `map.creatumundo.mx`
the relay in `@madfam/janua-next` can never fire. Not "is not configured yet" —
*cannot*: a browser rejects a `.madfam.io` cookie from a `creatumundo.mx` page.
Without the estate cookie the ERP's `prompt=none` answers `login_required`
every time and the person is asked for a second email.

J6 closes that by moving where the emailed link lands.

### The rule: derived per host, not a flag

`app/auth/hosted_hop.py` decides. `should_use_hosted_hop(redirect_url)` returns
true exactly when the destination host is **not** covered by `COOKIE_DOMAIN` —
i.e. exactly when the product could not receive the estate cookie by relay.

`domain_covers_host` is the Python twin of `domainCoversHost` in
`@madfam/janua-next` (`packages/janua-next/src/magic-verify.ts`), deliberately
behaviour-identical. The two halves of the same question must agree: janua uses
it to decide whether to mail a product link, the package uses it to decide
whether the cookie may be relayed. If they disagreed, janua would mail a direct
link for a host whose relay silently refuses — the live brand-host defect.

Consequences worth stating:

- **Nothing that worked at the time changed.** `crea-map.madfam.io` and
  `crea-erp.madfam.io` kept the byte-identical link they had. The hop lights up
  only for hosts that are provably broken.
- **Cutover needed no deploy, and this is how it actually went.** When
  `map.creatumundo.mx` went live on 2026-09-07 its links took the hop with no
  janua deploy; a host that later moved under `madfam.io` would revert the same
  way.
- `hosted_hop: true|false` on `POST /api/v1/auth/magic-link` overrides the rule
  in either direction. It is an escape hatch (a rehearsal host, a future tenant
  zone), never the mechanism — with one exception, Janua's own hosted login
  form, which forces it (see *The hosted login form forces the hop*, below).
- **An unset `COOKIE_DOMAIN` never hops.** The predicate answers "cannot
  receive" for every host when no cookie domain is configured — truthfully,
  since there is then no estate cookie for anyone to relay — but "estate SSO is
  not configured here" is a different fact from "this host is outside the
  estate", and only the second one is what the hop is for. Without the guard,
  every magic link in an unconfigured deployment would move off the product host
  onto janua's callback: the first-contact failure of 2026-08-15. Prod and
  staging both set `COOKIE_DOMAIN=.madfam.io`, so the guard costs the brand
  hosts nothing.

### The hosted login form forces the hop

The derived rule reasons about **product** destinations — a host whose own
`/portal/verify` page redeems the forwarded `?token=`. Janua's **own hosted
login form** (`POST /api/v1/auth/login-form/magic-link`) is the one place where
`hosted_hop=True` is the mechanism rather than an escape hatch, and it sets it
unconditionally (`login_form_magic_link`, `routers/v1/auth.py`).

Its emailed link's destination is always the **rebuilt `/oauth/authorize` URL on
`auth.madfam.io`** — a host *inside* `COOKIE_DOMAIN`, so the derived rule says
"can receive the cookie, no hop needed" and would mail `{authorize_url}&token=…`.
But `/oauth/authorize` never redeems a magic-link token — only
`/magic-link/callback` does — so that link sets no session and `/authorize`
bounces the browser straight back to the login form. Rendered without a
`login_method`, that is the **password** form, and a passwordless magic-link user
has nothing to type: an endless loop. Forcing the hop routes the link through
`/magic-link/callback`, which mints the `janua_sso` cookie on this origin and
then forwards to the authorize URL, which now completes.

This shipped broken in the first hosted-login release and was fixed in #620
(found live 2026-09-17, on the Yantra4D hosted login). The regression guard is a
behavioural one: the router test asserts the `hosted_hop=True` kwarg reaches the
mailer, not merely that the destination is the authorize URL — the earlier test
checked only the destination, which is how the bug shipped green.

### What the hop does not touch (J6 × J8 × J10)

Branding (`resolve_branding`), Spanish register (`default_formality_for`),
subject timestamp (`timezone_for`) and the From line (`email_sender.sender_for`)
are all resolved from `redirect_url` — the **destination** — and the hop changes
only where the link *lands*, never the destination itself. So a hop link to a CTM
host still carries the Crea header, still reads «tu», is still stamped in CDMX
and still comes from `Crea Tu Mundo <hola@creatumundo.mx>` once that domain is
Resend-verified. Only `magic_url` differs.

### The link, and the contract that did not change

A hop link is
`https://auth.madfam.io/api/v1/auth/magic-link/callback?token=…`. The
destination is **not** in the URL — it is read from the `MagicLink` row, and
re-validated against the allowlist at redemption, so the emailed link cannot be
edited into forwarding somewhere else.

The forward is still `<redirect_url>?token=<access_token>`, byte-for-byte the
contract products already implement. Body branding still resolves from the
destination host (`CTM_HOSTS`), so a CTM link keeps the Crea header: the hop
changes the link's host, not whose email it is.

**What the PRODUCT owes, and the way it bites.** The `?token=` forwarded by the
hop is an **access token**, not the one-time magic-link token. A product route
that only knows how to redeem the latter answers a hop link with "the link is no
longer valid" — the user-visible failure observed on `map.creatumundo.mx` at
03:07 CDMX on 2026-09-07. Landing it takes two things on the product side:
`@madfam/janua-next@0.3.0` (0.2.0 has no hop landing) and a `redirect_url`
pointing at a route that completes a session from an access token. crea-map uses
a route dedicated to exactly that, `/api/auth/magic-complete`, distinct from its
one-time-token `/api/auth/magic-verify`.

Janua does not know or care which route that is — it forwards to whatever
`redirect_url` the caller registered — so this is a product contract, recorded
here because janua's hop is what makes it load-bearing.

### The callback is now scanner-proof (a latent bug, fixed here)

`GET /api/v1/auth/magic-link/callback` used to **spend the one-time token on the
GET**: it burned `used_at`, minted a session and redirected. Mail scanners GET
every URL in an email, so a scanner consumed the link and the human's own click
replayed a spent token. This estate has already hit that failure once (nauta
portal, first real ceremony 2026-08-16); it is the reason
`@madfam/janua-next` splits its own magic-link route.

The route now splits the same way, and the split is the whole security property:

- **GET** renders a branded one-button interstitial and **spends nothing**.
  It still *reads* (a dead link says so immediately) but never mutates.
- **POST** — the button's submit — is the **only** place the token is exchanged,
  the session is minted, and `janua_sso` is set first-party.

Do not "simplify" the GET back into a handler that verifies.

Because the hop makes this route the primary path for the brand hosts, the fix
had to land with it: shipping the hop without it would have shipped the
2026-08-16 outage to the client's own domain.

### Test recipe (both directions, both host pairs)

Substitute `HOST_MAP` / `HOST_ERP` for the pair under test. Since 2026-09-07
the CANONICAL pair is `map.creatumundo.mx` / `erp.creatumundo.mx`; the estate
pair `crea-map.madfam.io` / `crea-erp.madfam.io` now answers 301 to it
(Cloudflare redirect rules on the `madfam.io` zone). Both are still worth
testing — they exercise the two SIDES of the hop rule, which is the point of
the recipe: the brand pair must take the hop, the estate pair must not.

**1. The hop fires only where it should** (no mail needed):

```bash
# Brand host → the link must be janua's callback.
curl -sS -X POST https://auth.madfam.io/api/v1/auth/magic-link \
  -H 'content-type: application/json' \
  -d '{"email":"<addr>","redirect_url":"https://map.creatumundo.mx/api/auth/magic-verify"}'
# Estate host → the link must stay on the product.
curl -sS -X POST https://auth.madfam.io/api/v1/auth/magic-link \
  -H 'content-type: application/json' \
  -d '{"email":"<addr>","redirect_url":"https://crea-map.madfam.io/api/auth/magic-verify"}'
```

Both answer `{"message":"Magic link sent to email"}`; the emailed link's host is
the assertion. Read it in the mailbox, not from the response.

**2. The GET spends nothing** (the scanner test, and the one to never skip):

```bash
# GET the emailed link TWICE, then click through. Both GETs must return 200 with
# a button, and the click must still sign in. Before J6 the first GET burned it.
curl -sS -o /dev/null -w '%{http_code}\n' '<emailed link>'
curl -sS -o /dev/null -w '%{http_code}\n' '<emailed link>'
```

**3. MAP → ERP, silent** (browser): sign in at `https://HOST_MAP`, then open
`https://HOST_ERP`. Expect «Tablero de Crea» with no second email and no
`?silent=fallido` in the final URL.

**4. ERP → MAP, silent** (browser): with a fresh profile, sign in at
`https://HOST_ERP` first, then open `https://HOST_MAP`. Expect the MAP to land
signed in rather than showing the magic-link form.

**5. The estate cookie exists** (browser devtools, after step 3 or 4): a
`janua_sso` cookie on `auth.madfam.io`, `HttpOnly`, `Secure`, `SameSite=Lax`.
On the brand hosts it is set by the hop; on the estate hosts by the relay.

**6. Silent auth answers a code, not `login_required`**: with only that cookie,

```bash
curl -sS -o /dev/null -w '%{http_code} %{redirect_url}\n' \
  --cookie 'janua_sso=<value>' \
  'https://auth.madfam.io/api/v1/oauth/authorize?response_type=code&client_id=<client>&redirect_uri=<cb>&scope=openid+profile+email+madfam:silent_auth&audience=<aud>&prompt=none&state=x&nonce=y'
```

A 302 whose `redirect_url` carries `?code=` is the pass; `error=login_required`
is the failure this lane exists to remove.
