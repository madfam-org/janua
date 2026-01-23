# Janua Troubleshooting Guide

> **Comprehensive guide for resolving common issues in development and production**

## Table of Contents

- [Build Issues](#build-issues)
- [Runtime Errors](#runtime-errors)
- [Authentication Problems](#authentication-problems)
- [Database Issues](#database-issues)
- [Deployment Problems](#deployment-problems)
- [SDK Integration Issues](#sdk-integration-issues)
- [Performance Issues](#performance-issues)
- [Development Environment](#development-environment)

## Build Issues

### Missing UI Components

**Error**: `Cannot find module '@/components/ui/card' or its corresponding type declarations`

**Cause**: Missing shadcn/ui components in the admin or dashboard apps.

**Solution**:
```bash
# Navigate to the affected app
cd apps/admin  # or apps/dashboard

# Install missing Radix UI dependencies
yarn add @radix-ui/react-dialog @radix-ui/react-label @radix-ui/react-select
yarn add @radix-ui/react-switch @radix-ui/react-tabs

# Ensure all UI components exist
ls components/ui/

# If components are missing, they need to be created
# See apps/admin/components/ui/ for reference implementations
```

### TypeScript Errors in SDK

**Error**: Type mismatches in `@janua/typescript-sdk`

**Cause**: Outdated type definitions or version mismatches.

**Solution**:
```bash
# Rebuild the SDK
yarn workspace @janua/typescript-sdk build

# Clear TypeScript cache
rm -rf node_modules/.cache
rm -rf apps/*/.next

# Reinstall and rebuild
yarn install
yarn build
```

### Turborepo Cache Issues

**Error**: Build not reflecting recent changes

**Solution**:
```bash
# Clear Turborepo cache
rm -rf .turbo
yarn cache clean

# Force rebuild without cache
yarn build --force
```

## Runtime Errors

### Session Verification Failures

**Error**: `401 Unauthorized` when accessing protected routes

**Causes & Solutions**:

1. **Expired Token**:
   ```typescript
   // Check token expiration
   const decoded = jwt.decode(token);
   if (decoded.exp < Date.now() / 1000) {
     // Token expired, refresh needed
   }
   ```

2. **Wrong JWKS URL**:
   ```env
   # Ensure correct JWKS URL in .env.local
   JANUA_JWKS_URL=https://janua.dev/.well-known/jwks.json
   ```

3. **Incorrect Audience/Issuer**:
   ```env
   JANUA_ISSUER=https://janua.dev
   JANUA_AUDIENCE=janua.dev
   ```

### CORS Errors

**Error**: `Access to fetch at 'https://janua.dev/api' from origin 'http://localhost:3000' has been blocked by CORS policy`

**Solution**:
```typescript
// In API configuration (apps/api/src/main.ts)
app.enableCors({
  origin: process.env.ALLOWED_ORIGINS?.split(',') || ['http://localhost:3000'],
  credentials: true,
});
```

### WebAuthn/Passkey Issues

**Error**: `NotAllowedError: The operation is not allowed at this time`

**Causes**:
- Not using HTTPS in development
- User gesture requirement not met
- Browser doesn't support WebAuthn

**Solution**:
```bash
# Use HTTPS in development
yarn dev --https

# Or use ngrok for local HTTPS
ngrok http 3000
```

## Authentication Problems

### MFA Not Working

**Error**: MFA codes always rejected

**Causes**:
- Time sync issues between client and server
- Incorrect secret storage

**Solution**:
```bash
# Check server time
date

# Sync time if needed (Ubuntu/Debian)
sudo timedatectl set-ntp on

# Verify TOTP window
# In apps/api/src/auth/mfa.service.ts
const verified = speakeasy.totp.verify({
  secret: user.mfaSecret,
  encoding: 'base32',
  token: code,
  window: 2, // Allow 2 time steps tolerance
});
```

### Social Login Integration

**Error**: `redirect_uri_mismatch` with OAuth providers

**Solution**:
```env
# Ensure callback URLs match provider configuration
GOOGLE_CALLBACK_URL=https://janua.dev/api/auth/google/callback
GITHUB_CALLBACK_URL=https://janua.dev/api/auth/github/callback

# Add to provider's authorized redirect URIs:
# - https://janua.dev/api/auth/[provider]/callback
# - http://localhost:8000/api/auth/[provider]/callback (for dev)
```

## Database Issues

### Connection Refused

**Error**: `ECONNREFUSED 127.0.0.1:5432`

**Solution**:
```bash
# Start PostgreSQL with Docker
docker-compose up -d postgres

# Or check if PostgreSQL is running
pg_isready

# Check connection string
echo $DATABASE_URL
# Should be: postgresql://user:password@localhost:5432/janua
```

### Migration Failures

**Error**: `relation "users" already exists`

**Solution**:
```bash
# Check migration status
yarn workspace @janua/database migrate:status

# Reset database (CAUTION: destroys data)
yarn workspace @janua/database migrate:reset

# Run migrations fresh
yarn workspace @janua/database migrate:up
```

### Redis Connection Issues

**Error**: `Redis connection to localhost:6379 failed`

**Solution**:
```bash
# Start Redis with Docker
docker-compose up -d redis

# Or install and start locally
brew install redis  # macOS
brew services start redis

# Test connection
redis-cli ping
# Should return: PONG
```

## Deployment Problems

### Vercel Build Failures

**Error**: Build failing on Vercel

**Common Solutions**:

1. **Environment Variables**:
   - Ensure all required env vars are set in Vercel dashboard
   - Check for typos in variable names

2. **Node Version**:
   ```json
   // package.json
   {
     "engines": {
       "node": ">=18.0.0"
     }
   }
   ```

3. **Build Command**:
   ```json
   // vercel.json
   {
     "buildCommand": "yarn build",
     "installCommand": "yarn install --frozen-lockfile"
   }
   ```

### Railway Deployment Issues

**Error**: API not starting on Railway

**Solution**:
```toml
# railway.toml
[build]
builder = "NIXPACKS"
buildCommand = "yarn install && yarn workspace @janua/api build"

[deploy]
startCommand = "yarn workspace @janua/api start:prod"
healthcheckPath = "/health"
healthcheckTimeout = 300

# Environment variables in Railway dashboard:
# - DATABASE_URL (automatically set by Railway PostgreSQL)
# - REDIS_URL (if using Railway Redis)
# - PORT (automatically set, usually 3000)
```

### Cloudflare Workers Issues

**Error**: Edge verification failing

**Solution**:
```typescript
// Ensure JWKS is accessible
const jwksUrl = 'https://janua.dev/.well-known/jwks.json';

// Add caching headers
export default {
  async fetch(request: Request): Promise<Response> {
    // Cache JWKS for 1 hour
    const cache = caches.default;
    const cached = await cache.match(jwksUrl);
    
    if (cached) {
      return cached;
    }
    
    const response = await fetch(jwksUrl);
    const headers = new Headers(response.headers);
    headers.set('Cache-Control', 'public, max-age=3600');
    
    const cachedResponse = new Response(response.body, {
      status: response.status,
      statusText: response.statusText,
      headers,
    });
    
    await cache.put(jwksUrl, cachedResponse.clone());
    return cachedResponse;
  },
};
```

## SDK Integration Issues

### Next.js Middleware Not Working

**Error**: Protected routes accessible without authentication

**Solution**:
```typescript
// middleware.ts
import { withJanua } from '@janua/nextjs/middleware';

export const config = {
  matcher: [
    /*
     * Match all request paths except:
     * - api routes
     * - static files
     * - public routes
     */
    '/((?!api|_next/static|_next/image|favicon.ico|public|sign-in|sign-up).*)',
  ],
};

export default withJanua({
  publicRoutes: ['/sign-in', '/sign-up', '/'],
  audience: process.env.JANUA_AUDIENCE!,
  issuer: process.env.JANUA_ISSUER!,
  jwksUrl: process.env.JANUA_JWKS_URL!,
});
```

### React Hooks Not Working

**Error**: `useUser()` returns null

**Solution**:
```tsx
// Ensure JanuaProvider wraps your app
// app/layout.tsx or _app.tsx
import { JanuaProvider } from '@janua/nextjs';

export default function RootLayout({ children }) {
  return (
    <html>
      <body>
        <JanuaProvider
          audience={process.env.NEXT_PUBLIC_JANUA_AUDIENCE}
          issuer={process.env.NEXT_PUBLIC_JANUA_ISSUER}
        >
          {children}
        </JanuaProvider>
      </body>
    </html>
  );
}
```

## Performance Issues

### Slow API Response Times

**Diagnostic Steps**:
```bash
# Check API health
curl https://janua.dev/api/health

# Monitor database queries
yarn workspace @janua/api dev:debug

# Check for N+1 queries in logs
```

**Solutions**:
1. Enable query logging to identify slow queries
2. Add database indexes for frequently queried fields
3. Implement caching with Redis
4. Use DataLoader for batching in GraphQL

### High Memory Usage

**Solution**:
```javascript
// Add memory monitoring
if (process.env.NODE_ENV === 'production') {
  setInterval(() => {
    const usage = process.memoryUsage();
    console.log('Memory Usage:', {
      rss: `${Math.round(usage.rss / 1024 / 1024)}MB`,
      heapTotal: `${Math.round(usage.heapTotal / 1024 / 1024)}MB`,
      heapUsed: `${Math.round(usage.heapUsed / 1024 / 1024)}MB`,
    });
  }, 60000); // Log every minute
}

// Set Node.js memory limit
// package.json
{
  "scripts": {
    "start": "node --max-old-space-size=2048 dist/main.js"
  }
}
```

## Development Environment

### Port Already in Use

**Error**: `Error: listen EADDRINUSE: address already in use :::3000`

**Solution**:
```bash
# Find process using the port
lsof -i :3000  # macOS/Linux
netstat -ano | findstr :3000  # Windows

# Kill the process
kill -9 <PID>  # macOS/Linux
taskkill /PID <PID> /F  # Windows

# Or use different ports
PORT=3001 yarn dev
```

### Yarn Workspace Issues

**Error**: `Cannot find module '@janua/core'

**Solution**:
```bash
# Clear all node_modules
find . -name "node_modules" -type d -prune -exec rm -rf {} +

# Clear yarn cache
yarn cache clean

# Reinstall everything
yarn install

# Build shared packages first
yarn workspace @janua/core build
yarn workspace @janua/database build
yarn workspace @janua/typescript-sdk build

# Then build apps
yarn build
```

### Git Hooks Not Running

**Error**: Commits not following conventional format

**Solution**:
```bash
# Install husky
yarn husky install

# Add commit-msg hook
yarn husky add .husky/commit-msg 'yarn commitlint --edit $1'

# Add pre-commit hook
yarn husky add .husky/pre-commit 'yarn lint-staged'

# Make hooks executable
chmod +x .husky/*
```

## Getting Help

### Debug Mode

Enable verbose logging for troubleshooting:

```bash
# API debug mode
DEBUG=janua:* yarn workspace @janua/api dev

# Next.js verbose logging
NEXT_PUBLIC_DEBUG=true yarn workspace @janua/admin dev

# Database query logging
DATABASE_LOGGING=true yarn dev
```

### Log Locations

- **API Logs**: `apps/api/logs/`
- **Admin Logs**: Check browser console and network tab
- **Build Logs**: `.turbo/` and individual app `.next/` directories
- **Database Logs**: PostgreSQL logs in Docker or system logs

### Support Channels

1. **GitHub Issues**: For bug reports and feature requests
2. **Discord**: Real-time help from the community
3. **Email**: dev-support@janua.dev for critical issues
4. **Documentation**: Check [docs/](../docs/) for detailed guides

### Reporting Issues

When reporting issues, include:

1. **Environment**:
   - OS and version
   - Node.js version (`node -v`)
   - Yarn version (`yarn -v`)
   - Browser and version

2. **Steps to Reproduce**:
   - Exact commands run
   - Configuration files
   - Code snippets

3. **Error Details**:
   - Full error message
   - Stack trace
   - Relevant logs

4. **What You've Tried**:
   - Solutions attempted
   - Workarounds discovered

## Common Commands Reference

```bash
# Development
yarn dev                  # Start all services
yarn build               # Build all packages
yarn test                # Run all tests
yarn lint                # Lint all code
yarn typecheck           # Check TypeScript

# Database
yarn db:migrate          # Run migrations
yarn db:seed            # Seed database
yarn db:reset           # Reset database

# Troubleshooting
yarn clean              # Clean all build artifacts
yarn reinstall          # Clean and reinstall deps
yarn debug              # Start with debug logging

# Production
yarn start              # Start production servers
yarn build:prod         # Production build
```