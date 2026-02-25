# MADFAM Ecosystem Integration Guide

**Last Updated**: 2026-02-24
**Applies to**: All MADFAM ecosystem apps consuming Janua as their identity provider

---

## Overview

Janua is the central OAuth2/OIDC identity provider for the MADFAM ecosystem. All MADFAM applications authenticate users through Janua rather than implementing their own auth systems.

- **Issuer URL**: `https://api.janua.dev`
- **OIDC Discovery**: `https://api.janua.dev/.well-known/openid-configuration`
- **JWKS Endpoint**: `https://api.janua.dev/.well-known/jwks.json`
- **API Reference**: `https://docs.janua.dev` or `/docs` on your local API instance
- **Flow**: OAuth 2.0 Authorization Code with PKCE (recommended for all clients)

### Authorization Code Flow with PKCE

```
1. App generates code_verifier + code_challenge (S256)
2. App redirects to: https://api.janua.dev/oauth/authorize
     ?response_type=code
     &client_id=YOUR_CLIENT_ID
     &redirect_uri=YOUR_CALLBACK_URL
     &scope=openid profile email
     &code_challenge=...
     &code_challenge_method=S256
     &state=RANDOM_STATE
3. User authenticates on Janua
4. Janua redirects to YOUR_CALLBACK_URL?code=AUTH_CODE&state=...
5. App exchanges code + code_verifier for tokens at /oauth/token
6. App validates the returned JWT and creates a local session
```

---

## Universal Integration Steps

These steps apply to every consumer app regardless of framework or language.

### 1. Register an OAuth Client

Register your app as an OAuth client. You can do this via the seed script or the API.

**Via seed script** (recommended for ecosystem apps):

```bash
cd scripts
python seed_ecosystem_clients.py --app your-app-name
```

**Via API**:

```bash
curl -X POST https://api.janua.dev/api/v1/oauth/clients \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "your-app-name",
    "redirect_uris": ["https://your-app.dev/api/auth/callback"],
    "audience": "your-app-api",
    "allowed_scopes": ["openid", "profile", "email"]
  }'
```

### 2. Configure Environment Variables

Every consumer app needs these variables:

```bash
JANUA_CLIENT_ID=your_client_id
JANUA_CLIENT_SECRET=your_client_secret
JANUA_ISSUER_URL=https://api.janua.dev
```

Add these to your `.env.example` so other developers know they are required.

### 3. Validate the `aud` Claim

Every JWT issued by Janua contains an `aud` (audience) claim. Your app must reject tokens where `aud` does not match your registered audience string. This prevents tokens issued to one MADFAM app from being accepted by another.

### 4. Use Namespaced Scopes

Request only the scopes your app needs. Use namespaced scopes for app-specific permissions:

| App | Example Scopes |
|-----|----------------|
| Dhanam | `billing:read`, `billing:write`, `portfolio:read` |
| Tezca | `scenes:read`, `scenes:write`, `assets:manage` |
| Stratum-TCG | `decks:read`, `decks:write`, `matches:join` |
| Yantra4D | `projects:read`, `projects:write`, `render:execute` |

### 5. Register Your CORS Origin

Ensure your app's origin is in Janua's allowed CORS origins list. Contact the Janua admin or add it via the admin panel at `admin.janua.dev`.

---

## SDK Options

| SDK | Package | Best For |
|-----|---------|----------|
| React | `@janua/react-sdk` | React SPAs (Vite, CRA) |
| Next.js | `@janua/nextjs-sdk` | Next.js App Router apps |
| Vue | `@janua/vue-sdk` | Vue 3 apps |
| TypeScript | `@janua/typescript-sdk` | Low-level client, Node.js backends |
| Python | `@janua/python-sdk` (`janua-sdk` on PyPI) | Python backend services |

Basic React integration:

```tsx
import { JanuaProvider, useJanua } from "@janua/react-sdk";

function App() {
  return (
    <JanuaProvider
      clientId={import.meta.env.VITE_JANUA_CLIENT_ID}
      issuerUrl="https://api.janua.dev"
      redirectUri={`${window.location.origin}/api/auth/callback`}
    >
      <YourApp />
    </JanuaProvider>
  );
}

function Profile() {
  const { user, isAuthenticated, login, logout } = useJanua();

  if (!isAuthenticated) {
    return <button onClick={login}>Sign in</button>;
  }

  return <p>Hello, {user.email}</p>;
}
```

---

## Per-Consumer Guidance

### Stratum-TCG (stratum-tcg.dev)

**Status**: Auth disabled. Highest integration priority.

**Client config**:
- Audience: `stratum-tcg-api`
- Redirect URI: `https://stratum-tcg.dev/api/auth/callback`

**Steps**:

1. Install the SDK:
   ```bash
   pnpm add @janua/react-sdk
   ```

2. Replace the no-op `AuthProvider` in `apps/client/src/auth.tsx` with the real SDK:
   ```tsx
   // Before: no-op stub
   // After:
   import { JanuaProvider } from "@janua/react-sdk";

   export function AuthProvider({ children }: { children: React.ReactNode }) {
     return (
       <JanuaProvider
         clientId={import.meta.env.VITE_JANUA_CLIENT_ID}
         issuerUrl="https://api.janua.dev"
         redirectUri={`${window.location.origin}/api/auth/callback`}
       >
         {children}
       </JanuaProvider>
     );
   }
   ```

3. Enable backend JWT validation by setting `AUTH_ENABLED=true` in the backend environment.

4. Add Janua environment variables to `.env.example`:
   ```bash
   JANUA_CLIENT_ID=
   JANUA_CLIENT_SECRET=
   JANUA_ISSUER_URL=https://api.janua.dev
   AUTH_ENABLED=true
   ```

5. Add a login page that initiates the OAuth redirect flow.

6. Register the OAuth client via the seed script:
   ```bash
   python scripts/seed_ecosystem_clients.py --app stratum-tcg
   ```

---

### Dhanam (dhan.am)

**Status**: Uses a local SDK stub. Minimal work remaining.

**Client config**:
- Audience: `dhanam-api`
- Redirect URI: `https://dhan.am/api/auth/callback/janua`

**Steps**:

1. Replace `apps/web/src/lib/janua-sdk-stub.tsx` with `@janua/react-sdk` once published to npm:
   ```bash
   pnpm add @janua/react-sdk
   # Then update imports from the stub to the real package
   ```

2. No other changes needed. Dhanam already has JIT (just-in-time) user provisioning and a well-designed bridge pattern that abstracts the auth provider.

---

### Enclii (enclii.dev / admin.enclii.dev)

**Status**: Custom OIDC middleware with Dex fallback. Needs SDK migration.

**Client config**:
- Audience: `enclii-api`
- Redirect URI: `https://admin.enclii.dev/api/auth/callback`

**Steps**:

1. Install the Next.js SDK:
   ```bash
   pnpm add @janua/nextjs-sdk
   ```

2. Replace the custom OIDC middleware with the SDK's built-in middleware. The SDK handles token refresh, session management, and PKCE automatically.

3. Remove the Dex fallback dependency. Once Janua is the sole IdP, the Dex configuration and related code can be deleted.

4. Add a login page with provider enumeration (email/password, Google, GitHub) using the SDK's prebuilt components or your own UI calling `login()`.

---

### Yantra4D (yantra4d.dev)

**Status**: Mostly complete. Missing social login and JIT provisioning.

**Client config**:
- Audience: `yantra4d-api`
- Redirect URI: `https://yantra4d.dev/api/auth/callback`

**Steps**:

1. Add social login buttons to the admin login page. The SDK provides the `login({ provider: "google" })` method for initiating provider-specific flows.

2. Add JIT user provisioning. When a user authenticates via Janua for the first time and no local user record exists, create one from the JWT claims:
   ```typescript
   // In your auth callback handler
   const januaUser = await verifyToken(code);

   let localUser = await db.users.findByEmail(januaUser.email);
   if (!localUser) {
     localUser = await db.users.create({
       email: januaUser.email,
       name: januaUser.name,
       januaSubject: januaUser.sub,
       role: "viewer", // default role for new users
     });
   }
   ```

---

### Tezca (tezca.dev)

**Status**: Most complete integration. Use as reference.

**Client config**:
- Audience: `tezca-api`
- Redirect URI: `https://tezca.dev/api/auth/callback/janua`

**Steps**:

1. Add an SDK mock in the admin app for testing. This allows running admin app tests without a live Janua instance:
   ```typescript
   // test/mocks/janua.ts
   import { vi } from "vitest";

   export const mockJanuaAuth = {
     user: { sub: "test-user", email: "dev@tezca.dev", roles: ["admin"] },
     isAuthenticated: true,
     login: vi.fn(),
     logout: vi.fn(),
   };
   ```

2. No other integration work needed. Tezca's implementation is exemplary and can serve as a reference for other MADFAM apps.

---

### Janua Dashboard (app.janua.dev)

**Status**: Fully integrated (dogfooding).

The Dashboard uses `@janua/nextjs-sdk` internally and serves as the canonical reference implementation. See `apps/dashboard/lib/janua-client.ts` for configuration patterns.

---

## Token Validation

All consumer apps must validate JWTs from Janua. Here is the process.

### Fetch the Public Keys

Retrieve the JWKS (JSON Web Key Set) from Janua's well-known endpoint:

```
GET https://api.janua.dev/.well-known/jwks.json
```

Cache this response. Refresh when you encounter an unknown `kid` (key ID) in a token header.

### Validate the Token

Verify these properties on every request:

| Check | Expected Value |
|-------|----------------|
| Algorithm | `RS256` |
| `iss` (issuer) | `https://api.janua.dev` |
| `aud` (audience) | Your registered audience (e.g., `tezca-api`) |
| `exp` (expiry) | Must be in the future |
| Signature | Valid against the JWKS public key matching the token's `kid` |

### Extract User Information

Standard claims available in Janua JWTs:

| Claim | Type | Description |
|-------|------|-------------|
| `sub` | string | Unique user identifier |
| `email` | string | User's email address |
| `roles` | string[] | Assigned roles |
| `tier` | string | Subscription tier (community, pro, scale, enterprise) |
| `org_id` | string | Organization ID (if applicable) |

### Example: Node.js Validation

```typescript
import jwt from "jsonwebtoken";
import jwksClient from "jwks-rsa";

const client = jwksClient({
  jwksUri: "https://api.janua.dev/.well-known/jwks.json",
  cache: true,
  rateLimit: true,
});

function getKey(header: jwt.JwtHeader, callback: jwt.SigningKeyCallback) {
  client.getSigningKey(header.kid, (err, key) => {
    callback(err, key?.getPublicKey());
  });
}

export function verifyJanuaToken(token: string): Promise<jwt.JwtPayload> {
  return new Promise((resolve, reject) => {
    jwt.verify(
      token,
      getKey,
      {
        issuer: "https://api.janua.dev",
        audience: "your-app-api", // replace with your audience
        algorithms: ["RS256"],
      },
      (err, decoded) => {
        if (err) reject(err);
        else resolve(decoded as jwt.JwtPayload);
      }
    );
  });
}
```

### Example: Python Validation

```python
import jwt
import requests

JWKS_URL = "https://api.janua.dev/.well-known/jwks.json"
ISSUER = "https://api.janua.dev"
AUDIENCE = "your-app-api"  # replace with your audience

jwks_client = jwt.PyJWKClient(JWKS_URL)

def verify_janua_token(token: str) -> dict:
    signing_key = jwks_client.get_signing_key_from_jwt(token)
    return jwt.decode(
        token,
        signing_key.key,
        algorithms=["RS256"],
        issuer=ISSUER,
        audience=AUDIENCE,
    )
```

---

## Troubleshooting

### CORS Errors

**Symptom**: Browser console shows `Access-Control-Allow-Origin` errors when calling Janua endpoints.

**Fix**: Ensure your app's origin (e.g., `https://tezca.dev`) is registered in Janua's allowed CORS origins. Check via the admin panel or the API configuration.

### Token Audience Mismatch

**Symptom**: Token validation fails with "audience invalid" even though the user authenticated successfully.

**Fix**: Verify that the `audience` parameter in your OAuth client registration matches exactly what your token validation code expects. These are case-sensitive strings.

### Expired Tokens

**Symptom**: API calls return `401` after a period of inactivity.

**Fix**: Implement token refresh. Access tokens expire after 15 minutes by default. Use the refresh token to obtain a new access token:

```bash
POST https://api.janua.dev/oauth/token
Content-Type: application/x-www-form-urlencoded

grant_type=refresh_token
&refresh_token=YOUR_REFRESH_TOKEN
&client_id=YOUR_CLIENT_ID
```

The Janua SDKs handle this automatically when configured.

### PKCE Failures

**Symptom**: Token exchange returns `invalid_grant` error.

**Fix**: Ensure the `code_verifier` sent to the token endpoint matches the `code_challenge` sent during the authorization request. Common causes:
- Using a different `code_verifier` than the one used to generate the `code_challenge`
- URL-encoding issues with the base64url-encoded challenge
- Reusing an authorization code (codes are single-use)

### JWT Signature Verification Fails

**Symptom**: Token validation throws "invalid signature" errors.

**Fix**: Ensure you are fetching keys from the correct JWKS endpoint (`https://api.janua.dev/.well-known/jwks.json`). If Janua recently rotated its signing keys, clear your JWKS cache and re-fetch.
