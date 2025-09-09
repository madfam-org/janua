'use client'

import { motion } from 'framer-motion'
import { Github, Twitter, Linkedin, Mail, ArrowRight } from 'lucide-react'
import { Button } from '@/components/ui/button'
import Link from 'next/link'

const navigation = {
  product: [
    { name: 'Features', href: '#features' },
    { name: 'Security', href: '#security' },
    { name: 'Performance', href: '#performance' },
    { name: 'Integrations', href: '#integrations' },
    { name: 'Pricing', href: '/pricing' },
    { name: 'Changelog', href: '/changelog' }
  ],
  developers: [
    { name: 'Documentation', href: '/docs' },
    { name: 'API Reference', href: '/api' },
    { name: 'SDKs', href: '/sdks' },
    { name: 'Examples', href: '/examples' },
    { name: 'Playground', href: '#playground' },
    { name: 'Status', href: '/status' }
  ],
  solutions: [
    { name: 'E-commerce', href: '/solutions/ecommerce' },
    { name: 'SaaS Platforms', href: '/solutions/saas' },
    { name: 'Enterprise', href: '/solutions/enterprise' },
    { name: 'Healthcare', href: '/solutions/healthcare' },
    { name: 'Education', href: '/solutions/education' },
    { name: 'Financial Services', href: '/solutions/fintech' }
  ],
  company: [
    { name: 'About', href: '/about' },
    { name: 'Blog', href: '/blog' },
    { name: 'Careers', href: '/careers' },
    { name: 'Contact', href: '/contact' },
    { name: 'Press Kit', href: '/press' },
    { name: 'Partners', href: '/partners' }
  ],
  legal: [
    { name: 'Privacy Policy', href: '/privacy' },
    { name: 'Terms of Service', href: '/terms' },
    { name: 'Cookie Policy', href: '/cookies' },
    { name: 'Security', href: '/security' },
    { name: 'Compliance', href: '/compliance' }
  ]
}

const socialLinks = [
  {
    name: 'Twitter',
    href: 'https://twitter.com/plinto',
    icon: Twitter
  },
  {
    name: 'GitHub',
    href: 'https://github.com/plinto',
    icon: Github
  },
  {
    name: 'LinkedIn',
    href: 'https://linkedin.com/company/plinto',
    icon: Linkedin
  },
  {
    name: 'Email',
    href: 'mailto:hello@plinto.dev',
    icon: Mail
  }
]

export function Footer() {
  return (
    <footer className="bg-gray-900 text-white">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        {/* Newsletter section */}
        <div className="py-12 border-b border-gray-800">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.6 }}
            className="max-w-2xl mx-auto text-center"
          >
            <h3 className="text-2xl font-bold mb-4">
              Stay up to date with Plinto
            </h3>
            <p className="text-gray-400 mb-8">
              Get the latest updates on new features, security insights, and developer resources.
            </p>
            <div className="flex flex-col sm:flex-row gap-4 max-w-md mx-auto">
              <input
                type="email"
                placeholder="Enter your email"
                className="flex-1 px-4 py-3 bg-gray-800 border border-gray-700 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              />
              <Button className="bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-700 hover:to-purple-700 px-6">
                Subscribe
                <ArrowRight className="ml-2 h-4 w-4" />
              </Button>
            </div>
          </motion.div>
        </div>

        {/* Main footer content */}
        <div className="py-12">
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-8">
            {/* Brand */}
            <div className="col-span-2 lg:col-span-2">
              <Link href="/" className="flex items-center space-x-2 mb-6">
                <div className="w-8 h-8 bg-gradient-to-br from-blue-600 to-purple-600 rounded-lg flex items-center justify-center">
                  <span className="text-white font-bold text-sm">P</span>
                </div>
                <span className="text-xl font-bold">Plinto</span>
              </Link>
              <p className="text-gray-400 mb-6 max-w-sm">
                Secure identity infrastructure that moves at the speed of your users. 
                Sub-30ms verification, passkeys-first, your data under your control.
              </p>
              <div className="flex space-x-4">
                {socialLinks.map((item) => {
                  const Icon = item.icon
                  return (
                    <Link
                      key={item.name}
                      href={item.href}
                      className="text-gray-400 hover:text-white transition-colors"
                      aria-label={item.name}
                    >
                      <Icon className="h-5 w-5" />
                    </Link>
                  )
                })}
              </div>
            </div>

            {/* Product */}
            <div>
              <h3 className="text-sm font-semibold text-gray-100 uppercase tracking-wider mb-4">
                Product
              </h3>
              <ul className="space-y-3">
                {navigation.product.map((item) => (
                  <li key={item.name}>
                    <Link
                      href={item.href}
                      className="text-gray-400 hover:text-white transition-colors text-sm"
                    >
                      {item.name}
                    </Link>
                  </li>
                ))}
              </ul>
            </div>

            {/* Developers */}
            <div>
              <h3 className="text-sm font-semibold text-gray-100 uppercase tracking-wider mb-4">
                Developers
              </h3>
              <ul className="space-y-3">
                {navigation.developers.map((item) => (
                  <li key={item.name}>
                    <Link
                      href={item.href}
                      className="text-gray-400 hover:text-white transition-colors text-sm"
                    >
                      {item.name}
                    </Link>
                  </li>
                ))}
              </ul>
            </div>

            {/* Solutions */}
            <div>
              <h3 className="text-sm font-semibold text-gray-100 uppercase tracking-wider mb-4">
                Solutions
              </h3>
              <ul className="space-y-3">
                {navigation.solutions.map((item) => (
                  <li key={item.name}>
                    <Link
                      href={item.href}
                      className="text-gray-400 hover:text-white transition-colors text-sm"
                    >
                      {item.name}
                    </Link>
                  </li>
                ))}
              </ul>
            </div>

            {/* Company */}
            <div>
              <h3 className="text-sm font-semibold text-gray-100 uppercase tracking-wider mb-4">
                Company
              </h3>
              <ul className="space-y-3">
                {navigation.company.map((item) => (
                  <li key={item.name}>
                    <Link
                      href={item.href}
                      className="text-gray-400 hover:text-white transition-colors text-sm"
                    >
                      {item.name}
                    </Link>
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </div>

        {/* Bottom section */}
        <div className="py-8 border-t border-gray-800">
          <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between">
            <div className="flex flex-col sm:flex-row sm:items-center space-y-4 sm:space-y-0 sm:space-x-6 mb-4 lg:mb-0">
              <p className="text-gray-400 text-sm">
                © 2024 Plinto by Aureo Labs. All rights reserved.
              </p>
              <div className="flex space-x-6">
                {navigation.legal.map((item) => (
                  <Link
                    key={item.name}
                    href={item.href}
                    className="text-gray-400 hover:text-white transition-colors text-sm"
                  >
                    {item.name}
                  </Link>
                ))}
              </div>
            </div>
            
            <div className="flex items-center space-x-4">
              <div className="flex items-center space-x-2 text-sm text-gray-400">
                <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse"></div>
                <span>All systems operational</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </footer>
  )
}