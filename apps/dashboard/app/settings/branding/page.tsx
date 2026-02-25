'use client'

import { useState, useEffect } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@janua/ui'
import { Button } from '@janua/ui'
import { Badge } from '@janua/ui'
import { Input } from '@janua/ui'
import { Label } from '@janua/ui'
import Link from 'next/link'
import {
  Palette,
  ArrowLeft,
  Loader2,
  AlertCircle,
  CheckCircle2,
  Upload,
  Globe,
  Eye,
  Save,
} from 'lucide-react'
import { getBranding, updateBranding, getDomains, addDomain, verifyDomain } from '@/lib/api'
import { januaClient } from '@/lib/janua-client'

interface BrandingConfiguration {
  id: string
  organization_id: string
  branding_level: 'basic' | 'standard' | 'enterprise'
  is_enabled: boolean
  company_name: string | null
  company_logo_url: string | null
  company_logo_dark_url: string | null
  company_favicon_url: string | null
  company_website: string | null
  theme_mode: 'light' | 'dark' | 'system'
  primary_color: string
  secondary_color: string
  accent_color: string
  background_color: string
  surface_color: string
  text_color: string
  font_family: string
  border_radius: string
  custom_css: string | null
  created_at: string
  updated_at: string
}

interface CustomDomain {
  id: string
  organization_id: string
  domain: string
  status: 'pending' | 'verified' | 'failed'
  verification_token: string
  created_at: string
}

export default function BrandingSettingsPage() {
  const [config, setConfig] = useState<BrandingConfiguration | null>(null)
  const [domains, setDomains] = useState<CustomDomain[]>([])
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)
  const [organizationId, setOrganizationId] = useState<string | null>(null)
  const [newDomain, setNewDomain] = useState('')
  const [showPreview, setShowPreview] = useState(false)

  // Form state
  const [formData, setFormData] = useState({
    company_name: '',
    company_logo_url: '',
    company_logo_dark_url: '',
    company_favicon_url: '',
    company_website: '',
    primary_color: '#1a73e8',
    secondary_color: '#ea4335',
    accent_color: '#34a853',
    background_color: '#ffffff',
    surface_color: '#f8f9fa',
    text_color: '#202124',
    font_family: 'Inter, system-ui, sans-serif',
    border_radius: '8px',
    custom_css: '',
  })

  useEffect(() => {
    fetchBrandingConfig()
  }, [])

  const fetchBrandingConfig = async () => {
    try {
      setLoading(true)
      setError(null)

      // Get current user's organization
      const userData = await januaClient.auth.getCurrentUser() as unknown as Record<string, unknown>

      const orgId = (userData.current_organization_id as string)
        || (userData.organization_id as string)
      if (!orgId) {
        setError('No organization found. Please join or create an organization first.')
        setLoading(false)
        return
      }
      setOrganizationId(orgId)

      // Fetch branding configuration
      try {
        const data = await getBranding(orgId)
        setConfig(data as unknown as BrandingConfiguration)
        setFormData({
          company_name: (data as Record<string, string>).company_name || '',
          company_logo_url: (data as Record<string, string>).company_logo_url || '',
          company_logo_dark_url: (data as Record<string, string>).company_logo_dark_url || '',
          company_favicon_url: (data as Record<string, string>).company_favicon_url || '',
          company_website: (data as Record<string, string>).company_website || '',
          primary_color: data.primary_color || '#1a73e8',
          secondary_color: (data as Record<string, string>).secondary_color || '#ea4335',
          accent_color: data.accent_color || '#34a853',
          background_color: (data as Record<string, string>).background_color || '#ffffff',
          surface_color: (data as Record<string, string>).surface_color || '#f8f9fa',
          text_color: (data as Record<string, string>).text_color || '#202124',
          font_family: (data as Record<string, string>).font_family || 'Inter, system-ui, sans-serif',
          border_radius: (data as Record<string, string>).border_radius || '8px',
          custom_css: data.custom_css || '',
        })
      } catch {
        // No config exists yet, use defaults
        setConfig(null)
      }

      // Fetch custom domains
      try {
        const domainsData = await getDomains(orgId)
        setDomains(Array.isArray(domainsData) ? domainsData as unknown as CustomDomain[] : [])
      } catch {
        setDomains([])
      }
    } catch (err) {
      console.error('Failed to fetch branding config:', err)
      setError(err instanceof Error ? err.message : 'Failed to load branding configuration')
    } finally {
      setLoading(false)
    }
  }

  const handleSave = async () => {
    if (!organizationId) return

    setSaving(true)
    setError(null)
    setSuccess(null)

    try {
      const data = await updateBranding(organizationId, formData)
      setConfig(data as unknown as BrandingConfiguration)
      setSuccess('Branding configuration saved successfully!')
      setTimeout(() => setSuccess(null), 3000)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save configuration')
    } finally {
      setSaving(false)
    }
  }

  const handleAddDomain = async () => {
    if (!organizationId || !newDomain.trim()) return

    try {
      await addDomain({
        organization_id: organizationId,
        domain: newDomain.trim(),
      })
      setNewDomain('')
      fetchBrandingConfig()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to add domain')
    }
  }

  const handleVerifyDomain = async (domainId: string) => {
    try {
      await verifyDomain(domainId)
      fetchBrandingConfig()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to verify domain')
    }
  }

  if (loading) {
    return (
      <div className="bg-background flex min-h-screen items-center justify-center">
        <div className="text-center">
          <Loader2 className="text-muted-foreground mx-auto size-8 animate-spin" />
          <p className="text-muted-foreground mt-2 text-sm">Loading branding settings...</p>
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
              <Palette className="text-primary size-8" />
              <div>
                <h1 className="text-2xl font-bold">Branding & White Label</h1>
                <p className="text-muted-foreground text-sm">
                  Customize your organization&apos;s look and feel
                </p>
              </div>
            </div>
            <Badge variant="secondary">Enterprise</Badge>
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

        {/* Company Info */}
        <Card>
          <CardHeader>
            <CardTitle>Company Information</CardTitle>
            <CardDescription>
              Basic company details that appear in your branded login pages
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
              <div className="space-y-2">
                <Label htmlFor="company_name">Company Name</Label>
                <Input
                  id="company_name"
                  value={formData.company_name}
                  onChange={(e) => setFormData({ ...formData, company_name: e.target.value })}
                  placeholder="Acme Inc."
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="company_website">Company Website</Label>
                <Input
                  id="company_website"
                  value={formData.company_website}
                  onChange={(e) => setFormData({ ...formData, company_website: e.target.value })}
                  placeholder="https://example.com"
                />
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Logo Upload */}
        <Card>
          <CardHeader>
            <CardTitle>Logo & Favicon</CardTitle>
            <CardDescription>
              Upload your company logos for branded experiences
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
              <div className="space-y-2">
                <Label htmlFor="company_logo_url">Primary Logo URL</Label>
                <div className="flex gap-2">
                  <Input
                    id="company_logo_url"
                    value={formData.company_logo_url}
                    onChange={(e) => setFormData({ ...formData, company_logo_url: e.target.value })}
                    placeholder="https://example.com/logo.png"
                  />
                  <Button variant="outline" size="icon" disabled>
                    <Upload className="size-4" />
                  </Button>
                </div>
              </div>
              <div className="space-y-2">
                <Label htmlFor="company_logo_dark_url">Dark Mode Logo URL</Label>
                <div className="flex gap-2">
                  <Input
                    id="company_logo_dark_url"
                    value={formData.company_logo_dark_url}
                    onChange={(e) => setFormData({ ...formData, company_logo_dark_url: e.target.value })}
                    placeholder="https://example.com/logo-dark.png"
                  />
                  <Button variant="outline" size="icon" disabled>
                    <Upload className="size-4" />
                  </Button>
                </div>
              </div>
              <div className="space-y-2">
                <Label htmlFor="company_favicon_url">Favicon URL</Label>
                <div className="flex gap-2">
                  <Input
                    id="company_favicon_url"
                    value={formData.company_favicon_url}
                    onChange={(e) => setFormData({ ...formData, company_favicon_url: e.target.value })}
                    placeholder="https://example.com/favicon.ico"
                  />
                  <Button variant="outline" size="icon" disabled>
                    <Upload className="size-4" />
                  </Button>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Color Scheme */}
        <Card>
          <CardHeader>
            <CardTitle>Color Scheme</CardTitle>
            <CardDescription>
              Customize colors to match your brand identity
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 gap-4 md:grid-cols-3 lg:grid-cols-6">
              {[
                { id: 'primary_color', label: 'Primary' },
                { id: 'secondary_color', label: 'Secondary' },
                { id: 'accent_color', label: 'Accent' },
                { id: 'background_color', label: 'Background' },
                { id: 'surface_color', label: 'Surface' },
                { id: 'text_color', label: 'Text' },
              ].map(({ id, label }) => (
                <div key={id} className="space-y-2">
                  <Label htmlFor={id}>{label}</Label>
                  <div className="flex gap-2">
                    <input
                      type="color"
                      id={id}
                      value={formData[id as keyof typeof formData] as string}
                      onChange={(e) => setFormData({ ...formData, [id]: e.target.value })}
                      className="h-10 w-12 cursor-pointer rounded border"
                    />
                    <Input
                      value={formData[id as keyof typeof formData] as string}
                      onChange={(e) => setFormData({ ...formData, [id]: e.target.value })}
                      className="font-mono text-xs"
                    />
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>

        {/* Typography */}
        <Card>
          <CardHeader>
            <CardTitle>Typography & Styling</CardTitle>
            <CardDescription>
              Customize fonts and visual styling
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
              <div className="space-y-2">
                <Label htmlFor="font_family">Font Family</Label>
                <Input
                  id="font_family"
                  value={formData.font_family}
                  onChange={(e) => setFormData({ ...formData, font_family: e.target.value })}
                  placeholder="Inter, system-ui, sans-serif"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="border_radius">Border Radius</Label>
                <Input
                  id="border_radius"
                  value={formData.border_radius}
                  onChange={(e) => setFormData({ ...formData, border_radius: e.target.value })}
                  placeholder="8px"
                />
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Custom CSS */}
        <Card>
          <CardHeader>
            <CardTitle>Custom CSS</CardTitle>
            <CardDescription>
              Add custom CSS for advanced styling (Enterprise only)
            </CardDescription>
          </CardHeader>
          <CardContent>
            <textarea
              value={formData.custom_css}
              onChange={(e: React.ChangeEvent<HTMLTextAreaElement>) => setFormData({ ...formData, custom_css: e.target.value })}
              placeholder={`/* Custom CSS */\n.login-container {\n  /* Your styles */\n}`}
              rows={6}
              className="border-input bg-background ring-offset-background placeholder:text-muted-foreground focus-visible:ring-ring flex min-h-[80px] w-full rounded-md border px-3 py-2 font-mono text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
            />
          </CardContent>
        </Card>

        {/* Custom Domains */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Globe className="size-5" />
              Custom Domains
            </CardTitle>
            <CardDescription>
              Use your own domain for authentication pages (e.g., auth.yourcompany.com)
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex gap-2">
              <Input
                value={newDomain}
                onChange={(e) => setNewDomain(e.target.value)}
                placeholder="auth.yourcompany.com"
              />
              <Button onClick={handleAddDomain} disabled={!newDomain.trim()}>
                Add Domain
              </Button>
            </div>

            {domains.length > 0 && (
              <div className="space-y-2">
                {domains.map((domain) => (
                  <div
                    key={domain.id}
                    className="flex items-center justify-between rounded-lg border p-3"
                  >
                    <div className="flex items-center gap-3">
                      <Globe className="text-muted-foreground size-4" />
                      <span className="font-mono text-sm">{domain.domain}</span>
                      <Badge
                        variant={
                          domain.status === 'verified'
                            ? 'default'
                            : domain.status === 'pending'
                              ? 'secondary'
                              : 'destructive'
                        }
                      >
                        {domain.status}
                      </Badge>
                    </div>
                    {domain.status === 'pending' && (
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => handleVerifyDomain(domain.id)}
                      >
                        Verify
                      </Button>
                    )}
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        {/* Preview Modal */}
        {showPreview && (
          <Card className="border-primary">
            <CardHeader>
              <div className="flex items-center justify-between">
                <CardTitle>Branding Preview</CardTitle>
                <Button variant="outline" size="sm" onClick={() => setShowPreview(false)}>
                  Close Preview
                </Button>
              </div>
              <CardDescription>
                Preview how your branding will appear on login pages
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div
                className="rounded-lg border p-8"
                style={{
                  backgroundColor: formData.background_color,
                  fontFamily: formData.font_family,
                }}
              >
                <div
                  className="mx-auto max-w-sm rounded-lg p-6"
                  style={{
                    backgroundColor: formData.surface_color,
                    borderRadius: formData.border_radius,
                  }}
                >
                  {/* Logo */}
                  <div className="mb-6 text-center">
                    {formData.company_logo_url ? (
                      <img
                        src={formData.company_logo_url}
                        alt={formData.company_name || 'Company Logo'}
                        className="mx-auto h-12 object-contain"
                      />
                    ) : (
                      <div
                        className="mx-auto flex size-12 items-center justify-center rounded-lg text-xl font-bold"
                        style={{ backgroundColor: formData.primary_color, color: '#fff' }}
                      >
                        {formData.company_name?.charAt(0) || 'J'}
                      </div>
                    )}
                    <h2
                      className="mt-4 text-xl font-bold"
                      style={{ color: formData.text_color }}
                    >
                      {formData.company_name || 'Your Company'}
                    </h2>
                    <p style={{ color: formData.text_color, opacity: 0.7 }} className="text-sm">
                      Sign in to continue
                    </p>
                  </div>

                  {/* Mock Form */}
                  <div className="space-y-4">
                    <div>
                      <label
                        className="mb-1 block text-sm font-medium"
                        style={{ color: formData.text_color }}
                      >
                        Email
                      </label>
                      <input
                        type="email"
                        placeholder="you@example.com"
                        className="w-full border px-3 py-2"
                        style={{
                          borderRadius: formData.border_radius,
                          backgroundColor: formData.background_color,
                          color: formData.text_color,
                        }}
                        disabled
                      />
                    </div>
                    <div>
                      <label
                        className="mb-1 block text-sm font-medium"
                        style={{ color: formData.text_color }}
                      >
                        Password
                      </label>
                      <input
                        type="password"
                        placeholder="••••••••"
                        className="w-full border px-3 py-2"
                        style={{
                          borderRadius: formData.border_radius,
                          backgroundColor: formData.background_color,
                          color: formData.text_color,
                        }}
                        disabled
                      />
                    </div>
                    <button
                      className="w-full py-2 font-medium text-white"
                      style={{
                        backgroundColor: formData.primary_color,
                        borderRadius: formData.border_radius,
                      }}
                      disabled
                    >
                      Sign In
                    </button>
                  </div>

                  {/* Footer */}
                  <p
                    className="mt-4 text-center text-xs"
                    style={{ color: formData.text_color, opacity: 0.5 }}
                  >
                    Powered by{' '}
                    <span style={{ color: formData.accent_color }}>
                      {formData.company_name || 'Janua'}
                    </span>
                  </p>
                </div>
              </div>
            </CardContent>
          </Card>
        )}

        {/* Actions */}
        <div className="flex justify-end gap-4">
          <Button variant="outline" onClick={() => setShowPreview(!showPreview)}>
            <Eye className="mr-2 size-4" />
            {showPreview ? 'Hide Preview' : 'Preview'}
          </Button>
          <Button onClick={handleSave} disabled={saving}>
            {saving ? (
              <Loader2 className="mr-2 size-4 animate-spin" />
            ) : (
              <Save className="mr-2 size-4" />
            )}
            Save Changes
          </Button>
        </div>
      </div>
    </div>
  )
}
