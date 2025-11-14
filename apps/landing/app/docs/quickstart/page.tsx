import { Metadata } from 'next'
import { CodeExample } from '@/components/CodeExample'

export const metadata: Metadata = {
  title: 'Quickstart - Plinto Documentation',
  description: 'Get started with Plinto in 5 minutes. Build your first authentication flow.',
}

export default function QuickstartPage() {
  return (
    <div className="prose prose-lg max-w-none">
      <h1>Quickstart Guide</h1>
      
      <p className="lead">
        Get up and running with Plinto in 5 minutes. This guide will walk you through 
        setting up authentication for a basic application.
      </p>

      <h2>Prerequisites</h2>
      <ul>
        <li>Node.js 18+ or Python 3.9+</li>
        <li>PostgreSQL 14+ (or use managed Plinto cloud)</li>
        <li>Redis 6+ (optional, for session management)</li>
      </ul>

      <h2>Step 1: Install the SDK</h2>
      <p>
        Choose your preferred SDK based on your application framework:
      </p>

      <CodeExample
        title="Install TypeScript SDK"
        language="bash"
        code={`npm install @plinto/typescript-sdk
# or
yarn add @plinto/typescript-sdk
# or
pnpm add @plinto/typescript-sdk`}
      />

      <CodeExample
        title="Install React SDK"
        language="bash"
        code={`npm install @plinto/react-sdk`}
      />

      <CodeExample
        title="Install Python SDK"
        language="bash"
        code={`pip install plinto-sdk`}
      />

      <h2>Step 2: Configure Environment Variables</h2>
      <p>
        Create a <code>.env</code> file in your project root:
      </p>

      <CodeExample
        title=".env"
        language="bash"
        code={`PLINTO_API_URL=http://localhost:8000
PLINTO_API_KEY=your-api-key-here

# Or use managed Plinto cloud:
# PLINTO_API_URL=https://api.plinto.dev
# PLINTO_API_KEY=your-cloud-api-key`}
      />

      <h2>Step 3: Initialize the Client</h2>
      <p>
        Create a Plinto client instance in your application:
      </p>

      <CodeExample
        title="Initialize Client (TypeScript)"
        language="typescript"
        code={`import { PlintoClient } from '@plinto/typescript-sdk';

export const plinto = new PlintoClient({
  baseURL: process.env.PLINTO_API_URL!,
  apiKey: process.env.PLINTO_API_KEY!,
});`}
      />

      <CodeExample
        title="Initialize Client (Python)"
        language="python"
        code={`from plinto_sdk import PlintoClient
import os

plinto = PlintoClient(
    api_url=os.getenv('PLINTO_API_URL'),
    api_key=os.getenv('PLINTO_API_KEY')
)`}
      />

      <h2>Step 4: Implement Signup</h2>
      <p>
        Create a signup endpoint that registers new users:
      </p>

      <CodeExample
        title="Signup Implementation (TypeScript)"
        language="typescript"
        code={`import express from 'express';
import { plinto } from './plinto-client';

const app = express();
app.use(express.json());

app.post('/api/signup', async (req, res) => {
  try {
    const { email, password, name } = req.body;
    
    // Sign up user
    const result = await plinto.auth.signUp({
      email,
      password,
      name
    });
    
    // Store tokens securely
    res.cookie('access_token', result.tokens.access_token, {
      httpOnly: true,
      secure: process.env.NODE_ENV === 'production',
      sameSite: 'lax',
      maxAge: 15 * 60 * 1000 // 15 minutes
    });
    
    res.cookie('refresh_token', result.tokens.refresh_token, {
      httpOnly: true,
      secure: process.env.NODE_ENV === 'production',
      sameSite: 'lax',
      maxAge: 7 * 24 * 60 * 60 * 1000 // 7 days
    });
    
    res.json({ user: result.user });
  } catch (error) {
    console.error('Signup error:', error);
    res.status(400).json({ error: error.message });
  }
});`}
      />

      <h2>Step 5: Implement Login</h2>
      <p>
        Create a login endpoint for existing users:
      </p>

      <CodeExample
        title="Login Implementation (TypeScript)"
        language="typescript"
        code={`app.post('/api/login', async (req, res) => {
  try {
    const { email, password, mfa_code } = req.body;
    
    // Sign in user
    const result = await plinto.auth.signIn({
      email,
      password,
      mfa_code // Optional, only if MFA is enabled
    });
    
    // Store tokens securely
    res.cookie('access_token', result.tokens.access_token, {
      httpOnly: true,
      secure: process.env.NODE_ENV === 'production',
      sameSite: 'lax',
      maxAge: 15 * 60 * 1000
    });
    
    res.cookie('refresh_token', result.tokens.refresh_token, {
      httpOnly: true,
      secure: process.env.NODE_ENV === 'production',
      sameSite: 'lax',
      maxAge: 7 * 24 * 60 * 60 * 1000
    });
    
    res.json({ user: result.user });
  } catch (error) {
    console.error('Login error:', error);
    res.status(401).json({ error: 'Invalid credentials' });
  }
});`}
      />

      <h2>Step 6: Protect Routes</h2>
      <p>
        Create middleware to protect authenticated routes:
      </p>

      <CodeExample
        title="Auth Middleware (TypeScript)"
        language="typescript"
        code={`import { Request, Response, NextFunction } from 'express';

async function requireAuth(req: Request, res: Response, next: NextFunction) {
  try {
    const accessToken = req.cookies.access_token;
    
    if (!accessToken) {
      return res.status(401).json({ error: 'Not authenticated' });
    }
    
    // Get current user (verifies token)
    const user = await plinto.auth.getCurrentUser();
    
    // Attach user to request
    req.user = user;
    next();
  } catch (error) {
    // Try to refresh token
    try {
      const refreshToken = req.cookies.refresh_token;
      const result = await plinto.auth.refreshToken(refreshToken);
      
      // Update tokens
      res.cookie('access_token', result.access_token, {
        httpOnly: true,
        secure: process.env.NODE_ENV === 'production',
        sameSite: 'lax',
        maxAge: 15 * 60 * 1000
      });
      
      // Get current user (verifies new token)
      const user = await plinto.auth.getCurrentUser();
      req.user = user;
      next();
    } catch (refreshError) {
      res.status(401).json({ error: 'Session expired' });
    }
  }
}

// Use middleware on protected routes
app.get('/api/profile', requireAuth, (req, res) => {
  res.json({ user: req.user });
});`}
      />

      <h2>Step 7: Enable MFA (Optional)</h2>
      <p>
        Add multi-factor authentication for enhanced security:
      </p>

      <CodeExample
        title="MFA Setup (TypeScript)"
        language="typescript"
        code={`app.post('/api/mfa/enable', requireAuth, async (req, res) => {
  try {
    const accessToken = req.cookies.access_token;
    
    // Enable MFA for user
    const mfaSetup = await plinto.auth.enableMFA('totp', {
      headers: { Authorization: \`Bearer \${accessToken}\` }
    });
    
    // Return QR code and backup codes to user
    res.json({
      qr_code: mfaSetup.qr_code,
      backup_codes: mfaSetup.backup_codes
    });
  } catch (error) {
    console.error('MFA enable error:', error);
    res.status(500).json({ error: 'Failed to enable MFA' });
  }
});

app.post('/api/mfa/verify', requireAuth, async (req, res) => {
  try {
    const { code } = req.body;
    const accessToken = req.cookies.access_token;
    
    // Verify MFA code
    const result = await plinto.auth.verifyMFA({
      code,
      headers: { Authorization: \`Bearer \${accessToken}\` }
    });
    
    res.json({ success: true });
  } catch (error) {
    res.status(400).json({ error: 'Invalid MFA code' });
  }
});`}
      />

      <h2>Complete Example</h2>
      <p>
        Here's a complete working example with all the pieces together:
      </p>

      <CodeExample
        title="Complete Server Example"
        language="typescript"
        code={`import express from 'express';
import cookieParser from 'cookie-parser';
import { PlintoClient } from '@plinto/typescript-sdk';

const app = express();
app.use(express.json());
app.use(cookieParser());

// Initialize Plinto client
const plinto = new PlintoClient({
  baseURL: process.env.PLINTO_API_URL!,
  apiKey: process.env.PLINTO_API_KEY!,
});

// Signup
app.post('/api/signup', async (req, res) => {
  const { email, password, name } = req.body;
  const result = await plinto.auth.signUp({ email, password, name });
  
  res.cookie('access_token', result.tokens.access_token, {
    httpOnly: true,
    secure: true,
    sameSite: 'lax',
    maxAge: 15 * 60 * 1000
  });
  
  res.json({ user: result.user });
});

// Login
app.post('/api/login', async (req, res) => {
  const { email, password, mfa_code } = req.body;
  const result = await plinto.auth.signIn({ email, password, mfa_code });
  
  res.cookie('access_token', result.tokens.access_token, {
    httpOnly: true,
    secure: true,
    sameSite: 'lax',
    maxAge: 15 * 60 * 1000
  });
  
  res.json({ user: result.user });
});

// Auth middleware
async function requireAuth(req, res, next) {
  const token = req.cookies.access_token;
  if (!token) return res.status(401).json({ error: 'Not authenticated' });
  
  try {
    const user = await plinto.auth.getCurrentUser();
    req.user = user;
    next();
  } catch (error) {
    res.status(401).json({ error: 'Invalid token' });
  }
}

// Protected route
app.get('/api/profile', requireAuth, (req, res) => {
  res.json({ user: req.user });
});

app.listen(3000, () => {
  console.log('Server running on http://localhost:3000');
});`}
      />

      <h2>Next Steps</h2>
      <ul>
        <li>
          <a href="/docs/authentication">Learn about authentication concepts</a> and best practices
        </li>
        <li>
          <a href="/docs/mfa">Set up multi-factor authentication</a> for enhanced security
        </li>
        <li>
          <a href="/docs/passkeys">Implement passkeys</a> for passwordless authentication
        </li>
        <li>
          <a href="/docs/rbac">Add role-based access control</a> to manage permissions
        </li>
      </ul>

      <div className="not-prose bg-primary-50 border-l-4 border-primary-600 p-6 my-8">
        <h3 className="text-lg font-semibold text-gray-900 mb-2">Need Help?</h3>
        <p className="text-gray-700">
          Join our <a href="https://github.com/madfam-io/plinto/discussions" className="text-primary-600 hover:text-primary-700">GitHub Discussions</a> for 
          community support or check out our <a href="https://github.com/madfam-io/plinto/issues" className="text-primary-600 hover:text-primary-700">GitHub Issues</a> to 
          report bugs.
        </p>
      </div>
    </div>
  )
}
