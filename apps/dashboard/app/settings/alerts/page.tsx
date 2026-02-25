'use client'

import { useState, useEffect } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@janua/ui'
import { Button } from '@janua/ui'
import { Badge } from '@janua/ui'
import { Input } from '@janua/ui'
import { Label } from '@janua/ui'
import Link from 'next/link'
import {
  Bell,
  ArrowLeft,
  Loader2,
  AlertCircle,
  CheckCircle2,
  AlertTriangle,
  XCircle,
  Plus,
  Mail,
  Webhook,
  RefreshCw,
  Settings,
  Trash2,
} from 'lucide-react'
import {
  getActiveAlerts,
  getAlertChannels,
  getAlertRules,
  acknowledgeAlert,
  resolveAlert,
  createChannel,
  deleteChannel,
  createRule,
  deleteRule,
  toggleRule,
} from '@/lib/api'

interface Alert {
  id: string
  type: 'security' | 'usage' | 'system'
  severity: 'critical' | 'high' | 'medium' | 'low'
  title: string
  message: string
  created_at: string
  acknowledged_at: string | null
  resolved_at: string | null
  metadata: Record<string, unknown>
}

interface AlertChannel {
  id: string
  name: string
  type: 'email' | 'webhook' | 'slack'
  config: Record<string, string>
  enabled: boolean
  created_at: string
}

interface AlertRule {
  id: string
  name: string
  condition: string
  threshold: number
  severity: 'critical' | 'high' | 'medium' | 'low'
  channels: string[]
  enabled: boolean
  created_at: string
}

const severityIcons = {
  critical: <XCircle className="text-destructive size-4" />,
  high: <AlertTriangle className="size-4 text-orange-500" />,
  medium: <AlertCircle className="size-4 text-yellow-500" />,
  low: <Bell className="text-muted-foreground size-4" />,
}

const severityColors = {
  critical: 'destructive',
  high: 'default',
  medium: 'secondary',
  low: 'outline',
} as const

export default function AlertsPage() {
  const [activeAlerts, setActiveAlerts] = useState<Alert[]>([])
  const [channels, setChannels] = useState<AlertChannel[]>([])
  const [rules, setRules] = useState<AlertRule[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)

  // New channel form
  const [showChannelForm, setShowChannelForm] = useState(false)
  const [newChannel, setNewChannel] = useState({
    name: '',
    type: 'email' as 'email' | 'webhook' | 'slack',
    config: { endpoint: '' },
  })

  // New rule form
  const [showRuleForm, setShowRuleForm] = useState(false)
  const [savingRule, setSavingRule] = useState(false)
  const [newRule, setNewRule] = useState({
    name: '',
    condition: 'login_failures',
    threshold: 5,
    severity: 'medium' as 'critical' | 'high' | 'medium' | 'low',
    channels: [] as string[],
  })

  useEffect(() => {
    fetchAlertData()
  }, [])

  const fetchAlertData = async () => {
    try {
      setLoading(true)
      setError(null)

      const [alertsData, channelsData, rulesData] = await Promise.all([
        getActiveAlerts().catch(() => []),
        getAlertChannels().catch(() => []),
        getAlertRules().catch(() => []),
      ])

      setActiveAlerts(Array.isArray(alertsData) ? alertsData as unknown as Alert[] : [])
      setChannels(Array.isArray(channelsData) ? channelsData as unknown as AlertChannel[] : [])
      setRules(Array.isArray(rulesData) ? rulesData as unknown as AlertRule[] : [])
    } catch (err) {
      console.error('Failed to fetch alert data:', err)
      setError(err instanceof Error ? err.message : 'Failed to load alert configuration')
    } finally {
      setLoading(false)
    }
  }

  const handleAcknowledge = async (alertId: string) => {
    try {
      await acknowledgeAlert(alertId)
      setSuccess('Alert acknowledged')
      setTimeout(() => setSuccess(null), 3000)
      fetchAlertData()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to acknowledge alert')
    }
  }

  const handleResolve = async (alertId: string) => {
    try {
      await resolveAlert(alertId)
      setSuccess('Alert resolved')
      setTimeout(() => setSuccess(null), 3000)
      fetchAlertData()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to resolve alert')
    }
  }

  const handleCreateChannel = async () => {
    if (!newChannel.name.trim()) {
      setError('Please enter a channel name')
      return
    }

    try {
      await createChannel(newChannel)
      setSuccess('Notification channel created')
      setTimeout(() => setSuccess(null), 3000)
      setShowChannelForm(false)
      setNewChannel({ name: '', type: 'email', config: { endpoint: '' } })
      fetchAlertData()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create channel')
    }
  }

  const handleDeleteChannel = async (channelId: string) => {
    if (!confirm('Are you sure you want to delete this notification channel?')) return

    try {
      await deleteChannel(channelId)
      setSuccess('Channel deleted')
      setTimeout(() => setSuccess(null), 3000)
      fetchAlertData()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete channel')
    }
  }

  const handleToggleRule = async (ruleId: string, enabled: boolean) => {
    try {
      await toggleRule(ruleId, enabled)
      fetchAlertData()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to update rule')
    }
  }

  const handleCreateRule = async () => {
    if (!newRule.name.trim()) {
      setError('Please enter a rule name')
      return
    }

    setSavingRule(true)
    setError(null)

    try {
      await createRule({
        name: newRule.name.trim(),
        condition: newRule.condition,
        threshold: newRule.threshold,
        channel_id: newRule.channels[0] || '',
        is_active: true,
      })

      setSuccess('Alert rule created successfully')
      setTimeout(() => setSuccess(null), 3000)
      setShowRuleForm(false)
      setNewRule({
        name: '',
        condition: 'login_failures',
        threshold: 5,
        severity: 'medium',
        channels: [],
      })
      fetchAlertData()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create rule')
    } finally {
      setSavingRule(false)
    }
  }

  const handleDeleteRule = async (ruleId: string) => {
    if (!confirm('Are you sure you want to delete this alert rule?')) return

    try {
      await deleteRule(ruleId)
      setSuccess('Rule deleted successfully')
      setTimeout(() => setSuccess(null), 3000)
      fetchAlertData()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete rule')
    }
  }

  const toggleRuleChannel = (channelId: string) => {
    setNewRule((prev) => ({
      ...prev,
      channels: prev.channels.includes(channelId)
        ? prev.channels.filter((c) => c !== channelId)
        : [...prev.channels, channelId],
    }))
  }

  // Available alert conditions
  const alertConditions = [
    { value: 'login_failures', label: 'Failed Login Attempts', description: 'Triggers when login failures exceed threshold' },
    { value: 'suspicious_activity', label: 'Suspicious Activity', description: 'Unusual patterns detected' },
    { value: 'new_device_login', label: 'New Device Login', description: 'Login from unrecognized device' },
    { value: 'mfa_disabled', label: 'MFA Disabled', description: 'Multi-factor authentication disabled' },
    { value: 'password_changed', label: 'Password Changed', description: 'User password was changed' },
    { value: 'api_rate_limit', label: 'API Rate Limit', description: 'API rate limit exceeded' },
    { value: 'session_hijack', label: 'Session Hijacking', description: 'Potential session hijacking detected' },
  ]

  if (loading) {
    return (
      <div className="bg-background flex min-h-screen items-center justify-center">
        <div className="text-center">
          <Loader2 className="text-muted-foreground mx-auto size-8 animate-spin" />
          <p className="text-muted-foreground mt-2 text-sm">Loading alert settings...</p>
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
              <Bell className="text-primary size-8" />
              <div>
                <h1 className="text-2xl font-bold">Security Alerts</h1>
                <p className="text-muted-foreground text-sm">
                  Configure security notifications and alert rules
                </p>
              </div>
            </div>
            <Button variant="outline" size="sm" onClick={fetchAlertData}>
              <RefreshCw className="mr-2 size-4" />
              Refresh
            </Button>
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

        {/* Active Alerts */}
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <div>
                <CardTitle className="flex items-center gap-2">
                  <AlertTriangle className="size-5 text-orange-500" />
                  Active Alerts
                  {activeAlerts.length > 0 && (
                    <Badge variant="destructive">{activeAlerts.length}</Badge>
                  )}
                </CardTitle>
                <CardDescription>
                  Security events requiring attention
                </CardDescription>
              </div>
            </div>
          </CardHeader>
          <CardContent>
            {activeAlerts.length === 0 ? (
              <div className="py-8 text-center">
                <CheckCircle2 className="mx-auto size-12 text-green-500" />
                <h3 className="mt-4 text-lg font-medium">No active alerts</h3>
                <p className="text-muted-foreground mt-2">
                  All security checks are passing. Great job!
                </p>
              </div>
            ) : (
              <div className="space-y-3">
                {activeAlerts.map((alert) => (
                  <div
                    key={alert.id}
                    className="flex items-start justify-between rounded-lg border p-4"
                  >
                    <div className="flex items-start gap-3">
                      {severityIcons[alert.severity]}
                      <div>
                        <div className="flex items-center gap-2">
                          <span className="font-medium">{alert.title}</span>
                          <Badge variant={severityColors[alert.severity]}>
                            {alert.severity}
                          </Badge>
                          <Badge variant="outline">{alert.type}</Badge>
                        </div>
                        <p className="text-muted-foreground mt-1 text-sm">{alert.message}</p>
                        <p className="text-muted-foreground mt-1 text-xs">
                          {new Date(alert.created_at).toLocaleString()}
                        </p>
                      </div>
                    </div>
                    <div className="flex gap-2">
                      {!alert.acknowledged_at && (
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => handleAcknowledge(alert.id)}
                        >
                          Acknowledge
                        </Button>
                      )}
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => handleResolve(alert.id)}
                      >
                        Resolve
                      </Button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        {/* Notification Channels */}
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <div>
                <CardTitle>Notification Channels</CardTitle>
                <CardDescription>
                  Configure where to send alert notifications
                </CardDescription>
              </div>
              <Button size="sm" onClick={() => setShowChannelForm(true)}>
                <Plus className="mr-2 size-4" />
                Add Channel
              </Button>
            </div>
          </CardHeader>
          <CardContent className="space-y-4">
            {showChannelForm && (
              <Card className="border-primary">
                <CardContent className="space-y-4 pt-6">
                  <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                    <div className="space-y-2">
                      <Label htmlFor="channel_name">Channel Name</Label>
                      <Input
                        id="channel_name"
                        value={newChannel.name}
                        onChange={(e) => setNewChannel({ ...newChannel, name: e.target.value })}
                        placeholder="Security Team"
                      />
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="channel_type">Type</Label>
                      <select
                        id="channel_type"
                        value={newChannel.type}
                        onChange={(e) =>
                          setNewChannel({
                            ...newChannel,
                            type: e.target.value as 'email' | 'webhook' | 'slack',
                          })
                        }
                        className="border-input bg-background flex h-10 w-full rounded-md border px-3 py-2"
                      >
                        <option value="email">Email</option>
                        <option value="webhook">Webhook</option>
                        <option value="slack">Slack</option>
                      </select>
                    </div>
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="channel_endpoint">
                      {newChannel.type === 'email' ? 'Email Address' : 'Webhook URL'}
                    </Label>
                    <Input
                      id="channel_endpoint"
                      value={newChannel.config.endpoint}
                      onChange={(e) =>
                        setNewChannel({
                          ...newChannel,
                          config: { ...newChannel.config, endpoint: e.target.value },
                        })
                      }
                      placeholder={
                        newChannel.type === 'email'
                          ? 'security@example.com'
                          : 'https://hooks.slack.com/...'
                      }
                    />
                  </div>
                  <div className="flex justify-end gap-2">
                    <Button variant="outline" onClick={() => setShowChannelForm(false)}>
                      Cancel
                    </Button>
                    <Button onClick={handleCreateChannel}>Create Channel</Button>
                  </div>
                </CardContent>
              </Card>
            )}

            {channels.length === 0 && !showChannelForm ? (
              <div className="py-6 text-center">
                <Mail className="text-muted-foreground mx-auto size-8" />
                <p className="text-muted-foreground mt-2 text-sm">
                  No notification channels configured
                </p>
              </div>
            ) : (
              <div className="space-y-2">
                {channels.map((channel) => (
                  <div
                    key={channel.id}
                    className="flex items-center justify-between rounded-lg border p-3"
                  >
                    <div className="flex items-center gap-3">
                      {channel.type === 'email' ? (
                        <Mail className="text-muted-foreground size-5" />
                      ) : (
                        <Webhook className="text-muted-foreground size-5" />
                      )}
                      <div>
                        <span className="font-medium">{channel.name}</span>
                        <Badge variant="outline" className="ml-2">
                          {channel.type}
                        </Badge>
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      <Badge variant={channel.enabled ? 'default' : 'secondary'}>
                        {channel.enabled ? 'Active' : 'Disabled'}
                      </Badge>
                      <Button
                        variant="ghost"
                        size="icon"
                        onClick={() => handleDeleteChannel(channel.id)}
                      >
                        <Trash2 className="size-4" />
                      </Button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        {/* Alert Rules */}
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <div>
                <CardTitle>Alert Rules</CardTitle>
                <CardDescription>
                  Configure when to trigger security alerts
                </CardDescription>
              </div>
              <Button size="sm" onClick={() => setShowRuleForm(true)}>
                <Plus className="mr-2 size-4" />
                Add Rule
              </Button>
            </div>
          </CardHeader>
          <CardContent className="space-y-4">
            {/* Create Rule Form */}
            {showRuleForm && (
              <Card className="border-primary">
                <CardHeader>
                  <CardTitle className="text-base">Create Alert Rule</CardTitle>
                  <CardDescription>
                    Define custom conditions for triggering security alerts
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                    <div className="space-y-2">
                      <Label htmlFor="rule_name">Rule Name</Label>
                      <Input
                        id="rule_name"
                        value={newRule.name}
                        onChange={(e) => setNewRule({ ...newRule, name: e.target.value })}
                        placeholder="e.g., Brute Force Detection"
                      />
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="rule_severity">Severity</Label>
                      <select
                        id="rule_severity"
                        value={newRule.severity}
                        onChange={(e) =>
                          setNewRule({
                            ...newRule,
                            severity: e.target.value as 'critical' | 'high' | 'medium' | 'low',
                          })
                        }
                        className="border-input bg-background flex h-10 w-full rounded-md border px-3 py-2"
                      >
                        <option value="critical">Critical</option>
                        <option value="high">High</option>
                        <option value="medium">Medium</option>
                        <option value="low">Low</option>
                      </select>
                    </div>
                  </div>

                  <div className="space-y-2">
                    <Label htmlFor="rule_condition">Condition</Label>
                    <select
                      id="rule_condition"
                      value={newRule.condition}
                      onChange={(e) => setNewRule({ ...newRule, condition: e.target.value })}
                      className="border-input bg-background flex h-10 w-full rounded-md border px-3 py-2"
                    >
                      {alertConditions.map((condition) => (
                        <option key={condition.value} value={condition.value}>
                          {condition.label}
                        </option>
                      ))}
                    </select>
                    <p className="text-muted-foreground text-sm">
                      {alertConditions.find((c) => c.value === newRule.condition)?.description}
                    </p>
                  </div>

                  <div className="space-y-2">
                    <Label htmlFor="rule_threshold">Threshold</Label>
                    <Input
                      id="rule_threshold"
                      type="number"
                      min={1}
                      max={100}
                      value={newRule.threshold}
                      onChange={(e) =>
                        setNewRule({ ...newRule, threshold: parseInt(e.target.value) || 1 })
                      }
                    />
                    <p className="text-muted-foreground text-sm">
                      Number of occurrences before triggering an alert
                    </p>
                  </div>

                  {channels.length > 0 && (
                    <div className="space-y-2">
                      <Label>Notification Channels</Label>
                      <div className="grid grid-cols-1 gap-2 md:grid-cols-2">
                        {channels.map((channel) => (
                          <label
                            key={channel.id}
                            className={`flex cursor-pointer items-center gap-3 rounded-lg border p-3 transition-colors ${
                              newRule.channels.includes(channel.id)
                                ? 'border-primary bg-primary/5'
                                : 'hover:bg-muted'
                            }`}
                          >
                            <input
                              type="checkbox"
                              checked={newRule.channels.includes(channel.id)}
                              onChange={() => toggleRuleChannel(channel.id)}
                            />
                            <div className="flex items-center gap-2">
                              {channel.type === 'email' ? (
                                <Mail className="text-muted-foreground size-4" />
                              ) : (
                                <Webhook className="text-muted-foreground size-4" />
                              )}
                              <span>{channel.name}</span>
                              <Badge variant="outline" className="text-xs">
                                {channel.type}
                              </Badge>
                            </div>
                          </label>
                        ))}
                      </div>
                    </div>
                  )}

                  <div className="flex justify-end gap-2">
                    <Button
                      variant="outline"
                      onClick={() => {
                        setShowRuleForm(false)
                        setNewRule({
                          name: '',
                          condition: 'login_failures',
                          threshold: 5,
                          severity: 'medium',
                          channels: [],
                        })
                      }}
                    >
                      Cancel
                    </Button>
                    <Button onClick={handleCreateRule} disabled={savingRule}>
                      {savingRule ? (
                        <Loader2 className="mr-2 size-4 animate-spin" />
                      ) : (
                        <Plus className="mr-2 size-4" />
                      )}
                      Create Rule
                    </Button>
                  </div>
                </CardContent>
              </Card>
            )}

            {rules.length === 0 && !showRuleForm ? (
              <div className="py-6 text-center">
                <Settings className="text-muted-foreground mx-auto size-8" />
                <p className="text-muted-foreground mt-2 text-sm">
                  No custom alert rules configured. Default security rules are active.
                </p>
                <Button
                  variant="outline"
                  size="sm"
                  className="mt-4"
                  onClick={() => setShowRuleForm(true)}
                >
                  <Plus className="mr-2 size-4" />
                  Create Custom Rule
                </Button>
              </div>
            ) : (
              <div className="space-y-2">
                {rules.map((rule) => (
                  <div
                    key={rule.id}
                    className="flex items-center justify-between rounded-lg border p-3"
                  >
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="font-medium">{rule.name}</span>
                        <Badge variant={severityColors[rule.severity]}>{rule.severity}</Badge>
                        <Badge variant={rule.enabled ? 'default' : 'secondary'}>
                          {rule.enabled ? 'Active' : 'Disabled'}
                        </Badge>
                      </div>
                      <p className="text-muted-foreground mt-1 text-sm">
                        {alertConditions.find((c) => c.value === rule.condition)?.label ||
                          rule.condition}{' '}
                        (threshold: {rule.threshold})
                      </p>
                    </div>
                    <div className="flex gap-2">
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => handleToggleRule(rule.id, !rule.enabled)}
                      >
                        {rule.enabled ? 'Disable' : 'Enable'}
                      </Button>
                      <Button
                        variant="outline"
                        size="sm"
                        className="text-destructive hover:bg-destructive hover:text-destructive-foreground"
                        onClick={() => handleDeleteRule(rule.id)}
                      >
                        <Trash2 className="size-4" />
                      </Button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        {/* Default Security Rules */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Default Security Rules</CardTitle>
            <CardDescription>
              These rules are always active and cannot be disabled
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-2 text-sm">
              <div className="flex items-center gap-2 text-green-600 dark:text-green-400">
                <CheckCircle2 className="size-4" />
                <span>Multiple failed login attempts (5+ in 10 minutes)</span>
              </div>
              <div className="flex items-center gap-2 text-green-600 dark:text-green-400">
                <CheckCircle2 className="size-4" />
                <span>Login from new device or location</span>
              </div>
              <div className="flex items-center gap-2 text-green-600 dark:text-green-400">
                <CheckCircle2 className="size-4" />
                <span>Password reset request</span>
              </div>
              <div className="flex items-center gap-2 text-green-600 dark:text-green-400">
                <CheckCircle2 className="size-4" />
                <span>MFA disabled on account</span>
              </div>
              <div className="flex items-center gap-2 text-green-600 dark:text-green-400">
                <CheckCircle2 className="size-4" />
                <span>Suspicious activity patterns</span>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
