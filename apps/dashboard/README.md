# Plinto Dashboard

> **Customer tenant management portal** for the Plinto platform

**Status:** Active Development · **Domain:** `app.plinto.dev` · **Port:** 3001

## 📋 Overview

The Plinto Dashboard is the primary customer-facing application where users manage their accounts, organizations, team members, and platform settings. Built with Next.js 14 and modern React patterns for optimal performance and user experience.

## 🚀 Quick Start

### Prerequisites

- Node.js 18+
- Yarn (workspace management)
- Access to Plinto API (local or remote)

### Installation

```bash
# From monorepo root
yarn install

# Navigate to dashboard
cd apps/dashboard

# Start development server
yarn dev
```

The dashboard will be available at [http://localhost:3001](http://localhost:3001)

### Environment Setup

Create a `.env.local` file in the dashboard directory:

```env
# API Configuration
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_APP_URL=http://localhost:3001

# Authentication
NEXT_PUBLIC_AUTH_DOMAIN=plinto.dev
NEXT_PUBLIC_JWT_ISSUER=https://plinto.dev

# Features
NEXT_PUBLIC_ENABLE_ANALYTICS=true
NEXT_PUBLIC_ENABLE_BILLING=true
NEXT_PUBLIC_ENABLE_SUPPORT=true

# External Services
NEXT_PUBLIC_POSTHOG_KEY=your-posthog-key
NEXT_PUBLIC_STRIPE_PUBLIC_KEY=your-stripe-key
```

## 🏗️ Architecture

### Project Structure

```
apps/dashboard/
├── app/                    # Next.js 14 App Router
│   ├── (auth)/            # Authentication routes
│   │   ├── login/         # Login page
│   │   ├── signup/        # Registration
│   │   └── forgot/        # Password recovery
│   ├── (dashboard)/       # Authenticated routes
│   │   ├── page.tsx       # Dashboard home
│   │   ├── settings/      # Account settings
│   │   ├── team/          # Team management
│   │   ├── billing/       # Subscription & billing
│   │   └── analytics/     # Usage analytics
│   ├── api/              # API routes (if needed)
│   ├── layout.tsx        # Root layout
│   └── globals.css       # Global styles
├── components/           # React components
│   ├── ui/              # UI components (local overrides)
│   ├── dashboard/       # Dashboard-specific components
│   ├── forms/           # Form components
│   └── charts/          # Data visualization
├── lib/                 # Utilities
│   ├── api/            # API client
│   ├── auth/           # Auth utilities
│   ├── hooks/          # Custom React hooks
│   └── utils/          # Helper functions
├── public/             # Static assets
└── styles/            # Additional styles
```

### Technology Stack

- **Framework:** Next.js 14 (App Router)
- **UI Library:** @plinto/ui (shared design system)
- **State Management:** TanStack Query v5
- **Forms:** React Hook Form + Zod validation
- **Tables:** TanStack Table v8
- **Charts:** Recharts
- **Styling:** Tailwind CSS + Radix UI

## 🎨 Features

### Core Functionality

#### 🔐 Authentication
- Email/password login
- Social authentication (Google, GitHub)
- Passkey/WebAuthn support
- Session management
- MFA/2FA support

#### 👥 Team Management
- Invite team members
- Role-based permissions
- Team activity logs
- Member provisioning/deprovisioning

#### 💳 Billing & Subscriptions
- Subscription management
- Payment method updates
- Invoice history
- Usage-based billing
- Plan upgrades/downgrades

#### 📊 Analytics Dashboard
- User activity metrics
- API usage statistics
- Performance monitoring
- Custom report generation

#### ⚙️ Settings
- Profile management
- Security settings
- API key management
- Webhook configuration
- Notification preferences

## 🧩 Components

### Shared Components from @plinto/ui

The dashboard leverages the shared design system:

```tsx
import { Button, Card, Input, Select } from '@plinto/ui';
import { useAuth } from '@plinto/react-sdk';
```

### Dashboard-Specific Components

```tsx
// components/dashboard/StatsCard.tsx
import { Card } from '@plinto/ui';

export function StatsCard({ title, value, change }) {
  return (
    <Card>
      <Card.Header>{title}</Card.Header>
      <Card.Content>
        <div className="text-3xl font-bold">{value}</div>
        <div className="text-sm text-muted">{change}% from last month</div>
      </Card.Content>
    </Card>
  );
}
```

## 🔌 API Integration

### Using TanStack Query

```tsx
// lib/api/queries.ts
import { useQuery } from '@tanstack/react-query';

export function useUserData() {
  return useQuery({
    queryKey: ['user'],
    queryFn: async () => {
      const response = await fetch('/api/v1/auth/me');
      return response.json();
    },
  });
}
```

### API Client Configuration

```tsx
// lib/api/client.ts
import { PlintoClient } from '@plinto/sdk';

export const plinto = new PlintoClient({
  apiUrl: process.env.NEXT_PUBLIC_API_URL,
  authDomain: process.env.NEXT_PUBLIC_AUTH_DOMAIN,
});
```

## 🧪 Testing

### Running Tests

```bash
# Unit tests
yarn test

# E2E tests
yarn test:e2e

# Coverage report
yarn test:coverage
```

### Test Structure

```
tests/
├── unit/              # Component tests
├── integration/       # API integration tests
└── e2e/              # End-to-end tests
```

## 🚢 Deployment

### Build for Production

```bash
# Build the application
yarn build

# Start production server
yarn start
```

### Vercel Deployment

The dashboard is configured for automatic deployment on Vercel:

1. Push to `main` branch triggers production deployment
2. Pull requests create preview deployments
3. Environment variables configured in Vercel dashboard

### Docker Support

```bash
# Build Docker image
docker build -t plinto-dashboard .

# Run container
docker run -p 3001:3001 plinto-dashboard
```

## 🔧 Configuration

### Tailwind Configuration

The dashboard extends the base Tailwind config from @plinto/ui:

```js
// tailwind.config.js
module.exports = {
  presets: [require('@plinto/ui/tailwind.config')],
  content: [
    './app/**/*.{js,ts,jsx,tsx}',
    './components/**/*.{js,ts,jsx,tsx}',
  ],
};
```

### TypeScript Configuration

```json
// tsconfig.json
{
  "extends": "../../tsconfig.base.json",
  "compilerOptions": {
    "paths": {
      "@/*": ["./app/*"],
      "@/components/*": ["./components/*"],
      "@/lib/*": ["./lib/*"]
    }
  }
}
```

## 📊 Performance

### Optimization Strategies

- **Code Splitting:** Automatic with Next.js App Router
- **Image Optimization:** Next.js Image component
- **Font Optimization:** Next.js Font optimization
- **Bundle Analysis:** `yarn analyze`
- **Lighthouse Score:** Target 95+ on all metrics

### Monitoring

- Real User Monitoring (RUM) via PostHog
- Error tracking with Sentry
- Performance monitoring with Vercel Analytics

## 🔒 Security

### Security Features

- **CSRF Protection:** Built into Next.js
- **XSS Prevention:** React's built-in protections
- **Content Security Policy:** Configured headers
- **Secure Cookies:** httpOnly, secure, sameSite
- **Rate Limiting:** API-level protection

### Authentication Flow

1. User enters credentials
2. API validates and returns JWT tokens
3. Tokens stored in secure cookies
4. Automatic token refresh
5. Session validation on each request

## 🛠️ Development

### Code Style

```bash
# Format code
yarn format

# Lint code
yarn lint

# Type checking
yarn typecheck
```

### Git Hooks

Pre-commit hooks ensure code quality:
- ESLint validation
- TypeScript checking
- Prettier formatting

## 🎯 Roadmap

### Current Sprint
- [ ] Complete team invitation flow
- [ ] Implement usage analytics
- [ ] Add export functionality

### Next Quarter
- [ ] Advanced filtering and search
- [ ] Bulk operations support
- [ ] API playground integration
- [ ] Custom dashboard widgets

## 📚 Resources

- [Next.js Documentation](https://nextjs.org/docs)
- [TanStack Query](https://tanstack.com/query)
- [Radix UI](https://radix-ui.com)
- [Tailwind CSS](https://tailwindcss.com)

## 🤝 Contributing

See the [Contributing Guide](../../CONTRIBUTING.md) for development guidelines.

## 📄 License

Part of the Plinto platform. See [LICENSE](../../LICENSE) in the root directory.