/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'standalone',
  // The production build type-checks app code only. Unit tests and
  // Playwright specs are excluded here (see tsconfig.build.json) and are run
  // by their own tooling; tsconfig.json still includes them for the editor
  // and for `pnpm typecheck`.
  typescript: {
    tsconfigPath: 'tsconfig.build.json',
  },
  transpilePackages: ['@janua/ui', '@janua/react-sdk', '@janua/typescript-sdk'],
  // Enable Turbopack with empty config (Next.js 16 default)
  turbopack: {},
  images: {
    remotePatterns: [
      { protocol: 'https', hostname: 'images.unsplash.com' },
      { protocol: 'https', hostname: 'github.com' },
    ],
  },
  async headers() {
    const cspDirectives = [
      "default-src 'self'",
      "script-src 'self' 'unsafe-inline'",
      "style-src 'self' 'unsafe-inline'",
      "img-src 'self' data: blob: https://images.unsplash.com https://github.com",
      "font-src 'self'",
      "connect-src 'self' https://analytics.madfam.io https://us.i.posthog.com https://eu.i.posthog.com",
      "object-src 'none'",
      "base-uri 'self'",
      "form-action 'self'",
      "frame-ancestors 'none'",
    ]

    return [
      {
        source: '/:path*',
        headers: [
          {
            key: 'Content-Security-Policy',
            value: cspDirectives.join('; '),
          },
          {
            key: 'Strict-Transport-Security',
            value: 'max-age=31536000; includeSubDomains',
          },
          {
            key: 'X-Frame-Options',
            value: 'DENY',
          },
          {
            key: 'X-Content-Type-Options',
            value: 'nosniff',
          },
          {
            key: 'X-XSS-Protection',
            value: '0',
          },
          {
            key: 'Referrer-Policy',
            value: 'strict-origin-when-cross-origin',
          },
          {
            key: 'Permissions-Policy',
            value: 'camera=(), microphone=(), geolocation=()',
          },
        ],
      },
    ]
  },
}

module.exports = nextConfig
