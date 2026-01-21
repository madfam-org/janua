'use client'

import { useState, useEffect } from 'react'
import { Card, CardContent } from '@janua/ui'
import { Badge } from '@janua/ui'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@janua/ui'
import Link from 'next/link'
import { FileCheck, ArrowLeft, Shield, Settings, FileText, Loader2, AlertCircle } from 'lucide-react'
import { apiCall } from '../../lib/auth'

import type { DataSubjectRequest, ConsentRecord, PrivacyPreferences, UserData, DataSubjectRightType } from './types'
import { DEFAULT_PRIVACY_PREFERENCES } from './constants'
import {
  PrivacySettingsSection,
  DSRForm,
  RequestHistory,
  ConsentRecords,
  PrivacyRightsInfo,
} from './components'

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'https://api.janua.dev'

export default function CompliancePage() {
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [user, setUser] = useState<UserData | null>(null)
  const [requests, setRequests] = useState<DataSubjectRequest[]>([])
  const [consents, setConsents] = useState<ConsentRecord[]>([])
  const [preferences, setPreferences] = useState<Partial<PrivacyPreferences>>({})
  const [submitting, setSubmitting] = useState(false)
  const [activeTab, setActiveTab] = useState('privacy')

  // DSR Form State
  const [dsrType, setDsrType] = useState<DataSubjectRightType>('access')
  const [dsrReason, setDsrReason] = useState('')

  // Privacy Settings State
  const [localPrefs, setLocalPrefs] = useState<PrivacyPreferences>(DEFAULT_PRIVACY_PREFERENCES)

  useEffect(() => {
    fetchData()
  }, [])

  useEffect(() => {
    if (preferences) {
      setLocalPrefs({
        analytics: preferences.analytics ?? false,
        marketing: preferences.marketing ?? false,
        third_party_sharing: preferences.third_party_sharing ?? false,
        profile_visibility: preferences.profile_visibility ?? 'organization',
        email_notifications: preferences.email_notifications ?? true,
        activity_tracking: preferences.activity_tracking ?? false,
        data_retention_override: preferences.data_retention_override,
        cookie_consent: preferences.cookie_consent ?? false,
      })
    }
  }, [preferences])

  const fetchData = async () => {
    try {
      setLoading(true)
      setError(null)

      // Fetch current user
      const meResponse = await apiCall(`${API_BASE_URL}/api/v1/auth/me`)
      if (!meResponse.ok) throw new Error('Failed to fetch user info')
      const userData = await meResponse.json()
      setUser(userData)

      // Fetch DSR requests
      try {
        const requestsResponse = await apiCall(`${API_BASE_URL}/api/v1/compliance/data-subject-requests`)
        if (requestsResponse.ok) {
          const requestsData = await requestsResponse.json()
          setRequests(Array.isArray(requestsData) ? requestsData : requestsData.requests || [])
        }
      } catch {
        setRequests([])
      }

      // Fetch consent records
      try {
        const consentsResponse = await apiCall(`${API_BASE_URL}/api/v1/compliance/consent`)
        if (consentsResponse.ok) {
          const consentsData = await consentsResponse.json()
          setConsents(Array.isArray(consentsData) ? consentsData : consentsData.consents || [])
        }
      } catch {
        setConsents([])
      }

      // Fetch privacy preferences
      try {
        const prefsResponse = await apiCall(`${API_BASE_URL}/api/v1/compliance/privacy-settings`)
        if (prefsResponse.ok) {
          const prefsData = await prefsResponse.json()
          setPreferences(prefsData.preferences || prefsData || {})
        }
      } catch {
        setPreferences({})
      }
    } catch (err) {
      console.error('Failed to fetch compliance data:', err)
      setError(err instanceof Error ? err.message : 'Failed to load compliance data')
    } finally {
      setLoading(false)
    }
  }

  const handleSubmitDSR = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!user) return

    setSubmitting(true)
    try {
      const response = await apiCall(`${API_BASE_URL}/api/v1/compliance/data-subject-requests`, {
        method: 'POST',
        body: JSON.stringify({
          user_id: user.id,
          request_type: dsrType,
          reason: dsrReason || undefined,
          email: user.email,
          verification_method: 'email',
        }),
      })

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}))
        throw new Error(errorData.detail || 'Failed to submit request')
      }

      setDsrReason('')
      fetchData()
      alert('Your request has been submitted. We will respond within 30 days as required by GDPR.')
    } catch (err) {
      alert(err instanceof Error ? err.message : 'Failed to submit request')
    } finally {
      setSubmitting(false)
    }
  }

  const handleSavePrivacySettings = async () => {
    if (!user) return

    setSubmitting(true)
    try {
      const response = await apiCall(`${API_BASE_URL}/api/v1/compliance/privacy-settings`, {
        method: 'PUT',
        body: JSON.stringify({
          user_id: user.id,
          preferences: localPrefs,
        }),
      })

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}))
        throw new Error(errorData.detail || 'Failed to save settings')
      }

      setPreferences(localPrefs)
      alert('Privacy settings saved successfully')
    } catch (err) {
      alert(err instanceof Error ? err.message : 'Failed to save settings')
    } finally {
      setSubmitting(false)
    }
  }

  const handleWithdrawConsent = async (consent: ConsentRecord) => {
    try {
      const response = await apiCall(`${API_BASE_URL}/api/v1/compliance/consent/${consent.purpose}`, {
        method: 'DELETE',
        body: JSON.stringify({ user_id: user?.id }),
      })
      if (!response.ok) throw new Error('Failed to withdraw consent')
      fetchData()
    } catch (err) {
      alert(err instanceof Error ? err.message : 'Failed to withdraw consent')
    }
  }

  if (loading) {
    return (
      <div className="bg-background flex min-h-screen items-center justify-center">
        <div className="text-center">
          <Loader2 className="text-muted-foreground mx-auto size-8 animate-spin" />
          <p className="text-muted-foreground mt-2 text-sm">Loading compliance data...</p>
        </div>
      </div>
    )
  }

  return (
    <div className="bg-background min-h-screen">
      {/* Header */}
      <header className="border-b">
        <div className="container mx-auto p-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-4">
              <Link href="/settings" className="text-muted-foreground hover:text-foreground">
                <ArrowLeft className="size-5" />
              </Link>
              <FileCheck className="text-primary size-8" />
              <div>
                <h1 className="text-2xl font-bold">Privacy & Compliance</h1>
                <p className="text-muted-foreground text-sm">
                  Manage your privacy settings and exercise your data rights
                </p>
              </div>
            </div>
            <Badge variant="secondary">GDPR Compliant</Badge>
          </div>
        </div>
      </header>

      <div className="container mx-auto px-4 py-8">
        {error && (
          <Card className="border-destructive mb-6">
            <CardContent className="pt-6">
              <div className="text-destructive flex items-center gap-2">
                <AlertCircle className="size-5" />
                <span>{error}</span>
              </div>
            </CardContent>
          </Card>
        )}

        <Tabs value={activeTab} onValueChange={setActiveTab} className="space-y-6">
          <TabsList className="grid w-full grid-cols-3">
            <TabsTrigger value="privacy" className="flex items-center gap-2">
              <Settings className="size-4" />
              Privacy Settings
            </TabsTrigger>
            <TabsTrigger value="requests" className="flex items-center gap-2">
              <FileText className="size-4" />
              Data Requests
            </TabsTrigger>
            <TabsTrigger value="consent" className="flex items-center gap-2">
              <Shield className="size-4" />
              Consent Management
            </TabsTrigger>
          </TabsList>

          {/* Privacy Settings Tab */}
          <TabsContent value="privacy" className="space-y-6">
            <PrivacySettingsSection
              preferences={localPrefs}
              onPreferencesChange={setLocalPrefs}
              onSave={handleSavePrivacySettings}
              saving={submitting}
            />
          </TabsContent>

          {/* Data Requests Tab */}
          <TabsContent value="requests" className="space-y-6">
            <DSRForm
              selectedType={dsrType}
              reason={dsrReason}
              onTypeChange={setDsrType}
              onReasonChange={setDsrReason}
              onSubmit={handleSubmitDSR}
              submitting={submitting}
            />
            <RequestHistory requests={requests} onRefresh={fetchData} />
          </TabsContent>

          {/* Consent Management Tab */}
          <TabsContent value="consent" className="space-y-6">
            <ConsentRecords consents={consents} onWithdraw={handleWithdrawConsent} />
            <PrivacyRightsInfo />
          </TabsContent>
        </Tabs>
      </div>
    </div>
  )
}
