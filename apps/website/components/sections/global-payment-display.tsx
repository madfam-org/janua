'use client'

import { motion } from 'framer-motion'
import { CreditCard, Globe, DollarSign, Building2, Check, ArrowRight, Percent, Shield } from 'lucide-react'
import { Badge } from '@janua/ui'
import { Button } from '@janua/ui'

interface PaymentProvider {
  name: string
  logo: string
  region: string
  currencies: string[]
  paymentMethods: string[]
  features: string[]
  processingFees: string
  settlementTime: string
}

export function GlobalPaymentDisplay() {
  const paymentProviders: PaymentProvider[] = [
    {
      name: 'Conekta',
      logo: '🇲🇽',
      region: 'Mexico & LATAM',
      currencies: ['MXN', 'USD'],
      paymentMethods: ['OXXO', 'SPEI', 'Credit/Debit Cards', 'Bank Transfer'],
      features: [
        'Mexican peso native billing',
        'OXXO cash payments',
        'SPEI instant transfers',
        'SAT compliant invoicing',
        'Monthly installments (MSI)',
        'Local payment methods'
      ],
      processingFees: '2.9% + $2.50 MXN',
      settlementTime: '1-2 business days'
    },
    {
      name: 'Fungies.io',
      logo: '🌍',
      region: 'Global (150+ countries)',
      currencies: ['USD', 'EUR', 'GBP', 'JPY', 'CAD', 'AUD', '+135 more'],
      paymentMethods: ['Credit/Debit Cards', 'ACH', 'SEPA', 'Wire Transfer', 'Digital Wallets'],
      features: [
        'Global payment processing',
        'Multi-currency support',
        'Automatic tax calculation',
        'Fraud detection AI',
        'Subscription management',
        'Revenue optimization'
      ],
      processingFees: '2.5% + $0.30 USD',
      settlementTime: '2-3 business days'
    }
  ]

  const regionalBenefits = [
    {
      region: 'Mexico',
      flag: '🇲🇽',
      benefits: [
        'Pay in Mexican Pesos',
        'OXXO & SPEI support',
        'SAT-compliant invoicing',
        'Local bank transfers',
        'No FX conversion fees'
      ]
    },
    {
      region: 'United States',
      flag: '🇺🇸',
      benefits: [
        'ACH direct debit',
        'All major cards',
        'Instant verification',
        'Same-day settlement',
        'Tax compliance'
      ]
    },
    {
      region: 'Europe',
      flag: '🇪🇺',
      benefits: [
        'SEPA payments',
        'PSD2 compliant',
        'GDPR ready',
        'Multi-currency',
        'VAT handling'
      ]
    },
    {
      region: 'Asia Pacific',
      flag: '🌏',
      benefits: [
        'Local payment methods',
        'Multi-language support',
        'Regional compliance',
        'Fast settlement',
        'Mobile wallets'
      ]
    }
  ]

  return (
    <section className="py-24 px-4 sm:px-6 lg:px-8 bg-gradient-to-b from-white to-gray-50 dark:from-gray-950 dark:to-gray-900">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.6 }}
          className="text-center mb-16"
        >
          <Badge variant="outline" className="mb-4">
            <CreditCard className="w-3 h-3 mr-1" />
            Global Payments
          </Badge>
          <h2 className="text-4xl sm:text-5xl font-bold text-gray-900 dark:text-white mb-6">
            Smart Payment Routing,
            <span className="block text-transparent bg-clip-text bg-gradient-to-r from-green-600 to-blue-600 dark:from-green-400 dark:to-blue-400">
              Local Experience Everywhere
            </span>
          </h2>
          <p className="text-xl text-gray-600 dark:text-gray-300 max-w-3xl mx-auto">
            Mexican customers pay in pesos with Conekta. International customers enjoy global payment options with Fungies.io.
            Automatic routing based on customer location.
          </p>
        </motion.div>

        {/* Payment Providers Comparison */}
        <div className="grid lg:grid-cols-2 gap-8 mb-16">
          {paymentProviders.map((provider, index) => (
            <motion.div
              key={provider.name}
              initial={{ opacity: 0, x: index === 0 ? -20 : 20 }}
              whileInView={{ opacity: 1, x: 0 }}
              viewport={{ once: true }}
              transition={{ duration: 0.6, delay: index * 0.1 }}
              className={`bg-white dark:bg-gray-800 rounded-2xl p-8 border-2 ${
                provider.name === 'Conekta'
                  ? 'border-green-200 dark:border-green-800'
                  : 'border-blue-200 dark:border-blue-800'
              }`}
            >
              {/* Provider Header */}
              <div className="flex items-start justify-between mb-6">
                <div>
                  <div className="flex items-center gap-3 mb-2">
                    <span className="text-4xl">{provider.logo}</span>
                    <h3 className="text-2xl font-bold text-gray-900 dark:text-white">
                      {provider.name}
                    </h3>
                  </div>
                  <p className="text-gray-600 dark:text-gray-300 font-medium">
                    {provider.region}
                  </p>
                </div>
                {provider.name === 'Conekta' && (
                  <Badge className="bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400">
                    Mexico Optimized
                  </Badge>
                )}
              </div>

              {/* Currencies */}
              <div className="mb-6">
                <h4 className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-3">
                  Supported Currencies
                </h4>
                <div className="flex flex-wrap gap-2">
                  {provider.currencies.map((currency) => (
                    <Badge key={currency} variant="secondary" className="font-mono">
                      {currency}
                    </Badge>
                  ))}
                </div>
              </div>

              {/* Payment Methods */}
              <div className="mb-6">
                <h4 className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-3">
                  Payment Methods
                </h4>
                <div className="flex flex-wrap gap-2">
                  {provider.paymentMethods.map((method) => (
                    <span
                      key={method}
                      className="text-xs px-3 py-1 bg-gray-100 dark:bg-gray-700 rounded-full text-gray-700 dark:text-gray-300"
                    >
                      {method}
                    </span>
                  ))}
                </div>
              </div>

              {/* Features */}
              <div className="mb-6">
                <h4 className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-3">
                  Key Features
                </h4>
                <ul className="space-y-2">
                  {provider.features.map((feature) => (
                    <li key={feature} className="flex items-start text-sm">
                      <Check className="w-4 h-4 text-green-500 mr-2 flex-shrink-0 mt-0.5" />
                      <span className="text-gray-600 dark:text-gray-300">{feature}</span>
                    </li>
                  ))}
                </ul>
              </div>

              {/* Pricing Info */}
              <div className="pt-6 border-t border-gray-200 dark:border-gray-700">
                <div className="grid grid-cols-2 gap-4 text-sm">
                  <div>
                    <span className="text-gray-500 dark:text-gray-400">Processing Fees</span>
                    <p className="font-semibold text-gray-900 dark:text-white">{provider.processingFees}</p>
                  </div>
                  <div>
                    <span className="text-gray-500 dark:text-gray-400">Settlement</span>
                    <p className="font-semibold text-gray-900 dark:text-white">{provider.settlementTime}</p>
                  </div>
                </div>
              </div>
            </motion.div>
          ))}
        </div>

        {/* Regional Benefits */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.6, delay: 0.3 }}
          className="mb-16"
        >
          <h3 className="text-2xl font-bold text-gray-900 dark:text-white mb-8 text-center">
            Optimized for Every Region
          </h3>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
            {regionalBenefits.map((region, index) => (
              <motion.div
                key={region.region}
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ duration: 0.5, delay: index * 0.1 }}
                whileHover={{ scale: 1.05 }}
                className="bg-white dark:bg-gray-800 rounded-xl p-6 border border-gray-200 dark:border-gray-700 hover:shadow-lg transition-all"
              >
                <div className="text-3xl mb-3 text-center">{region.flag}</div>
                <h4 className="text-lg font-semibold text-gray-900 dark:text-white mb-3 text-center">
                  {region.region}
                </h4>
                <ul className="space-y-2">
                  {region.benefits.map((benefit) => (
                    <li key={benefit} className="flex items-start text-sm">
                      <Check className="w-4 h-4 text-green-500 mr-2 flex-shrink-0 mt-0.5" />
                      <span className="text-gray-600 dark:text-gray-300">{benefit}</span>
                    </li>
                  ))}
                </ul>
              </motion.div>
            ))}
          </div>
        </motion.div>

        {/* Smart Routing Visualization */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.6, delay: 0.4 }}
          className="bg-gradient-to-r from-blue-600 to-purple-600 rounded-2xl p-12 text-center text-white"
        >
          <Globe className="w-16 h-16 mx-auto mb-6 text-white/80" />
          <h3 className="text-3xl font-bold mb-4">
            Automatic Payment Routing
          </h3>
          <p className="text-xl text-blue-100 mb-8 max-w-2xl mx-auto">
            Our intelligent system automatically routes payments to the optimal provider based on customer location,
            ensuring the best experience and lowest fees.
          </p>
          <div className="grid md:grid-cols-3 gap-8 mb-8">
            <div>
              <div className="text-4xl font-bold mb-2">98%</div>
              <div className="text-blue-100">Success Rate</div>
            </div>
            <div>
              <div className="text-4xl font-bold mb-2">150+</div>
              <div className="text-blue-100">Countries Supported</div>
            </div>
            <div>
              <div className="text-4xl font-bold mb-2">30%</div>
              <div className="text-blue-100">Lower Fees vs Competitors</div>
            </div>
          </div>
          <Button
            size="lg"
            variant="secondary"
            className="bg-white text-blue-600 hover:bg-gray-100"
          >
            View Pricing Calculator
            <ArrowRight className="ml-2 w-5 h-5" />
          </Button>
        </motion.div>
      </div>
    </section>
  )
}