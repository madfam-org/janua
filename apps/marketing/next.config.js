/** @type {import('next').NextConfig} */
const nextConfig = {
  transpilePackages: ['@plinto/ui', '@plinto/react-sdk-sdk'],
  images: {
    domains: ['images.unsplash.com', 'github.com'],
  },
}

module.exports = nextConfig