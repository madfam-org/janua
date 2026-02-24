'use client'

import { useState, useEffect, useRef, useCallback } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@janua/ui'
import { Button } from '@janua/ui'
import { Badge } from '@janua/ui'
import { Input } from '@janua/ui'
import { Label } from '@janua/ui'
import Link from 'next/link'
import {
  ArrowLeft,
  Mail,
  Loader2,
  AlertCircle,
  CheckCircle2,
  Save,
  RotateCcw,
  Eye,
  Code,
  ChevronRight,
  UserPlus,
  ShieldCheck,
  KeyRound,
  Smartphone,
  MailCheck,
  Info,
} from 'lucide-react'
import { apiCall } from '../../../lib/auth'

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'https://api.janua.dev'

interface EmailTemplate {
  id: string
  type: 'welcome' | 'verification' | 'password_reset' | 'invitation' | 'mfa_setup'
  name: string
  subject: string
  html_body: string
  is_custom: boolean
  updated_at: string
}

const templateTypeConfig: Record<
  string,
  { label: string; description: string; icon: React.ReactNode; color: string }
> = {
  welcome: {
    label: 'Welcome Email',
    description: 'Sent to new users after registration',
    icon: <UserPlus className="size-5" />,
    color: 'text-blue-500',
  },
  verification: {
    label: 'Email Verification',
    description: 'Sent when a user needs to verify their email address',
    icon: <MailCheck className="size-5" />,
    color: 'text-green-500',
  },
  password_reset: {
    label: 'Password Reset',
    description: 'Sent when a user requests a password reset',
    icon: <KeyRound className="size-5" />,
    color: 'text-orange-500',
  },
  invitation: {
    label: 'Team Invitation',
    description: 'Sent when a user is invited to join an organization',
    icon: <Mail className="size-5" />,
    color: 'text-purple-500',
  },
  mfa_setup: {
    label: 'MFA Setup',
    description: 'Sent when a user sets up multi-factor authentication',
    icon: <Smartphone className="size-5" />,
    color: 'text-teal-500',
  },
}

const templateVariables: Record<string, { variable: string; description: string }[]> = {
  welcome: [
    { variable: '{{user_name}}', description: "The user's display name" },
    { variable: '{{user_email}}', description: "The user's email address" },
    { variable: '{{app_name}}', description: 'Your application name' },
    { variable: '{{dashboard_url}}', description: 'URL to the user dashboard' },
    { variable: '{{support_email}}', description: 'Support contact email' },
  ],
  verification: [
    { variable: '{{user_name}}', description: "The user's display name" },
    { variable: '{{verification_link}}', description: 'Email verification URL (expires in 24h)' },
    { variable: '{{verification_code}}', description: '6-digit verification code' },
    { variable: '{{app_name}}', description: 'Your application name' },
    { variable: '{{expiry_hours}}', description: 'Hours until link expires' },
  ],
  password_reset: [
    { variable: '{{user_name}}', description: "The user's display name" },
    { variable: '{{reset_link}}', description: 'Password reset URL (expires in 1h)' },
    { variable: '{{app_name}}', description: 'Your application name' },
    { variable: '{{expiry_minutes}}', description: 'Minutes until link expires' },
    { variable: '{{ip_address}}', description: 'IP address that requested the reset' },
  ],
  invitation: [
    { variable: '{{inviter_name}}', description: 'Name of the person who sent the invite' },
    { variable: '{{organization_name}}', description: 'Organization being invited to' },
    { variable: '{{invitation_link}}', description: 'URL to accept the invitation' },
    { variable: '{{role}}', description: 'Role assigned in the organization' },
    { variable: '{{app_name}}', description: 'Your application name' },
    { variable: '{{expiry_days}}', description: 'Days until invitation expires' },
  ],
  mfa_setup: [
    { variable: '{{user_name}}', description: "The user's display name" },
    { variable: '{{mfa_method}}', description: 'MFA method configured (TOTP, SMS, WebAuthn)' },
    { variable: '{{setup_link}}', description: 'URL to complete MFA setup' },
    { variable: '{{app_name}}', description: 'Your application name' },
    { variable: '{{support_email}}', description: 'Support contact email' },
  ],
}

export default function EmailTemplatesPage() {
  const [templates, setTemplates] = useState<EmailTemplate[]>([])
  const [selectedTemplate, setSelectedTemplate] = useState<EmailTemplate | null>(null)
  const [editedSubject, setEditedSubject] = useState('')
  const [editedBody, setEditedBody] = useState('')
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [resetting, setResetting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)
  const [viewMode, setViewMode] = useState<'editor' | 'preview'>('editor')
  const [hasChanges, setHasChanges] = useState(false)
  const previewIframeRef = useRef<HTMLIFrameElement>(null)

  useEffect(() => {
    fetchTemplates()
  }, [])

  const fetchTemplates = async () => {
    try {
      setLoading(true)
      setError(null)

      const response = await apiCall(`${API_BASE_URL}/api/v1/email/templates`)

      if (response.ok) {
        const data = await response.json()
        const templateList = Array.isArray(data) ? data : data.templates || []
        setTemplates(templateList)

        // Auto-select the first template if none selected
        if (templateList.length > 0 && !selectedTemplate) {
          selectTemplate(templateList[0])
        }
      } else {
        // Use default placeholder templates if endpoint not available
        const defaultTemplates: EmailTemplate[] = [
          {
            id: 'welcome',
            type: 'welcome',
            name: 'Welcome Email',
            subject: 'Welcome to {{app_name}}!',
            html_body:
              '<h1>Welcome, {{user_name}}!</h1>\n<p>Thank you for joining {{app_name}}. We are excited to have you on board.</p>\n<p><a href="{{dashboard_url}}">Go to Dashboard</a></p>',
            is_custom: false,
            updated_at: new Date().toISOString(),
          },
          {
            id: 'verification',
            type: 'verification',
            name: 'Email Verification',
            subject: 'Verify your email address',
            html_body:
              '<h1>Verify your email</h1>\n<p>Hi {{user_name}},</p>\n<p>Please verify your email address by clicking the link below:</p>\n<p><a href="{{verification_link}}">Verify Email</a></p>\n<p>Or enter this code: <strong>{{verification_code}}</strong></p>\n<p>This link expires in {{expiry_hours}} hours.</p>',
            is_custom: false,
            updated_at: new Date().toISOString(),
          },
          {
            id: 'password_reset',
            type: 'password_reset',
            name: 'Password Reset',
            subject: 'Reset your password',
            html_body:
              '<h1>Password Reset</h1>\n<p>Hi {{user_name}},</p>\n<p>A password reset was requested for your account. Click the link below to set a new password:</p>\n<p><a href="{{reset_link}}">Reset Password</a></p>\n<p>This link expires in {{expiry_minutes}} minutes.</p>\n<p>If you did not request this, you can ignore this email. Request originated from IP: {{ip_address}}</p>',
            is_custom: false,
            updated_at: new Date().toISOString(),
          },
          {
            id: 'invitation',
            type: 'invitation',
            name: 'Team Invitation',
            subject: "You've been invited to join {{organization_name}}",
            html_body:
              '<h1>You have been invited!</h1>\n<p>{{inviter_name}} has invited you to join <strong>{{organization_name}}</strong> as a <strong>{{role}}</strong>.</p>\n<p><a href="{{invitation_link}}">Accept Invitation</a></p>\n<p>This invitation expires in {{expiry_days}} days.</p>',
            is_custom: false,
            updated_at: new Date().toISOString(),
          },
          {
            id: 'mfa_setup',
            type: 'mfa_setup',
            name: 'MFA Setup',
            subject: 'Multi-factor authentication enabled',
            html_body:
              '<h1>MFA Enabled</h1>\n<p>Hi {{user_name}},</p>\n<p>Multi-factor authentication ({{mfa_method}}) has been set up for your account.</p>\n<p>If you did not make this change, please contact support immediately at {{support_email}}.</p>',
            is_custom: false,
            updated_at: new Date().toISOString(),
          },
        ]
        setTemplates(defaultTemplates)
        if (!selectedTemplate) {
          selectTemplate(defaultTemplates[0])
        }
      }
    } catch (err) {
      console.error('Failed to fetch email templates:', err)
      setError(err instanceof Error ? err.message : 'Failed to load email templates')
    } finally {
      setLoading(false)
    }
  }

  const selectTemplate = (template: EmailTemplate) => {
    if (hasChanges) {
      const confirmed = confirm(
        'You have unsaved changes. Are you sure you want to switch templates?'
      )
      if (!confirmed) return
    }

    setSelectedTemplate(template)
    setEditedSubject(template.subject)
    setEditedBody(template.html_body)
    setHasChanges(false)
    setError(null)
    setSuccess(null)
  }

  const handleSubjectChange = (value: string) => {
    setEditedSubject(value)
    setHasChanges(value !== selectedTemplate?.subject || editedBody !== selectedTemplate?.html_body)
  }

  const handleBodyChange = (value: string) => {
    setEditedBody(value)
    setHasChanges(editedSubject !== selectedTemplate?.subject || value !== selectedTemplate?.html_body)
  }

  const updatePreview = useCallback(() => {
    if (previewIframeRef.current) {
      const iframeDoc = previewIframeRef.current.contentDocument
      if (iframeDoc) {
        // Replace template variables with sample data for preview
        let previewHtml = editedBody
          .replace(/\{\{user_name\}\}/g, 'Jane Doe')
          .replace(/\{\{user_email\}\}/g, 'jane@example.com')
          .replace(/\{\{app_name\}\}/g, 'Janua')
          .replace(/\{\{dashboard_url\}\}/g, '#')
          .replace(/\{\{support_email\}\}/g, 'support@janua.dev')
          .replace(/\{\{verification_link\}\}/g, '#')
          .replace(/\{\{verification_code\}\}/g, '123456')
          .replace(/\{\{expiry_hours\}\}/g, '24')
          .replace(/\{\{reset_link\}\}/g, '#')
          .replace(/\{\{expiry_minutes\}\}/g, '60')
          .replace(/\{\{ip_address\}\}/g, '192.168.1.1')
          .replace(/\{\{inviter_name\}\}/g, 'John Smith')
          .replace(/\{\{organization_name\}\}/g, 'Acme Corp')
          .replace(/\{\{invitation_link\}\}/g, '#')
          .replace(/\{\{role\}\}/g, 'Member')
          .replace(/\{\{expiry_days\}\}/g, '7')
          .replace(/\{\{mfa_method\}\}/g, 'TOTP')
          .replace(/\{\{setup_link\}\}/g, '#')

        const fullHtml = `<!DOCTYPE html>
<html>
<head>
  <style>
    body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; padding: 20px; margin: 0; color: #1a1a1a; line-height: 1.6; }
    a { color: #2563eb; }
    h1 { font-size: 24px; margin-bottom: 16px; }
    p { margin: 8px 0; }
    strong { font-weight: 600; }
  </style>
</head>
<body>${previewHtml}</body>
</html>`

        iframeDoc.open()
        iframeDoc.write(fullHtml)
        iframeDoc.close()
      }
    }
  }, [editedBody])

  useEffect(() => {
    if (viewMode === 'preview') {
      // Small delay to ensure iframe is mounted
      const timeout = setTimeout(updatePreview, 50)
      return () => clearTimeout(timeout)
    }
  }, [viewMode, editedBody, updatePreview])

  const handleSave = async () => {
    if (!selectedTemplate) return

    try {
      setSaving(true)
      setError(null)

      const response = await apiCall(
        `${API_BASE_URL}/api/v1/email/templates/${selectedTemplate.id}`,
        {
          method: 'PATCH',
          body: JSON.stringify({
            subject: editedSubject,
            html_body: editedBody,
          }),
        }
      )

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}))
        throw new Error(errorData.detail || 'Failed to save template')
      }

      const updatedTemplate = await response.json()

      setTemplates((prev) =>
        prev.map((t) => (t.id === selectedTemplate.id ? { ...t, ...updatedTemplate } : t))
      )
      setSelectedTemplate((prev) => (prev ? { ...prev, ...updatedTemplate } : prev))
      setHasChanges(false)
      setSuccess('Template saved successfully')
      setTimeout(() => setSuccess(null), 3000)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save template')
    } finally {
      setSaving(false)
    }
  }

  const handleReset = async () => {
    if (!selectedTemplate) return

    const confirmed = confirm(
      'Are you sure you want to reset this template to its default? This cannot be undone.'
    )
    if (!confirmed) return

    try {
      setResetting(true)
      setError(null)

      const response = await apiCall(
        `${API_BASE_URL}/api/v1/email/templates/${selectedTemplate.id}/reset`,
        { method: 'POST' }
      )

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}))
        throw new Error(errorData.detail || 'Failed to reset template')
      }

      setSuccess('Template reset to default')
      setTimeout(() => setSuccess(null), 3000)
      fetchTemplates()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to reset template')
    } finally {
      setResetting(false)
    }
  }

  const currentVariables = selectedTemplate
    ? templateVariables[selectedTemplate.type] || []
    : []

  if (loading) {
    return (
      <div className="bg-background flex min-h-screen items-center justify-center">
        <div className="text-center">
          <Loader2 className="text-muted-foreground mx-auto size-8 animate-spin" />
          <p className="text-muted-foreground mt-2 text-sm">Loading email templates...</p>
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
            <Mail className="text-primary size-8" />
            <div>
              <h1 className="text-2xl font-bold">Email Templates</h1>
              <p className="text-muted-foreground text-sm">
                Customize the emails sent to your users
              </p>
            </div>
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

        {success && (
          <Card className="mb-6 border-green-500">
            <CardContent className="pt-6">
              <div className="flex items-center gap-2 text-green-600 dark:text-green-400">
                <CheckCircle2 className="size-5" />
                <span>{success}</span>
              </div>
            </CardContent>
          </Card>
        )}

        <div className="grid grid-cols-1 gap-6 lg:grid-cols-12">
          {/* Template List Sidebar */}
          <div className="lg:col-span-3">
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-base">Templates</CardTitle>
                <CardDescription>Select a template to edit</CardDescription>
              </CardHeader>
              <CardContent className="p-0">
                <nav aria-label="Email templates" className="divide-y">
                  {templates.map((template) => {
                    const config = templateTypeConfig[template.type]
                    const isSelected = selectedTemplate?.id === template.id

                    return (
                      <button
                        key={template.id}
                        onClick={() => selectTemplate(template)}
                        className={`flex w-full items-center gap-3 px-4 py-3 text-left transition-colors ${
                          isSelected
                            ? 'bg-primary/5 border-primary border-l-2'
                            : 'hover:bg-muted border-l-2 border-transparent'
                        }`}
                        aria-current={isSelected ? 'page' : undefined}
                      >
                        <span className={config?.color || 'text-muted-foreground'}>
                          {config?.icon || <Mail className="size-5" />}
                        </span>
                        <div className="min-w-0 flex-1">
                          <p className="truncate text-sm font-medium">
                            {config?.label || template.name}
                          </p>
                          <p className="text-muted-foreground truncate text-xs">
                            {config?.description || ''}
                          </p>
                        </div>
                        {template.is_custom && (
                          <Badge variant="secondary" className="shrink-0 text-xs">
                            Custom
                          </Badge>
                        )}
                        <ChevronRight
                          className={`size-4 shrink-0 ${
                            isSelected ? 'text-primary' : 'text-muted-foreground'
                          }`}
                        />
                      </button>
                    )
                  })}
                </nav>
              </CardContent>
            </Card>
          </div>

          {/* Editor Area */}
          <div className="lg:col-span-6">
            {selectedTemplate ? (
              <Card>
                <CardHeader>
                  <div className="flex items-center justify-between">
                    <div>
                      <CardTitle className="flex items-center gap-2">
                        {templateTypeConfig[selectedTemplate.type]?.label || selectedTemplate.name}
                        {hasChanges && (
                          <Badge variant="secondary">Unsaved changes</Badge>
                        )}
                      </CardTitle>
                      <CardDescription>
                        {templateTypeConfig[selectedTemplate.type]?.description}
                      </CardDescription>
                    </div>
                    <div className="flex items-center gap-2">
                      <div
                        className="inline-flex rounded-lg border p-1"
                        role="tablist"
                        aria-label="Editor view mode"
                      >
                        <button
                          role="tab"
                          aria-selected={viewMode === 'editor'}
                          onClick={() => setViewMode('editor')}
                          className={`inline-flex items-center gap-1.5 rounded-md px-3 py-1.5 text-sm font-medium transition-colors ${
                            viewMode === 'editor'
                              ? 'bg-background shadow-sm'
                              : 'text-muted-foreground hover:text-foreground'
                          }`}
                        >
                          <Code className="size-4" />
                          Editor
                        </button>
                        <button
                          role="tab"
                          aria-selected={viewMode === 'preview'}
                          onClick={() => setViewMode('preview')}
                          className={`inline-flex items-center gap-1.5 rounded-md px-3 py-1.5 text-sm font-medium transition-colors ${
                            viewMode === 'preview'
                              ? 'bg-background shadow-sm'
                              : 'text-muted-foreground hover:text-foreground'
                          }`}
                        >
                          <Eye className="size-4" />
                          Preview
                        </button>
                      </div>
                    </div>
                  </div>
                </CardHeader>
                <CardContent className="space-y-4">
                  {/* Subject Line */}
                  <div className="space-y-2">
                    <Label htmlFor="template-subject">Subject Line</Label>
                    <Input
                      id="template-subject"
                      value={editedSubject}
                      onChange={(e) => handleSubjectChange(e.target.value)}
                      placeholder="Email subject..."
                    />
                  </div>

                  {/* Editor / Preview */}
                  {viewMode === 'editor' ? (
                    <div className="space-y-2">
                      <Label htmlFor="template-body">HTML Body</Label>
                      <textarea
                        id="template-body"
                        value={editedBody}
                        onChange={(e) => handleBodyChange(e.target.value)}
                        className="border-input bg-background focus-visible:ring-ring min-h-[400px] w-full rounded-md border px-3 py-2 font-mono text-sm focus-visible:outline-none focus-visible:ring-2"
                        placeholder="Enter HTML content..."
                        spellCheck={false}
                      />
                    </div>
                  ) : (
                    <div className="space-y-2">
                      <Label>Preview</Label>
                      <div className="overflow-hidden rounded-md border">
                        <div className="bg-muted/50 border-b px-4 py-2">
                          <p className="text-sm">
                            <span className="text-muted-foreground">Subject: </span>
                            <span className="font-medium">
                              {editedSubject
                                .replace(/\{\{app_name\}\}/g, 'Janua')
                                .replace(/\{\{organization_name\}\}/g, 'Acme Corp')
                                .replace(/\{\{user_name\}\}/g, 'Jane Doe')}
                            </span>
                          </p>
                        </div>
                        <iframe
                          ref={previewIframeRef}
                          title="Email template preview"
                          sandbox="allow-same-origin"
                          className="h-[400px] w-full bg-white"
                        />
                      </div>
                    </div>
                  )}

                  {/* Action Buttons */}
                  <div className="flex items-center justify-between border-t pt-4">
                    <Button
                      variant="outline"
                      onClick={handleReset}
                      disabled={resetting || !selectedTemplate.is_custom}
                    >
                      {resetting ? (
                        <Loader2 className="mr-2 size-4 animate-spin" />
                      ) : (
                        <RotateCcw className="mr-2 size-4" />
                      )}
                      Reset to Default
                    </Button>
                    <Button onClick={handleSave} disabled={saving || !hasChanges}>
                      {saving ? (
                        <Loader2 className="mr-2 size-4 animate-spin" />
                      ) : (
                        <Save className="mr-2 size-4" />
                      )}
                      Save Template
                    </Button>
                  </div>
                </CardContent>
              </Card>
            ) : (
              <Card>
                <CardContent className="py-12 text-center">
                  <Mail className="text-muted-foreground mx-auto size-12" />
                  <h3 className="mt-4 text-lg font-medium">Select a template</h3>
                  <p className="text-muted-foreground mt-2">
                    Choose a template from the sidebar to start editing.
                  </p>
                </CardContent>
              </Card>
            )}
          </div>

          {/* Variable Reference Panel */}
          <div className="lg:col-span-3">
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="flex items-center gap-2 text-base">
                  <Info className="size-4" />
                  Template Variables
                </CardTitle>
                <CardDescription>
                  Use these variables in your template. They will be replaced with actual values
                  when the email is sent.
                </CardDescription>
              </CardHeader>
              <CardContent>
                {currentVariables.length > 0 ? (
                  <div className="space-y-3">
                    {currentVariables.map((v) => (
                      <div key={v.variable} className="space-y-1">
                        <code className="bg-muted rounded px-1.5 py-0.5 text-xs font-semibold">
                          {v.variable}
                        </code>
                        <p className="text-muted-foreground text-xs">{v.description}</p>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-muted-foreground text-sm">
                    Select a template to see available variables.
                  </p>
                )}
              </CardContent>
            </Card>

            {/* Tips Card */}
            <Card className="mt-4">
              <CardHeader className="pb-3">
                <CardTitle className="flex items-center gap-2 text-base">
                  <ShieldCheck className="size-4" />
                  Best Practices
                </CardTitle>
              </CardHeader>
              <CardContent>
                <ul className="text-muted-foreground space-y-2 text-xs">
                  <li>Keep subject lines under 50 characters for best open rates.</li>
                  <li>Always include a plain-text fallback for accessibility.</li>
                  <li>
                    Test templates across email clients (Gmail, Outlook, Apple Mail) before going
                    live.
                  </li>
                  <li>
                    Use inline CSS styles for maximum email client compatibility.
                  </li>
                  <li>
                    Include your organization name and unsubscribe link for compliance (CAN-SPAM).
                  </li>
                </ul>
              </CardContent>
            </Card>
          </div>
        </div>
      </div>
    </div>
  )
}
