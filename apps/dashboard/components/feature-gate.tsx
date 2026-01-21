'use client'

import { useState, useEffect, createContext, useContext, ReactNode } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@janua/ui'
import { Button } from '@janua/ui'
import { Badge } from '@janua/ui'
import { Lock, Sparkles, ArrowRight } from 'lucide-react'
import { apiCall } from '@/lib/auth'

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'https://api.janua.dev'

// Feature definitions
export type FeatureKey =
  | 'sso_saml'
  | 'sso_oidc'
  | 'scim'
  | 'audit_logs'
  | 'advanced_rbac'
  | 'custom_branding'
  | 'compliance_reports'
  | 'api_rate_limit_increase'
  | 'priority_support'

interface FeatureDefinition {
  key: FeatureKey
  name: string
  description: string
  requiredPlan: 'free' | 'pro' | 'enterprise'
}

export const FEATURES: Record<FeatureKey, FeatureDefinition> = {
  sso_saml: {
    key: 'sso_saml',
    name: 'SAML SSO',
    description: 'Single Sign-On with SAML 2.0 identity providers',
    requiredPlan: 'enterprise',
  },
  sso_oidc: {
    key: 'sso_oidc',
    name: 'OIDC SSO',
    description: 'Single Sign-On with OpenID Connect providers',
    requiredPlan: 'enterprise',
  },
  scim: {
    key: 'scim',
    name: 'SCIM Provisioning',
    description: 'Automated user provisioning from identity providers',
    requiredPlan: 'enterprise',
  },
  audit_logs: {
    key: 'audit_logs',
    name: 'Audit Logs',
    description: 'Detailed audit trail and security event logs',
    requiredPlan: 'pro',
  },
  advanced_rbac: {
    key: 'advanced_rbac',
    name: 'Advanced RBAC',
    description: 'Custom roles and fine-grained permissions',
    requiredPlan: 'pro',
  },
  custom_branding: {
    key: 'custom_branding',
    name: 'Custom Branding',
    description: 'White-label login pages and email templates',
    requiredPlan: 'enterprise',
  },
  compliance_reports: {
    key: 'compliance_reports',
    name: 'Compliance Reports',
    description: 'SOC 2, GDPR, and HIPAA compliance reports',
    requiredPlan: 'enterprise',
  },
  api_rate_limit_increase: {
    key: 'api_rate_limit_increase',
    name: 'Increased Rate Limits',
    description: 'Higher API rate limits for high-volume applications',
    requiredPlan: 'pro',
  },
  priority_support: {
    key: 'priority_support',
    name: 'Priority Support',
    description: '24/7 priority support with dedicated account manager',
    requiredPlan: 'enterprise',
  },
}

// Plan hierarchy for comparison
const PLAN_HIERARCHY: Record<string, number> = {
  free: 0,
  pro: 1,
  enterprise: 2,
}

interface OrganizationPlan {
  plan: 'free' | 'pro' | 'enterprise'
  features: FeatureKey[]
}

interface FeatureGateContextType {
  plan: OrganizationPlan | null
  loading: boolean
  hasFeature: (feature: FeatureKey) => boolean
  canAccessPlan: (requiredPlan: string) => boolean
  refresh: () => Promise<void>
}

const FeatureGateContext = createContext<FeatureGateContextType>({
  plan: null,
  loading: true,
  hasFeature: () => false,
  canAccessPlan: () => false,
  refresh: async () => {},
})

export function FeatureGateProvider({ children }: { children: ReactNode }) {
  const [plan, setPlan] = useState<OrganizationPlan | null>(null)
  const [loading, setLoading] = useState(true)

  const fetchPlan = async () => {
    try {
      // Get current user's organization
      const meResponse = await apiCall(`${API_BASE_URL}/api/v1/auth/me`)
      if (!meResponse.ok) {
        setLoading(false)
        return
      }
      const userData = await meResponse.json()

      const orgId = userData.current_organization_id || userData.organization_id
      if (!orgId) {
        // Default to free plan if no organization
        setPlan({ plan: 'free', features: [] })
        setLoading(false)
        return
      }

      // Fetch organization details with plan info
      const orgResponse = await apiCall(`${API_BASE_URL}/api/v1/organizations/${orgId}`)
      if (orgResponse.ok) {
        const orgData = await orgResponse.json()
        setPlan({
          plan: orgData.billing_plan || 'free',
          features: orgData.enabled_features || [],
        })
      } else {
        // Default to free plan on error
        setPlan({ plan: 'free', features: [] })
      }
    } catch (error) {
      console.error('Failed to fetch organization plan:', error)
      setPlan({ plan: 'free', features: [] })
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchPlan()
  }, [])

  const hasFeature = (feature: FeatureKey): boolean => {
    if (!plan) return false

    // Check if feature is explicitly enabled
    if (plan.features.includes(feature)) return true

    // Check if plan level grants access
    const featureDef = FEATURES[feature]
    if (!featureDef) return false

    return (PLAN_HIERARCHY[plan.plan] || 0) >= (PLAN_HIERARCHY[featureDef.requiredPlan] || 0)
  }

  const canAccessPlan = (requiredPlan: string): boolean => {
    if (!plan) return false
    return (PLAN_HIERARCHY[plan.plan] || 0) >= (PLAN_HIERARCHY[requiredPlan] || 0)
  }

  return (
    <FeatureGateContext.Provider
      value={{
        plan,
        loading,
        hasFeature,
        canAccessPlan,
        refresh: fetchPlan,
      }}
    >
      {children}
    </FeatureGateContext.Provider>
  )
}

export function useFeatureGate() {
  return useContext(FeatureGateContext)
}

// Component to gate content based on feature access
interface FeatureGateProps {
  feature: FeatureKey
  children: ReactNode
  fallback?: ReactNode
}

export function FeatureGate({ feature, children, fallback }: FeatureGateProps) {
  const { hasFeature, loading } = useFeatureGate()

  if (loading) {
    return (
      <div className="bg-muted h-32 animate-pulse rounded-lg" />
    )
  }

  if (hasFeature(feature)) {
    return <>{children}</>
  }

  if (fallback) {
    return <>{fallback}</>
  }

  return <FeatureLockedCard feature={feature} />
}

// Locked feature card
interface FeatureLockedCardProps {
  feature: FeatureKey
}

export function FeatureLockedCard({ feature }: FeatureLockedCardProps) {
  const featureDef = FEATURES[feature]

  if (!featureDef) return null

  const planLabel = featureDef.requiredPlan === 'enterprise' ? 'Enterprise' : 'Pro'

  return (
    <Card className="border-dashed">
      <CardHeader>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="bg-muted rounded-lg p-2">
              <Lock className="text-muted-foreground size-5" />
            </div>
            <div>
              <CardTitle className="flex items-center gap-2 text-lg">
                {featureDef.name}
                <Badge variant="secondary">{planLabel}</Badge>
              </CardTitle>
              <CardDescription>{featureDef.description}</CardDescription>
            </div>
          </div>
        </div>
      </CardHeader>
      <CardContent>
        <div className="bg-muted/50 flex items-center justify-between rounded-lg p-4">
          <div className="text-muted-foreground flex items-center gap-2 text-sm">
            <Sparkles className="size-4" />
            <span>Upgrade to {planLabel} to unlock this feature</span>
          </div>
          <Button size="sm" variant="outline" asChild>
            <a href="https://janua.dev/pricing" target="_blank" rel="noopener noreferrer">
              View Plans
              <ArrowRight className="ml-2 size-4" />
            </a>
          </Button>
        </div>
      </CardContent>
    </Card>
  )
}

// Badge for feature requirement indication
interface FeatureBadgeProps {
  feature: FeatureKey
  showLock?: boolean
}

export function FeatureBadge({ feature, showLock = true }: FeatureBadgeProps) {
  const { hasFeature } = useFeatureGate()
  const featureDef = FEATURES[feature]

  if (!featureDef) return null
  if (hasFeature(feature)) return null

  const planLabel = featureDef.requiredPlan === 'enterprise' ? 'Enterprise' : 'Pro'

  return (
    <Badge variant="secondary" className="flex items-center gap-1">
      {showLock && <Lock className="size-3" />}
      {planLabel}
    </Badge>
  )
}

// Hook for checking multiple features at once
export function useFeatures(features: FeatureKey[]): Record<FeatureKey, boolean> {
  const { hasFeature } = useFeatureGate()

  return features.reduce(
    (acc, feature) => ({
      ...acc,
      [feature]: hasFeature(feature),
    }),
    {} as Record<FeatureKey, boolean>
  )
}
