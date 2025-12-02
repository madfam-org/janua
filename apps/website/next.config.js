/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'standalone',
  transpilePackages: ['@janua/ui', '@janua/react-sdk', '@janua/typescript-sdk'],
  images: {
    domains: ['images.unsplash.com', 'github.com'],
  },
}

module.exports = nextConfig
