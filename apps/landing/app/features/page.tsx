import { Metadata } from 'next'
import { CodeExample } from '@/components/CodeExample'

export const metadata: Metadata = {
  title: 'Features - Plinto Authentication Platform',
  description: 'Comprehensive authentication features including MFA, passkeys, SSO, RBAC, and more.',
}

export default function FeaturesPage() {
  return (
    <div className="bg-white">
      {/* Header */}
      <div className="bg-gradient-to-br from-primary-50 to-white py-16">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <h1 className="text-4xl font-extrabold text-gray-900">Features</h1>
          <p className="mt-4 text-xl text-gray-600">
            Every feature battle-tested with comprehensive journey validation
          </p>
        </div>
      </div>

      {/* Authentication Features */}
      <section className="py-16">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <h2 className="text-3xl font-bold text-gray-900 mb-8">Core Authentication</h2>

          {/* User Signup */}
          <div className="mb-16">
            <h3 className="text-2xl font-semibold text-gray-900 mb-4">User Signup & Login</h3>
            <p className="text-gray-600 mb-6">
              Email/password authentication with secure bcrypt hashing, email verification, 
              and automatic session management. Supports custom user metadata and profile fields.
            </p>
            <CodeExample
              title="Signup Example"
              language="typescript"
              code={`import { PlintoClient } from '@plinto/typescript-sdk';

const plinto = new PlintoClient({
  baseURL: process.env.PLINTO_API_URL,
  apiKey: process.env.PLINTO_API_KEY
});

// Sign up new user
const result = await plinto.auth.signUp({
  email: 'user@example.com',
  password: 'SecurePass123!',
  name: 'John Doe',
  metadata: {
    company: 'Acme Corp',
    role: 'Developer'
  }
});

console.log('User ID:', result.user.id);
console.log('Access Token:', result.tokens.access_token);

// Login existing user
const loginResult = await plinto.auth.signIn({
  email: 'user@example.com',
  password: 'SecurePass123!'
});`}
            />
          </div>

          {/* MFA */}
          <div className="mb-16">
            <h3 className="text-2xl font-semibold text-gray-900 mb-4">Multi-Factor Authentication</h3>
            <p className="text-gray-600 mb-6">
              TOTP-based MFA with QR code generation for authenticator apps, backup codes for 
              account recovery, and SMS verification support. Compatible with Google Authenticator, 
              Authy, and other TOTP apps.
            </p>
            <CodeExample
              title="MFA Setup"
              language="typescript"
              code={`// Enable MFA for user
const mfaSetup = await plinto.auth.enableMFA('totp', {
  headers: { Authorization: \`Bearer \${accessToken}\` }
});

// Display QR code to user for scanning
console.log('QR Code URL:', mfaSetup.qr_code);

// Save backup codes securely
console.log('Backup Codes:', mfaSetup.backup_codes);

// Verify MFA code
const verified = await plinto.auth.verifyMFA({
  code: '123456',
  headers: { Authorization: \`Bearer \${accessToken}\` }
});

// Login with MFA
const loginResult = await plinto.auth.signIn({
  email: 'user@example.com',
  password: 'SecurePass123!',
  mfa_code: '123456'
});`}
            />
          </div>

          {/* Passkeys */}
          <div className="mb-16">
            <h3 className="text-2xl font-semibold text-gray-900 mb-4">Passkeys (WebAuthn)</h3>
            <p className="text-gray-600 mb-6">
              Passwordless authentication using FIDO2/WebAuthn standard. Support for biometric 
              authentication (Face ID, Touch ID, Windows Hello) and hardware security keys.
            </p>
            <CodeExample
              title="Passkey Registration"
              language="typescript"
              code={`// Get registration options from server
const options = await plinto.auth.getPasskeyOptions({
  headers: { Authorization: \`Bearer \${accessToken}\` }
});

// Create credential using WebAuthn browser API
const credential = await navigator.credentials.create({
  publicKey: {
    ...options,
    challenge: base64urlToBuffer(options.challenge),
    user: {
      ...options.user,
      id: base64urlToBuffer(options.user.id)
    }
  }
});

// Verify and save credential
const result = await plinto.auth.verifyPasskey({
  credential: {
    id: credential.id,
    rawId: bufferToBase64url(credential.rawId),
    response: {
      attestationObject: bufferToBase64url(
        credential.response.attestationObject
      ),
      clientDataJSON: bufferToBase64url(
        credential.response.clientDataJSON
      )
    }
  },
  headers: { Authorization: \`Bearer \${accessToken}\` }
});`}
            />
          </div>
        </div>
      </section>

      {/* Enterprise Features */}
      <section className="py-16 bg-gray-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <h2 className="text-3xl font-bold text-gray-900 mb-8">Enterprise Features</h2>

          {/* SSO */}
          <div className="mb-16">
            <h3 className="text-2xl font-semibold text-gray-900 mb-4">SAML & OIDC SSO</h3>
            <p className="text-gray-600 mb-6">
              Enterprise single sign-on with SAML 2.0 and OpenID Connect. Integrate with 
              Okta, Azure AD, Google Workspace, OneLogin, and other identity providers.
            </p>
            <CodeExample
              title="SSO Configuration"
              language="typescript"
              code={`// Configure SAML SSO
const ssoConfig = await plinto.sso.configureSAML({
  provider: 'okta',
  entity_id: 'https://your-company.okta.com',
  sso_url: 'https://your-company.okta.com/app/plinto/sso/saml',
  x509_certificate: '-----BEGIN CERTIFICATE-----\\n...',
  attribute_mapping: {
    email: 'http://schemas.xmlsoap.org/ws/2005/05/identity/claims/emailaddress',
    name: 'http://schemas.xmlsoap.org/ws/2005/05/identity/claims/name'
  }
});

// Initiate SSO login
const loginUrl = await plinto.sso.initiateSAMLLogin({
  connection_id: ssoConfig.id,
  callback_url: 'https://app.example.com/auth/callback'
});

// Redirect user to loginUrl for authentication`}
            />
          </div>

          {/* RBAC */}
          <div className="mb-16">
            <h3 className="text-2xl font-semibold text-gray-900 mb-4">Role-Based Access Control</h3>
            <p className="text-gray-600 mb-6">
              Flexible RBAC with custom roles, permissions, and resource-based policies. 
              Support for hierarchical roles and dynamic permission evaluation.
            </p>
            <CodeExample
              title="RBAC Management"
              language="typescript"
              code={`// Create custom role
const role = await plinto.rbac.createRole({
  name: 'editor',
  description: 'Can edit content',
  permissions: ['content:read', 'content:write']
});

// Assign role to user
await plinto.rbac.assignRole({
  user_id: 'user_123',
  role_id: role.id
});

// Check permission
const hasPermission = await plinto.rbac.checkPermission({
  user_id: 'user_123',
  permission: 'content:write',
  resource: 'article:456'
});

// Create resource policy
await plinto.rbac.createPolicy({
  name: 'article-ownership',
  effect: 'allow',
  actions: ['article:delete'],
  resources: ['article:*'],
  conditions: {
    'user.id': { equals: 'resource.owner_id' }
  }
});`}
            />
          </div>
        </div>
      </section>

      {/* SDK Examples */}
      <section className="py-16">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <h2 className="text-3xl font-bold text-gray-900 mb-8">Framework Integration</h2>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
            {/* React Example */}
            <div>
              <h3 className="text-xl font-semibold text-gray-900 mb-4">React Integration</h3>
              <CodeExample
                title="React Component"
                language="tsx"
                code={`import { useAuth } from '@plinto/react-sdk';

function LoginForm() {
  const { signIn, loading, error } = useAuth();
  
  const handleSubmit = async (e) => {
    e.preventDefault();
    const formData = new FormData(e.target);
    
    await signIn({
      email: formData.get('email'),
      password: formData.get('password')
    });
  };
  
  return (
    <form onSubmit={handleSubmit}>
      {error && <div>{error.message}</div>}
      <input name="email" type="email" required />
      <input name="password" type="password" required />
      <button disabled={loading}>Sign In</button>
    </form>
  );
}`}
              />
            </div>

            {/* Next.js Example */}
            <div>
              <h3 className="text-xl font-semibold text-gray-900 mb-4">Next.js Integration</h3>
              <CodeExample
                title="Next.js Middleware"
                language="typescript"
                code={`import { NextResponse } from 'next/server';
import { withAuth } from '@plinto/nextjs-sdk';

export default withAuth({
  callbacks: {
    authorized({ token }) {
      return !!token;
    }
  },
  pages: {
    signIn: '/login'
  }
});

export const config = {
  matcher: ['/dashboard/:path*']
};`}
              />
            </div>

            {/* Vue Example */}
            <div>
              <h3 className="text-xl font-semibold text-gray-900 mb-4">Vue Integration</h3>
              <CodeExample
                title="Vue Composition API"
                language="vue"
                code={`<script setup>
import { useAuth } from '@plinto/vue-sdk';

const { user, signIn, loading } = useAuth();

const handleLogin = async () => {
  await signIn({
    email: email.value,
    password: password.value
  });
};
</script>

<template>
  <div v-if="user">
    Welcome, {{ user.name }}
  </div>
  <form v-else @submit.prevent="handleLogin">
    <input v-model="email" type="email" />
    <input v-model="password" type="password" />
    <button :disabled="loading">Sign In</button>
  </form>
</template>`}
              />
            </div>

            {/* Python Example */}
            <div>
              <h3 className="text-xl font-semibold text-gray-900 mb-4">Python Integration</h3>
              <CodeExample
                title="Python FastAPI"
                language="python"
                code={`from plinto_sdk import PlintoClient
from fastapi import Depends, HTTPException

plinto = PlintoClient(
    api_url=os.getenv('PLINTO_API_URL'),
    api_key=os.getenv('PLINTO_API_KEY')
)

async def get_current_user(token: str = Depends(oauth2_scheme)):
    try:
        user = await plinto.auth.verify_token(token)
        return user
    except Exception:
        raise HTTPException(status_code=401)

@app.get('/protected')
async def protected_route(user = Depends(get_current_user)):
    return {'user': user}`}
              />
            </div>
          </div>
        </div>
      </section>
    </div>
  )
}
