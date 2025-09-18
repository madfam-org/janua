# Plinto Developer Getting Started Guide

Complete developer onboarding guide for the Plinto Identity Platform with step-by-step implementation examples.

## 🚀 Quick Start

Get started with Plinto in under 5 minutes using our comprehensive SDK ecosystem.

### 1. Choose Your Stack

| Frontend | Backend | Mobile | Description |
|----------|---------|---------|-------------|
| 🌐 **React** | 🐍 **Python** | 📱 **React Native** | Full-stack web + mobile |
| ⚛️ **Next.js** | 🦀 **Go** | 🎯 **Flutter** | Server-side rendering |
| 🌟 **Vue.js** | 📦 **Node.js** | 📱 **Native iOS/Android** | Progressive web apps |

### 2. Installation

#### JavaScript/TypeScript
```bash
npm install @plinto/typescript-sdk
# or for specific frameworks
npm install @plinto/react-sdk @plinto/nextjs-sdk @plinto/vue-sdk
```

#### Python
```bash
pip install plinto-python
```

#### Go
```bash
go get github.com/plinto/go-sdk
```

#### Flutter
```yaml
dependencies:
  plinto: ^1.0.0
```

### 3. Basic Configuration

```typescript
import { PlintoClient } from '@plinto/typescript-sdk';

const plinto = new PlintoClient({
  baseURL: 'https://api.plinto.dev',
  apiKey: 'your-api-key', // Get from dashboard
  environment: 'production' // or 'development'
});
```

## 🏗️ Core Implementation Patterns

### Authentication Flow Implementation

#### 1. Email/Password Authentication
```typescript
// Sign up new user
const signUpResult = await plinto.auth.signUp({
  email: 'user@company.com',
  password: 'securePassword123',
  firstName: 'John',
  lastName: 'Doe'
});

// Sign in existing user
const signInResult = await plinto.auth.signIn({
  email: 'user@company.com',
  password: 'securePassword123'
});

// Access tokens
const { accessToken, refreshToken } = signInResult;
```

#### 2. Social Authentication
```typescript
// Initiate OAuth flow
const oauthUrl = await plinto.auth.oauth.getAuthUrl({
  provider: 'google', // google, github, microsoft, apple
  redirectUri: 'https://yourapp.com/callback',
  scopes: ['email', 'profile']
});

// Handle OAuth callback
const tokens = await plinto.auth.oauth.handleCallback({
  code: 'authorization-code-from-callback',
  state: 'csrf-state-token'
});
```

#### 3. Passwordless Authentication
```typescript
// Send magic link
await plinto.auth.magicLink.send({
  email: 'user@company.com',
  redirectUri: 'https://yourapp.com/dashboard'
});

// Verify magic link
const result = await plinto.auth.magicLink.verify({
  token: 'magic-link-token-from-email'
});
```

#### 4. Multi-Factor Authentication
```typescript
// Enable MFA for user
const mfaSetup = await plinto.auth.mfa.setup({
  type: 'totp' // or 'sms'
});

// Verify TOTP code
const verified = await plinto.auth.mfa.verify({
  code: '123456',
  type: 'totp'
});
```

### React Integration Example

```tsx
import React, { useEffect, useState } from 'react';
import { usePlinto, PlintoProvider } from '@plinto/react-sdk';

// App root with Plinto provider
function App() {
  return (
    <PlintoProvider
      baseURL="https://api.plinto.dev"
      apiKey="your-api-key">
      <AuthenticatedApp />
    </PlintoProvider>
  );
}

// Component using Plinto hooks
function AuthenticatedApp() {
  const { user, signIn, signOut, isLoading } = usePlinto();

  if (isLoading) return <div>Loading...</div>;

  if (!user) {
    return <LoginForm onSignIn={signIn} />;
  }

  return (
    <div>
      <h1>Welcome, {user.firstName}!</h1>
      <button onClick={signOut}>Sign Out</button>
    </div>
  );
}

// Login form component
function LoginForm({ onSignIn }) {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault();
    try {
      await onSignIn({ email, password });
    } catch (error) {
      console.error('Sign in failed:', error);
    }
  };

  return (
    <form onSubmit={handleSubmit}>
      <input
        type="email"
        value={email}
        onChange={(e) => setEmail(e.target.value)}
        placeholder="Email"
        required
      />
      <input
        type="password"
        value={password}
        onChange={(e) => setPassword(e.target.value)}
        placeholder="Password"
        required
      />
      <button type="submit">Sign In</button>
    </form>
  );
}
```

### Next.js Integration Example

```typescript
// pages/api/auth/[...plinto].ts
import { PlintoNextAuth } from '@plinto/nextjs-sdk';

export default PlintoNextAuth({
  apiKey: process.env.PLINTO_API_KEY!,
  baseURL: process.env.PLINTO_BASE_URL!,
  callbacks: {
    async signIn({ user, account, profile }) {
      // Custom sign-in logic
      return true;
    },
    async session({ session, token }) {
      // Add custom session data
      session.organizationId = token.organizationId;
      return session;
    }
  }
});
```

```tsx
// pages/_app.tsx
import { SessionProvider } from '@plinto/nextjs-sdk';
import type { AppProps } from 'next/app';

export default function App({
  Component,
  pageProps: { session, ...pageProps }
}: AppProps) {
  return (
    <SessionProvider session={session}>
      <Component {...pageProps} />
    </SessionProvider>
  );
}
```

```tsx
// pages/dashboard.tsx
import { useSession, getServerSideProps } from '@plinto/nextjs-sdk';

export default function Dashboard() {
  const { data: session, status } = useSession();

  if (status === 'loading') return <p>Loading...</p>;
  if (status === 'unauthenticated') return <p>Access Denied</p>;

  return (
    <div>
      <h1>Dashboard</h1>
      <p>Welcome, {session?.user?.email}!</p>
    </div>
  );
}

export const getServerSideProps = getServerSideProps({
  requireAuth: true
});
```

### Python/FastAPI Backend Example

```python
from fastapi import FastAPI, Depends, HTTPException
from plinto import PlintoClient, verify_token

app = FastAPI()
plinto = PlintoClient(
    api_key="your-api-key",
    base_url="https://api.plinto.dev"
)

# Authentication dependency
async def get_current_user(token: str = Depends(verify_token)):
    try:
        user = await plinto.auth.verify_token(token)
        return user
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")

@app.post("/api/users")
async def create_user(user_data: dict, current_user=Depends(get_current_user)):
    # Ensure user has admin permissions
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin required")

    new_user = await plinto.users.create(user_data)
    return new_user

@app.get("/api/profile")
async def get_profile(current_user=Depends(get_current_user)):
    return {
        "id": current_user.id,
        "email": current_user.email,
        "firstName": current_user.first_name,
        "lastName": current_user.last_name
    }
```

### Go Backend Example

```go
package main

import (
    "context"
    "log"
    "net/http"

    "github.com/gin-gonic/gin"
    "github.com/plinto/go-sdk"
)

func main() {
    client := plinto.NewClient(&plinto.Config{
        APIKey:  "your-api-key",
        BaseURL: "https://api.plinto.dev",
    })

    r := gin.Default()

    // Authentication middleware
    r.Use(authMiddleware(client))

    r.GET("/profile", getProfile(client))
    r.POST("/users", createUser(client))

    log.Fatal(r.Run(":8080"))
}

func authMiddleware(client *plinto.Client) gin.HandlerFunc {
    return func(c *gin.Context) {
        token := c.GetHeader("Authorization")
        if token == "" {
            c.JSON(http.StatusUnauthorized, gin.H{"error": "Missing token"})
            c.Abort()
            return
        }

        user, err := client.Auth.VerifyToken(context.Background(), token)
        if err != nil {
            c.JSON(http.StatusUnauthorized, gin.H{"error": "Invalid token"})
            c.Abort()
            return
        }

        c.Set("user", user)
        c.Next()
    }
}

func getProfile(client *plinto.Client) gin.HandlerFunc {
    return func(c *gin.Context) {
        user := c.MustGet("user").(*plinto.User)
        c.JSON(http.StatusOK, user)
    }
}
```

### Flutter Mobile Example

```dart
import 'package:flutter/material.dart';
import 'package:plinto/plinto.dart';

void main() {
  runApp(MyApp());
}

class MyApp extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Plinto Demo',
      home: PlintoProvider(
        config: PlintoConfig(
          apiKey: 'your-api-key',
          baseUrl: 'https://api.plinto.dev',
        ),
        child: AuthScreen(),
      ),
    );
  }
}

class AuthScreen extends StatefulWidget {
  @override
  _AuthScreenState createState() => _AuthScreenState();
}

class _AuthScreenState extends State<AuthScreen> {
  final _emailController = TextEditingController();
  final _passwordController = TextEditingController();

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text('Sign In')),
      body: Padding(
        padding: EdgeInsets.all(16.0),
        child: Column(
          children: [
            TextField(
              controller: _emailController,
              decoration: InputDecoration(labelText: 'Email'),
              keyboardType: TextInputType.emailAddress,
            ),
            TextField(
              controller: _passwordController,
              decoration: InputDecoration(labelText: 'Password'),
              obscureText: true,
            ),
            SizedBox(height: 20),
            ElevatedButton(
              onPressed: _signIn,
              child: Text('Sign In'),
            ),
            TextButton(
              onPressed: _signInWithGoogle,
              child: Text('Sign In with Google'),
            ),
          ],
        ),
      ),
    );
  }

  void _signIn() async {
    try {
      final result = await Plinto.of(context).auth.signIn(
        email: _emailController.text,
        password: _passwordController.text,
      );

      Navigator.pushReplacement(
        context,
        MaterialPageRoute(builder: (context) => DashboardScreen()),
      );
    } catch (error) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Sign in failed: $error')),
      );
    }
  }

  void _signInWithGoogle() async {
    try {
      await Plinto.of(context).auth.signInWithOAuth('google');
      Navigator.pushReplacement(
        context,
        MaterialPageRoute(builder: (context) => DashboardScreen()),
      );
    } catch (error) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Google sign in failed: $error')),
      );
    }
  }
}
```

## 🏢 Organization Management

### Creating Organizations
```typescript
const organization = await plinto.organizations.create({
  name: 'Acme Corporation',
  slug: 'acme-corp',
  description: 'Leading provider of anvils and roadrunner traps',
  billingEmail: 'billing@acme.com'
});
```

### Managing Members
```typescript
// Invite user to organization
await plinto.organizations.inviteUser(organizationId, {
  email: 'user@company.com',
  role: 'member', // owner, admin, member, viewer
  message: 'Welcome to our organization!'
});

// Update member role
await plinto.organizations.updateMember(organizationId, userId, {
  role: 'admin'
});

// Remove member
await plinto.organizations.removeMember(organizationId, userId);
```

### Custom Roles
```typescript
// Create custom role
const customRole = await plinto.organizations.createRole(organizationId, {
  name: 'Content Editor',
  description: 'Can edit content but not manage users',
  permissions: [
    'content:read',
    'content:write',
    'content:delete'
  ]
});

// Assign custom role
await plinto.organizations.assignRole(organizationId, userId, customRole.id);
```

## 🔗 Webhook Integration

### Setting Up Webhooks
```typescript
// Create webhook endpoint
const webhook = await plinto.webhooks.create({
  url: 'https://yourapp.com/webhooks/plinto',
  events: [
    'user.created',
    'user.updated',
    'user.deleted',
    'organization.member_added',
    'session.expired'
  ],
  secret: 'your-webhook-secret'
});
```

### Handling Webhook Events
```typescript
import crypto from 'crypto';

app.post('/webhooks/plinto', (req, res) => {
  const signature = req.headers['x-plinto-signature'];
  const payload = JSON.stringify(req.body);
  const secret = 'your-webhook-secret';

  // Verify webhook signature
  const expectedSignature = crypto
    .createHmac('sha256', secret)
    .update(payload)
    .digest('hex');

  if (signature !== `sha256=${expectedSignature}`) {
    return res.status(401).json({ error: 'Invalid signature' });
  }

  // Process webhook event
  const { event_type, data } = req.body;

  switch (event_type) {
    case 'user.created':
      console.log('New user created:', data.user);
      // Add user to your system
      break;
    case 'user.updated':
      console.log('User updated:', data.user);
      // Update user in your system
      break;
    case 'session.expired':
      console.log('Session expired:', data.session);
      // Handle session cleanup
      break;
  }

  res.status(200).json({ status: 'processed' });
});
```

## 🔐 Advanced Security Features

### Passkey Authentication
```typescript
// Check if passkeys are supported
const isSupported = await plinto.auth.passkeys.isSupported();

// Register a new passkey
const registration = await plinto.auth.passkeys.register({
  username: 'user@company.com',
  displayName: 'John Doe'
});

// Authenticate with passkey
const authentication = await plinto.auth.passkeys.authenticate();
```

### Session Management
```typescript
// Get current session
const session = await plinto.auth.getCurrentSession();

// Refresh session
const newTokens = await plinto.auth.refreshSession();

// Revoke session
await plinto.auth.revokeSession(sessionId);

// Get all user sessions
const sessions = await plinto.auth.getSessions(userId);
```

### Rate Limiting Handling
```typescript
try {
  await plinto.auth.signIn({ email, password });
} catch (error) {
  if (error.code === 'RATE_LIMITED') {
    const retryAfter = error.details.retryAfter;
    console.log(`Rate limited. Retry after ${retryAfter} seconds`);
  }
}
```

## 📊 Analytics & Monitoring

### User Analytics
```typescript
// Get user activity
const activity = await plinto.analytics.getUserActivity(userId, {
  startDate: '2024-01-01',
  endDate: '2024-01-31',
  granularity: 'day'
});

// Get organization metrics
const metrics = await plinto.analytics.getOrganizationMetrics(orgId, {
  metrics: ['active_users', 'sign_ins', 'sign_ups'],
  period: 'last_30_days'
});
```

### Custom Events
```typescript
// Track custom events
await plinto.analytics.track({
  event: 'feature_used',
  userId: 'user-123',
  properties: {
    feature: 'advanced_search',
    plan: 'enterprise'
  }
});
```

## 🚨 Error Handling

### Common Error Patterns
```typescript
import { PlintoError, ErrorCodes } from '@plinto/typescript-sdk';

try {
  await plinto.auth.signIn({ email, password });
} catch (error) {
  if (error instanceof PlintoError) {
    switch (error.code) {
      case ErrorCodes.INVALID_CREDENTIALS:
        showError('Invalid email or password');
        break;
      case ErrorCodes.ACCOUNT_LOCKED:
        showError('Account locked. Contact support.');
        break;
      case ErrorCodes.MFA_REQUIRED:
        redirectToMFA();
        break;
      case ErrorCodes.RATE_LIMITED:
        showError(`Too many attempts. Try again in ${error.details.retryAfter}s`);
        break;
      default:
        showError('Sign in failed. Please try again.');
    }
  }
}
```

## 🧪 Testing

### Unit Testing
```typescript
import { PlintoClient } from '@plinto/typescript-sdk';
import { jest } from '@jest/globals';

// Mock Plinto client for testing
jest.mock('@plinto/typescript-sdk');

const mockPlinto = {
  auth: {
    signIn: jest.fn(),
    signOut: jest.fn()
  }
};

describe('Authentication', () => {
  test('should sign in user successfully', async () => {
    mockPlinto.auth.signIn.mockResolvedValue({
      user: { id: '123', email: 'test@example.com' },
      tokens: { accessToken: 'token123' }
    });

    const result = await signInUser('test@example.com', 'password');
    expect(result.user.email).toBe('test@example.com');
  });
});
```

### Integration Testing
```typescript
// Test with real Plinto API using test environment
const testPlinto = new PlintoClient({
  baseURL: 'https://api-test.plinto.dev',
  apiKey: process.env.PLINTO_TEST_API_KEY
});

describe('Integration Tests', () => {
  test('should create and delete user', async () => {
    // Create test user
    const user = await testPlinto.users.create({
      email: 'test@example.com',
      password: 'testPassword123'
    });

    expect(user.email).toBe('test@example.com');

    // Clean up
    await testPlinto.users.delete(user.id);
  });
});
```

## 📚 Additional Resources

### Code Examples Repository
- [GitHub: plinto-examples](https://github.com/plinto/examples)
- [CodeSandbox Demos](https://codesandbox.io/plinto)
- [Interactive Playground](https://playground.plinto.dev)

### Community & Support
- [Developer Discord](https://discord.gg/plinto)
- [Stack Overflow](https://stackoverflow.com/questions/tagged/plinto)
- [Community Forum](https://community.plinto.dev)

### Documentation Links
- [API Reference](https://docs.plinto.dev/api)
- [SDK Documentation](https://docs.plinto.dev/sdks)
- [Integration Guides](https://docs.plinto.dev/integrations)
- [Security Best Practices](https://docs.plinto.dev/security)

---

## 🎉 Next Steps

1. **🚀 Set up your first application** using the examples above
2. **🔧 Configure authentication** for your specific use case
3. **🏢 Set up organizations** if building a B2B application
4. **🔗 Add webhooks** for real-time event handling
5. **📊 Implement analytics** to track user behavior
6. **🔐 Add advanced security** features like MFA and passkeys

Need help? Contact our developer support team at [developers@plinto.dev](mailto:developers@plinto.dev) or join our [Discord community](https://discord.gg/plinto).