'use client'

import { motion } from 'framer-motion'
import { Github, Twitter, Linkedin, Mail, ArrowRight, BookOpen } from 'lucide-react'
import { Button } from '@janua/ui'
import Link from 'next/link'
import Image from 'next/image'

const navigation = {
  product: [
    { name: 'Features', href: '/#features' },
    { name: 'Security', href: '/#security' },
    { name: 'Performance', href: '/#performance' },
    { name: 'Integrations', href: '/#integrations' },
    { name: 'Pricing', href: '/pricing' },
  ],
  developers: [
    { name: 'Documentation', href: 'https://docs.janua.dev' },
    { name: 'API Reference', href: 'https://docs.janua.dev/api' },
    { name: 'SDKs', href: 'https://docs.janua.dev/sdks' },
    { name: 'Examples', href: 'https://docs.janua.dev/examples' },
    { name: 'Live demo', href: '/demo' },
    { name: 'Deploy with Enclii', href: '/deploy/enclii' },
    { name: 'Status', href: 'https://status.janua.dev' },
  ],
  solutions: [
    { name: 'E-commerce', href: '/solutions/ecommerce' },
    { name: 'SaaS Platforms', href: '/solutions/saas' },
    { name: 'Enterprise', href: '/solutions/enterprise' },
    { name: 'Healthcare', href: '/solutions/healthcare' },
  ],
  company: [
    { name: 'About', href: '/about' },
    { name: 'Blog', href: '/blog' },
    { name: 'Careers', href: '/careers' },
    { name: 'Contact', href: '/contact' },
  ],
  legal: [
    { name: 'Privacy Policy', href: '/legal/privacy' },
    { name: 'Terms of Service', href: '/legal/terms' },
    { name: 'Cookie Policy', href: '/legal/cookies' },
  ],
}

const socialLinks = [
  {
    name: 'Twitter',
    href: 'https://twitter.com/getjanua',
    icon: Twitter
  },
  {
    name: 'GitHub',
    href: 'https://github.com/madfam-org/janua',
    icon: Github
  },
  {
    name: 'LinkedIn',
    href: 'https://linkedin.com/company/janua-dev',
    icon: Linkedin
  },
  {
    name: 'Email',
    href: 'mailto:hello@janua.dev',
    icon: Mail
  }
]

export function Footer() {
  return (
    <footer className="bg-slate-950 text-white">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="py-12 border-b border-slate-800">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.6 }}
            className="max-w-2xl mx-auto text-center"
          >
            <h3 className="font-display text-2xl font-bold mb-4">
              Build with open identity infrastructure
            </h3>
            <p className="text-slate-400 mb-8">
              Star the repo, read the docs, or run the live demo — no mailing list required.
            </p>
            <div className="flex flex-col sm:flex-row gap-4 justify-center">
              <Button asChild className="bg-brand-gradient hover:opacity-90 text-white px-6">
                <Link href="https://github.com/madfam-org/janua" target="_blank" rel="noopener noreferrer">
                  <Github className="mr-2 h-4 w-4" />
                  View on GitHub
                  <ArrowRight className="ml-2 h-4 w-4" />
                </Link>
              </Button>
              <Button asChild variant="outline" className="border-slate-700 text-white hover:bg-slate-900">
                <Link href="https://docs.janua.dev">
                  <BookOpen className="mr-2 h-4 w-4" />
                  Documentation
                </Link>
              </Button>
            </div>
          </motion.div>
        </div>

        <div className="py-12">
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-8">
            <div className="col-span-2 lg:col-span-2">
              <Link href="/" className="flex items-center space-x-2 mb-6">
                <Image
                  src="/images/janua-logo.png"
                  alt="Janua Logo"
                  width={32}
                  height={32}
                  className="w-8 h-8 object-contain"
                />
                <span className="font-display text-xl font-bold">Janua</span>
              </Link>
              <p className="text-slate-400 mb-6 max-w-sm">
                Secure identity infrastructure that moves at the speed of your users.
                Passkeys-first, your data under your control.
              </p>
              <div className="flex space-x-4">
                {socialLinks.map((item) => {
                  const Icon = item.icon
                  return (
                    <Link
                      key={item.name}
                      href={item.href}
                      className="text-slate-400 hover:text-white transition-colors"
                      aria-label={item.name}
                    >
                      <Icon className="h-5 w-5" />
                    </Link>
                  )
                })}
              </div>
            </div>

            <div>
              <h3 className="text-sm font-semibold text-slate-100 uppercase tracking-wider mb-4">
                Product
              </h3>
              <ul className="space-y-3">
                {navigation.product.map((item) => (
                  <li key={item.name}>
                    <Link
                      href={item.href}
                      className="text-slate-400 hover:text-white transition-colors text-sm"
                    >
                      {item.name}
                    </Link>
                  </li>
                ))}
              </ul>
            </div>

            <div>
              <h3 className="text-sm font-semibold text-slate-100 uppercase tracking-wider mb-4">
                Developers
              </h3>
              <ul className="space-y-3">
                {navigation.developers.map((item) => (
                  <li key={item.name}>
                    <Link
                      href={item.href}
                      className="text-slate-400 hover:text-white transition-colors text-sm"
                    >
                      {item.name}
                    </Link>
                  </li>
                ))}
              </ul>
            </div>

            <div>
              <h3 className="text-sm font-semibold text-slate-100 uppercase tracking-wider mb-4">
                Solutions
              </h3>
              <ul className="space-y-3">
                {navigation.solutions.map((item) => (
                  <li key={item.name}>
                    <Link
                      href={item.href}
                      className="text-slate-400 hover:text-white transition-colors text-sm"
                    >
                      {item.name}
                    </Link>
                  </li>
                ))}
              </ul>
            </div>

            <div>
              <h3 className="text-sm font-semibold text-slate-100 uppercase tracking-wider mb-4">
                Company
              </h3>
              <ul className="space-y-3">
                {navigation.company.map((item) => (
                  <li key={item.name}>
                    <Link
                      href={item.href}
                      className="text-slate-400 hover:text-white transition-colors text-sm"
                    >
                      {item.name}
                    </Link>
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </div>

        <div className="py-8 border-t border-slate-800">
          <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between">
            <div className="flex flex-col sm:flex-row sm:items-center space-y-4 sm:space-y-0 sm:space-x-6 mb-4 lg:mb-0">
              <p className="text-slate-400 text-sm">
                © 2026 Janua by Innovaciones MADFAM. All rights reserved.
              </p>
              <div className="flex flex-wrap gap-x-6 gap-y-2">
                {navigation.legal.map((item) => (
                  <Link
                    key={item.name}
                    href={item.href}
                    className="text-slate-400 hover:text-white transition-colors text-sm"
                  >
                    {item.name}
                  </Link>
                ))}
              </div>
            </div>

            <div className="flex items-center space-x-4">
              <Link
                href="https://status.janua.dev"
                className="flex items-center space-x-2 text-sm text-slate-400 hover:text-white transition-colors"
              >
                <div className="w-2 h-2 bg-emerald-500 rounded-full animate-pulse" />
                <span>All systems operational</span>
              </Link>
            </div>
          </div>
        </div>
      </div>
    </footer>
  )
}
