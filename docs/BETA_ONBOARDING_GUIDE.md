# Plinto Beta Onboarding Guide

**Version**: 1.0.0 (Beta)  
**Last Updated**: November 16, 2025  
**Status**: Ready for Beta Users

---

## 🎯 Welcome to Plinto Beta!

Thank you for joining the Plinto beta program! This guide will help you integrate Plinto authentication into your application in less than 5 minutes.

### What You Get
- ✅ Complete authentication system (email, OAuth, MFA, passkeys)
- ✅ Production-ready React components
- ✅ TypeScript SDK with full type safety
- ✅ Interactive API documentation
- ✅ Actionable error messages
- ✅ Self-hosting option (optional)

### Beta Program Benefits
- **Early Access**: Be among the first to use Plinto
- **Pricing Lock**: Beta pricing guaranteed for 12 months
- **Priority Support**: Direct access to engineering team
- **Influence Roadmap**: Your feedback shapes future features

---

## 📋 Prerequisites

### Required
- Node.js 18+ or Python 3.11+
- Modern web framework (React, Vue, Angular, Next.js, etc.)
- Package manager (npm, yarn, pnpm)

### Optional
- Docker (for self-hosting)
- PostgreSQL 14+ (for self-hosting)
- Redis 6+ (for caching and rate limiting)

---

## 🚀 Quick Start (React/Next.js)

### Step 1: Install Packages (1 minute)

```bash
npm install @plinto/ui @plinto/typescript-sdk
# or
yarn add @plinto/ui @plinto/typescript-sdk
# or
pnpm add @plinto/ui @plinto/typescript-sdk
```

### Step 2: Configure Client (1 minute)

Create `lib/plinto-client.ts`:

```typescript
import { PlintoClient } from '@plinto/typescript-sdk'

export const plintoClient = new PlintoClient({
  apiUrl: process.env.NEXT_PUBLIC_PLINTO_API_URL || 'https://api.plinto.dev',
  publishableKey: process.env.NEXT_PUBLIC_PLINTO_PUBLISHABLE_KEY!,
})
```

### Step 3: Add Provider (1 minute)

**Next.js App Router** (`app/providers.tsx`):

```typescript
'use client'

import { PlintoProvider } from '@plinto/ui'
import { plintoClient } from '@/lib/plinto-client'

export function Providers({ children }: { children: React.Node }) {
  return (
    <PlintoProvider client={plintoClient}>
      {children}
    </PlintoProvider>
  )
}
```

Wrap your app in `app/layout.tsx`:

```typescript
import { Providers } from './providers'

export default function RootLayout({ children }) {
  return (
    <html>
      <body>
        <Providers>{children}</Providers>
      </body>
    </html>
  )
}
```

### Step 4: Add Authentication (2 minutes)

**Sign-In Page** (`app/auth/signin/page.tsx`):

```typescript
'use client'

import { SignIn } from '@plinto/ui'
import { useRouter } from 'next/navigation'

export default function SignInPage() {
  const router = useRouter()

  return (
    <div className="min-h-screen flex items-center justify-center">
      <SignIn
        onSuccess={() => router.push('/dashboard')}
        onError={(error) => console.error('Sign-in error:', error)}
      />
    </div>
  )
}
```

**Protected Dashboard**:

```typescript
'use client'

import { useAuth } from '@plinto/ui'
import { useRouter } from 'next/navigation'
import { useEffect } from 'react'

export default function Dashboard() {
  const { user, isLoading } = useAuth()
  const router = useRouter()

  useEffect(() => {
    if (!isLoading && !user) {
      router.push('/auth/signin')
    }
  }, [user, isLoading, router])

  if (isLoading) {
    return <div>Loading...</div>
  }

  return (
    <div>
      <h1>Welcome, {user?.email}!</h1>
      {/* Your dashboard content */}
    </div>
  )
}
```

**That's it!** You now have a complete authentication system. 🎉

---

## 🔑 Getting Your API Keys

### Beta Environment

For beta testing, we provide a shared beta environment:

- **API URL**: `https://beta-api.plinto.dev`
- **Publishable Key**: Provided in your beta invitation email

### Self-Hosted (Optional)

If you prefer to self-host:

1. Follow the [Production Deployment Guide](DEPLOYMENT.md)
2. Set up PostgreSQL and Redis
3. Configure environment variables in `.env`
4. Run: `docker-compose up -d`

Your API will be available at `http://localhost:8000`.

---

## 📚 Complete Documentation

### Essential Guides
1. **[React Quickstart](REACT_QUICKSTART.md)** - Full React/Next.js integration guide
2. **[API Documentation](docs/api/API_DOCUMENTATION.md)** - Complete API reference
3. **[Deployment Guide](DEPLOYMENT.md)** - Production deployment options

### Interactive Documentation
- **Swagger UI**: https://beta-api.plinto.dev/docs (Try endpoints live)
- **ReDoc**: https://beta-api.plinto.dev/redoc (Beautiful API docs)

### Component Documentation
All authentication components with props and examples:
- `SignIn` - Email/password authentication
- `SignUp` - User registration
- `EmailVerification` - Email verification flow
- `PasswordReset` - Password recovery
- `MFASetup` - Multi-factor authentication
- `PhoneVerification` - SMS verification
- `PasskeySetup` - WebAuthn passkeys
- `OrganizationSwitcher` - Multi-tenant support

---

## 🧪 Testing Your Integration

### 1. Test Error Messages
We've built comprehensive, actionable error messages. Test them:

```bash
# Try invalid credentials
Email: wrong@example.com
Password: WrongPassword123!

# Expected: Clear error with 3+ recovery steps
```

See [Manual Error Message Testing Checklist](testing/MANUAL_ERROR_MESSAGE_TESTING_CHECKLIST.md) for complete test scenarios.

### 2. Test Authentication Flow
1. Sign up with test email
2. Verify email (check inbox or use test codes)
3. Sign in with credentials
4. Access protected routes
5. Sign out

### 3. Test Edge Cases
- Weak passwords
- Invalid email formats
- Network errors (go offline)
- Rate limiting (multiple failed attempts)
- Session expiration

---

## 🐛 Reporting Issues

### Beta Bug Reports

Please report bugs via:
- **GitHub Issues**: https://github.com/plinto/plinto/issues
- **Email**: beta@plinto.dev
- **Discord**: https://discord.gg/plinto (Coming soon)

### Issue Template

```
**Description**: What went wrong?
**Steps to Reproduce**: 
1. Navigate to...
2. Click on...
3. See error...

**Expected Behavior**: What should happen?
**Actual Behavior**: What actually happened?
**Environment**: 
- OS: macOS/Windows/Linux
- Browser: Chrome/Firefox/Safari
- Framework: Next.js 14, React 18, etc.

**Error Messages**: (Copy full error message)
**Screenshots**: (If applicable)
```

---

## 💬 Getting Help

### Support Channels

**Priority Support (Beta Users)**:
- **Email**: beta@plinto.dev (Response within 4 hours during business hours)
- **Office Hours**: Wednesdays 2-4pm EST (Zoom link in beta email)
- **GitHub Discussions**: https://github.com/plinto/plinto/discussions

**Resources**:
- **Documentation**: https://docs.plinto.dev
- **API Status**: https://status.plinto.dev
- **Changelog**: https://github.com/plinto/plinto/blob/main/CHANGELOG.md

### Common Questions

**Q: Where do I get my publishable key?**  
A: Check your beta invitation email or contact beta@plinto.dev

**Q: Can I use Plinto in production during beta?**  
A: Beta is stable but not recommended for production. GA expected Q1 2026.

**Q: What happens after beta ends?**  
A: Your integration continues to work. Beta pricing honored for 12 months.

**Q: Can I self-host during beta?**  
A: Yes! Follow the [Deployment Guide](DEPLOYMENT.md).

**Q: What if I need a feature that's not available?**  
A: Email beta@plinto.dev with your use case. We prioritize beta user requests.

---

## 🎯 Success Criteria

You'll know your integration is successful when:

✅ **Sign-up works**: New users can create accounts  
✅ **Sign-in works**: Users can authenticate  
✅ **Protected routes work**: Authentication is enforced  
✅ **Error messages help**: Users can self-resolve issues  
✅ **Session management works**: Users stay authenticated  
✅ **Sign-out works**: Users can log out properly

---

## 🚀 Next Steps

### After Basic Integration

1. **Add MFA**: Enable two-factor authentication
   ```typescript
   import { MFASetup } from '@plinto/ui'
   
   <MFASetup onSuccess={() => console.log('MFA enabled')} />
   ```

2. **Add OAuth**: Social login with Google, GitHub, etc.
   ```typescript
   <SignIn 
     socialProviders={['google', 'github']}
   />
   ```

3. **Add Organizations**: Multi-tenant support
   ```typescript
   import { OrganizationSwitcher } from '@plinto/ui'
   
   <OrganizationSwitcher />
   ```

4. **Add Passkeys**: Passwordless WebAuthn authentication
   ```typescript
   import { PasskeySetup } from '@plinto/ui'
   
   <PasskeySetup />
   ```

### Advanced Features

- **Session Management**: Track and revoke active sessions
- **Device Management**: Manage trusted devices
- **Audit Logs**: Security event tracking
- **Custom Webhooks**: Real-time event notifications
- **RBAC**: Role-based access control
- **SAML/SSO**: Enterprise single sign-on
- **SCIM**: User provisioning

See [API Documentation](docs/api/API_DOCUMENTATION.md) for implementation details.

---

## 📊 Beta Feedback

### We Value Your Input!

Please share feedback on:
- **Integration Experience**: How easy was setup?
- **Documentation Quality**: Was anything unclear?
- **Error Messages**: Were errors helpful?
- **Performance**: Any speed issues?
- **Feature Requests**: What's missing?

### Feedback Channels

- **Survey**: https://forms.plinto.dev/beta-feedback
- **Email**: beta@plinto.dev
- **Office Hours**: Wednesdays 2-4pm EST

### Incentives

- **Bug Bounty**: $50-500 for valid bugs
- **Feature Influence**: Top requests prioritized
- **Beta Credits**: Feedback = free usage credits
- **Early Access**: New features before GA

---

## 📅 Beta Timeline

### Current Phase: Private Beta (November 2025)
- Limited to 50 beta users
- Weekly updates and improvements
- Direct engineering support

### Upcoming Milestones
- **December 2025**: Public Beta (500 users)
- **January 2026**: Feature freeze, stability focus
- **February 2026**: Security audit, compliance certification
- **March 2026**: General Availability (GA)

---

## 🔒 Security & Privacy

### During Beta
- ✅ All data encrypted in transit (TLS 1.3)
- ✅ All data encrypted at rest (AES-256)
- ✅ SOC 2 Type II compliance in progress
- ✅ GDPR and CCPA compliant
- ✅ Regular security audits

### Data Handling
- **Beta Data**: May be reset/migrated before GA
- **Backups**: Daily backups, 30-day retention
- **Deletion**: Request via beta@plinto.dev

---

## 💰 Beta Pricing

### Free During Beta
- ✅ Unlimited users
- ✅ All authentication features
- ✅ MFA, OAuth, passkeys included
- ✅ Priority support

### Post-Beta Pricing (Locked for Beta Users)
- **Starter**: $0.005/MAU (vs $0.02 for Clerk)
- **Pro**: Custom enterprise pricing
- **Self-Hosted**: Free (MIT license)

Beta users get 12 months at beta pricing.

---

## 🎉 Welcome Aboard!

Thank you for being part of the Plinto beta journey. Your feedback and patience help us build the best authentication platform for developers.

**Let's build something great together!**

---

**Questions?** Email beta@plinto.dev  
**Issues?** https://github.com/plinto/plinto/issues  
**Stay Updated**: Follow @plinto on Twitter

**Happy Building! 🚀**
