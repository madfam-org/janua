# Plinto Next.js Example Application

A production-ready example demonstrating Plinto authentication integration with Next.js 14 App Router.

## Features Demonstrated

- ✅ User authentication (sign in/sign up)
- ✅ Protected routes and session management
- ✅ User profile management
- ✅ OAuth provider integration
- ✅ Organization management
- ✅ Active sessions display
- ✅ Responsive UI with Tailwind CSS
- ✅ TypeScript with full type safety
- ✅ Production error handling

## Quick Start

### 1. Install Dependencies

```bash
npm install
# or
yarn install
# or
pnpm install
```

### 2. Configure Environment Variables

Create a `.env.local` file:

```env
# Required
NEXT_PUBLIC_PLINTO_API_URL=https://api.plinto.dev
NEXT_PUBLIC_PLINTO_API_KEY=your_api_key_here

# Optional
NEXT_PUBLIC_PLINTO_REDIRECT_URL=http://localhost:3000/auth/callback
```

### 3. Run Development Server

```bash
npm run dev
# or
yarn dev
# or
pnpm dev
```

Open [http://localhost:3000](http://localhost:3000) in your browser.

## Project Structure

```
nextjs-app/
├── app/
│   ├── layout.tsx          # Root layout with PlintoProvider
│   ├── page.tsx            # Home page with auth check
│   ├── globals.css         # Global styles
│   └── components/
│       ├── LoginForm.tsx   # Authentication form
│       ├── UserProfile.tsx # User profile display
│       └── Dashboard.tsx   # Session & org management
├── public/                 # Static assets
├── package.json           # Dependencies
└── README.md             # This file
```

## Code Examples

### Basic Authentication

```typescript
import { useAuth } from '@plinto/react-sdk';

function MyComponent() {
  const { isAuthenticated, user, signIn, signOut } = useAuth();

  const handleLogin = async () => {
    try {
      await signIn('user@example.com', 'password');
    } catch (error) {
      console.error('Login failed:', error);
    }
  };

  return (
    <div>
      {isAuthenticated ? (
        <p>Welcome, {user?.email}!</p>
      ) : (
        <button onClick={handleLogin}>Sign In</button>
      )}
    </div>
  );
}
```

### Protected Routes

```typescript
// app/protected/page.tsx
'use client';

import { useAuth } from '@plinto/react-sdk';
import { useRouter } from 'next/navigation';
import { useEffect } from 'react';

export default function ProtectedPage() {
  const { isAuthenticated, isLoading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!isLoading && !isAuthenticated) {
      router.push('/');
    }
  }, [isAuthenticated, isLoading, router]);

  if (isLoading || !isAuthenticated) {
    return <div>Loading...</div>;
  }

  return <div>Protected content here</div>;
}
```

### Organization Management

```typescript
import { useOrganization } from '@plinto/react-sdk';

function OrgSelector() {
  const { organization, organizations, switchOrganization } = useOrganization();

  return (
    <select 
      value={organization?.id} 
      onChange={(e) => switchOrganization(e.target.value)}
    >
      {organizations?.map((org) => (
        <option key={org.id} value={org.id}>
          {org.name}
        </option>
      ))}
    </select>
  );
}
```

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `NEXT_PUBLIC_PLINTO_API_URL` | Yes | Plinto API endpoint |
| `NEXT_PUBLIC_PLINTO_API_KEY` | Yes | Your Plinto API key |
| `NEXT_PUBLIC_PLINTO_REDIRECT_URL` | No | OAuth callback URL |
| `NEXT_PUBLIC_PLINTO_ENVIRONMENT` | No | 'development' or 'production' |

## Deployment

### Vercel

[![Deploy with Vercel](https://vercel.com/button)](https://vercel.com/new/clone?repository-url=https://github.com/madfam-io/plinto/tree/main/examples/nextjs-app)

### Docker

```dockerfile
FROM node:20-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM node:20-alpine
WORKDIR /app
COPY --from=builder /app/.next ./.next
COPY --from=builder /app/node_modules ./node_modules
COPY --from=builder /app/package*.json ./
COPY --from=builder /app/public ./public

EXPOSE 3000
CMD ["npm", "start"]
```

## Testing

```bash
# Run tests
npm test

# Run with coverage
npm run test:coverage

# E2E tests
npm run test:e2e
```

## Security Best Practices

1. **Never expose API keys in client code** - Use environment variables
2. **Validate all user inputs** - Prevent XSS and injection attacks
3. **Use HTTPS in production** - Ensure secure data transmission
4. **Implement rate limiting** - Prevent abuse of authentication endpoints
5. **Enable MFA** - Add extra security layer for sensitive accounts
6. **Regular dependency updates** - Keep SDKs and packages current

## Troubleshooting

### Common Issues

**"API key is invalid"**
- Verify your API key in Plinto dashboard
- Ensure environment variables are loaded correctly

**"CORS error"**
- Add your domain to allowed origins in Plinto settings
- Check API URL configuration

**"Session expired"**
- Plinto automatically refreshes tokens
- If persistent, check token storage configuration

## Resources

- [Plinto Documentation](https://docs.plinto.dev)
- [SDK Reference](https://docs.plinto.dev/sdk/react)
- [API Reference](https://docs.plinto.dev/api)
- [Security Best Practices](https://docs.plinto.dev/security)

## Support

- **GitHub Issues**: [github.com/madfam-io/plinto/issues](https://github.com/madfam-io/plinto/issues)
- **Discord Community**: [discord.gg/plinto](https://discord.gg/plinto)
- **Email Support**: support@plinto.dev

## License

MIT - See [LICENSE](../../LICENSE) for details