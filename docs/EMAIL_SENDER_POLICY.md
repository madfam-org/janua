# Who our email comes from

**2026-08-14.** A policy that grew to four phases. Phase 1 is in force for every
engagement by default; Phases 2-4 begin per-client, as MADFAM takes over that
client's web presence and, eventually, hands the sending account back to them.

> **Where this stands today (2026-09-07).** All four phases are live, and CTM is
> the worked example of the end state: a magic link requested at
> `map.creatumundo.mx` arrived at 12:07:06 CDMX from
> **`Crea Tu Mundo <hola@creatumundo.mx>`**, sent on **CTM's own Resend
> account**. Reading order for the current contract: [THE RULE](#the-rule-2026-09-07--the-display-name-follows-the-address)
> (what a From header may never be), then
> [Phase 3](#phase-3--a-branded-sender-is-a-vcto-privilege-and-it-is-portable)
> (who is entitled to one), then
> [Phase 4](#phase-4--ctm-is-live-on-its-own-resend-account-2026-09-07)
> (the account, the credential path, and the rollback). Phases 1-2 remain the
> description of every tenant that has not reached Phase 3.

## THE RULE (2026-09-07) — the display name follows the address

> A From header pairing a client's display name with an address on MADFAM's
> domain — `Crea Tu Mundo <hola@madfam.io>` — must **never** be produced.

Only MADFAM sends from `hola@madfam.io`. A brand display name may appear only
beside **that brand's own address** (`hola@creatumundo.mx`), which is allowed
only once `creatumundo.mx` is in `RESEND_VERIFIED_DOMAINS`. Until then every
message for that tenant is sent as the platform sender, whole:
`MADFAM <hola@madfam.io>`.

Display name and address are **one decision**, keyed on a single fact: is the
binding's own address domain verified for the account that will send it. Both
move together or neither moves. There is no intermediate state.

**Why.** A display name is a claim about who owns the mailbox beside it. The
recipient cannot verify it, and a name that does not match its address is the
exact shape of the display-name spoof mail clients teach people to distrust.
Withholding the address while shipping the name does not deliver "half the
brand" — it delivers a false statement.

**This reverses the earlier rule, and the reversal is evidence-driven.** #603
deliberately shipped the opposite ("the display name moves as soon as the code
ships; only the address waits"). That behaviour was **observed in production on
2026-09-07**: the first magic link requested from `map.creatumundo.mx` arrived
in the CTM inbox at 02:32:21 CDMX as `Crea Tu Mundo <hola@madfam.io>`, subject
`Tu enlace de acceso | 2026-09-07 02:32:21`. Owner directive the same night
rejected it. Everything below that describes a partial downgrade is superseded
by this section.

**Body branding is unaffected.** `email_branding.py` still renders the tenant's
header wordmark, palette, voice (tú/usted) and CDMX clock on both sides of the
verification line, and the hosted-hop interstitial still carries the tenant
title. What waits for verification is the **envelope claim**, not the tenant's
presence in the message.

Enforced in `app/services/email_sender.py::_fallback_for`, fenced by
`tests/unit/services/test_email_sender.py::TestDisplayNameFollowsAddress`
(including a property-style sweep asserting that no binding, under any signal
or gate state, ever pairs a tenant display name with an address on the platform
domain).

## Phase 1 — MADFAM sends, the platform is credited

Applies from first contact until we manage the client's domain.

```
From:    MADFAM <hola@madfam.io>
Header:  MADFAM
Footer:  © Innovaciones MADFAM S.A.S. de C.V.
         Con tecnología de <platform>   ("Powered by" in en)
```

**Every** message, from **every** platform — Janua, Nauta, Karafiel. The
platform is credited, never branded as the sender.

### Why one sender rather than per-platform

A bespoke client meets several of our platforms over an engagement. A sender
that changes per product teaches them nothing and reads as several vendors.
One consistent sender builds recognition, and recognition is what makes the
*next* email safe to open — which matters most for the first message anyone
receives, a sign-in link.

This is what went wrong before the policy existed: the first message a client
would have received came from `Janua <noreply@janua.dev>` — an unknown brand
on an unrelated domain, asking them to authenticate. Indistinguishable from
phishing, and deleting it is the correct reaction.

### Why not the client's own name on the From line

It was tried and rejected. Sender and destination agreeing sounds right, but
it optimises the wrong thing: the goal in Phase 1 is familiarity with MADFAM,
not the illusion that each product is theirs. Their name belongs on their
workspace, not on our envelope — until Phase 2, when it is genuinely theirs.

### Why not `noreply@<tenant>.madfam.io`

Per-subdomain sending splits reputation across domains that each send a
handful of messages a year, and a domain with no reputation lands in spam. One
verified domain accumulates reputation across every client and every service,
with one SPF/DKIM/DMARC setup instead of N.

**`madfam.io` is Resend-verified** (four months as of 2026-08-14). Verify before
changing a sending domain: sending from an unverified domain is worse than the
wrong brand, because it does not arrive at all.

## Phase 2 — the client's domain, the client's branding

**IN CODE as of 2026-09-06, gated on verification.** Begins per-client when
MADFAM manages that client's web presence (e.g. `creatumundo.mx`).

```
From:    Crea Tu Mundo <hola@creatumundo.mx>
Reply-To: hola@creatumundo.mx
Header:  client logo and palette
Footer:  Con tecnología de MADFAM
```

Owner directive, 2026-09-06: "so far we've been sending the emails from
madfam.io, which should change now that we have @creatumundo.mx accessible via
email. Sender should be hola@creatumundo.mx." `hola@`, matching MADFAM's own
`hola@madfam.io` — a repliable human address, not `noreply@` as this document
originally sketched.

**Precondition, non-negotiable:** the client's domain verified in Resend, which
needs DNS records published — exactly what managing their web presence gives
us. Without it, mail from their domain is not spam-foldered, it is **rejected
by Resend** and never sent at all.

### How the precondition is enforced in code

`RESEND_VERIFIED_DOMAINS` (default `madfam.io`) is the list of domains Resend
has verified. `app/services/email_sender.py::sender_for()` resolves the tenant
from the redirect host (or an explicit `org_id`) and then checks the resolved
address against that list. An address on an unverified domain is **downgraded,
not sent** — and since 2026-09-07 the downgrade is **total**: the display name
goes back with the address.

| `RESEND_VERIFIED_DOMAINS` | A CTM message comes from |
|---|---|
| `madfam.io` | `MADFAM <hola@madfam.io>` |
| `madfam.io,creatumundo.mx` | `Crea Tu Mundo <hola@creatumundo.mx>` |

The tenant's **display name waits with the address** — see [THE RULE](#the-rule-2026-09-07--the-display-name-follows-the-address).
This table previously showed `Crea Tu Mundo <hola@madfam.io>` in the first row;
that state was observed in production on 2026-09-07 and rejected. Merging still
moves no mail, and the production cutover is still one env edit with a
one-env-edit rollback — over the same code path that was already running, which
is why the cutover is not also a first execution.

The step-by-step is [`runbooks/resend-domain-onboarding.md`](./runbooks/resend-domain-onboarding.md);
`scripts/resend_domain_onboard.py` creates the domain and prints the exact DNS
records (DKIM `resend._domainkey` TXT, plus `send.` MX + TXT for the SPF return
path) as `enclii providers cloudflare dns-apply` lines.

### The internal door

`POST /api/v1/email/send` accepts `from_email` / `from_name` from other MADFAM
services. These used to be ignored outright. They are now honoured **under the
same gate**: an explicit address is used only when its domain is verified, and
otherwise discarded in favour of the tenant/host rule.

**2026-09-07: the caller's display name is discarded with it.** The earlier
rule — "a caller's display name is always honoured; naming yourself is
harmless, claiming a domain is not" — is what allowed the forbidden header to
be assembled from two individually harmless halves, including by a caller
passing `from_name` alone with no address at all. A display name is honoured
exactly where the address is: on a verified address the caller was entitled to
claim, and nowhere else.

## Phase 1, refined — MADFAM sends, the BODY is the tenant's

**2026-08-29.** The sender line above is untouched. What changed is the BODY:
the header wordmark and palette may now read as the client's, with MADFAM
credited underneath. A person signing into their own workspace sees their own
name at the top of the sign-in mail; the envelope is still MADFAM's.

```
From:    MADFAM <hola@madfam.io>            (UNCHANGED — Phase 1)
Header:  the tenant's name and palette      (e.g. "Crea Tu Mundo", indigo)
Footer:  Con tecnología de MADFAM           ("Powered by MADFAM" in en)
```

This is a refinement of Phase 1, not the start of Phase 2. Phase 2 — the
client's DOMAIN on the From line — remains gated on that domain being verified
in Resend, exactly as below. Only the parts of the message that do not affect
deliverability were made per-tenant.

The resolver is `app/services/email_branding.py::resolve_branding()`. It keys on
the magic-link `redirect_url` host (crea-map / kalya → CTM) or an explicit
`org_id`, and returns the header name, header palette, and footer credit;
everything else defaults to the MADFAM frame, so an unknown or absent signal
renders exactly what it rendered before. It is deliberately kept separate from
`resolve_sender`, and nothing it returns is ever used to build the From line.
(Superseded in part by Phase 2 below: the From line DOES now carry the tenant,
but it is resolved by `email_sender.sender_for` from the same host signal —
never from anything `resolve_branding` returns. `test_email_branding.py` still
pins that separation.)

Why keyed on the redirect host rather than `WhiteLabelConfiguration`: the auth
mailer runs in FastAPI BackgroundTasks with no DB session, so the org-branding
table (keyed by `organization_id`) is not reachable at send time. The redirect
host is the tenant signal that IS available — and the one Phase 2 now reads.
When a send path carries a session, `resolve_branding(org_id=…)` is the seam to
hang the DB-backed config on.

## The voice each message speaks in

**2026-09-06.** The From line and the header were already the requester's.
The WORDS were not: every Spanish message addressed its reader as `usted`,
whichever product had asked for it.

Spanish forces a choice English does not — every sentence aimed at the reader
is either `tú` or `usted`, with no neutral second person. The register
machinery has existed in `app/services/email_i18n.py` since the formality work
landed (both copies, both subjects, both templates), but nothing on the live
path ever selected between them: the magic-link router passed `locale` and not
`formality`, so everything resolved through `DEFAULT_FORMALITY` to `usted`.

The result, found live: crea-map's own login page says «Escribe el correo con
el que la dirección te dio de alta — te llega un enlace y con un clic estás
dentro» (`tú`), and the mail janua sent for that page opened «Inicie sesión en
su portal · Use el siguiente botón» (`usted`). Two screens, seen back to back,
addressing the same person two different ways.

### Precedence

Highest first. Each tier is skipped when absent or unsupported, so a bad value
falls through instead of shadowing a good one below it.

| # | Tier | Where it comes from |
|---|------|---------------------|
| 1 | The request | `formality` on `POST /api/v1/auth/magic-link` — `"tu"` or `"usted"` |
| 2 | The reader | `users.spanish_formality`, read by the router while it still holds a session |
| 3 | The product | the redirect host's registered voice — `email_branding.default_formality_for` |
| 4 | The default | `usted` (`email_i18n.DEFAULT_FORMALITY`) |

Tier 3 is the one that fires in practice: `users.spanish_formality` is NULL for
almost every row, because NULL means "has not chosen" rather than "usted". It
is keyed on the SAME redirect host as the branding above, so a message's
header, its voice, and its From line all resolve from one signal:

- CTM products (`crea-map`, `ensayo-map`, `kalya.app`, `*.creatumundo.mx`) → `tú`
- everything else, including the nauta client portal and every unlisted host → `usted`

Tier 2 sitting ABOVE tier 3 is deliberate: a product may state its own voice,
but it must never overwrite someone who has told us how they want to be
addressed.

`formality` is normalized rather than validated: an unsupported value (
`vosotros` included — see `email_i18n` for why that register is not coming)
becomes None and falls to the next tier. A sign-in request must not 422 over a
cosmetic field.

**Consumers:** a product only needs to send `formality` when its voice differs
from its host's registered default. crea-map should send `"tu"` explicitly so
its mail does not depend on a host table entry; nauta needs no change — its
portal hosts already resolve to `usted`, and its request route deliberately
cannot vary its behavior per recipient (that would leak workspace membership).

## The timestamp on every re-sendable subject

**2026-09-06.** Subjects are constant strings, so five requests produce five
messages titled «Su enlace de acceso» — and every mail client threads them
into one conversation. A threaded reader opens the top of the thread, which is
the OLDEST message, lands on an expired link, and has nothing on screen that
distinguishes the live link from the dead ones. Observed on a real inbox as a
single thread labelled «[32] Su enlace de acceso».

Every re-sendable transactional subject now ends with the send moment:

```
Tu enlace de acceso | 2026-09-06 16:23:11
Su enlace de acceso | 2026-09-06 16:23:11
Your sign-in link | 2026-09-06 16:23:11
```

After Anthropic's `Your secure link to Claude.ai is here | 2026-09-06 16:23:11`.
The shape is deliberate: the stamp is LAST so the subject still starts with the
words a reader scans for and a truncating client eats the stamp rather than the
meaning; the date is ISO-ordered and the clock is 24h so it sorts and is
unambiguous between es-MX and en readers; seconds are included because two
links requested in the same minute is exactly the case someone hits when the
first seems not to have arrived.

**The zone is the requester's, and there is no zone suffix.** The stamp is only
useful if the reader can compare it to their own wall clock without arithmetic,
so it is rendered in the product's operating timezone —
`email_branding.timezone_for`, keyed on the same redirect host, defaulting to
`America/Mexico_City` (MADFAM's operating timezone, and the ecosystem rule for
every human-facing time). UTC would read six hours in the future to every
Mexican reader, making the NEWEST link look like it had not arrived yet.

The clock is read per send (`email_i18n.now_for_timezone`), never cached at
import — a module-level "now" would stamp every message in a long-lived worker
with the time that worker booted.

Applies to the three re-sendable messages: **magic link**, **password reset**,
**email verification**. Not to welcome or invitation, which are sent once and
whose subjects already carry a distinguishing organization name.

## The seam that made Phase 2 cheap — now used

`app/services/email_service.py::resolve_sender()` accepted `redirect_url` and
ignored it, with a docstring insisting it was not dead code: "the redirect host
identifies the tenant, so when a client's domain is verified, the switch
happens in one function rather than as another signature change through four
callers."

That is exactly what happened. `resolve_sender` now delegates to
`email_sender.sender_for()`, and no caller signature changed. The prediction is
recorded here because it is the argument for leaving the next such seam alone.

Per-client logo and palette landed earlier, in the Phase-1 refinement above.

## Rules that hold in both phases

- **Never send from an unverified domain.** This is no longer only a habit:
  `RESEND_VERIFIED_DOMAINS` enforces it in code, and adding a domain to that
  list before `scripts/resend_domain_onboard.py` reports `verified` is the one
  way to break it.
- **Credit, do not brand.** Whoever is not the sender goes in "Powered by".
- **es-MX uses "Con tecnología de"**, not "Impulsado por" — the first reads as
  an attribution, the second as marketing.

## Phase 3 — a branded sender is a vCTO privilege, and it is portable

Owner directive, 2026-09-06, two sentences that shaped this phase:

> «this type of treatment should be left exclusively for our vCTO clients,
> where we have full operational control. And we should allow mechanisms so
> that CTM and any other vCTO client can easily move to their own Resend (or
> preferred provider) account.»

Phase 2 answered *which address goes on the envelope*. Neither of those
sentences is answerable in those terms, because both are properties of the
TENANT rather than of the address:

- a branded From is now a **privilege that must be checked**, not a property of
  a host;
- the From line and **the account that sends it** are separable, and Phase 2
  welded them together — `resend.api_key` is set once at service construction,
  so every tenant sent on MADFAM's account.

So the per-tenant sender became a record instead of a triple.

### The binding

`app/services/sender_binding.py`. One `SenderBinding` per tenant:

```
tenant · display_name · from_address · reply_to
provider (resend|smtp) · account (madfam|tenant) · credential_ref · verified_domains
```

`credential_ref` is a **name** — an env var or a Vault path — never a value.
That is what makes a binding safe to commit, safe to diff in a PR and safe for
an operator script to print. `app/services/sender_credentials.py` is the only
module that ever resolves one, through the repo's existing
`core/secrets_provider` (SOC 2 CF-06).

`_TENANT_SENDERS` and `SENDER_HOSTS` in `email_sender.py` are now **derived
views** over this registry rather than parallel tables. A malformed binding —
unknown provider, tenant account still pointing at MADFAM's key, tenant account
with no verified domains of its own — raises at **import**, so the API does not
start rather than discovering it on a sign-in link.

### Verification is per ACCOUNT, not per domain

Resend verifies a domain **for an account**. `creatumundo.mx` verified on
MADFAM's account says nothing about CTM's own account. So `is_verified_domain`
now takes the binding: a binding on MADFAM's account reads the global
`RESEND_VERIFIED_DOMAINS` exactly as before, and a binding on the tenant's own
account reads its own `verified_domains`, because the global list describes the
wrong account.

### The gate, and why it is not a call to nauta

The task that produced this phase proposed reading nauta's `Workspace.tier`
over an internal endpoint. Reading nauta first settled it the other way:

1. **Nauta has the tier but exposes it to nobody.** `Workspace.tier`
   (`SELF_SERVE | PROJECT | FRACTIONAL_CTO`) is reachable only through
   human-session tRPC admin mutations. Nauta's two machine-authenticated routes
   return `{workspaceId, provisioning, locale}` and a write-only time draft.
2. **The call would run the wrong way.** The integration today is strictly
   nauta → janua. Janua calls nauta nowhere. This would make the identity
   provider depend on a downstream product at send time, inside a
   BackgroundTask with no session and no retry budget, for a sign-in link.
3. **It would contradict the ratified boundary.** Nauta's own ADR-0001 and its
   `erp-catalog.ts` state that «janua is the sole entitlement authority».
   "Is this client entitled to a branded sender" is an entitlement question, so
   asking nauta inverts the rule nauta is written to respect.

So the source of truth is janua's own `Organization.product_tiers` — the store
that already feeds `madfam_entitled_products`, already has audited admin
grant/revoke endpoints, and is therefore **not a second registry**:

```json
{ "vcto": "fractional_cto" }
```

`fractional_cto` deliberately mirrors nauta's enum so the two vocabularies read
the same even though janua is the authority.

### Fail closed, but never fail to deliver

The auth mailer has no DB session, so the authoritative read cannot happen on
the send path. `sender_policy.is_vcto_entitled` consults, in order: an explicit
decision from a caller that DOES hold a session, then a process cache refreshed
by the admin endpoints, then **not entitled**.

"Fail closed" means the message still goes out — as `MADFAM <hola@madfam.io>`,
the platform sender whole (2026-09-07: it used to keep the tenant's display
name; see THE RULE). It never means a sign-in link fails to arrive. That
ordering is the same one the verified-domain gate was built on.

CTM is **seeded** entitled in code, because a cold process has an empty cache
and the auth mailer never touches the DB, so a strict gate would silently
regress everything Phase 2 shipped. The seed is a statement of a signed
commercial fact, versioned in git and revocable by deleting one line — not a
bypass: an explicit `vcto_entitled=False` from an authoritative read still wins.

### The internal door is gated too

`sender_for_address` honours a caller's explicit `from_email` only from a
verified domain — and now, when that domain belongs to a **client**, only when
that client passes the vCTO gate. Otherwise the internal API key would be a way
around the restriction, and the internal caller is exactly the one most likely
to be automating a client's mail. An address on MADFAM's own domain is
unaffected: sending as MADFAM was never the branded privilege.

### Portability

`scripts/sender_binding_switch.py` moves a tenant to their own account:
`--onboard` creates and prints DNS for the domain in the TENANT's Resend
account, `--verify` polls it, `--switch` flips `account` / `credential_ref` /
`verified_domains` (refusing to run before the domain verifies), `--rollback`
reverses it, `--check-credential` answers whether the Vault reference resolves
without printing it. The runbook has the operator one-shot.

The `smtp` provider is a binding-level **stub with no transport behind it**. A
binding declaring it fails visibly at send rather than quietly leaving via
Resend, which would be a lie about how the mail left. Implementing SMTP is the
work the first client who asks for it will trigger — the interface is already
the binding, so it stays a config change.

## Phase 4 — CTM is live on its own Resend account (2026-09-07)

Phase 3 built the portability. This is CTM using it: the first tenant-account
binding in production.

```
tenant           ctm
account          tenant                    (was: madfam)
credential_ref   CTM_RESEND_API_KEY        (a NAME — an env var)
verified_domains ("creatumundo.mx",)       (was: () — deferring to the global list)
```

CTM created its own Resend account and `creatumundo.mx` is **Verified** there
(DKIM `resend._domainkey`, send MX/TXT published through Enclii and the
Cloudflare dashboard). From that moment the global `RESEND_VERIFIED_DOMAINS` —
which describes **MADFAM's** account — is the wrong authority for CTM, which is
why `verified_domains` becomes non-empty at exactly the same commit as
`account`.

### The credential path, end to end

```
Vault  secret/janua#ctm_resend_api_key
  ↓  (enclii-managed ExternalSecret)
K8s Secret  janua-secrets, key `ctm-resend-api-key`
  ↓  (env, marked optional in k8s/base/deployments/janua-api.yaml)
Pod env  CTM_RESEND_API_KEY
  ↓
app/services/sender_credentials.py
```

**`credential_ref` names an ENV VAR, not a Vault path, and that is deliberate.**
`sender_credentials` supports both shapes, but janua-api runs **without**
`VAULT_ADDR` / `VAULT_TOKEN` (verified on the live pod, 2026-09-07), so a
`path#field` reference can never resolve in production — it would fail every
time, silently, and degrade CTM to the platform sender forever. The
ExternalSecret is what bridges Vault to the pod; the env var is what the process
can actually read. A Vault-path `credential_ref` remains valid for any future
deployment that *does* carry a Vault token.

The env entry is marked **optional** in the deployment: a missing key degrades
the sender (below) instead of blocking the pod from starting.

### A missing tenant credential degrades the sender — it never blocks a sign-in link

This is the owner's rule from #607 applied one layer down. With CTM's binding on
its own account, the key may legitimately be absent for a window — an operator
flips the binding before writing the secret, or the ExternalSecret has not synced
yet. In that window:

- **The magic link still goes out.** From the PLATFORM sender,
  `MADFAM <hola@madfam.io>`, whole. Never `Crea Tu Mundo <hola@madfam.io>` — a
  degraded send is still subject to THE RULE.
- **A warning is logged**, `sender_credentials.tenant_credential_missing`,
  carrying the tenant and the credential **reference**. Never the value.
- **The body is unaffected.** The message still reads as Crea Tu Mundo
  throughout; what is withheld is the envelope claim.

Why this is not merely nice-to-have: a tenant-account binding carries its own
`verified_domains`, describing an account the process can only reach with that
tenant's key. Without the key, the first two gates still *pass* — the domain IS
verified, on an account we cannot authenticate to — and the branded address
would leave on MADFAM's account, where `creatumundo.mx` is **not** verified.
Resend rejects that outright. The failure mode is not a wrong-looking From; it
is a client who cannot sign in.

So `email_sender.sender_for` applies a **third gate**,
`sender_credentials.tenant_credential_available`, after the vCTO gate and the
verified-domain gate. It is **synchronous** on purpose: `sender_for` is the sync
resolution *every* send path reads the From line from, and a check that lived
only in the async send path would let the envelope and the account disagree.
`resolve_credential` still **raises** for a caller asking for the secret itself,
which is what `--check-credential` reports NO from; the send path asks the
boolean question instead.

### The account and the envelope are one decision

Both Resend send paths now read the tenant's key when the binding calls for it:

- `resend_email_service.py` swaps the SDK's module-global `resend.api_key`
  under a lock for the duration of the call (the SDK exposes no per-call
  credential).
- `email_service.py::_send_via_resend` — the path the **magic link actually
  takes** — sends the tenant key in its own `Authorization` header. This one
  previously resolved the From through `sender_for` but sent with
  `settings.RESEND_API_KEY` unconditionally, which for a tenant-account binding
  means presenting `Crea Tu Mundo <hola@creatumundo.mx>` to an account that has
  never verified that domain.

Both paths fall back to the platform sender, whole, on the platform account if
the credential does not resolve.

### Rollback

One field. Set CTM's `account` back to `madfam`, `credential_ref` to
`RESEND_API_KEY`, `verified_domains` to `()` — or run
`scripts/sender_binding_switch.py ctm --rollback` — and CTM sends on MADFAM's
account again, gated by the global `RESEND_VERIFIED_DOMAINS` as in Phase 2.
Deleting the secret alone is *not* a rollback: it degrades CTM to the platform
sender rather than restoring the branded MADFAM-account send.

### Provider account isolation (2026-09-22)

All Python Resend send adapters now pass an explicit account credential to
`app/services/resend_transport.py`. Only that transport may swap the SDK's
process-global key. Platform sends use the same lock as tenant sends, and
constructors do not mutate the key. This prevents concurrent platform sends or
new service instances from borrowing or overwriting an in-flight tenant account.
The selected credential is restored in `finally`, including provider failure.

Provider acceptance requires a nonempty message ID. Disabled/console sends are
simulated, with no recipient or body in logs. The internal email API's receipt
contract is documented in `MADFAM_EMAIL_INTEGRATION.md`; acceptance is distinct
from inbox delivery and from exactly-once retry guarantees.
