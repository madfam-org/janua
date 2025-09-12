# @plinto/edge

Edge-fast JWT verification for Cloudflare Workers and Edge environments. Sub-50ms verification latency guaranteed.

## Installation

```bash
npm install @plinto/edge
```

## Usage

### Basic Verification

```javascript
import { verify } from '@plinto/edge';

export default {
  async fetch(request, env) {
    const token = request.headers.get('Authorization')?.substring(7);
    
    const result = await verify(token, {
      publicKey: env.PLINTO_PUBLIC_KEY,
      issuer: 'https://api.plinto.dev',
      audience: 'your-app-id',
    });

    if (!result.valid) {
      return new Response('Unauthorized', { status: 401 });
    }

    return new Response(`Hello ${result.payload.email}!`);
  },
};
```

### Cloudflare Worker Handler

```javascript
import { createWorkerHandler } from '@plinto/edge';

export default createWorkerHandler({
  publicKey: PLINTO_PUBLIC_KEY,
  issuer: 'https://api.plinto.dev',
  audience: 'your-app-id',
});
```

### Middleware Pattern

```javascript
import { middleware } from '@plinto/edge';

const authMiddleware = middleware({
  jwksUrl: 'https://api.plinto.dev/.well-known/jwks.json',
  issuer: 'https://api.plinto.dev',
});

export default {
  async fetch(request, env) {
    // Check auth
    const authResponse = await authMiddleware(request);
    if (authResponse) return authResponse;

    // User is authenticated
    const user = request.user;
    return new Response(`Authenticated as ${user.email}`);
  },
};
```

### Performance Monitoring

```javascript
import { verifyWithMetrics, VerificationMetrics } from '@plinto/edge';

// Use verifyWithMetrics instead of verify
const result = await verifyWithMetrics(token, config);

// Get performance stats
const stats = VerificationMetrics.getStats();
console.log(`Average verification time: ${stats.avg}ms`);
console.log(`P95 verification time: ${stats.p95}ms`);
```

## Features

- ⚡ **Sub-50ms verification** - Optimized for edge environments
- 🔐 **JWKS support** - With intelligent caching
- 🌍 **Universal** - Works in Cloudflare Workers, Deno Deploy, etc.
- 📊 **Performance metrics** - Built-in latency monitoring
- 🔑 **Multiple token sources** - Header, cookie, query parameter
- 🛡️ **Type-safe** - Full TypeScript support

## Configuration

| Option | Type | Description |
|--------|------|-------------|
| `publicKey` | string | RSA public key in PEM format |
| `jwksUrl` | string | URL to fetch JWKS |
| `issuer` | string | Expected token issuer |
| `audience` | string | Expected token audience |
| `maxAge` | number | Maximum token age in seconds |
| `clockTolerance` | number | Clock skew tolerance in seconds |

## License

MIT