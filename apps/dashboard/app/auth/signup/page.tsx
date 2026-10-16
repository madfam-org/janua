'use client'

import { Suspense, useCallback, useEffect, useRef, useState, type FormEvent } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import {
  Button,
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
  Input,
  Label,
  SignUp,
} from '@janua/ui'
import { Building2, Loader2, Shield, Sparkles } from 'lucide-react'
import { januaClient } from '@/lib/janua-client'
import { setAuthCookie } from '@/lib/auth-storage'
import { useAuth } from '@/lib/auth'

// Storage keys - must match auth.tsx
const STORAGE_KEYS = {
  ACCESS_TOKEN: 'janua_access_token',
  USER: 'janua_user',
  COOKIE: 'janua_access_token',
} as const

// Carries the plan selected on the pricing page through the signup flow.
// sessionStorage (not only the query param) because the OAuth round-trip
// strips query params when it returns to this page.
const PLAN_STORAGE_KEY = 'janua_signup_plan'

const PAID_PLANS = ['pro', 'scale'] as const
type PaidPlan = (typeof PAID_PLANS)[number]

const PLAN_LABELS: Record<PaidPlan, string> = {
  pro: 'Pro',
  scale: 'Scale',
}

function parsePlan(value: string | null): PaidPlan | null {
  return value && (PAID_PLANS as readonly string[]).includes(value) ? (value as PaidPlan) : null
}

/** Derives a URL-safe slug from an organization name (mirrors the API's slug rules). */
function slugifyOrgName(name: string): string {
  return name
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 100)
}

type SignupPhase = 'account' | 'organization' | 'plan'

function SignupFlow() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const { isAuthenticated, isLoading } = useAuth()

  const [phase, setPhase] = useState<SignupPhase>('account')
  const [plan, setPlan] = useState<PaidPlan | null>(null)
  const [checkingAccount, setCheckingAccount] = useState(false)

  const [orgName, setOrgName] = useState('')
  const [orgError, setOrgError] = useState<string | null>(null)
  const [orgSubmitting, setOrgSubmitting] = useState(false)

  const orgSlug = slugifyOrgName(orgName)

  // Resolve plan intent from the query param first, then sessionStorage.
  useEffect(() => {
    const fromQuery = parsePlan(searchParams.get('plan'))
    if (fromQuery) {
      sessionStorage.setItem(PLAN_STORAGE_KEY, fromQuery)
      setPlan(fromQuery)
    } else {
      setPlan(parsePlan(sessionStorage.getItem(PLAN_STORAGE_KEY)))
    }
  }, [searchParams])

  const finishSignup = useCallback(
    (selectedPlan: PaidPlan | null) => {
      if (selectedPlan) {
        setPhase('plan')
      } else {
        sessionStorage.removeItem(PLAN_STORAGE_KEY)
        router.replace('/')
      }
    },
    [router]
  )

  // Once the session is live (post email signup or OAuth return), move past
  // the account step: brand-new accounts get the organization step, accounts
  // that already belong to an organization skip ahead.
  const advancedRef = useRef(false)
  useEffect(() => {
    if (isLoading || !isAuthenticated || phase !== 'account' || advancedRef.current) return
    advancedRef.current = true
    setCheckingAccount(true)

    let cancelled = false
    ;(async () => {
      let hasOrganization = false
      try {
        const data = await januaClient.organizations.listOrganizations()
        const organizations = Array.isArray(data)
          ? data
          : ((data as any)?.organizations ?? (data as any)?.items ?? [])
        hasOrganization = organizations.length > 0
      } catch {
        // Lookup failure: fall through to the (skippable) organization step.
      }
      if (cancelled) return
      setCheckingAccount(false)
      if (hasOrganization) {
        finishSignup(plan)
      } else {
        setPhase('organization')
      }
    })()

    return () => {
      cancelled = true
    }
  }, [isAuthenticated, isLoading, phase, plan, finishSignup])

  // Mirrors handleAfterSignIn on /login: sync the token cookie for the
  // middleware and persist the user for the dashboard shell. The SignUp
  // component then navigates to `redirectUrl` (this page) and the
  // authenticated re-entry above advances the flow.
  const handleAfterSignUp = (user: unknown) => {
    const token = localStorage.getItem(STORAGE_KEYS.ACCESS_TOKEN)
    if (token) {
      setAuthCookie(token)
    }
    if (user) {
      localStorage.setItem(STORAGE_KEYS.USER, JSON.stringify(user))
    }
  }

  const handleCreateOrganization = async (event: FormEvent) => {
    event.preventDefault()
    if (!orgSlug) {
      setOrgError('Please enter an organization name.')
      return
    }
    setOrgError(null)
    setOrgSubmitting(true)
    try {
      await januaClient.organizations.createOrganization({ name: orgName.trim(), slug: orgSlug })
      finishSignup(plan)
    } catch (err) {
      setOrgError(
        err instanceof Error && err.message
          ? err.message
          : 'Could not create the organization. Try a different name.'
      )
      setOrgSubmitting(false)
    }
  }

  // While the provider restores the session (e.g. right after the OAuth
  // return) show a neutral loading card instead of flashing the form.
  if (isLoading || checkingAccount) {
    return <SignupFallback />
  }

  if (phase === 'organization') {
    return (
      <Card className="w-full max-w-md">
        <CardHeader className="text-center">
          <div className="mb-2 flex justify-center">
            <Building2 className="text-primary size-10" />
          </div>
          <CardTitle className="text-2xl">Name your organization</CardTitle>
          <CardDescription>
            Organizations group your team, applications, and settings. You can rename it later.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleCreateOrganization} className="space-y-4">
            {orgError && (
              <div className="bg-destructive/15 text-destructive text-sm p-3 rounded-md">
                {orgError}
              </div>
            )}
            <div className="space-y-2">
              <Label htmlFor="signup-org-name">Organization name</Label>
              <Input
                id="signup-org-name"
                type="text"
                placeholder="Acme Inc."
                value={orgName}
                onChange={(e) => setOrgName(e.target.value)}
                disabled={orgSubmitting}
              />
              {orgSlug && (
                <p className="text-muted-foreground text-xs">URL identifier: {orgSlug}</p>
              )}
            </div>
            <Button type="submit" className="w-full" disabled={orgSubmitting || !orgSlug}>
              {orgSubmitting ? (
                <>
                  <Loader2 className="mr-2 size-4 animate-spin" />
                  Creating organization...
                </>
              ) : (
                'Create organization'
              )}
            </Button>
            <Button
              type="button"
              variant="ghost"
              className="w-full"
              disabled={orgSubmitting}
              onClick={() => finishSignup(plan)}
            >
              Skip for now
            </Button>
          </form>
        </CardContent>
      </Card>
    )
  }

  if (phase === 'plan' && plan) {
    return (
      <Card className="w-full max-w-md">
        <CardHeader className="text-center">
          <div className="mb-2 flex justify-center">
            <Sparkles className="text-primary size-10" />
          </div>
          <CardTitle className="text-2xl">You selected the {PLAN_LABELS[plan]} plan</CardTitle>
          <CardDescription>
            Your account starts on the free Community tier. Continue to billing to start your{' '}
            {PLAN_LABELS[plan]} upgrade.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <Button
            className="w-full"
            onClick={() => {
              sessionStorage.removeItem(PLAN_STORAGE_KEY)
              router.push('/settings/billing')
            }}
          >
            Continue to billing
          </Button>
          <Button
            variant="ghost"
            className="w-full"
            onClick={() => {
              sessionStorage.removeItem(PLAN_STORAGE_KEY)
              router.push('/')
            }}
          >
            Go to dashboard
          </Button>
        </CardContent>
      </Card>
    )
  }

  return (
    <div className="w-full max-w-md">
      <div className="mb-6 flex justify-center">
        <Shield className="text-primary size-12" />
      </div>

      {plan && (
        <div className="border-primary/30 bg-primary/10 mb-4 flex items-start gap-2 rounded-md border p-3">
          <Sparkles className="text-primary mt-0.5 size-5 shrink-0" />
          <p className="text-sm">
            You selected the <span className="font-semibold">{PLAN_LABELS[plan]}</span> plan.
            Create your account first — you can start the upgrade right after.
          </p>
        </div>
      )}

      <SignUp
        januaClient={januaClient}
        afterSignUp={handleAfterSignUp}
        redirectUrl={plan ? `/auth/signup?plan=${plan}` : '/auth/signup'}
        signInUrl="/login"
        requireEmailVerification={false}
        socialProviders={{ google: true, github: true, microsoft: true, apple: true }}
        termsUrl="https://janua.dev/legal/terms"
        privacyUrl="https://janua.dev/legal/privacy"
      />
    </div>
  )
}

function SignupFallback() {
  return (
    <Card className="w-full max-w-md">
      <CardHeader className="text-center">
        <div className="mb-4 flex justify-center">
          <Shield className="text-primary size-12" />
        </div>
        <CardTitle className="text-2xl">Create your Janua account</CardTitle>
        <CardDescription>Loading...</CardDescription>
      </CardHeader>
      <CardContent>
        <div className="flex justify-center py-8">
          <Loader2 className="text-primary size-8 animate-spin" />
        </div>
      </CardContent>
    </Card>
  )
}

export default function SignupPage() {
  return (
    <div className="bg-background flex min-h-screen items-center justify-center p-4">
      <Suspense fallback={<SignupFallback />}>
        <SignupFlow />
      </Suspense>
    </div>
  )
}
