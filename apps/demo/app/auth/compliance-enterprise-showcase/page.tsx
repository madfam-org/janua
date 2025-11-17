'use client'

import { ConsentManager, DataSubjectRequestForm, PrivacySettings } from '@plinto/ui'
import { useState } from 'react'

export default function ComplianceEnterpriseShowcase() {
  const [activeTab, setActiveTab] = useState<'consent' | 'rights' | 'privacy'>('consent')

  // Sample consent purposes
  const samplePurposes = [
    {
      id: 'essential',
      name: 'Essential Operations',
      description: 'Required for basic platform functionality and security',
      required: true,
      legal_basis: 'contract' as const,
    },
    {
      id: 'analytics',
      name: 'Analytics & Performance',
      description: 'Help us improve the product by collecting usage data',
      required: false,
      legal_basis: 'legitimate_interest' as const,
    },
    {
      id: 'marketing',
      name: 'Marketing Communications',
      description: 'Receive product updates, newsletters, and promotional content',
      required: false,
      legal_basis: 'consent' as const,
    },
    {
      id: 'third_party',
      name: 'Third-Party Integrations',
      description: 'Share data with trusted partners for enhanced functionality',
      required: false,
      legal_basis: 'consent' as const,
    },
  ]

  return (
    <div className="min-h-screen bg-gray-50 p-8">
      <div className="mx-auto max-w-6xl">
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-gray-900">
            Compliance & Privacy Dashboard
          </h1>
          <p className="mt-2 text-gray-600">
            GDPR-compliant data management, consent tracking, and privacy controls
          </p>
        </div>

        {/* Tab Navigation */}
        <div className="mb-6 flex space-x-1 rounded-lg bg-white p-1 shadow">
          {[
            { key: 'consent' as const, label: 'Consent Management', icon: '✓' },
            { key: 'rights' as const, label: 'Data Rights', icon: '📋' },
            { key: 'privacy' as const, label: 'Privacy Settings', icon: '🔒' },
          ].map((tab) => (
            <button
              key={tab.key}
              onClick={() => setActiveTab(tab.key)}
              className={`flex-1 rounded-md px-4 py-2 text-sm font-medium transition-colors ${
                activeTab === tab.key
                  ? 'bg-blue-600 text-white'
                  : 'text-gray-600 hover:bg-gray-100'
              }`}
            >
              <span className="mr-2">{tab.icon}</span>
              {tab.label}
            </button>
          ))}
        </div>

        {/* Tab Content */}
        <div>
          {activeTab === 'consent' && (
            <div className="space-y-6">
              <div className="rounded-lg bg-blue-50 p-4">
                <h3 className="font-semibold text-blue-900">
                  GDPR Article 7 - Consent Management
                </h3>
                <p className="mt-1 text-sm text-blue-700">
                  Record and manage user consent for data processing activities. Users can grant or
                  withdraw consent at any time.
                </p>
              </div>

              <ConsentManager
                userId="user-demo-123"
                purposes={samplePurposes}
                mode="manage"
                showLegalBasis={true}
                onSubmit={async (consents) => {
                  // removed console.log
                  // Simulate API call
                  await new Promise((resolve) => setTimeout(resolve, 1000))
                }}
                onWithdraw={async (purposeId) => {
                  // removed console.log
                  await new Promise((resolve) => setTimeout(resolve, 1000))
                }}
              />
            </div>
          )}

          {activeTab === 'rights' && (
            <div className="space-y-6">
              <div className="rounded-lg bg-purple-50 p-4">
                <h3 className="font-semibold text-purple-900">
                  GDPR Articles 15-22 - Data Subject Rights
                </h3>
                <p className="mt-1 text-sm text-purple-700">
                  Exercise your rights to access, erasure, rectification, portability, and more
                  under GDPR.
                </p>
              </div>

              <DataSubjectRequestForm
                userId="user-demo-123"
                userEmail="demo@example.com"
                onSubmit={async (request) => {
                  // removed console.log
                  // Simulate API call
                  await new Promise((resolve) => setTimeout(resolve, 1500))
                  return {
                    id: 'req-' + Date.now(),
                    user_id: request.user_id,
                    request_type: request.request_type,
                    status: 'pending' as const,
                    requested_at: new Date().toISOString(),
                    reason: request.reason,
                  }
                }}
              />
            </div>
          )}

          {activeTab === 'privacy' && (
            <div className="space-y-6">
              <div className="rounded-lg bg-green-50 p-4">
                <h3 className="font-semibold text-green-900">Privacy Preferences</h3>
                <p className="mt-1 text-sm text-green-700">
                  Control how your data is collected, used, and shared across the platform.
                </p>
              </div>

              <PrivacySettings
                userId="user-demo-123"
                currentPreferences={{
                  analytics: true,
                  marketing: false,
                  third_party_sharing: false,
                  profile_visibility: 'organization',
                  email_notifications: true,
                  activity_tracking: true,
                  cookie_consent: true,
                }}
                showAdvanced={true}
                onSave={async (preferences) => {
                  // removed console.log
                  await new Promise((resolve) => setTimeout(resolve, 1000))
                }}
              />
            </div>
          )}
        </div>

        {/* Features Grid */}
        <div className="mt-12 grid gap-6 md:grid-cols-3">
          <div className="rounded-lg bg-white p-6 shadow">
            <div className="flex h-12 w-12 items-center justify-center rounded-full bg-blue-100 text-2xl">
              ✓
            </div>
            <h3 className="mt-4 font-semibold">Consent Tracking</h3>
            <p className="mt-2 text-sm text-gray-600">
              Complete audit trail of all consent grants and withdrawals with legal basis
              documentation
            </p>
          </div>

          <div className="rounded-lg bg-white p-6 shadow">
            <div className="flex h-12 w-12 items-center justify-center rounded-full bg-purple-100 text-2xl">
              📋
            </div>
            <h3 className="mt-4 font-semibold">Data Rights</h3>
            <p className="mt-2 text-sm text-gray-600">
              30-day GDPR-compliant response workflow for access, erasure, and portability requests
            </p>
          </div>

          <div className="rounded-lg bg-white p-6 shadow">
            <div className="flex h-12 w-12 items-center justify-center rounded-full bg-green-100 text-2xl">
              🔒
            </div>
            <h3 className="mt-4 font-semibold">Privacy Controls</h3>
            <p className="mt-2 text-sm text-gray-600">
              Granular privacy settings with profile visibility, data sharing, and retention
              controls
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}
