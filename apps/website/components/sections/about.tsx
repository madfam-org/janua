'use client'

import { motion } from 'framer-motion'
import { Shield, Zap, Globe, Heart, Users, Target } from 'lucide-react'
import Image from 'next/image'

export function AboutSection() {
  const values = [
    {
      icon: Shield,
      title: 'Security First',
      description: 'Every line of code is written with security in mind. Your users\' data is sacred.'
    },
    {
      icon: Zap,
      title: 'Performance Obsessed',
      description: 'Sub-30ms verification isn\'t a goal, it\'s a requirement. Speed is a feature.'
    },
    {
      icon: Globe,
      title: 'Global by Default',
      description: 'Built for the internet, not just Silicon Valley. Multi-region from day one.'
    },
    {
      icon: Heart,
      title: 'Developer Love',
      description: 'We\'re developers building for developers. Great DX is non-negotiable.'
    },
    {
      icon: Users,
      title: 'Community Driven',
      description: 'Open roadmap, transparent pricing, and real humans answering support.'
    },
    {
      icon: Target,
      title: 'Focused Excellence',
      description: 'We do identity exceptionally well. Nothing more, nothing less.'
    }
  ]

  const team = [
    {
      name: 'The Janua Team',
      role: 'Building the future of identity',
      bio: 'A distributed team of security engineers, systems architects, and developer advocates from companies like Cloudflare, Auth0, and Okta.'
    }
  ]

  return (
    <div className="py-12">
      {/* Hero */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
        className="text-center mb-16"
      >
        <h1 className="text-5xl font-bold text-gray-900 dark:text-white mb-6">
          Identity infrastructure for the modern web
        </h1>
        <p className="text-xl text-gray-600 dark:text-gray-300 max-w-3xl mx-auto">
          We believe authentication should be invisible when it works and 
          impossible to compromise when attacked.
        </p>
      </motion.div>

      {/* Mission */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, delay: 0.1 }}
        className="mb-24"
      >
        <div className="bg-gradient-to-r from-blue-600 to-purple-600 rounded-2xl p-12 text-white">
          <h2 className="text-3xl font-bold mb-6">Our Mission</h2>
          <p className="text-lg leading-relaxed mb-6">
            To make secure identity management accessible to every developer and 
            affordable for every company. We're building the authentication layer 
            the internet deserves — fast, secure, and respectful of user privacy.
          </p>
          <p className="text-lg leading-relaxed">
            Authentication is the front door to your application. It should be 
            welcoming to legitimate users and impenetrable to attackers. That's 
            not a trade-off — it's a design requirement.
          </p>
        </div>
      </motion.div>

      {/* Values */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, delay: 0.2 }}
        className="mb-24"
      >
        <h2 className="text-3xl font-bold text-gray-900 dark:text-white mb-12 text-center">
          Our Values
        </h2>
        <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-8">
          {values.map((value, index) => {
            const Icon = value.icon
            return (
              <motion.div
                key={value.title}
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.5, delay: 0.1 + index * 0.05 }}
                className="bg-white dark:bg-gray-900 rounded-xl p-6 border border-gray-200 dark:border-gray-700"
              >
                <div className="flex items-center mb-4">
                  <div className="w-12 h-12 bg-gradient-to-br from-blue-600 to-purple-600 rounded-lg flex items-center justify-center">
                    <Icon className="h-6 w-6 text-white" />
                  </div>
                  <h3 className="ml-4 text-xl font-semibold text-gray-900 dark:text-white">
                    {value.title}
                  </h3>
                </div>
                <p className="text-gray-600 dark:text-gray-400">
                  {value.description}
                </p>
              </motion.div>
            )
          })}
        </div>
      </motion.div>

      {/* Story */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, delay: 0.3 }}
        className="mb-24"
      >
        <div className="grid lg:grid-cols-2 gap-12 items-center">
          <div>
            <h2 className="text-3xl font-bold text-gray-900 dark:text-white mb-6">
              Why We Built Janua
            </h2>
            <div className="space-y-4 text-gray-600 dark:text-gray-400">
              <p>
                After building authentication systems at scale for years, we kept 
                seeing the same problems: slow verification, poor developer experience, 
                vendor lock-in, and pricing that punishes growth.
              </p>
              <p>
                Existing solutions force you to choose between speed and security, 
                between developer experience and user experience, between features 
                and affordability. We rejected these false choices.
              </p>
              <p>
                Janua is our answer: authentication infrastructure that's fast 
                everywhere, secure by default, and priced fairly. Built on modern 
                edge computing, embracing standards like WebAuthn, and designed 
                for the way applications are built today.
              </p>
              <p>
                We're not trying to be everything to everyone. We're building the 
                best identity platform for developers who care about performance, 
                security, and their users' experience.
              </p>
            </div>
          </div>
          <div className="relative h-96 bg-gradient-to-br from-blue-100 to-purple-100 dark:from-blue-950 dark:to-purple-950 rounded-2xl flex items-center justify-center">
            <div className="text-6xl font-bold text-transparent bg-clip-text bg-gradient-to-br from-blue-600 to-purple-600">
              P
            </div>
          </div>
        </div>
      </motion.div>

      {/* Company Info */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, delay: 0.4 }}
        className="mb-24"
      >
        <div className="bg-gray-50 dark:bg-gray-900 rounded-2xl p-12">
          <h2 className="text-3xl font-bold text-gray-900 dark:text-white mb-8">
            Company Information
          </h2>
          <div className="grid md:grid-cols-2 gap-8">
            <div>
              <h3 className="font-semibold text-gray-900 dark:text-white mb-2">
                Headquarters
              </h3>
              <p className="text-gray-600 dark:text-gray-400">
                Janua by Aureo Labs<br />
                A MADFAM Company<br />
                Distributed Team<br />
                San Francisco, CA / Remote
              </p>
            </div>
            <div>
              <h3 className="font-semibold text-gray-900 dark:text-white mb-2">
                Founded
              </h3>
              <p className="text-gray-600 dark:text-gray-400">
                2024<br />
                Currently in Private Alpha<br />
                Backed by founders and angels<br />
                Growing thoughtfully
              </p>
            </div>
          </div>
          <div className="mt-8 pt-8 border-t border-gray-200 dark:border-gray-700">
            <h3 className="font-semibold text-gray-900 dark:text-white mb-4">
              Investors & Advisors
            </h3>
            <p className="text-gray-600 dark:text-gray-400">
              Backed by technical founders and operators from leading identity, 
              security, and infrastructure companies. Our advisors have built and 
              scaled authentication systems serving billions of users.
            </p>
          </div>
        </div>
      </motion.div>

      {/* Join Us */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, delay: 0.5 }}
        className="text-center"
      >
        <h2 className="text-3xl font-bold text-gray-900 dark:text-white mb-6">
          Join Our Mission
        </h2>
        <p className="text-xl text-gray-600 dark:text-gray-300 max-w-3xl mx-auto mb-8">
          We're looking for exceptional engineers who are passionate about 
          building foundational infrastructure for the internet.
        </p>
        <a
          href="/careers"
          className="inline-flex items-center text-blue-600 dark:text-blue-400 hover:underline font-semibold"
        >
          View Open Positions →
        </a>
      </motion.div>
    </div>
  )
}