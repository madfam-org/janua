/** @type {import('next').NextConfig} */
const nextConfig = {
  transpilePackages: ['@plinto/ui', '@plinto/react'],
  images: {
    domains: ['images.unsplash.com', 'github.com'],
  },
}

module.exports = nextConfig