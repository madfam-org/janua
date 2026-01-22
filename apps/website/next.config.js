/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'standalone',
  transpilePackages: ['@janua/ui', '@janua/react-sdk', '@janua/typescript-sdk'],
  // Enable Turbopack with empty config (Next.js 16 default)
  turbopack: {},
  images: {
    remotePatterns: [
      { protocol: 'https', hostname: 'images.unsplash.com' },
      { protocol: 'https', hostname: 'github.com' },
    ],
  },
}

module.exports = nextConfig
