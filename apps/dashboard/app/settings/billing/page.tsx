'use client'

import { useState, useEffect } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@janua/ui'
import { Button } from '@janua/ui'
import { Badge } from '@janua/ui'
import Link from 'next/link'
import {
  ArrowLeft,
  CreditCard,
  Loader2,
  AlertCircle,
  CheckCircle2,
  Download,
  ExternalLink,
  Zap,
  Shield,
  Users,
  Building2,
  Check,
  Star,
} from 'lucide-react'
import { getBillingCurrent, getInvoices, getPaymentMethods, createCheckout } from '@/lib/api'
import { TOAST_DISMISS_MS } from '@/lib/constants'

interface Subscription {
  id: string
  plan: 'community' | 'pro' | 'scale' | 'enterprise'
  status: 'active' | 'trialing' | 'past_due' | 'canceled'
  current_period_start: string
  current_period_end: string
  cancel_at_period_end: boolean
}

interface Invoice {
  id: string
  number: string
  amount: number
  currency: string
  status: 'paid' | 'open' | 'void' | 'draft'
  created_at: string
  pdf_url: string | null
}

interface PaymentMethod {
  id: string
  type: 'card' | 'bank_account'
  brand: string
  last4: string
  exp_month: number
  exp_year: number
  is_default: boolean
}

interface PlanDetails {
  id: 'community' | 'pro' | 'scale' | 'enterprise'
  name: string
  price: string
  period: string
  description: string
  features: string[]
  highlighted: boolean
  badge?: string
}

const plans: PlanDetails[] = [
  {
    id: 'community',
    name: 'Community',
    price: 'Free',
    period: 'forever',
    description: 'For personal projects and small teams getting started.',
    features: [
      'Up to 1,000 monthly active users',
      'Email/password authentication',
      'Social login (Google, GitHub)',
      'Basic MFA (TOTP)',
      'Community support',
      '1 organization',
    ],
    highlighted: false,
  },
  {
    id: 'pro',
    name: 'Pro',
    price: '$49',
    period: '/month',
    description: 'For growing teams that need more power and flexibility.',
    features: [
      'Up to 10,000 monthly active users',
      'All Community features',
      'SAML 2.0 SSO',
      'WebAuthn / Passkeys',
      'Custom branding',
      'Webhook events',
      'Priority email support',
      '5 organizations',
    ],
    highlighted: true,
    badge: 'Most Popular',
  },
  {
    id: 'scale',
    name: 'Scale',
    price: '$199',
    period: '/month',
    description: 'For scaling businesses with advanced security needs.',
    features: [
      'Up to 100,000 monthly active users',
      'All Pro features',
      'SCIM provisioning',
      'Advanced audit logs',
      'Custom password policies',
      'Rate limiting controls',
      'Dedicated support channel',
      'Unlimited organizations',
    ],
    highlighted: false,
  },
  {
    id: 'enterprise',
    name: 'Enterprise',
    price: 'Custom',
    period: '',
    description: 'For organizations with custom compliance and scale needs.',
    features: [
      'Unlimited monthly active users',
      'All Scale features',
      'Dedicated infrastructure',
      'SLA guarantees (99.99%)',
      'SOC 2 compliance support',
      'Custom integrations',
      'On-call engineering support',
      'Migration assistance',
    ],
    highlighted: false,
    badge: 'Contact Sales',
  },
]

const planOrder: Record<string, number> = {
  community: 0,
  pro: 1,
  scale: 2,
  enterprise: 3,
}

const statusColors: Record<string, 'default' | 'secondary' | 'destructive' | 'outline'> = {
  active: 'default',
  trialing: 'secondary',
  past_due: 'destructive',
  canceled: 'outline',
  paid: 'default',
  open: 'secondary',
  void: 'outline',
  draft: 'outline',
}

const planIcons: Record<string, React.ReactNode> = {
  community: <Users className="size-5" />,
  pro: <Zap className="size-5" />,
  scale: <Shield className="size-5" />,
  enterprise: <Building2 className="size-5" />,
}

export default function BillingPage() {
  const [subscription, setSubscription] = useState<Subscription | null>(null)
  const [invoices, setInvoices] = useState<Invoice[]>([])
  const [paymentMethods, setPaymentMethods] = useState<PaymentMethod[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)
  const [upgrading, setUpgrading] = useState<string | null>(null)

  useEffect(() => {
    fetchBillingData()
  }, [])

  const fetchBillingData = async () => {
    try {
      setLoading(true)
      setError(null)

      const [subResult, invResult] = await Promise.allSettled([
        getBillingCurrent(),
        getInvoices(),
      ])

      if (subResult.status === 'fulfilled') {
        setSubscription(subResult.value as unknown as Subscription)
      } else {
        // Default to community plan if no billing data
        setSubscription({
          id: 'default',
          plan: 'community',
          status: 'active',
          current_period_start: new Date().toISOString(),
          current_period_end: new Date(Date.now() + 30 * 24 * 60 * 60 * 1000).toISOString(),
          cancel_at_period_end: false,
        })
      }

      if (invResult.status === 'fulfilled') {
        const data = invResult.value
        setInvoices(Array.isArray(data) ? data as unknown as Invoice[] : (data as unknown as { invoices?: Invoice[] }).invoices || [])
      }

      // Fetch payment methods
      try {
        const data = await getPaymentMethods()
        setPaymentMethods(Array.isArray(data) ? data as unknown as PaymentMethod[] : (data as unknown as { payment_methods?: PaymentMethod[] }).payment_methods || [])
      } catch {
        // Payment methods may not exist yet
      }
    } catch (err) {
      console.error('Failed to fetch billing data:', err)
      setError(err instanceof Error ? err.message : 'Failed to load billing information')
    } finally {
      setLoading(false)
    }
  }

  const handleUpgrade = async (planId: string) => {
    if (planId === 'enterprise') {
      window.open('mailto:sales@janua.dev?subject=Enterprise%20Plan%20Inquiry', '_blank')
      return
    }

    try {
      setUpgrading(planId)
      setError(null)

      const data = await createCheckout({ plan_id: planId })

      if (data.checkout_url) {
        window.location.href = data.checkout_url
      } else {
        setSuccess(`Successfully switched to ${planId} plan`)
        setTimeout(() => setSuccess(null), TOAST_DISMISS_MS)
        fetchBillingData()
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to process upgrade')
    } finally {
      setUpgrading(null)
    }
  }

  const formatCurrency = (amount: number, currency: string): string => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: currency.toUpperCase(),
    }).format(amount / 100)
  }

  const currentPlanLevel = subscription ? planOrder[subscription.plan] ?? 0 : 0

  if (loading) {
    return (
      <div className="bg-background flex min-h-screen items-center justify-center">
        <div className="text-center">
          <Loader2 className="text-muted-foreground mx-auto size-8 animate-spin" />
          <p className="text-muted-foreground mt-2 text-sm">Loading billing information...</p>
        </div>
      </div>
    )
  }

  return (
    <div className="bg-background min-h-screen">
      {/* Header */}
      <header className="border-b">
        <div className="container mx-auto p-4">
          <div className="flex items-center space-x-4">
            <Link href="/settings" className="text-muted-foreground hover:text-foreground">
              <ArrowLeft className="size-5" />
            </Link>
            <CreditCard className="text-primary size-8" />
            <div>
              <h1 className="text-2xl font-bold">Billing & Plans</h1>
              <p className="text-muted-foreground text-sm">
                Manage your subscription, payment methods, and invoices
              </p>
            </div>
          </div>
        </div>
      </header>

      <div className="container mx-auto space-y-6 px-4 py-8">
        {error && (
          <Card className="border-destructive">
            <CardContent className="pt-6">
              <div className="text-destructive flex items-center gap-2">
                <AlertCircle className="size-5" />
                <span>{error}</span>
              </div>
            </CardContent>
          </Card>
        )}

        {success && (
          <Card className="border-green-500">
            <CardContent className="pt-6">
              <div className="flex items-center gap-2 text-green-600 dark:text-green-400">
                <CheckCircle2 className="size-5" />
                <span>{success}</span>
              </div>
            </CardContent>
          </Card>
        )}

        {/* Current Subscription */}
        {subscription && (
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle className="flex items-center gap-2">
                    Current Plan
                    <Badge variant={statusColors[subscription.status] ?? 'outline'}>
                      {subscription.status}
                    </Badge>
                  </CardTitle>
                  <CardDescription>
                    Your current subscription details
                  </CardDescription>
                </div>
                <div className="flex items-center gap-2">
                  {planIcons[subscription.plan]}
                  <span className="text-2xl font-bold capitalize">{subscription.plan}</span>
                </div>
              </div>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
                <div>
                  <p className="text-muted-foreground text-sm">Billing Period Start</p>
                  <p className="font-medium">
                    {new Date(subscription.current_period_start).toLocaleDateString()}
                  </p>
                </div>
                <div>
                  <p className="text-muted-foreground text-sm">Billing Period End</p>
                  <p className="font-medium">
                    {new Date(subscription.current_period_end).toLocaleDateString()}
                  </p>
                </div>
                <div>
                  <p className="text-muted-foreground text-sm">Auto-Renewal</p>
                  <p className="font-medium">
                    {subscription.cancel_at_period_end ? (
                      <span className="text-destructive">Cancels at period end</span>
                    ) : (
                      <span className="text-green-600 dark:text-green-400">Enabled</span>
                    )}
                  </p>
                </div>
              </div>
            </CardContent>
          </Card>
        )}

        {/* Plan Cards */}
        <div>
          <h2 className="mb-4 text-lg font-semibold">Available Plans</h2>
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
            {plans.map((plan) => {
              const isCurrentPlan = subscription?.plan === plan.id
              const planLevel = planOrder[plan.id] ?? 0
              const isDowngrade = planLevel < currentPlanLevel
              const isUpgrade = planLevel > currentPlanLevel

              return (
                <Card
                  key={plan.id}
                  className={`relative flex flex-col ${
                    plan.highlighted ? 'border-primary shadow-md' : ''
                  } ${isCurrentPlan ? 'border-green-500 bg-green-50/50 dark:bg-green-950/20' : ''}`}
                >
                  {plan.badge && (
                    <div className="absolute -top-3 right-4">
                      <Badge
                        variant={plan.id === 'enterprise' ? 'outline' : 'default'}
                        className="flex items-center gap-1"
                      >
                        {plan.id === 'pro' && <Star className="size-3" />}
                        {plan.badge}
                      </Badge>
                    </div>
                  )}
                  <CardHeader className="pb-2">
                    <div className="flex items-center gap-2">
                      {planIcons[plan.id]}
                      <CardTitle className="text-lg">{plan.name}</CardTitle>
                    </div>
                    <div className="mt-2 flex items-baseline gap-1">
                      <span className="text-3xl font-bold">{plan.price}</span>
                      {plan.period && (
                        <span className="text-muted-foreground text-sm">{plan.period}</span>
                      )}
                    </div>
                    <CardDescription className="mt-1">{plan.description}</CardDescription>
                  </CardHeader>
                  <CardContent className="flex flex-1 flex-col">
                    <ul className="flex-1 space-y-2">
                      {plan.features.map((feature, index) => (
                        <li key={index} className="flex items-start gap-2 text-sm">
                          <Check className="text-primary mt-0.5 size-4 shrink-0" />
                          <span>{feature}</span>
                        </li>
                      ))}
                    </ul>
                    <div className="mt-6">
                      {isCurrentPlan ? (
                        <Button variant="outline" className="w-full" disabled>
                          <CheckCircle2 className="mr-2 size-4" />
                          Current Plan
                        </Button>
                      ) : plan.id === 'enterprise' ? (
                        <Button
                          variant="outline"
                          className="w-full"
                          onClick={() => handleUpgrade('enterprise')}
                        >
                          <ExternalLink className="mr-2 size-4" />
                          Contact Sales
                        </Button>
                      ) : isUpgrade ? (
                        <Button
                          className="w-full"
                          onClick={() => handleUpgrade(plan.id)}
                          disabled={upgrading === plan.id}
                        >
                          {upgrading === plan.id ? (
                            <Loader2 className="mr-2 size-4 animate-spin" />
                          ) : (
                            <Zap className="mr-2 size-4" />
                          )}
                          Upgrade to {plan.name}
                        </Button>
                      ) : isDowngrade ? (
                        <Button
                          variant="outline"
                          className="w-full"
                          onClick={() => handleUpgrade(plan.id)}
                          disabled={upgrading === plan.id}
                        >
                          {upgrading === plan.id ? (
                            <Loader2 className="mr-2 size-4 animate-spin" />
                          ) : null}
                          Downgrade to {plan.name}
                        </Button>
                      ) : null}
                    </div>
                  </CardContent>
                </Card>
              )
            })}
          </div>
        </div>

        {/* Payment Methods */}
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <div>
                <CardTitle>Payment Methods</CardTitle>
                <CardDescription>
                  Manage your payment methods for billing
                </CardDescription>
              </div>
            </div>
          </CardHeader>
          <CardContent>
            {paymentMethods.length === 0 ? (
              <div className="py-6 text-center">
                <CreditCard className="text-muted-foreground mx-auto size-8" />
                <p className="text-muted-foreground mt-2 text-sm">
                  No payment methods on file
                </p>
                <p className="text-muted-foreground mt-1 text-xs">
                  A payment method will be added when you upgrade to a paid plan.
                </p>
              </div>
            ) : (
              <div className="space-y-3">
                {paymentMethods.map((pm) => (
                  <div
                    key={pm.id}
                    className="flex items-center justify-between rounded-lg border p-4"
                  >
                    <div className="flex items-center gap-3">
                      <CreditCard className="text-muted-foreground size-5" />
                      <div>
                        <p className="font-medium">
                          {pm.brand.charAt(0).toUpperCase() + pm.brand.slice(1)} ending in{' '}
                          {pm.last4}
                        </p>
                        <p className="text-muted-foreground text-sm">
                          Expires {pm.exp_month.toString().padStart(2, '0')}/{pm.exp_year}
                        </p>
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      {pm.is_default && <Badge variant="default">Default</Badge>}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        {/* Invoice History */}
        <Card>
          <CardHeader>
            <CardTitle>Invoice History</CardTitle>
            <CardDescription>
              View and download past invoices
            </CardDescription>
          </CardHeader>
          <CardContent>
            {invoices.length === 0 ? (
              <div className="py-6 text-center">
                <Download className="text-muted-foreground mx-auto size-8" />
                <p className="text-muted-foreground mt-2 text-sm">No invoices yet</p>
                <p className="text-muted-foreground mt-1 text-xs">
                  Invoices will appear here once you have billing activity.
                </p>
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full" role="table">
                  <thead>
                    <tr className="border-b text-left">
                      <th className="text-muted-foreground pb-3 text-sm font-medium">Invoice</th>
                      <th className="text-muted-foreground pb-3 text-sm font-medium">Date</th>
                      <th className="text-muted-foreground pb-3 text-sm font-medium">Amount</th>
                      <th className="text-muted-foreground pb-3 text-sm font-medium">Status</th>
                      <th className="text-muted-foreground pb-3 text-right text-sm font-medium">
                        Actions
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {invoices.map((invoice) => (
                      <tr key={invoice.id} className="border-b last:border-0">
                        <td className="py-3 font-medium">{invoice.number}</td>
                        <td className="text-muted-foreground py-3 text-sm">
                          {new Date(invoice.created_at).toLocaleDateString()}
                        </td>
                        <td className="py-3">
                          {formatCurrency(invoice.amount, invoice.currency)}
                        </td>
                        <td className="py-3">
                          <Badge variant={statusColors[invoice.status] ?? 'outline'}>
                            {invoice.status}
                          </Badge>
                        </td>
                        <td className="py-3 text-right">
                          {invoice.pdf_url && (
                            <Button
                              variant="ghost"
                              size="sm"
                              asChild
                            >
                              <a
                                href={invoice.pdf_url}
                                target="_blank"
                                rel="noopener noreferrer"
                                aria-label={`Download invoice ${invoice.number}`}
                              >
                                <Download className="mr-1 size-4" />
                                PDF
                              </a>
                            </Button>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
