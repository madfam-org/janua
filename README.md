# Plinto

> **The secure substrate for identity.** Unify auth, orgs, and policy with edge‑fast verification and full control — all on **plinto.dev**.

**Status:** Private **alpha** · **Domain:** `https://plinto.dev` · **Stack:** Vercel + Railway + Cloudflare (R2 + CDN + Turnstile)

---

## Contents

* [What is Plinto?](#what-is-plinto)
* [Key features](#key-features)
* [How it works (at a glance)](#how-it-works-at-a-glance)
* [Quick start (Next.js)](#quick-start-nextjs)
* [Edge verification examples](#edge-verification-examples)
* [Core API (selected endpoints)](#core-api-selected-endpoints)
* [Configuration](#configuration)
* [Security notes](#security-notes)
* [Roadmap](#roadmap)
* [Contributing](#contributing)
* [License](#license)

## 📚 Documentation

* **[Documentation Hub](./docs/)** - All project documentation
  * **[Technical Docs](./docs/technical/)** - Architecture, codebase analysis, project structure
  * **[Deployment Guides](./docs/deployment/)** - Vercel setup, deployment instructions
  * **[API Reference](./docs/api/)** - API specifications and endpoints
  * **[Guides](./docs/guides/)** - Tutorials and how-to guides

---

## What is Plinto?

**Plinto** is an identity platform — a **secure substrate** that provides:

* **Core**: identity, sessions, orgs/tenants, roles, policies, audits, webhooks.
* **Edge**: ultra‑fast verification via Vercel Middleware & Cloudflare Workers with global JWKS caching.
* **Admin**: a dashboard for managing users, orgs, keys, webhooks, and compliance tasks.
* **SDKs**: developer‑first libraries for Next.js/React/Node (alpha), with Vue/Go/Python to follow.

Everything ships from **one domain: `plinto.dev`** during this stage.

---

## Key features

* **Passkeys (WebAuthn)** and **email/password** out of the box; social logins (G, GH, MS) in parity track.
* **Sessions & tokens** with refresh rotation, replay detection, and per‑tenant signing keys.
* **Orgs/teams/RBAC** + policy evaluation (OPA‑compatible) for route and resource decisions.
* **Edge verification** — p95 target < 50ms with CDN‑cached JWKS.
* **Audits & webhooks** — append‑only audit events; signed webhook deliveries with retries & DLQ.
* **Abuse‑resistant** flows — Turnstile on risky actions, rate limits per IP & tenant.
* **Enterprise track** — SSO (SAML/OIDC), SCIM, region pinning, advanced audit (rolling out).

---

## How it works (at a glance)

```
Browser/App → Cloudflare (WAF/CDN/Turnstile) → Vercel (Next.js) → Railway (Plinto Core API)
                                 ↘ Edge verification (Vercel/Cloudflare) using JWKS from plinto.dev/.well-known
```

* Your app integrates **Plinto SDKs** and uses **edge middleware** to verify sessions.
* Tokens are signed per tenant; verification is local/edge using **JWKS** cached at the CDN.
* Admin tasks live at `/admin`; API is served from `/api/v1/...` under the same domain.

---

## Quick start (Next.js)

> Works with **Next.js App Router** on Vercel. Example assumes TypeScript.

### 1) Install SDKs (alpha)

```bash
npm i @plinto/nextjs @plinto/react
# or
pnpm add @plinto/nextjs @plinto/react
```

### 2) Configure environment

Create `.env.local`:

```bash
# Issuer/audience are fixed to plinto.dev in alpha
PLINTO_ISSUER=https://plinto.dev
PLINTO_AUDIENCE=plinto.dev
PLINTO_TENANT_ID=tenant_123            # from Admin → Settings
PLINTO_JWKS_URL=https://plinto.dev/.well-known/jwks.json
```

### 3) Add Edge Middleware

`middleware.ts`

```ts
import { withPlinto } from "@plinto/nextjs/middleware";

export const config = {
  matcher: [
    "/((?!sign-in|sign-up|api|_next|public|favicon.ico|robots.txt).*)",
  ],
};

export default withPlinto({
  audience: process.env.PLINTO_AUDIENCE!,
  issuer: process.env.PLINTO_ISSUER!,
  jwksUrl: process.env.PLINTO_JWKS_URL!,
});
```

### 4) Wrap your app with the provider

`app/layout.tsx`

```tsx
import { PlintoProvider } from "@plinto/nextjs";

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <PlintoProvider>{children}</PlintoProvider>
      </body>
    </html>
  );
}
```

### 5) Drop in prebuilt auth UI

`app/sign-in/page.tsx`

```tsx
import { SignIn } from "@plinto/react";
export default function Page() {
  return <SignIn />;
}
```

### 6) Protect a route (server action / route handler)

`app/api/me/route.ts`

```ts
import { getSession } from "@plinto/nextjs/server";

export async function GET() {
  const session = await getSession();
  if (!session) return new Response("Unauthorized", { status: 401 });
  return Response.json({ userId: session.userId, tenantId: session.tenantId });
}
```

---

## Edge verification examples

### Vercel Edge Middleware

```ts
import { withPlinto } from "@plinto/nextjs/middleware";
export const config = { matcher: ["/dashboard/:path*"] };
export default withPlinto();
```

### Cloudflare Worker (minimal)

```ts
import { verify } from "@plinto/edge";

export default {
  async fetch(req: Request): Promise<Response> {
    const claims = await verify(req, {
      jwksUrl: "https://plinto.dev/.well-known/jwks.json",
      audience: "plinto.dev",
      issuer: "https://plinto.dev",
    });
    if (!claims) return new Response("Unauthorized", { status: 401 });
    return Response.json({ sub: claims.sub, tid: claims.tid });
  },
};
```

---

## Core API (selected endpoints)

**Base URL:** `https://plinto.dev/api/v1`

### Sign up (email + password)

```bash
curl -X POST https://plinto.dev/api/v1/auth/signup \
  -H 'Content-Type: application/json' \
  -d '{
    "email": "dev@example.com",
    "password": "CorrectHorseBatteryStaple",
    "tenantId": "tenant_123"
  }'
```

### Sign in (password)

```bash
curl -X POST https://plinto.dev/api/v1/auth/signin \
  -H 'Content-Type: application/json' \
  -d '{"email":"dev@example.com","password":"••••••••"}'
```

### Start passkey registration

```bash
curl -X POST https://plinto.dev/api/v1/auth/passkeys/register \
  -H 'Authorization: Bearer <sessionToken>'
```

### Verify session (introspection)

```bash
curl "https://plinto.dev/api/v1/sessions/verify" \
  -H "Authorization: Bearer <accessToken>"
```

> Full OpenAPI will be published under `/docs` during alpha.

---

## Configuration

**App-side env vars**

* `PLINTO_ISSUER` = `https://plinto.dev`
* `PLINTO_AUDIENCE` = `plinto.dev`
* `PLINTO_TENANT_ID` = your tenant identifier
* `PLINTO_JWKS_URL` = `https://plinto.dev/.well-known/jwks.json`

**Cookie guidance**

* HttpOnly, `SameSite=None; Secure`, domain: `plinto.dev`.

**Caching & keys**

* JWKS is **CDN‑cached**; we rotate keys on a schedule (90d) and on demand. Libraries respect `kid` to fetch fresh keys.

---

## Security notes

* Use **passkeys** where possible; fall back to email+password with strong password policy.
* Rotating refresh tokens with reuse detection; invalidating sessions on password change.
* Webhooks are **HMAC‑signed** with timestamp; verify signature before processing.
* Report vulnerabilities to **[security@plinto.dev](mailto:security@plinto.dev)** (PGP coming soon). Please do not open public issues for security findings.

---

## Roadmap

* [x] Single‑domain alpha on **plinto.dev**
* [x] Passkeys (WebAuthn) + email/password
* [x] Edge verification libraries (Vercel/Cloudflare)
* [ ] Social logins (Google, GitHub, Microsoft)
* [ ] Org/team management & custom roles (self‑serve)
* [ ] Webhooks console & DLQ
* [ ] Audit explorer
* [ ] SSO (SAML/OIDC) + SCIM (Enterprise)
* [ ] Region pinning & data residency controls

Track progress on `/docs/roadmap` (alpha).

---

## Contributing

Plinto is in **private alpha**. If you’re a design partner or MADFAM internal:

* Open issues in the private tracker.
* Submit PRs against the **alpha** branch; follow the conventional commits style.
* Before contributing code, ensure you’ve signed the contributor agreement.

---

## License

© **Aureo Labs** (a **MADFAM** company). All rights reserved during alpha.

Commercial and open‑core options will be announced at GA.
