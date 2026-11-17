# @janua/jwt-utils

JWT and JWKS utilities for the Janua Identity Platform.

> [!WARNING]
> `verifyToken` predates Janua's token verification contract
> ([`docs/reference/ISSUER_AND_JWKS.md`](../../docs/reference/ISSUER_AND_JWKS.md))
> and must not be used for resource-server verification until it is updated.
> As it stands (`src/jwt.ts`) it requires a `kid` in the JOSE header, so it
> rejects first-party session tokens, which carry none; it does not check the
> `type` claim; and it defaults `issuer` to `https://janua.dev` and `audience`
> to `janua.dev` when they are not passed.

## Installation

```bash
npm install @janua/jwt-utils
# or
yarn add @janua/jwt-utils
```

## Features

- JWT token verification
- JWKS cache management
- Token validation utilities
- Type-safe token handling

## Usage

### Verify JWT Token

```typescript
import { verifyToken } from '@janua/jwt-utils';

const payload = await verifyToken(token, jwks, {
  audience: 'your-app',
  issuer: 'https://janua.dev'
});
```

### JWKS Cache

```typescript
import { JWKSCache } from '@janua/jwt-utils';

const cache = new JWKSCache('https://janua.dev/.well-known/jwks.json');
const jwks = await cache.get();
```

## API Reference

### `verifyToken(token: string, jwks: JWKS, options: VerifyOptions): Promise<JWTPayload>`

Verifies a JWT token against a JWKS.

**Parameters:**
- `token`: The JWT token to verify
- `jwks`: The JSON Web Key Set
- `options`: Verification options (audience, issuer, etc.)

**Returns:** The decoded JWT payload

### `JWKSCache`

Manages caching of JWKS with automatic refresh.

**Methods:**
- `get(): Promise<JWKS>` - Get cached or fetch fresh JWKS
- `refresh(): Promise<JWKS>` - Force refresh of JWKS

## License

MIT