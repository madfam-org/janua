'use client'

import { useState } from 'react'
import { motion } from 'framer-motion'
import { CheckCircle2, Circle, AlertCircle, Clock, Users, Code2, Shield, Zap, TrendingUp, GitBranch } from 'lucide-react'
import { Badge } from '@janua/ui'
import { Button } from '@janua/ui'
import Link from 'next/link'

interface RoadmapItem {
  title: string
  description: string
  status: 'completed' | 'in-progress' | 'planned'
  quarter: string
  category: 'security' | 'features' | 'quality' | 'performance'
  icon: React.ReactNode
}

const roadmapData: RoadmapItem[] = [
  // Completed
  {
    title: 'Edge-Native Architecture',
    description: 'Built from ground up for edge deployment with sub-30ms potential',
    status: 'completed',
    quarter: 'Q4 2024',
    category: 'performance',
    icon: <Zap className="w-4 h-4" />
  },
  {
    title: '13 Production SDKs',
    description: 'TypeScript, Python, Go, React, Vue, Next.js, Flutter, and more',
    status: 'completed',
    quarter: 'Q4 2024',
    category: 'features',
    icon: <Code2 className="w-4 h-4" />
  },
  {
    title: 'Passkeys & MFA Implementation',
    description: 'WebAuthn/FIDO2 passkeys and TOTP with backup codes',
    status: 'completed',
    quarter: 'Q4 2024',
    category: 'security',
    icon: <Shield className="w-4 h-4" />
  },
  {
    title: 'Enterprise SSO',
    description: 'SAML 2.0 and OIDC support with multi-tenancy',
    status: 'completed',
    quarter: 'Q4 2024',
    category: 'features',
    icon: <Users className="w-4 h-4" />
  },

  // In Progress
  {
    title: 'Test Coverage to 85%',
    description: 'Currently at 31.3%, actively improving with each commit',
    status: 'in-progress',
    quarter: 'Q1 2025',
    category: 'quality',
    icon: <TrendingUp className="w-4 h-4" />
  },
  {
    title: 'Package Publishing',
    description: 'Publish all SDKs to NPM, PyPI, and package registries',
    status: 'in-progress',
    quarter: 'Q1 2025',
    category: 'features',
    icon: <GitBranch className="w-4 h-4" />
  },

  // Planned
  {
    title: 'Third-Party Security Audit',
    description: 'Professional penetration testing and security certification',
    status: 'planned',
    quarter: 'Q1 2025',
    category: 'security',
    icon: <Shield className="w-4 h-4" />
  },
  {
    title: 'SOC 2 Compliance',
    description: 'Complete SOC 2 Type I certification process',
    status: 'planned',
    quarter: 'Q2 2025',
    category: 'security',
    icon: <Shield className="w-4 h-4" />
  },
  {
    title: 'Real-World Performance Benchmarks',
    description: 'Published benchmarks from production deployments at scale',
    status: 'planned',
    quarter: 'Q1 2025',
    category: 'performance',
    icon: <Zap className="w-4 h-4" />
  },
  {
    title: 'Additional OAuth Providers',
    description: 'Expand from 5 to 20+ OAuth providers',
    status: 'planned',
    quarter: 'Q2 2025',
    category: 'features',
    icon: <Users className="w-4 h-4" />
  },
  {
    title: 'Ruby & Java SDKs',
    description: 'Complete missing SDK implementations',
    status: 'planned',
    quarter: 'Q1 2025',
    category: 'features',
    icon: <Code2 className="w-4 h-4" />
  }
]

interface CurrentState {
  metric: string
  value: string | number
  status: 'green' | 'yellow' | 'red'
  trend?: 'up' | 'down' | 'stable'
  description?: string
}

const currentStateData: CurrentState[] = [
  {
    metric: 'Test Coverage',
    value: '31.3%',
    status: 'yellow',
    trend: 'up',
    description: 'Improving weekly, targeting 85%+'
  },
  {
    metric: 'Production SDKs',
    value: '13 of 15',
    status: 'green',
    trend: 'stable',
    description: 'Ruby & Java coming Q1 2025'
  },
  {
    metric: 'Edge Response Time',
    value: '<30ms',
    status: 'green',
    trend: 'stable',
    description: 'Theoretical, awaiting scale benchmarks'
  },
  {
    metric: 'Security Audit',
    value: 'Pending',
    status: 'yellow',
    trend: 'up',
    description: 'Scheduled for Q1 2025'
  },
  {
    metric: 'Package Publishing',
    value: 'Not Yet',
    status: 'red',
    trend: 'up',
    description: 'Ready for NPM/PyPI, coming soon'
  },
  {
    metric: 'OAuth Providers',
    value: '5',
    status: 'yellow',
    trend: 'up',
    description: 'Expanding to 20+ in Q2'
  }
]

export function TransparencyRoadmap() {
  const [selectedCategory, setSelectedCategory] = useState<string>('all')

  const categories = ['all', 'security', 'features', 'quality', 'performance']
  
  const filteredRoadmap = selectedCategory === 'all' 
    ? roadmapData 
    : roadmapData.filter(item => item.category === selectedCategory)

  const getStatusIcon = (status: RoadmapItem['status']) => {
    switch (status) {
      case 'completed':
        return <CheckCircle2 className="w-5 h-5 text-green-600 dark:text-green-400" />
      case 'in-progress':
        return <Clock className="w-5 h-5 text-blue-600 dark:text-blue-400 animate-pulse" />
      case 'planned':
        return <Circle className="w-5 h-5 text-slate-400" />
    }
  }

  const getCategoryColor = (category: RoadmapItem['category']) => {
    switch (category) {
      case 'security':
        return 'bg-red-100 dark:bg-red-900/20 text-red-700 dark:text-red-300'
      case 'features':
        return 'bg-blue-100 dark:bg-blue-900/20 text-blue-700 dark:text-blue-300'
      case 'quality':
        return 'bg-amber-100 dark:bg-amber-900/20 text-amber-700 dark:text-amber-300'
      case 'performance':
        return 'bg-green-100 dark:bg-green-900/20 text-green-700 dark:text-green-300'
    }
  }

  const getStateColor = (status: CurrentState['status']) => {
    switch (status) {
      case 'green':
        return 'text-green-600 dark:text-green-400'
      case 'yellow':
        return 'text-amber-600 dark:text-amber-400'
      case 'red':
        return 'text-red-600 dark:text-red-400'
    }
  }

  const getTrendIcon = (trend?: CurrentState['trend']) => {
    if (!trend) return null
    switch (trend) {
      case 'up':
        return '↑'
      case 'down':
        return '↓'
      case 'stable':
        return '→'
    }
  }

  return (
    <section className="py-20 px-4 sm:px-6 lg:px-8">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="text-center mb-12">
          <h2 className="text-3xl sm:text-4xl font-bold text-slate-900 dark:text-white mb-4">
            Full Transparency: Where We Are Today
          </h2>
          <p className="text-lg text-slate-600 dark:text-slate-400 max-w-3xl mx-auto">
            We believe in radical honesty. Here's exactly where Janua stands today and where we're going.
            No marketing fluff, just facts.
          </p>
        </div>

        {/* Current State Dashboard */}
        <div className="mb-16">
          <h3 className="text-2xl font-bold text-slate-900 dark:text-white mb-8 text-center">
            Current State Metrics
          </h3>
          
          <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-6">
            {currentStateData.map((item, idx) => (
              <motion.div
                key={idx}
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: idx * 0.05 }}
                className="bg-white dark:bg-slate-900 rounded-lg border border-slate-200 dark:border-slate-800 p-6"
              >
                <div className="flex items-start justify-between mb-2">
                  <div>
                    <p className="text-sm font-medium text-slate-600 dark:text-slate-400">
                      {item.metric}
                    </p>
                    <div className="flex items-center gap-2 mt-1">
                      <span className={`text-2xl font-bold ${getStateColor(item.status)}`}>
                        {item.value}
                      </span>
                      {item.trend && (
                        <span className={`text-lg ${getStateColor(item.status)}`}>
                          {getTrendIcon(item.trend)}
                        </span>
                      )}
                    </div>
                  </div>
                </div>
                {item.description && (
                  <p className="text-sm text-slate-500 dark:text-slate-400 mt-2">
                    {item.description}
                  </p>
                )}
              </motion.div>
            ))}
          </div>
        </div>

        {/* Honest Assessment */}
        <div className="mb-16 p-8 bg-slate-50 dark:bg-slate-900/50 rounded-lg">
          <h3 className="text-xl font-semibold text-slate-900 dark:text-white mb-6">
            An Honest Assessment
          </h3>
          
          <div className="grid md:grid-cols-2 gap-8">
            <div>
              <h4 className="font-medium text-slate-700 dark:text-slate-300 mb-4 flex items-center gap-2">
                <CheckCircle2 className="w-5 h-5 text-green-600" />
                What's Working Well
              </h4>
              <ul className="space-y-3 text-sm text-slate-600 dark:text-slate-400">
                <li className="flex items-start gap-2">
                  <span className="text-green-600 mt-0.5">•</span>
                  <span>Edge-native architecture delivering on performance promises</span>
                </li>
                <li className="flex items-start gap-2">
                  <span className="text-green-600 mt-0.5">•</span>
                  <span>13 production-ready SDKs with clean, documented APIs</span>
                </li>
                <li className="flex items-start gap-2">
                  <span className="text-green-600 mt-0.5">•</span>
                  <span>Complete passkey and MFA implementation working in production</span>
                </li>
                <li className="flex items-start gap-2">
                  <span className="text-green-600 mt-0.5">•</span>
                  <span>Enterprise features (SSO, RBAC) fully implemented</span>
                </li>
                <li className="flex items-start gap-2">
                  <span className="text-green-600 mt-0.5">•</span>
                  <span>Open source core with transparent development</span>
                </li>
              </ul>
            </div>

            <div>
              <h4 className="font-medium text-slate-700 dark:text-slate-300 mb-4 flex items-center gap-2">
                <AlertCircle className="w-5 h-5 text-amber-600" />
                What Needs Work
              </h4>
              <ul className="space-y-3 text-sm text-slate-600 dark:text-slate-400">
                <li className="flex items-start gap-2">
                  <span className="text-amber-600 mt-0.5">•</span>
                  <span>Test coverage at 31.3% - actively improving but not enterprise-ready</span>
                </li>
                <li className="flex items-start gap-2">
                  <span className="text-amber-600 mt-0.5">•</span>
                  <span>No third-party security audit yet (scheduled Q1 2025)</span>
                </li>
                <li className="flex items-start gap-2">
                  <span className="text-amber-600 mt-0.5">•</span>
                  <span>SDKs not published to package registries yet</span>
                </li>
                <li className="flex items-start gap-2">
                  <span className="text-amber-600 mt-0.5">•</span>
                  <span>Limited OAuth providers (5 vs competitors' 20+)</span>
                </li>
                <li className="flex items-start gap-2">
                  <span className="text-amber-600 mt-0.5">•</span>
                  <span>Performance claims based on architecture, not production benchmarks</span>
                </li>
              </ul>
            </div>
          </div>
        </div>

        {/* Roadmap */}
        <div>
          <h3 className="text-2xl font-bold text-slate-900 dark:text-white mb-8 text-center">
            Development Roadmap
          </h3>

          {/* Category Filter */}
          <div className="flex flex-wrap gap-2 justify-center mb-8">
            {categories.map(category => (
              <Button
                key={category}
                variant={selectedCategory === category ? 'default' : 'outline'}
                size="sm"
                onClick={() => setSelectedCategory(category)}
                className="capitalize"
              >
                {category}
              </Button>
            ))}
          </div>

          {/* Roadmap Timeline */}
          <div className="space-y-4">
            {filteredRoadmap.map((item, idx) => (
              <motion.div
                key={idx}
                initial={{ opacity: 0, x: -20 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: idx * 0.05 }}
                className="flex gap-4 p-4 bg-white dark:bg-slate-900 rounded-lg border border-slate-200 dark:border-slate-800"
              >
                <div className="flex-shrink-0 mt-1">
                  {getStatusIcon(item.status)}
                </div>
                
                <div className="flex-grow">
                  <div className="flex items-start justify-between">
                    <div>
                      <h4 className="font-semibold text-slate-900 dark:text-white flex items-center gap-2">
                        {item.icon}
                        {item.title}
                      </h4>
                      <p className="text-sm text-slate-600 dark:text-slate-400 mt-1">
                        {item.description}
                      </p>
                    </div>
                    <div className="flex items-center gap-2 ml-4">
                      <Badge variant="outline" className={`text-xs ${getCategoryColor(item.category)}`}>
                        {item.category}
                      </Badge>
                      <Badge variant="outline" className="text-xs">
                        {item.quarter}
                      </Badge>
                    </div>
                  </div>
                </div>
              </motion.div>
            ))}
          </div>
        </div>

        {/* CTA Section */}
        <div className="mt-12 text-center">
          <p className="text-sm text-slate-600 dark:text-slate-400 mb-4">
            We update this roadmap weekly. Follow our progress on GitHub.
          </p>
          <div className="flex gap-4 justify-center">
            <Button asChild>
              <Link href="https://github.com/madfam-io/janua" target="_blank">
                <GitBranch className="w-4 h-4 mr-2" />
                View on GitHub
              </Link>
            </Button>
            <Button variant="outline" asChild>
              <Link href="https://github.com/madfam-io/janua/issues">
                Report Issues
              </Link>
            </Button>
          </div>
        </div>
      </div>
    </section>
  )
}