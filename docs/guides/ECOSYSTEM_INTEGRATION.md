# Janua Integration Guide

**Last Updated**: 2026-02-24
**Audience**: Any developer integrating Janua as their OAuth2/OIDC identity provider

---

## 1. Quick Start (5 min)

### Register an OAuth Client

Create an OAuth client for your application using one of these methods.

**Via Dashboard UI** (preferred):

1. Sign in at [app.janua.dev](https://app.janua.dev).
2. Navigate to **Settings > OAuth Clients**.
3. Click **Create Client** and fill in your app name, redirect URIs, and audience string.
4. Copy the generated `client_id` and `client_secret`.

**Via API**:

```bash
curl -X POST https://api.janua.dev/api/v1/oauth/clients \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "your-app-name",
    "redirect_uris": ["https://your-app.example.com/api/auth/callback"],
    "audience": "your-app-api",
    "allowed_scopes": ["openid", "profile", "email"]
  }'
```

### Add Environment Variables

Copy the credentials into your application's environment:

```bash
JANUA_CLIENT_ID=<client_id from registration>
JANUA_CLIENT_SECRET=<client_secret from registration>
JANUA_ISSUER_URL=https://api.janua.dev
JANUA_AUDIENCE=your-app-api
```

You are now ready to implement the authorization flow.

---

## 2. Environment Variables

The full set of variables available to consumer applications.

| Variable | Required | Description | Default |
|----------|----------|-------------|---------|
| `JANUA_CLIENT_ID` | Yes | OAuth client identifier from registration | -- |
| `JANUA_CLIENT_SECRET` | Confidential clients | OAuth client secret. Not required for public clients using PKCE only. | -- |
| `JANUA_ISSUER_URL` | Yes | Base URL of the Janua identity provider | `https://api.janua.dev` |
| `JANUA_AUDIENCE` | Yes | Audience string registered for your client. Must match the `aud` claim in issued tokens. | -- |
| `JANUA_JWKS_URL` | No | JWKS endpoint for token signature verification. Auto-derived from `JANUA_ISSUER_URL` if omitted. | `${JANUA_ISSUER_URL}/.well-known/jwks.json` |

Add these to your `.env.example` so other developers on your team know they are required.

---

## 3. Authorization Code Flow with PKCE

All clients should use the Authorization Code flow with Proof Key for Code Exchange (PKCE). This applies to both public clients (SPAs, mobile apps) and confidential clients (server-side apps).

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

**Discovery endpoints**:

- OIDC Configuration: `https://api.janua.dev/.well-known/openid-configuration`
- JWKS: `https://api.janua.dev/.well-known/jwks.json`

---

## 4. Token Validation

Every consumer application must validate JWTs issued by Janua before trusting their claims.

### Required Checks

| Check | Expected Value |
|-------|----------------|
| Algorithm | `RS256` |
| `iss` (issuer) | `https://api.janua.dev` |
| `aud` (audience) | Your registered audience string (e.g., `dhanam-api`) |
| `exp` (expiry) | Must be in the future |
| Signature | Valid against the JWKS public key matching the token's `kid` |

### Audience Claim

The `aud` claim prevents cross-application token reuse. Each consumer application registers a unique audience string when creating its OAuth client (for example, `dhanam-api`, `enclii-api`, `stratum-tcg-api`). During token validation, your application must reject any token whose `aud` value does not exactly match your registered audience. This is a case-sensitive comparison.

Without audience validation, a token issued for one application could be replayed against another, bypassing authorization boundaries.

### Standard JWT Claims

| Claim | Type | Description |
|-------|------|-------------|
| `sub` | string | Unique user identifier |
| `email` | string | User's email address |
| `roles` | string[] | Assigned roles |
| `tier` | string | Subscription tier (community, pro, scale, enterprise) |
| `org_id` | string | Organization ID (if applicable) |

### Code Examples

**Node.js**

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
        audience: process.env.JANUA_AUDIENCE,
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

**Python**

```python
import jwt
import os

JWKS_URL = os.environ.get("JANUA_JWKS_URL", "https://api.janua.dev/.well-known/jwks.json")
ISSUER = os.environ.get("JANUA_ISSUER_URL", "https://api.janua.dev")
AUDIENCE = os.environ["JANUA_AUDIENCE"]

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

**Go**

```go
package auth

import (
	"context"
	"fmt"
	"os"
	"time"

	"github.com/lestrrat-go/jwx/v2/jwk"
	"github.com/lestrrat-go/jwx/v2/jws"
	"github.com/lestrrat-go/jwx/v2/jwt"
)

type Verifier struct {
	cache    *jwk.Cache
	issuer   string
	audience string
	jwksURL  string
}

func NewVerifier() (*Verifier, error) {
	issuer := os.Getenv("JANUA_ISSUER_URL")
	if issuer == "" {
		issuer = "https://api.janua.dev"
	}

	jwksURL := os.Getenv("JANUA_JWKS_URL")
	if jwksURL == "" {
		jwksURL = issuer + "/.well-known/jwks.json"
	}

	audience := os.Getenv("JANUA_AUDIENCE")
	if audience == "" {
		return nil, fmt.Errorf("JANUA_AUDIENCE is required")
	}

	ctx := context.Background()
	cache := jwk.NewCache(ctx)
	err := cache.Register(jwksURL, jwk.WithMinRefreshInterval(1*time.Hour))
	if err != nil {
		return nil, fmt.Errorf("failed to register JWKS: %w", err)
	}

	// Force an initial fetch to verify connectivity.
	_, err = cache.Refresh(ctx, jwksURL)
	if err != nil {
		return nil, fmt.Errorf("failed to fetch JWKS: %w", err)
	}

	return &Verifier{
		cache:    cache,
		issuer:   issuer,
		audience: audience,
		jwksURL:  jwksURL,
	}, nil
}

func (v *Verifier) Verify(ctx context.Context, tokenString string) (jwt.Token, error) {
	keySet, err := v.cache.Get(ctx, v.jwksURL)
	if err != nil {
		return nil, fmt.Errorf("failed to get JWKS: %w", err)
	}

	token, err := jwt.Parse(
		[]byte(tokenString),
		jwt.WithKeySet(keySet),
		jwt.WithValidate(true),
		jwt.WithIssuer(v.issuer),
		jwt.WithAudience(v.audience),
		jwt.WithAcceptableSkew(30*time.Second),
	)
	if err != nil {
		return nil, fmt.Errorf("token validation failed: %w", err)
	}

	// Verify the algorithm is RS256.
	msg, err := jws.Parse([]byte(tokenString))
	if err != nil {
		return nil, fmt.Errorf("failed to parse JWS: %w", err)
	}
	for _, sig := range msg.Signatures() {
		if sig.ProtectedHeaders().Algorithm() != jws.RS256 {
			return nil, fmt.Errorf("unexpected algorithm: %s", sig.ProtectedHeaders().Algorithm())
		}
	}

	return token, nil
}
```

---

## 5. JWKS Caching Best Practices

Fetching the JWKS on every request adds latency and puts unnecessary load on the identity provider. Follow these guidelines for production deployments.

**Cache responses aggressively.** A TTL of 1 hour is a reasonable default. JWKS key sets change infrequently (only during key rotation events).

**Refresh on unknown `kid`.** If a token arrives with a `kid` that is not in your cached key set, fetch the JWKS again before rejecting the token. This handles key rotation gracefully without downtime.

**Use stale-while-revalidate.** When a cache refresh fails (network error, temporary outage), continue using the stale key set for a bounded period rather than rejecting all tokens. This keeps your service available during transient Janua outages.

**Avoid per-request fetches.** Libraries like `jwks-rsa` (Node.js) and `PyJWKClient` (Python) include built-in caching. The Go example above uses `jwk.Cache` from the `lestrrat-go/jwx` library with a 1-hour minimum refresh interval. Use these built-in mechanisms rather than implementing your own.

---

## 6. SDK Options

| SDK | Package | Best For |
|-----|---------|----------|
| React | `@janua/react-sdk` | React SPAs (Vite, CRA) |
| Next.js | `@janua/nextjs-sdk` | Next.js App Router apps |
| Vue | `@janua/vue-sdk` | Vue 3 apps |
| TypeScript | `@janua/typescript-sdk` | Low-level client, Node.js backends |
| Python | `@janua/python-sdk` (`janua-sdk` on PyPI) | Python backend services |

### Basic React Integration

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

The SDKs handle PKCE, token refresh, and session management automatically.

---

## 7. CORS

CORS origins are auto-provisioned from the `redirect_uris` you register with your OAuth client. When Janua processes a client registration or update, it extracts the origins from the redirect URIs and adds them to the allowed CORS list for that client.

No manual CORS configuration or admin intervention is needed. If your application makes cross-origin requests to Janua and receives CORS errors, verify that your redirect URIs are correctly registered and that the request origin matches one of them.

---

## 8. Troubleshooting

### CORS Errors

**Symptom**: Browser console shows `Access-Control-Allow-Origin` errors when calling Janua endpoints.

**Fix**: Verify that your application's origin matches one of the registered `redirect_uris` for your OAuth client. Update the client registration if your origin has changed.

### Token Audience Mismatch

**Symptom**: Token validation fails with "audience invalid" even though the user authenticated successfully.

**Fix**: Confirm that the `audience` value in your OAuth client registration matches exactly what your token validation code expects. These are case-sensitive strings. Check both the client registration in the Dashboard and your `JANUA_AUDIENCE` environment variable.

### Expired Tokens

**Symptom**: API calls return `401` after a period of inactivity.

**Fix**: Implement token refresh. Access tokens expire after 15 minutes by default. Use the refresh token to obtain a new access token:

```
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

- Using a different `code_verifier` than the one used to generate the `code_challenge`.
- URL-encoding issues with the base64url-encoded challenge.
- Reusing an authorization code (codes are single-use).

### JWT Signature Verification Fails

**Symptom**: Token validation throws "invalid signature" errors.

**Fix**: Ensure you are fetching keys from the correct JWKS endpoint (`https://api.janua.dev/.well-known/jwks.json`). If Janua recently rotated its signing keys, clear your JWKS cache and re-fetch. See [JWKS Caching Best Practices](#5-jwks-caching-best-practices) for cache invalidation strategies.

---

## Appendix: MADFAM Ecosystem Apps

This section lists the known MADFAM ecosystem applications and their Janua client configurations. If you are building a new application outside the MADFAM ecosystem, you do not need this section.

| Application | Status | Audience | Redirect URI |
|-------------|--------|----------|--------------|
| **Stratum-TCG** (stratum-tcg.dev) | Auth disabled. Highest integration priority. | `stratum-tcg-api` | `https://stratum-tcg.dev/api/auth/callback` |
| **Dhanam** (dhan.am) | Uses local SDK stub. Minimal work remaining. | `dhanam-api` | `https://dhan.am/api/auth/callback/janua` |
| **Enclii** (admin.enclii.dev) | Custom OIDC middleware with Dex fallback. Needs SDK migration. | `enclii-api` | `https://admin.enclii.dev/api/auth/callback` |
| **Yantra4D** (yantra4d.dev) | Mostly complete. Missing social login and JIT provisioning. | `yantra4d-api` | `https://yantra4d.dev/api/auth/callback` |
| **Tezca** (tezca.dev) | Most complete integration. Use as reference. | `tezca-api` | `https://tezca.dev/api/auth/callback/janua` |
| **Janua Dashboard** (app.janua.dev) | Fully integrated (dogfooding). See `apps/dashboard/lib/janua-client.ts`. | `janua-dashboard` | `https://app.janua.dev/api/auth/callback` |
