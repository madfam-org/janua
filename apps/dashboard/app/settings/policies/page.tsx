'use client'

import { useState, useEffect, useCallback } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@janua/ui'
import { Button } from '@janua/ui'
import { Badge } from '@janua/ui'
import { Input } from '@janua/ui'
import { Label } from '@janua/ui'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@janua/ui'
import Link from 'next/link'
import {
  Plus,
  Trash2,
  Pencil,
  Shield,
  ArrowLeft,
  Loader2,
  AlertCircle,
  CheckCircle2,
  RefreshCw,
  Search,
  X,
  Play,
  FileText,
  ShieldCheck,
  ShieldOff,
} from 'lucide-react'
import { apiCall } from '../../../lib/auth'

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'https://api.janua.dev'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface Policy {
  id: string
  name: string
  description: string | null
  type: 'rbac' | 'abac' | 'custom'
  effect: 'allow' | 'deny'
  conditions: Record<string, unknown> | null
  resources: string[]
  actions: string[]
  is_active: boolean
  rules_count: number
  created_at: string
  updated_at: string | null
}

interface PolicyFormData {
  name: string
  description: string
  type: 'rbac' | 'abac' | 'custom'
  effect: 'allow' | 'deny'
  conditions: string
  resources: string
  actions: string
}

interface EvaluationResult {
  allowed: boolean
  policy_id: string
  policy_name: string
  effect: string
  matched_rules: number
  details: string | null
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const POLICY_TYPES: { value: Policy['type']; label: string }[] = [
  { value: 'rbac', label: 'RBAC' },
  { value: 'abac', label: 'ABAC' },
  { value: 'custom', label: 'Custom' },
]

const POLICY_EFFECTS: { value: Policy['effect']; label: string }[] = [
  { value: 'allow', label: 'Allow' },
  { value: 'deny', label: 'Deny' },
]

const DEFAULT_FORM: PolicyFormData = {
  name: '',
  description: '',
  type: 'rbac',
  effect: 'allow',
  conditions: '{}',
  resources: '',
  actions: '',
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function policyTypeBadge(type: Policy['type']) {
  const variants: Record<Policy['type'], 'default' | 'secondary' | 'outline'> = {
    rbac: 'default',
    abac: 'secondary',
    custom: 'outline',
  }
  return (
    <Badge variant={variants[type]}>{type.toUpperCase()}</Badge>
  )
}

function statusBadge(active: boolean) {
  return active ? (
    <Badge variant="default" className="bg-green-600 hover:bg-green-700">Active</Badge>
  ) : (
    <Badge variant="secondary">Inactive</Badge>
  )
}

function effectBadge(effect: Policy['effect']) {
  return effect === 'allow' ? (
    <Badge variant="outline" className="border-green-500 text-green-600">Allow</Badge>
  ) : (
    <Badge variant="outline" className="border-red-500 text-red-600">Deny</Badge>
  )
}

function parseJsonSafe(str: string): Record<string, unknown> | null {
  try {
    const parsed = JSON.parse(str)
    return typeof parsed === 'object' && parsed !== null ? parsed : null
  } catch {
    return null
  }
}

// ---------------------------------------------------------------------------
// Confirm Dialog
// ---------------------------------------------------------------------------

function ConfirmDialog({
  open,
  onOpenChange,
  title,
  description,
  confirmLabel,
  destructive,
  loading,
  onConfirm,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  title: string
  description: string
  confirmLabel: string
  destructive?: boolean
  loading?: boolean
  onConfirm: () => void
}) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
        </DialogHeader>
        <p className="text-muted-foreground text-sm">{description}</p>
        <div className="flex justify-end gap-2 pt-2">
          <Button variant="outline" onClick={() => onOpenChange(false)} disabled={loading}>
            Cancel
          </Button>
          <Button
            variant={destructive ? 'destructive' : 'default'}
            onClick={onConfirm}
            disabled={loading}
          >
            {loading && <Loader2 className="mr-2 size-4 animate-spin" />}
            {confirmLabel}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  )
}

// ---------------------------------------------------------------------------
// Create / Edit Dialog
// ---------------------------------------------------------------------------

function PolicyFormDialog({
  open,
  onOpenChange,
  editPolicy,
  onSuccess,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  editPolicy?: Policy | null
  onSuccess: () => void
}) {
  const isEdit = !!editPolicy

  const [form, setForm] = useState<PolicyFormData>(DEFAULT_FORM)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (open) {
      if (editPolicy) {
        setForm({
          name: editPolicy.name,
          description: editPolicy.description || '',
          type: editPolicy.type,
          effect: editPolicy.effect,
          conditions: editPolicy.conditions
            ? JSON.stringify(editPolicy.conditions, null, 2)
            : '{}',
          resources: editPolicy.resources.join(', '),
          actions: editPolicy.actions.join(', '),
        })
      } else {
        setForm(DEFAULT_FORM)
      }
      setError(null)
    }
  }, [open, editPolicy])

  const updateField = <K extends keyof PolicyFormData>(key: K, value: PolicyFormData[K]) => {
    setForm((prev) => ({ ...prev, [key]: value }))
  }

  const handleSubmit = async () => {
    if (!form.name.trim()) {
      setError('Policy name is required')
      return
    }

    const conditions = parseJsonSafe(form.conditions)
    if (form.conditions.trim() !== '{}' && conditions === null) {
      setError('Conditions must be valid JSON')
      return
    }

    setSubmitting(true)
    setError(null)

    try {
      const body = {
        name: form.name.trim(),
        description: form.description.trim() || null,
        type: form.type,
        effect: form.effect,
        conditions: conditions || {},
        resources: form.resources
          .split(',')
          .map((r) => r.trim())
          .filter(Boolean),
        actions: form.actions
          .split(',')
          .map((a) => a.trim())
          .filter(Boolean),
      }

      const url = isEdit
        ? `${API_BASE_URL}/api/v1/policies/${editPolicy.id}`
        : `${API_BASE_URL}/api/v1/policies`
      const method = isEdit ? 'PATCH' : 'POST'

      const response = await apiCall(url, {
        method,
        body: JSON.stringify(body),
      })

      if (!response.ok) {
        const data = await response.json().catch(() => ({}))
        throw new Error(data.detail || `Failed to ${isEdit ? 'update' : 'create'} policy`)
      }

      onSuccess()
      onOpenChange(false)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An unexpected error occurred')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>{isEdit ? 'Edit Policy' : 'Create Policy'}</DialogTitle>
        </DialogHeader>

        <div className="space-y-5">
          {error && (
            <div className="text-destructive flex items-center gap-2 text-sm">
              <AlertCircle className="size-4 shrink-0" />
              <span>{error}</span>
            </div>
          )}

          <div className="grid gap-4 md:grid-cols-2">
            <div className="space-y-2">
              <Label htmlFor="policy_name">Name</Label>
              <Input
                id="policy_name"
                value={form.name}
                onChange={(e) => updateField('name', e.target.value)}
                placeholder="e.g., admin-full-access"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="policy_description">Description</Label>
              <Input
                id="policy_description"
                value={form.description}
                onChange={(e) => updateField('description', e.target.value)}
                placeholder="Brief description of this policy"
              />
            </div>
          </div>

          <div className="grid gap-4 md:grid-cols-2">
            <div className="space-y-2">
              <Label htmlFor="policy_type">Type</Label>
              <select
                id="policy_type"
                value={form.type}
                onChange={(e) => updateField('type', e.target.value as Policy['type'])}
                className="border-input bg-background ring-offset-background focus-visible:ring-ring flex h-10 w-full rounded-md border px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2"
                aria-label="Policy type"
              >
                {POLICY_TYPES.map((t) => (
                  <option key={t.value} value={t.value}>
                    {t.label}
                  </option>
                ))}
              </select>
            </div>
            <div className="space-y-2">
              <Label htmlFor="policy_effect">Effect</Label>
              <select
                id="policy_effect"
                value={form.effect}
                onChange={(e) => updateField('effect', e.target.value as Policy['effect'])}
                className="border-input bg-background ring-offset-background focus-visible:ring-ring flex h-10 w-full rounded-md border px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2"
                aria-label="Policy effect"
              >
                {POLICY_EFFECTS.map((e) => (
                  <option key={e.value} value={e.value}>
                    {e.label}
                  </option>
                ))}
              </select>
            </div>
          </div>

          <div className="space-y-2">
            <Label htmlFor="policy_resources">Resources (comma-separated)</Label>
            <Input
              id="policy_resources"
              value={form.resources}
              onChange={(e) => updateField('resources', e.target.value)}
              placeholder="e.g., users, organizations, settings"
            />
            <p className="text-muted-foreground text-xs">
              Resource identifiers this policy applies to. Use * for all resources.
            </p>
          </div>

          <div className="space-y-2">
            <Label htmlFor="policy_actions">Actions (comma-separated)</Label>
            <Input
              id="policy_actions"
              value={form.actions}
              onChange={(e) => updateField('actions', e.target.value)}
              placeholder="e.g., read, write, delete, admin"
            />
            <p className="text-muted-foreground text-xs">
              Actions that this policy controls. Use * for all actions.
            </p>
          </div>

          <div className="space-y-2">
            <Label htmlFor="policy_conditions">Conditions (JSON)</Label>
            <textarea
              id="policy_conditions"
              value={form.conditions}
              onChange={(e) => updateField('conditions', e.target.value)}
              rows={6}
              className="border-input bg-background ring-offset-background placeholder:text-muted-foreground focus-visible:ring-ring flex w-full rounded-md border px-3 py-2 font-mono text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2"
              placeholder='{"role": "admin", "ip_range": "10.0.0.0/8"}'
              aria-label="Policy conditions in JSON format"
            />
            <p className="text-muted-foreground text-xs">
              JSON object defining additional conditions for policy evaluation.
            </p>
          </div>

          <div className="flex justify-end gap-2">
            <Button variant="outline" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button onClick={handleSubmit} disabled={submitting}>
              {submitting && <Loader2 className="mr-2 size-4 animate-spin" />}
              {isEdit ? 'Save Changes' : 'Create Policy'}
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  )
}

// ---------------------------------------------------------------------------
// Evaluation Panel Dialog
// ---------------------------------------------------------------------------

function EvaluationDialog({
  open,
  onOpenChange,
  policies,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  policies: Policy[]
}) {
  const [selectedPolicyId, setSelectedPolicyId] = useState('')
  const [contextJson, setContextJson] = useState('{\n  "user_role": "admin",\n  "resource": "users",\n  "action": "read"\n}')
  const [evaluating, setEvaluating] = useState(false)
  const [result, setResult] = useState<EvaluationResult | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (open) {
      setResult(null)
      setError(null)
      if (policies.length > 0 && !selectedPolicyId) {
        setSelectedPolicyId(policies[0].id)
      }
    }
  }, [open, policies, selectedPolicyId])

  const handleEvaluate = async () => {
    if (!selectedPolicyId) {
      setError('Please select a policy to evaluate')
      return
    }

    const context = parseJsonSafe(contextJson)
    if (context === null) {
      setError('Context must be valid JSON')
      return
    }

    setEvaluating(true)
    setError(null)
    setResult(null)

    try {
      const response = await apiCall(`${API_BASE_URL}/api/v1/policies/evaluate`, {
        method: 'POST',
        body: JSON.stringify({
          policy_id: selectedPolicyId,
          context,
        }),
      })

      if (!response.ok) {
        const data = await response.json().catch(() => ({}))
        throw new Error(data.detail || 'Failed to evaluate policy')
      }

      const data: EvaluationResult = await response.json()
      setResult(data)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Evaluation failed')
    } finally {
      setEvaluating(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Play className="size-5" />
            Policy Evaluation Test
          </DialogTitle>
        </DialogHeader>

        <div className="space-y-5">
          {error && (
            <div className="text-destructive flex items-center gap-2 text-sm">
              <AlertCircle className="size-4 shrink-0" />
              <span>{error}</span>
            </div>
          )}

          <div className="space-y-2">
            <Label htmlFor="eval_policy">Select Policy</Label>
            <select
              id="eval_policy"
              value={selectedPolicyId}
              onChange={(e) => setSelectedPolicyId(e.target.value)}
              className="border-input bg-background ring-offset-background focus-visible:ring-ring flex h-10 w-full rounded-md border px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2"
              aria-label="Select a policy to evaluate"
            >
              <option value="" disabled>
                Choose a policy...
              </option>
              {policies.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name} ({p.type.toUpperCase()}, {p.effect})
                </option>
              ))}
            </select>
          </div>

          <div className="space-y-2">
            <Label htmlFor="eval_context">Evaluation Context (JSON)</Label>
            <textarea
              id="eval_context"
              value={contextJson}
              onChange={(e) => setContextJson(e.target.value)}
              rows={8}
              className="border-input bg-background ring-offset-background placeholder:text-muted-foreground focus-visible:ring-ring flex w-full rounded-md border px-3 py-2 font-mono text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2"
              placeholder='{"user_role": "admin", "resource": "users", "action": "read"}'
              aria-label="Evaluation context in JSON format"
            />
            <p className="text-muted-foreground text-xs">
              Provide a JSON object representing the request context to evaluate against the
              selected policy.
            </p>
          </div>

          <Button onClick={handleEvaluate} disabled={evaluating} className="w-full">
            {evaluating ? (
              <Loader2 className="mr-2 size-4 animate-spin" />
            ) : (
              <Play className="mr-2 size-4" />
            )}
            Evaluate Policy
          </Button>

          {result && (
            <Card
              className={
                result.allowed
                  ? 'border-green-500 bg-green-50 dark:bg-green-950/20'
                  : 'border-red-500 bg-red-50 dark:bg-red-950/20'
              }
            >
              <CardContent className="pt-6">
                <div className="space-y-3">
                  <div className="flex items-center gap-3">
                    {result.allowed ? (
                      <ShieldCheck className="size-8 text-green-600" />
                    ) : (
                      <ShieldOff className="size-8 text-red-600" />
                    )}
                    <div>
                      <h4 className="text-lg font-semibold">
                        {result.allowed ? 'Allowed' : 'Denied'}
                      </h4>
                      <p className="text-muted-foreground text-sm">
                        Policy: {result.policy_name} (effect: {result.effect})
                      </p>
                    </div>
                  </div>
                  <div className="text-sm">
                    <span className="text-muted-foreground">Matched rules:</span>{' '}
                    <strong>{result.matched_rules}</strong>
                  </div>
                  {result.details && (
                    <div className="text-sm">
                      <span className="text-muted-foreground">Details:</span>{' '}
                      {result.details}
                    </div>
                  )}
                </div>
              </CardContent>
            </Card>
          )}

          <div className="flex justify-end">
            <Button variant="outline" onClick={() => onOpenChange(false)}>
              Close
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  )
}

// ---------------------------------------------------------------------------
// Main Page
// ---------------------------------------------------------------------------

export default function PoliciesPage() {
  const [policies, setPolicies] = useState<Policy[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)
  const [search, setSearch] = useState('')

  // Dialogs
  const [createOpen, setCreateOpen] = useState(false)
  const [editPolicy, setEditPolicy] = useState<Policy | null>(null)
  const [deleteTarget, setDeleteTarget] = useState<Policy | null>(null)
  const [evalOpen, setEvalOpen] = useState(false)
  const [actionLoading, setActionLoading] = useState(false)

  const fetchPolicies = useCallback(async () => {
    try {
      setLoading(true)
      setError(null)
      const response = await apiCall(`${API_BASE_URL}/api/v1/policies`)

      if (response.status === 404) {
        setPolicies([])
      } else if (!response.ok) {
        throw new Error('Failed to fetch policies')
      } else {
        const data = await response.json()
        setPolicies(Array.isArray(data) ? data : data.items || [])
      }
    } catch (err) {
      console.error('Failed to fetch policies:', err)
      setError(err instanceof Error ? err.message : 'Failed to load policies')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchPolicies()
  }, [fetchPolicies])

  // Clear success message after timeout
  useEffect(() => {
    if (success) {
      const timer = setTimeout(() => setSuccess(null), 4000)
      return () => clearTimeout(timer)
    }
  }, [success])

  // ---- Delete ----
  const handleDeleteConfirm = async () => {
    if (!deleteTarget) return
    setActionLoading(true)
    try {
      const response = await apiCall(
        `${API_BASE_URL}/api/v1/policies/${deleteTarget.id}`,
        { method: 'DELETE' }
      )
      if (!response.ok) {
        const data = await response.json().catch(() => ({}))
        throw new Error(data.detail || 'Failed to delete policy')
      }
      setSuccess(`Policy "${deleteTarget.name}" has been deleted.`)
      setDeleteTarget(null)
      fetchPolicies()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete policy')
      setDeleteTarget(null)
    } finally {
      setActionLoading(false)
    }
  }

  // ---- Filter ----
  const filteredPolicies = policies.filter((p) =>
    p.name.toLowerCase().includes(search.toLowerCase())
  )

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------

  if (loading) {
    return (
      <div className="bg-background flex min-h-screen items-center justify-center">
        <div className="text-center">
          <Loader2 className="text-muted-foreground mx-auto size-8 animate-spin" />
          <p className="text-muted-foreground mt-2 text-sm">Loading policies...</p>
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
              <Link
                href="/settings"
                className="text-muted-foreground hover:text-foreground"
                aria-label="Back to settings"
              >
                <ArrowLeft className="size-5" />
              </Link>
              <Shield className="text-primary size-8" />
              <div>
                <h1 className="text-2xl font-bold">Authorization Policies</h1>
                <p className="text-muted-foreground text-sm">
                  Manage RBAC, ABAC, and custom authorization policies
                </p>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <Button variant="outline" onClick={() => setEvalOpen(true)}>
                <Play className="mr-2 size-4" />
                Test Policy
              </Button>
              <Button
                onClick={() => {
                  setEditPolicy(null)
                  setCreateOpen(true)
                }}
              >
                <Plus className="mr-2 size-4" />
                Create Policy
              </Button>
            </div>
          </div>
        </div>
      </header>

      <div className="container mx-auto space-y-6 px-4 py-8">
        {/* Error banner */}
        {error && (
          <Card className="border-destructive">
            <CardContent className="pt-6">
              <div className="text-destructive flex items-center gap-2">
                <AlertCircle className="size-5 shrink-0" />
                <span>{error}</span>
                <Button
                  variant="ghost"
                  size="icon"
                  className="ml-auto size-6"
                  onClick={() => setError(null)}
                  aria-label="Dismiss error"
                >
                  <X className="size-4" />
                </Button>
              </div>
            </CardContent>
          </Card>
        )}

        {/* Success banner */}
        {success && (
          <Card className="border-green-500">
            <CardContent className="pt-6">
              <div className="flex items-center gap-2 text-green-600 dark:text-green-400">
                <CheckCircle2 className="size-5 shrink-0" />
                <span>{success}</span>
              </div>
            </CardContent>
          </Card>
        )}

        {/* Policies Table */}
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <div>
                <CardTitle>Policies</CardTitle>
                <CardDescription>
                  Authorization policies controlling access to resources and actions
                </CardDescription>
              </div>
              <Button variant="outline" size="sm" onClick={fetchPolicies}>
                <RefreshCw className="mr-2 size-4" />
                Refresh
              </Button>
            </div>

            {/* Search */}
            <div className="relative mt-4">
              <Search className="text-muted-foreground absolute left-3 top-1/2 size-4 -translate-y-1/2" />
              <Input
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Search policies by name..."
                className="pl-10"
                aria-label="Search policies by name"
              />
              {search && (
                <Button
                  variant="ghost"
                  size="icon"
                  className="absolute right-1 top-1/2 size-7 -translate-y-1/2"
                  onClick={() => setSearch('')}
                  aria-label="Clear search"
                >
                  <X className="size-3" />
                </Button>
              )}
            </div>
          </CardHeader>
          <CardContent>
            {filteredPolicies.length === 0 && policies.length === 0 ? (
              <div className="py-8 text-center">
                <FileText className="text-muted-foreground mx-auto size-12" />
                <h3 className="mt-4 text-lg font-medium">No policies yet</h3>
                <p className="text-muted-foreground mt-2">
                  Create your first authorization policy to control access to your resources.
                </p>
                <Button
                  className="mt-4"
                  onClick={() => {
                    setEditPolicy(null)
                    setCreateOpen(true)
                  }}
                >
                  <Plus className="mr-2 size-4" />
                  Create Policy
                </Button>
              </div>
            ) : filteredPolicies.length === 0 ? (
              <div className="py-8 text-center">
                <Search className="text-muted-foreground mx-auto size-12" />
                <h3 className="mt-4 text-lg font-medium">No matching policies</h3>
                <p className="text-muted-foreground mt-2">
                  No policies match &quot;{search}&quot;. Try a different search term.
                </p>
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full" role="table">
                  <thead>
                    <tr className="border-b text-left">
                      <th className="text-muted-foreground pb-3 pr-4 text-sm font-medium">Name</th>
                      <th className="text-muted-foreground hidden pb-3 pr-4 text-sm font-medium md:table-cell">
                        Description
                      </th>
                      <th className="text-muted-foreground pb-3 pr-4 text-sm font-medium">Type</th>
                      <th className="text-muted-foreground pb-3 pr-4 text-sm font-medium">Effect</th>
                      <th className="text-muted-foreground pb-3 pr-4 text-sm font-medium">Status</th>
                      <th className="text-muted-foreground hidden pb-3 pr-4 text-sm font-medium lg:table-cell">
                        Rules
                      </th>
                      <th className="text-muted-foreground hidden pb-3 pr-4 text-sm font-medium lg:table-cell">
                        Created
                      </th>
                      <th className="text-muted-foreground pb-3 text-right text-sm font-medium">
                        Actions
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredPolicies.map((policy) => (
                      <tr
                        key={policy.id}
                        className="border-b last:border-b-0 transition-colors hover:bg-accent/50"
                      >
                        <td className="py-3 pr-4">
                          <div className="flex items-center gap-2">
                            <Shield className="text-muted-foreground size-4 shrink-0" />
                            <span className="font-medium">{policy.name}</span>
                          </div>
                          {/* Mobile description */}
                          {policy.description && (
                            <p className="text-muted-foreground mt-1 text-xs md:hidden">
                              {policy.description}
                            </p>
                          )}
                        </td>
                        <td className="text-muted-foreground hidden py-3 pr-4 text-sm md:table-cell">
                          <span className="line-clamp-1">
                            {policy.description || '\u2014'}
                          </span>
                        </td>
                        <td className="py-3 pr-4">{policyTypeBadge(policy.type)}</td>
                        <td className="py-3 pr-4">{effectBadge(policy.effect)}</td>
                        <td className="py-3 pr-4">{statusBadge(policy.is_active)}</td>
                        <td className="text-muted-foreground hidden py-3 pr-4 text-sm lg:table-cell">
                          {policy.rules_count}
                        </td>
                        <td className="text-muted-foreground hidden py-3 pr-4 text-sm lg:table-cell">
                          {new Date(policy.created_at).toLocaleDateString()}
                        </td>
                        <td className="py-3 text-right">
                          <div className="flex items-center justify-end gap-1">
                            <Button
                              variant="ghost"
                              size="icon"
                              className="size-8"
                              onClick={() => {
                                setEditPolicy(policy)
                                setCreateOpen(true)
                              }}
                              aria-label={`Edit ${policy.name}`}
                            >
                              <Pencil className="size-4" />
                            </Button>
                            <Button
                              variant="ghost"
                              size="icon"
                              className="text-destructive size-8"
                              onClick={() => setDeleteTarget(policy)}
                              aria-label={`Delete ${policy.name}`}
                            >
                              <Trash2 className="size-4" />
                            </Button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </CardContent>
        </Card>

        {/* Policy Information */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <Shield className="size-4" />
              About Authorization Policies
            </CardTitle>
          </CardHeader>
          <CardContent className="text-muted-foreground space-y-4 text-sm">
            <div>
              <h4 className="text-foreground mb-1 font-medium">Policy Types</h4>
              <ul className="ml-4 list-disc space-y-1">
                <li>
                  <strong>RBAC</strong> (Role-Based Access Control) &mdash; Grant or deny access
                  based on user roles within the organization.
                </li>
                <li>
                  <strong>ABAC</strong> (Attribute-Based Access Control) &mdash; Fine-grained
                  policies using attributes like IP address, time, department, and more.
                </li>
                <li>
                  <strong>Custom</strong> &mdash; Flexible policies combining multiple evaluation
                  strategies.
                </li>
              </ul>
            </div>
            <div>
              <h4 className="text-foreground mb-1 font-medium">Policy Effects</h4>
              <p>
                Each policy either <strong>allows</strong> or <strong>denies</strong> the matched
                action. Deny policies take precedence over allow policies when both match.
              </p>
            </div>
            <div>
              <h4 className="text-foreground mb-1 font-medium">Testing Policies</h4>
              <p>
                Use the <strong>Test Policy</strong> button to evaluate a policy against a given
                context before deploying changes. This helps verify that your policy rules behave
                as expected.
              </p>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* ---------- Dialogs ---------- */}

      {/* Create / Edit Dialog */}
      <PolicyFormDialog
        open={createOpen}
        onOpenChange={(open) => {
          setCreateOpen(open)
          if (!open) setEditPolicy(null)
        }}
        editPolicy={editPolicy}
        onSuccess={() => {
          setSuccess(editPolicy ? 'Policy updated successfully.' : 'Policy created successfully.')
          fetchPolicies()
        }}
      />

      {/* Delete Confirmation */}
      <ConfirmDialog
        open={!!deleteTarget}
        onOpenChange={(open) => {
          if (!open) setDeleteTarget(null)
        }}
        title="Delete Policy"
        description={`Are you sure you want to delete the policy "${deleteTarget?.name}"? Any resources relying on this policy will lose their authorization rules. This action cannot be undone.`}
        confirmLabel="Delete Policy"
        destructive
        loading={actionLoading}
        onConfirm={handleDeleteConfirm}
      />

      {/* Evaluation Test Panel */}
      <EvaluationDialog
        open={evalOpen}
        onOpenChange={setEvalOpen}
        policies={policies}
      />
    </div>
  )
}
