import { Metadata } from 'next'
import Link from 'next/link'
import {
  Server,
  Shield,
  Zap,
  DollarSign,
  Globe,
  Lock,
  CheckCircle,
  ArrowRight,
  Cloud,
  Database,
  Cpu,
  HardDrive
} from 'lucide-react'

export const metadata: Metadata = {
  title: 'Deploy Janua on Enclii | Self-Hosted Auth with Predictable Costs',
  description: 'Deploy Janua authentication on Enclii infrastructure. Own your auth data, pay predictable prices, scale without surprise bills.',
}

const benefits = [
  {
    icon: DollarSign,
    title: 'Predictable Costs',
    description: 'Flat monthly fee instead of per-MAU pricing. Know exactly what you\'ll pay at any scale.',
    highlight: 'Save 70%+ at scale vs Auth0/Clerk',
  },
  {
    icon: Shield,
    title: 'Data Sovereignty',
    description: 'Your auth data stays on your infrastructure. Full GDPR/HIPAA compliance ownership.',
    highlight: 'Zero third-party data access',
  },
  {
    icon: Zap,
    title: 'One-Click Deploy',
    description: 'Enclii\'s deployment system gets Janua running in minutes, not days.',
    highlight: '< 5 minute setup',
  },
  {
    icon: Globe,
    title: 'Edge-Ready',
    description: 'Deploy Janua close to your users with Enclii\'s multi-region support.',
    highlight: '< 50ms auth latency globally',
  },
]

const comparisonData = [
  {
    metric: '1K MAU',
    auth0: '$23/mo',
    clerk: '$25/mo',
    januaEnclii: '$0/mo*',
    savings: 'Free tier'
  },
  {
    metric: '10K MAU',
    auth0: '$228/mo',
    clerk: '$250/mo',
    januaEnclii: '$199/mo',
    savings: 'Save $29-51/mo'
  },
  {
    metric: '50K MAU',
    auth0: '$1,140/mo',
    clerk: '$1,250/mo',
    januaEnclii: '$199/mo',
    savings: 'Save $941-1,051/mo'
  },
  {
    metric: '100K MAU',
    auth0: '$2,280/mo',
    clerk: '$2,500/mo',
    januaEnclii: '$499/mo',
    savings: 'Save $1,781-2,001/mo'
  },
  {
    metric: '500K MAU',
    auth0: '$11,400/mo',
    clerk: 'Enterprise',
    januaEnclii: '$499/mo',
    savings: 'Save $10,900+/mo'
  },
]

const deploymentSteps = [
  {
    step: 1,
    title: 'Connect Infrastructure',
    description: 'Link your Hetzner, AWS, or other cloud account to Enclii',
    icon: Cloud,
  },
  {
    step: 2,
    title: 'Configure Janua',
    description: 'Set your auth requirements, SSO providers, and security policies',
    icon: Lock,
  },
  {
    step: 3,
    title: 'Deploy',
    description: 'One click deploys Janua with PostgreSQL, Redis, and all dependencies',
    icon: Server,
  },
  {
    step: 4,
    title: 'Integrate',
    description: 'Use Janua SDKs in your apps - same APIs, your infrastructure',
    icon: Cpu,
  },
]

const includedFeatures = [
  'Unlimited users (pay for infrastructure only)',
  'Social login (Google, GitHub, etc.)',
  'Enterprise SSO (SAML, OIDC)',
  'Multi-factor authentication',
  'Passwordless / Magic links',
  'User management dashboard',
  'Audit logs & compliance reports',
  'Custom branding',
  'Webhook integrations',
  'REST & GraphQL APIs',
  'React, Next.js, Vue SDKs',
  'Role-based access control',
]

export default function DeployOnEncliiPage() {
  return (
    <main className="min-h-screen bg-gradient-to-b from-gray-900 via-gray-800 to-gray-900">
      {/* Hero Section */}
      <section className="relative pt-24 pb-16 overflow-hidden">
        <div className="absolute inset-0 bg-grid-white/5" />
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 relative">
          <div className="text-center">
            <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-blue-500/10 border border-blue-500/20 text-blue-400 text-sm mb-8">
              <Server className="w-4 h-4" />
              <span>Janua + Enclii Bundle</span>
            </div>

            <h1 className="text-4xl md:text-6xl font-bold text-white mb-6">
              Deploy Janua on{' '}
              <span className="text-transparent bg-clip-text bg-gradient-to-r from-blue-400 to-cyan-400">
                Your Infrastructure
              </span>
            </h1>

            <p className="text-xl text-gray-300 max-w-3xl mx-auto mb-8">
              Stop paying per-user auth taxes. Deploy Janua on Enclii and own your
              authentication infrastructure with predictable, flat-rate pricing.
            </p>

            <div className="flex flex-col sm:flex-row gap-4 justify-center mb-12">
              <Link
                href="https://enclii.com/signup?template=janua"
                className="inline-flex items-center justify-center gap-2 px-8 py-4 bg-blue-600 hover:bg-blue-700 text-white font-semibold rounded-lg transition-colors"
              >
                Deploy Janua Now
                <ArrowRight className="w-5 h-5" />
              </Link>
              <Link
                href="/pricing"
                className="inline-flex items-center justify-center gap-2 px-8 py-4 bg-gray-700 hover:bg-gray-600 text-white font-semibold rounded-lg transition-colors"
              >
                Calculate Your Savings
              </Link>
            </div>

            {/* Quick Stats */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-6 max-w-4xl mx-auto">
              <div className="bg-gray-800/50 rounded-xl p-4 border border-gray-700">
                <div className="text-3xl font-bold text-blue-400">70%+</div>
                <div className="text-sm text-gray-400">Cost Savings at Scale</div>
              </div>
              <div className="bg-gray-800/50 rounded-xl p-4 border border-gray-700">
                <div className="text-3xl font-bold text-green-400">&lt;5min</div>
                <div className="text-sm text-gray-400">Deploy Time</div>
              </div>
              <div className="bg-gray-800/50 rounded-xl p-4 border border-gray-700">
                <div className="text-3xl font-bold text-purple-400">100%</div>
                <div className="text-sm text-gray-400">Data Ownership</div>
              </div>
              <div className="bg-gray-800/50 rounded-xl p-4 border border-gray-700">
                <div className="text-3xl font-bold text-cyan-400">∞</div>
                <div className="text-sm text-gray-400">Users Supported</div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Cost Comparison Section */}
      <section className="py-20 bg-gray-900/50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center mb-12">
            <h2 className="text-3xl md:text-4xl font-bold text-white mb-4">
              The Real Cost of Authentication
            </h2>
            <p className="text-lg text-gray-400 max-w-2xl mx-auto">
              Per-MAU pricing looks cheap at first. See what happens as you grow.
            </p>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-gray-700">
                  <th className="text-left py-4 px-4 text-gray-400 font-medium">Scale</th>
                  <th className="text-center py-4 px-4 text-gray-400 font-medium">Auth0</th>
                  <th className="text-center py-4 px-4 text-gray-400 font-medium">Clerk</th>
                  <th className="text-center py-4 px-4 text-blue-400 font-medium">Janua + Enclii</th>
                  <th className="text-center py-4 px-4 text-green-400 font-medium">Your Savings</th>
                </tr>
              </thead>
              <tbody>
                {comparisonData.map((row, idx) => (
                  <tr key={idx} className="border-b border-gray-800 hover:bg-gray-800/30">
                    <td className="py-4 px-4 text-white font-medium">{row.metric}</td>
                    <td className="py-4 px-4 text-center text-gray-300">{row.auth0}</td>
                    <td className="py-4 px-4 text-center text-gray-300">{row.clerk}</td>
                    <td className="py-4 px-4 text-center text-blue-400 font-semibold">{row.januaEnclii}</td>
                    <td className="py-4 px-4 text-center text-green-400 font-medium">{row.savings}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <p className="text-sm text-gray-500 mt-4 text-center">
            * Free tier includes self-hosted Janua on your own infrastructure. Enclii management fee starts at $199/mo for Pro tier.
          </p>
        </div>
      </section>

      {/* Benefits Section */}
      <section className="py-20">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center mb-12">
            <h2 className="text-3xl md:text-4xl font-bold text-white mb-4">
              Why Deploy Janua on Enclii?
            </h2>
            <p className="text-lg text-gray-400 max-w-2xl mx-auto">
              Get enterprise-grade authentication without enterprise-grade bills.
            </p>
          </div>

          <div className="grid md:grid-cols-2 gap-8">
            {benefits.map((benefit, idx) => (
              <div key={idx} className="bg-gray-800/30 rounded-2xl p-8 border border-gray-700 hover:border-blue-500/50 transition-colors">
                <div className="flex items-start gap-4">
                  <div className="p-3 bg-blue-500/10 rounded-xl">
                    <benefit.icon className="w-6 h-6 text-blue-400" />
                  </div>
                  <div>
                    <h3 className="text-xl font-semibold text-white mb-2">{benefit.title}</h3>
                    <p className="text-gray-400 mb-3">{benefit.description}</p>
                    <span className="inline-block px-3 py-1 bg-green-500/10 text-green-400 text-sm rounded-full">
                      {benefit.highlight}
                    </span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* How It Works */}
      <section className="py-20 bg-gray-900/50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center mb-12">
            <h2 className="text-3xl md:text-4xl font-bold text-white mb-4">
              Deploy in 4 Simple Steps
            </h2>
            <p className="text-lg text-gray-400 max-w-2xl mx-auto">
              From zero to production-ready auth in under 5 minutes.
            </p>
          </div>

          <div className="grid md:grid-cols-4 gap-6">
            {deploymentSteps.map((step, idx) => (
              <div key={idx} className="relative">
                <div className="bg-gray-800/50 rounded-xl p-6 border border-gray-700 h-full">
                  <div className="w-12 h-12 bg-blue-500/10 rounded-xl flex items-center justify-center mb-4">
                    <step.icon className="w-6 h-6 text-blue-400" />
                  </div>
                  <div className="text-sm text-blue-400 font-medium mb-2">Step {step.step}</div>
                  <h3 className="text-lg font-semibold text-white mb-2">{step.title}</h3>
                  <p className="text-sm text-gray-400">{step.description}</p>
                </div>
                {idx < deploymentSteps.length - 1 && (
                  <div className="hidden md:block absolute top-1/2 -right-3 transform -translate-y-1/2">
                    <ArrowRight className="w-6 h-6 text-gray-600" />
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Features Included */}
      <section className="py-20">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center mb-12">
            <h2 className="text-3xl md:text-4xl font-bold text-white mb-4">
              Everything Included
            </h2>
            <p className="text-lg text-gray-400 max-w-2xl mx-auto">
              Full Janua feature set, deployed on your infrastructure via Enclii.
            </p>
          </div>

          <div className="grid md:grid-cols-3 gap-4 max-w-4xl mx-auto">
            {includedFeatures.map((feature, idx) => (
              <div key={idx} className="flex items-center gap-3 p-4 bg-gray-800/30 rounded-lg">
                <CheckCircle className="w-5 h-5 text-green-400 flex-shrink-0" />
                <span className="text-gray-300">{feature}</span>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Infrastructure Section */}
      <section className="py-20 bg-gray-900/50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="grid md:grid-cols-2 gap-12 items-center">
            <div>
              <h2 className="text-3xl md:text-4xl font-bold text-white mb-6">
                Your Infrastructure, Your Rules
              </h2>
              <p className="text-lg text-gray-400 mb-6">
                Enclii deploys Janua to your cloud accounts. You maintain full control
                over your data and infrastructure while we handle the DevOps complexity.
              </p>
              <ul className="space-y-4">
                <li className="flex items-start gap-3">
                  <Database className="w-5 h-5 text-blue-400 mt-1" />
                  <div>
                    <span className="text-white font-medium">Managed PostgreSQL</span>
                    <p className="text-sm text-gray-400">Automatic backups, failover, and scaling</p>
                  </div>
                </li>
                <li className="flex items-start gap-3">
                  <HardDrive className="w-5 h-5 text-blue-400 mt-1" />
                  <div>
                    <span className="text-white font-medium">Redis Caching</span>
                    <p className="text-sm text-gray-400">Session management and rate limiting</p>
                  </div>
                </li>
                <li className="flex items-start gap-3">
                  <Server className="w-5 h-5 text-blue-400 mt-1" />
                  <div>
                    <span className="text-white font-medium">Auto-Scaling</span>
                    <p className="text-sm text-gray-400">Handle traffic spikes automatically</p>
                  </div>
                </li>
              </ul>
            </div>
            <div className="bg-gray-800 rounded-2xl p-8 border border-gray-700">
              <div className="text-sm text-gray-400 mb-4">Supported Providers</div>
              <div className="grid grid-cols-2 gap-4">
                {['Hetzner', 'AWS', 'Google Cloud', 'DigitalOcean', 'Vultr', 'Linode'].map((provider) => (
                  <div key={provider} className="flex items-center gap-2 p-3 bg-gray-900/50 rounded-lg">
                    <Cloud className="w-4 h-4 text-gray-400" />
                    <span className="text-gray-300">{provider}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* CTA Section */}
      <section className="py-20">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="bg-gradient-to-r from-blue-600 to-cyan-600 rounded-3xl p-12 text-center">
            <h2 className="text-3xl md:text-4xl font-bold text-white mb-4">
              Ready to Own Your Auth?
            </h2>
            <p className="text-lg text-blue-100 mb-8 max-w-2xl mx-auto">
              Deploy Janua on Enclii today. Start free, scale forever.
            </p>
            <div className="flex flex-col sm:flex-row gap-4 justify-center">
              <Link
                href="https://enclii.com/signup?template=janua"
                className="inline-flex items-center justify-center gap-2 px-8 py-4 bg-white text-blue-600 font-semibold rounded-lg hover:bg-gray-100 transition-colors"
              >
                Start Free Deployment
                <ArrowRight className="w-5 h-5" />
              </Link>
              <Link
                href="/contact"
                className="inline-flex items-center justify-center gap-2 px-8 py-4 bg-blue-700 text-white font-semibold rounded-lg hover:bg-blue-800 transition-colors"
              >
                Talk to Sales
              </Link>
            </div>
          </div>
        </div>
      </section>
    </main>
  )
}
