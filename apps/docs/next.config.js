const withMDX = require('@next/mdx')({
  extension: /\.mdx?$/,
  options: {
    remarkPlugins: [],
    rehypePlugins: [],
  },
})

/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'standalone',
  pageExtensions: ['ts', 'tsx', 'js', 'jsx', 'md', 'mdx'],
  reactStrictMode: true,
  transpilePackages: ['@janua/ui'],
  // Turbopack disabled for MDX compatibility
  images: {
    remotePatterns: [
      { protocol: 'https', hostname: 'janua.dev' },
      { protocol: 'https', hostname: 'github.com' },
      { protocol: 'https', hostname: 'raw.githubusercontent.com' },
    ],
  },
  async headers() {
    return [
      {
        source: '/:path*',
        headers: [
          {
            key: 'X-Frame-Options',
            value: 'DENY'
          },
          {
            key: 'X-Content-Type-Options',
            value: 'nosniff'
          },
          {
            key: 'X-XSS-Protection',
            value: '1; mode=block'
          }
        ]
      }
    ]
  },
  async redirects() {
    return [
      {
        source: '/docs',
        destination: '/',
        permanent: true,
      },
      {
        source: '/guide/:path*',
        destination: '/guides/:path*',
        permanent: true,
      },
    ]
  },
}

module.exports = withMDX(nextConfig)