'use client'

import { useState } from 'react'
import { motion } from 'framer-motion'
import { Menu, X, ArrowRight, ChevronDown } from 'lucide-react'
import { Button } from '@janua/ui'
import Link from 'next/link'
import Image from 'next/image'

const navigation = [
  {
    name: 'Product',
    href: '/#features',
    children: [
      { name: 'Features', href: '/#features' },
      { name: 'Security', href: '/#security' },
      { name: 'Performance', href: '/#performance' },
      { name: 'Integrations', href: '/#integrations' },
    ],
  },
  {
    name: 'Demo',
    href: '/demo',
  },
  {
    name: 'Developers',
    href: 'https://docs.janua.dev',
    children: [
      { name: 'Documentation', href: 'https://docs.janua.dev' },
      { name: 'API Reference', href: 'https://docs.janua.dev/api' },
      { name: 'SDKs', href: 'https://docs.janua.dev/sdks' },
      { name: 'Live Demo', href: '/demo' },
      { name: 'Deploy with Enclii', href: '/deploy/enclii' },
    ]
  },
  {
    name: 'Solutions',
    href: '/solutions/saas',
    children: [
      { name: 'E-commerce', href: '/solutions/ecommerce' },
      { name: 'SaaS', href: '/solutions/saas' },
      { name: 'Enterprise', href: '/solutions/enterprise' },
      { name: 'Healthcare', href: '/solutions/healthcare' }
    ]
  },
  {
    name: 'Pricing',
    href: '/pricing'
  },
  {
    name: 'Company',
    href: '/about',
    children: [
      { name: 'About', href: '/about' },
      { name: 'Blog', href: '/blog' },
      { name: 'Careers', href: '/careers' },
      { name: 'Contact', href: '/contact' }
    ]
  }
]

function NavParent({
  item,
  activeDropdown,
  setActiveDropdown,
}: {
  item: (typeof navigation)[number]
  activeDropdown: string | null
  setActiveDropdown: (name: string | null) => void
}) {
  const hasChildren = Boolean(item.children)

  if (!hasChildren) {
    return (
      <Link
        href={item.href}
        className="flex items-center text-slate-600 dark:text-slate-300 hover:text-slate-900 dark:hover:text-white transition-colors font-medium"
      >
        {item.name}
      </Link>
    )
  }

  return (
    <>
      <button
        type="button"
        className="flex items-center text-slate-600 dark:text-slate-300 hover:text-slate-900 dark:hover:text-white transition-colors font-medium"
        aria-expanded={activeDropdown === item.name}
        onMouseEnter={() => setActiveDropdown(item.name)}
        onFocus={() => setActiveDropdown(item.name)}
      >
        {item.name}
        <ChevronDown className="ml-1 h-4 w-4" />
      </button>
      {activeDropdown === item.name && (
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: 10 }}
          className="absolute top-full left-0 mt-2 w-48 bg-white dark:bg-slate-900 rounded-lg shadow-lg border border-slate-200 dark:border-slate-800 py-2"
        >
          {item.children!.map((child) => (
            <Link
              key={child.name}
              href={child.href}
              className="block px-4 py-2 text-sm text-slate-600 dark:text-slate-300 hover:text-slate-900 dark:hover:text-white hover:bg-slate-50 dark:hover:bg-slate-800 transition-colors"
            >
              {child.name}
            </Link>
          ))}
        </motion.div>
      )}
    </>
  )
}

export function Navigation() {
  const [isOpen, setIsOpen] = useState(false)
  const [activeDropdown, setActiveDropdown] = useState<string | null>(null)

  return (
    <nav className="fixed top-0 w-full bg-white/85 dark:bg-slate-950/85 backdrop-blur-lg border-b border-slate-200 dark:border-slate-800 z-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">
          <div className="flex items-center">
            <Link href="/" className="flex items-center space-x-2 group">
              <Image
                src="/images/janua-logo.png"
                alt="Janua Logo"
                width={32}
                height={32}
                className="w-8 h-8 object-contain transition-transform group-hover:scale-105"
              />
              <span className="font-display text-xl font-bold text-slate-900 dark:text-white">
                Janua
              </span>
            </Link>
          </div>

          <div className="hidden md:flex items-center space-x-8">
            {navigation.map((item) => (
              <div
                key={item.name}
                className="relative"
                onMouseEnter={() => item.children && setActiveDropdown(item.name)}
                onMouseLeave={() => setActiveDropdown(null)}
              >
                <NavParent
                  item={item}
                  activeDropdown={activeDropdown}
                  setActiveDropdown={setActiveDropdown}
                />
              </div>
            ))}
          </div>

          <div className="hidden md:flex items-center space-x-4">
            <Link href="https://app.janua.dev/auth/signin">
              <Button variant="ghost">Sign In</Button>
            </Link>
            <Link href="https://app.janua.dev/auth/signup">
              <Button className="bg-brand-gradient hover:opacity-90 text-white shadow-brand">
                Start Free
                <ArrowRight className="ml-2 h-4 w-4" />
              </Button>
            </Link>
          </div>

          <div className="md:hidden">
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setIsOpen(!isOpen)}
              aria-label="Toggle menu"
            >
              {isOpen ? (
                <X className="h-6 w-6" />
              ) : (
                <Menu className="h-6 w-6" />
              )}
            </Button>
          </div>
        </div>

        {isOpen && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            className="md:hidden border-t border-slate-200 dark:border-slate-800 py-4"
          >
            <div className="flex flex-col space-y-4">
              {navigation.map((item) => (
                <div key={item.name}>
                  <Link
                    href={item.href}
                    className="block text-slate-600 dark:text-slate-300 hover:text-slate-900 dark:hover:text-white font-medium"
                    onClick={() => setIsOpen(false)}
                  >
                    {item.name}
                  </Link>
                  {item.children && (
                    <div className="ml-4 mt-2 space-y-2">
                      {item.children.map((child) => (
                        <Link
                          key={child.name}
                          href={child.href}
                          className="block text-sm text-slate-500 dark:text-slate-400 hover:text-slate-700 dark:hover:text-slate-300"
                          onClick={() => setIsOpen(false)}
                        >
                          {child.name}
                        </Link>
                      ))}
                    </div>
                  )}
                </div>
              ))}

              <div className="pt-4 border-t border-slate-200 dark:border-slate-800 space-y-2">
                <Link href="https://app.janua.dev/auth/signin" className="block">
                  <Button variant="outline" className="w-full">
                    Sign In
                  </Button>
                </Link>
                <Link href="https://app.janua.dev/auth/signup" className="block">
                  <Button className="w-full bg-brand-gradient hover:opacity-90 text-white">
                    Start Free
                    <ArrowRight className="ml-2 h-4 w-4" />
                  </Button>
                </Link>
              </div>
            </div>
          </motion.div>
        )}
      </div>
    </nav>
  )
}
