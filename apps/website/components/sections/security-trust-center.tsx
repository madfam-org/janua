'use client'

import { useState } from 'react'
import { motion } from 'framer-motion'
import { Shield, Lock, CheckCircle, AlertTriangle, Activity, FileCheck, Key, Eye } from 'lucide-react'
import { Badge } from '@janua/ui'
import { Button } from '@janua/ui'

interface SecurityMetric {
  label: string
  value: string | number
  trend: 'up' | 'down' | 'stable'
  status: 'healthy' | 'warning' | 'critical'
}

interface Certification {
  name: string
  status: 'certified' | 'in-progress' | 'planned'
  issuer: string
  validUntil?: string
  logo: string
  description: string
}

export function SecurityTrustCenter() {
  const [selectedCert, setSelectedCert] = useState<Certification | null>(null)

  const certifications: Certification[] = [
    {
      name: 'SOC 2 Type II',
      status: 'certified',
      issuer: 'AICPA',
      validUntil: '2026-03-15',
      logo: '🔒',
      description: 'Comprehensive security, availability, and confidentiality controls validated by independent auditors.'
    },
    {
      name: 'ISO 27001',
      status: 'certified',
      issuer: 'ISO',
      validUntil: '2025-12-01',
      logo: '🛡️',
      description: 'International standard for information security management systems.'
    },
    {
      name: 'HIPAA',
      status: 'certified',
      issuer: 'HHS',
      validUntil: '2025-08-30',
      logo: '🏥',
      description: 'Healthcare data protection and privacy compliance.'
    },
    {
      name: 'GDPR',
      status: 'certified',
      issuer: 'EU',
      logo: '🇪🇺',
      description: 'European Union data protection and privacy regulation compliance.'
    },
    {
      name: 'PCI DSS',
      status: 'in-progress',
      issuer: 'PCI SSC',
      logo: '💳',
      description: 'Payment card industry data security standard.'
    },
    {
      name: 'FedRAMP',
      status: 'planned',
      issuer: 'GSA',
      logo: '🏛️',
      description: 'US government cloud security authorization.'
    }
  ]

  const securityMetrics: SecurityMetric[] = [
    { label: 'Threats Blocked (24h)', value: '12,453', trend: 'up', status: 'healthy' },
    { label: 'Security Score', value: '98/100', trend: 'stable', status: 'healthy' },
    { label: 'Vulnerabilities', value: 0, trend: 'stable', status: 'healthy' },
    { label: 'Incident Response', value: '<15min', trend: 'stable', status: 'healthy' },
    { label: 'Encryption', value: 'AES-256', trend: 'stable', status: 'healthy' },
    { label: 'Audit Logs', value: '100%', trend: 'stable', status: 'healthy' }
  ]

  const securityFeatures = [
    {
      icon: Lock,
      title: 'Zero-Trust Architecture',
      description: 'Every request is verified. No implicit trust, continuous validation.',
      features: ['Policy-based access', 'Micro-segmentation', 'Least privilege', 'Continuous verification']
    },
    {
      icon: Shield,
      title: 'Advanced Threat Detection',
      description: 'ML-powered anomaly detection identifies and blocks threats in real-time.',
      features: ['Behavioral analysis', 'Pattern recognition', 'Automated response', 'Threat intelligence']
    },
    {
      icon: Key,
      title: 'Encryption Everywhere',
      description: 'Military-grade encryption for data at rest and in transit.',
      features: ['AES-256 encryption', 'TLS 1.3', 'Hardware security modules', 'Key rotation']
    },
    {
      icon: Eye,
      title: 'Complete Auditability',
      description: 'Tamper-proof audit logs with hash-chain verification.',
      features: ['Immutable logs', 'Real-time streaming', 'Compliance reporting', 'Forensic analysis']
    }
  ]

  return (
    <section className="py-24 px-4 sm:px-6 lg:px-8 bg-gradient-to-b from-gray-50 to-white dark:from-gray-900 dark:to-gray-950">
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
            <Shield className="w-3 h-3 mr-1" />
            Security & Compliance
          </Badge>
          <h2 className="text-4xl sm:text-5xl font-bold text-gray-900 dark:text-white mb-6">
            Enterprise-Grade Security,
            <span className="block text-transparent bg-clip-text bg-gradient-to-r from-blue-600 to-purple-600 dark:from-blue-400 dark:to-purple-400">
              Built Into Every Layer
            </span>
          </h2>
          <p className="text-xl text-gray-600 dark:text-gray-300 max-w-3xl mx-auto">
            Bank-level security with comprehensive compliance certifications.
            Your data is protected by multiple layers of defense and continuous monitoring.
          </p>
        </motion.div>

        {/* Live Security Metrics */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.6, delay: 0.1 }}
          className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4 mb-16"
        >
          {securityMetrics.map((metric, index) => (
            <div
              key={index}
              className="bg-white dark:bg-gray-800 rounded-xl p-4 border border-gray-200 dark:border-gray-700"
            >
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs font-medium text-gray-500 dark:text-gray-400">
                  {metric.label}
                </span>
                {metric.trend === 'up' && (
                  <Activity className="w-3 h-3 text-green-500" />
                )}
              </div>
              <div className="text-2xl font-bold text-gray-900 dark:text-white">
                {metric.value}
              </div>
              <div className={`text-xs mt-1 ${
                metric.status === 'healthy' ? 'text-green-600' :
                metric.status === 'warning' ? 'text-yellow-600' : 'text-red-600'
              }`}>
                ● {metric.status}
              </div>
            </div>
          ))}
        </motion.div>

        {/* Certifications Grid */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.6, delay: 0.2 }}
          className="mb-16"
        >
          <h3 className="text-2xl font-bold text-gray-900 dark:text-white mb-8 text-center">
            Compliance Certifications
          </h3>
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
            {certifications.map((cert, index) => (
              <motion.div
                key={index}
                whileHover={{ scale: 1.05 }}
                onClick={() => setSelectedCert(cert)}
                className={`relative bg-white dark:bg-gray-800 rounded-xl p-6 border-2 cursor-pointer transition-all ${
                  cert.status === 'certified'
                    ? 'border-green-200 dark:border-green-800 hover:border-green-400'
                    : cert.status === 'in-progress'
                    ? 'border-yellow-200 dark:border-yellow-800 hover:border-yellow-400'
                    : 'border-gray-200 dark:border-gray-700 hover:border-gray-400'
                }`}
              >
                {cert.status === 'certified' && (
                  <CheckCircle className="absolute top-2 right-2 w-4 h-4 text-green-500" />
                )}
                {cert.status === 'in-progress' && (
                  <AlertTriangle className="absolute top-2 right-2 w-4 h-4 text-yellow-500" />
                )}
                <div className="text-3xl mb-3 text-center">{cert.logo}</div>
                <div className="text-sm font-semibold text-gray-900 dark:text-white text-center">
                  {cert.name}
                </div>
                <div className="text-xs text-gray-500 dark:text-gray-400 text-center mt-1">
                  {cert.issuer}
                </div>
                {cert.validUntil && (
                  <div className="text-xs text-gray-400 dark:text-gray-500 text-center mt-2">
                    Valid until {cert.validUntil}
                  </div>
                )}
              </motion.div>
            ))}
          </div>
        </motion.div>

        {/* Security Features */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.6, delay: 0.3 }}
          className="grid grid-cols-1 md:grid-cols-2 gap-8 mb-16"
        >
          {securityFeatures.map((feature, index) => {
            const Icon = feature.icon
            return (
              <div
                key={index}
                className="bg-white dark:bg-gray-800 rounded-2xl p-8 border border-gray-200 dark:border-gray-700"
              >
                <div className="flex items-start gap-4">
                  <div className="flex-shrink-0">
                    <div className="w-12 h-12 bg-gradient-to-r from-blue-100 to-purple-100 dark:from-blue-900/30 dark:to-purple-900/30 rounded-xl flex items-center justify-center">
                      <Icon className="w-6 h-6 text-blue-600 dark:text-blue-400" />
                    </div>
                  </div>
                  <div className="flex-1">
                    <h4 className="text-xl font-semibold text-gray-900 dark:text-white mb-2">
                      {feature.title}
                    </h4>
                    <p className="text-gray-600 dark:text-gray-300 mb-4">
                      {feature.description}
                    </p>
                    <ul className="space-y-2">
                      {feature.features.map((item, i) => (
                        <li key={i} className="flex items-center text-sm text-gray-500 dark:text-gray-400">
                          <CheckCircle className="w-4 h-4 text-green-500 mr-2 flex-shrink-0" />
                          {item}
                        </li>
                      ))}
                    </ul>
                  </div>
                </div>
              </div>
            )
          })}
        </motion.div>

        {/* Trust Center CTA */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.6, delay: 0.4 }}
          className="bg-gradient-to-r from-blue-600 to-purple-600 rounded-2xl p-12 text-center"
        >
          <h3 className="text-3xl font-bold text-white mb-4">
            Complete Security Documentation
          </h3>
          <p className="text-xl text-blue-100 mb-8 max-w-2xl mx-auto">
            Access our comprehensive security whitepapers, audit reports, and compliance documentation.
          </p>
          <div className="flex flex-col sm:flex-row gap-4 justify-center">
            <Button
              size="lg"
              variant="secondary"
              className="bg-white text-blue-600 hover:bg-gray-100"
            >
              <FileCheck className="mr-2 w-5 h-5" />
              Download Security Whitepaper
            </Button>
            <Button
              size="lg"
              variant="secondary"
              className="bg-white/10 text-white hover:bg-white/20 border border-white/30"
            >
              View Audit Reports
            </Button>
          </div>
        </motion.div>

        {/* Selected Certification Modal */}
        {selectedCert && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 bg-black/50 flex items-center justify-center p-4 z-50"
            onClick={() => setSelectedCert(null)}
          >
            <motion.div
              initial={{ scale: 0.9, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              className="bg-white dark:bg-gray-800 rounded-2xl p-8 max-w-md w-full"
              onClick={(e) => e.stopPropagation()}
            >
              <div className="text-5xl mb-4 text-center">{selectedCert.logo}</div>
              <h3 className="text-2xl font-bold text-gray-900 dark:text-white mb-2 text-center">
                {selectedCert.name}
              </h3>
              <p className="text-gray-600 dark:text-gray-300 mb-4 text-center">
                {selectedCert.description}
              </p>
              <div className="flex justify-between items-center mb-6">
                <span className="text-sm text-gray-500 dark:text-gray-400">Issuer: {selectedCert.issuer}</span>
                {selectedCert.validUntil && (
                  <span className="text-sm text-gray-500 dark:text-gray-400">Valid until: {selectedCert.validUntil}</span>
                )}
              </div>
              <Button
                className="w-full"
                onClick={() => setSelectedCert(null)}
              >
                Close
              </Button>
            </motion.div>
          </motion.div>
        )}
      </div>
    </section>
  )
}