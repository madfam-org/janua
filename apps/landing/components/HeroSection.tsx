import Link from 'next/link'

export function HeroSection() {
  return (
    <section className="relative overflow-hidden bg-gradient-to-br from-primary-50 to-white" data-testid="hero-section">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-24 sm:py-32">
        <div className="text-center">
          <h1 className="text-4xl font-extrabold tracking-tight text-gray-900 sm:text-5xl md:text-6xl">
            <span className="block">Enterprise Authentication</span>
            <span className="block text-primary-600">Built for Developers</span>
          </h1>
          <p className="mt-6 max-w-2xl mx-auto text-xl text-gray-600">
            Open-source authentication platform with MFA, passkeys, SAML/OIDC SSO, 
            and comprehensive security features. Self-hosted or cloud-managed.
          </p>
          <div className="mt-10 flex justify-center gap-4">
            <Link
              href="/docs/quickstart"
              className="inline-flex items-center px-6 py-3 border border-transparent text-base font-medium rounded-md text-white bg-primary-600 hover:bg-primary-700 transition-colors"
              data-testid="get-started-button"
            >
              Get Started Free
            </Link>
            <Link
              href="/docs"
              className="inline-flex items-center px-6 py-3 border border-gray-300 text-base font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 transition-colors"
              data-testid="view-docs-button"
            >
              View Documentation
            </Link>
          </div>

          {/* Trust indicators */}
          <div className="mt-16 grid grid-cols-2 gap-8 md:grid-cols-4">
            <div className="flex flex-col items-center">
              <div className="text-3xl font-bold text-primary-600">100%</div>
              <div className="mt-2 text-sm text-gray-600">Open Source</div>
            </div>
            <div className="flex flex-col items-center">
              <div className="text-3xl font-bold text-primary-600">SOC 2</div>
              <div className="mt-2 text-sm text-gray-600">Compliant</div>
            </div>
            <div className="flex flex-col items-center">
              <div className="text-3xl font-bold text-primary-600">99.9%</div>
              <div className="mt-2 text-sm text-gray-600">Uptime SLA</div>
            </div>
            <div className="flex flex-col items-center">
              <div className="text-3xl font-bold text-primary-600">6 SDKs</div>
              <div className="mt-2 text-sm text-gray-600">Ready to Use</div>
            </div>
          </div>
        </div>
      </div>

      {/* Code example preview */}
      <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 pb-24">
        <div className="bg-gray-900 rounded-lg shadow-2xl overflow-hidden">
          <div className="flex items-center gap-2 px-4 py-3 bg-gray-800">
            <div className="w-3 h-3 rounded-full bg-red-500"></div>
            <div className="w-3 h-3 rounded-full bg-yellow-500"></div>
            <div className="w-3 h-3 rounded-full bg-green-500"></div>
            <span className="ml-2 text-sm text-gray-400">quickstart.ts</span>
          </div>
          <pre className="p-6 overflow-x-auto text-sm">
            <code className="text-gray-300">
{`import { PlintoClient } from '@plinto/typescript-sdk';

const plinto = new PlintoClient({
  baseURL: process.env.PLINTO_API_URL,
  apiKey: process.env.PLINTO_API_KEY
});

// Sign up new user
const user = await plinto.auth.signUp({
  email: 'user@example.com',
  password: 'SecurePass123!',
  name: 'John Doe'
});

// Enable MFA
const mfa = await plinto.auth.enableMFA('totp');
console.log('QR Code:', mfa.qr_code);

// Register passkey
const passkey = await plinto.auth.registerPasskey();`}
            </code>
          </pre>
        </div>
      </div>
    </section>
  )
}
