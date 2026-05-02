/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'standalone',
  transpilePackages: ['@janua/ui', '@janua/react-sdk'],
  // Enable Turbopack with empty config (Next.js 16 default)
  turbopack: {},
  images: {
    remotePatterns: [
      { protocol: 'https', hostname: 'images.unsplash.com' },
      { protocol: 'https', hostname: 'github.com' },
    ],
  },
  env: {
    NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL || 'https://api.janua.dev',
  },
  async headers() {
    const isDev = process.env.NODE_ENV === 'development'
    const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'https://api.janua.dev'

    // Cloudflare Insights is auto-injected by the Cloudflare proxy on
    // production hosts; allow its beacon script and analytics endpoint
    // without weakening the rest of the CSP. Mirrors the dashboard fix
    // landed on main in 628e3a85.
    const cfInsightsScript = 'https://static.cloudflareinsights.com'
    const cfInsightsConnect = 'https://cloudflareinsights.com'

    const cspDirectives = [
      "default-src 'self'",
      `script-src 'self'${isDev ? " 'unsafe-eval'" : ""} 'unsafe-inline' ${cfInsightsScript}`,
      `script-src-elem 'self' 'unsafe-inline' ${cfInsightsScript}`,
      "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com",
      "font-src 'self' data: https://fonts.gstatic.com",
      "img-src 'self' data: https:",
      `connect-src 'self' ${apiUrl} ${cfInsightsConnect}${isDev ? ' ws://localhost:*' : ''}`,
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
