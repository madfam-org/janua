'use client'

import * as React from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import * as z from 'zod'
import {
  Key,
  Eye,
  EyeOff,
  RefreshCw,
  AlertTriangle,
  Clock,
  Shield,
  Server,
  Mail,
  CreditCard,
  Copy,
  Check,
  Loader2,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent } from '@/components/ui/card'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from '@/components/ui/sheet'
import {
  Form,
  FormControl,
  FormDescription,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from '@/components/ui/form'
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog'
import { Separator } from '@/components/ui/separator'
import { Label } from '@/components/ui/label'

// Types
export type SecretCategory = 'authentication' | 'payment' | 'infrastructure' | 'email'
export type SecretStatus = 'active' | 'rotating' | 'expired' | 'revoked'

export interface MaskedSecret {
  id: string
  name: string
  maskedValue: string
  fullValue?: string // Only populated when revealed
  category: SecretCategory
  status: SecretStatus
  lastRotated: Date
  nextRotation: Date
  dependentServices: string[]
  description?: string
}

// Category icon mapping
const categoryIcons: Record<SecretCategory, React.ReactNode> = {
  authentication: <Shield className="h-4 w-4" />,
  payment: <CreditCard className="h-4 w-4" />,
  infrastructure: <Server className="h-4 w-4" />,
  email: <Mail className="h-4 w-4" />,
}

const categoryLabels: Record<SecretCategory, string> = {
  authentication: 'Authentication',
  payment: 'Payment',
  infrastructure: 'Infrastructure',
  email: 'Email',
}

// Status badge component
function StatusBadge({ status }: { status: SecretStatus }) {
  const statusConfig: Record<SecretStatus, { className: string; label: string }> = {
    active: { className: 'status-active', label: 'Active' },
    rotating: { className: 'status-rotating', label: 'Rotating' },
    expired: { className: 'status-expired', label: 'Expired' },
    revoked: { className: 'status-revoked', label: 'Revoked' },
  }
  
  const config = statusConfig[status]
  
  return (
    <Badge variant="outline" className={`${config.className} font-mono text-xs`}>
      {config.label}
    </Badge>
  )
}

// Masked value component with click-to-reveal
function MaskedValue({
  maskedValue,
  fullValue,
  onReveal,
  revealed,
}: {
  maskedValue: string
  fullValue?: string
  onReveal: () => void
  revealed: boolean
}) {
  const [copied, setCopied] = React.useState(false)
  
  const handleCopy = async () => {
    if (fullValue) {
      await navigator.clipboard.writeText(fullValue)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    }
  }
  
  return (
    <div className="flex items-center gap-2 font-mono text-sm">
      <span className="secret-masked text-muted-foreground">
        {revealed && fullValue ? fullValue : maskedValue}
      </span>
      <Button
        variant="ghost"
        size="sm"
        className="h-6 w-6 p-0"
        onClick={revealed ? handleCopy : onReveal}
      >
        {revealed ? (
          copied ? (
            <Check className="h-3 w-3 text-primary" />
          ) : (
            <Copy className="h-3 w-3" />
          )
        ) : (
          <Eye className="h-3 w-3" />
        )}
      </Button>
      {revealed && (
        <Button
          variant="ghost"
          size="sm"
          className="h-6 w-6 p-0"
          onClick={onReveal}
        >
          <EyeOff className="h-3 w-3" />
        </Button>
      )}
    </div>
  )
}

// Rotation validation schema
const rotationSchema = z.object({
  newValue: z.string().min(1, 'New secret value is required'),
  confirmValue: z.string().min(1, 'Please confirm the secret value'),
  reason: z.string().optional(),
}).refine((data) => data.newValue === data.confirmValue, {
  message: "Values don't match",
  path: ['confirmValue'],
})

type RotationFormValues = z.infer<typeof rotationSchema>

// Rotation sheet component
function RotationSheet({
  secret,
  onRotate,
}: {
  secret: MaskedSecret
  onRotate: (secretId: string, newValue: string, reason?: string) => Promise<void>
}) {
  const [open, setOpen] = React.useState(false)
  const [loading, setLoading] = React.useState(false)
  const [confirmDialog, setConfirmDialog] = React.useState(false)
  
  const form = useForm<RotationFormValues>({
    resolver: zodResolver(rotationSchema),
    defaultValues: {
      newValue: '',
      confirmValue: '',
      reason: '',
    },
  })
  
  const onSubmit = async (_data: RotationFormValues) => {
    setConfirmDialog(true)
  }
  
  const executeRotation = async () => {
    const values = form.getValues()
    setLoading(true)
    try {
      await onRotate(secret.id, values.newValue, values.reason)
      form.reset()
      setConfirmDialog(false)
      setOpen(false)
    } catch (error) {
      console.error('Rotation failed:', error)
    } finally {
      setLoading(false)
    }
  }
  
  const isOverdue = new Date(secret.nextRotation) < new Date()
  
  return (
    <>
      <Sheet open={open} onOpenChange={setOpen}>
        <SheetTrigger asChild>
          <Button variant="ghost" size="sm" className="h-8">
            <RefreshCw className="h-4 w-4 mr-2" />
            Rotate
          </Button>
        </SheetTrigger>
        <SheetContent className="w-[500px] sm:max-w-[500px]">
          <SheetHeader>
            <SheetTitle className="flex items-center gap-2">
              <Key className="h-5 w-5 text-primary" />
              Rotate Secret: {secret.name}
            </SheetTitle>
            <SheetDescription>
              Rotate this secret to a new value. This will update all dependent services.
            </SheetDescription>
          </SheetHeader>
          
          <div className="py-6 space-y-6">
            {/* Secret info */}
            <div className="space-y-2">
              <Label className="text-muted-foreground">Current Secret</Label>
              <div className="p-3 bg-muted rounded-lg font-mono text-sm">
                {secret.maskedValue}
              </div>
            </div>
            
            {/* Overdue warning */}
            {isOverdue && (
              <div className="p-3 bg-destructive/10 border border-destructive/30 rounded-lg flex items-start gap-3">
                <AlertTriangle className="h-5 w-5 text-destructive shrink-0 mt-0.5" />
                <div>
                  <p className="font-medium text-destructive">Rotation Overdue</p>
                  <p className="text-sm text-muted-foreground">
                    This secret was due for rotation on{' '}
                    {new Date(secret.nextRotation).toLocaleDateString()}
                  </p>
                </div>
              </div>
            )}
            
            {/* Dependent services */}
            <div className="space-y-2">
              <Label className="text-muted-foreground">Dependent Services</Label>
              <div className="flex flex-wrap gap-2">
                {secret.dependentServices.map((service) => (
                  <Badge key={service} variant="secondary" className="font-mono">
                    {service}
                  </Badge>
                ))}
              </div>
            </div>
            
            <Separator />
            
            {/* Rotation form */}
            <Form {...form}>
              <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
                <FormField
                  control={form.control}
                  name="newValue"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>New Secret Value</FormLabel>
                      <FormControl>
                        <Input
                          type="password"
                          placeholder="Enter new secret value"
                          className="font-mono"
                          {...field}
                        />
                      </FormControl>
                      <FormDescription>
                        Paste or enter the new secret value
                      </FormDescription>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                
                <FormField
                  control={form.control}
                  name="confirmValue"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Confirm Secret Value</FormLabel>
                      <FormControl>
                        <Input
                          type="password"
                          placeholder="Confirm new secret value"
                          className="font-mono"
                          {...field}
                        />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                
                <FormField
                  control={form.control}
                  name="reason"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Rotation Reason (Optional)</FormLabel>
                      <FormControl>
                        <Input
                          placeholder="e.g., Scheduled rotation, Security incident"
                          {...field}
                        />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                
                {/* Danger zone */}
                <div className="danger-zone mt-6">
                  <div className="flex items-center gap-2 mb-2">
                    <AlertTriangle className="h-4 w-4 text-destructive" />
                    <span className="font-semibold text-destructive">Danger Zone</span>
                  </div>
                  <p className="text-sm text-muted-foreground mb-4">
                    Rotating this secret will immediately invalidate the old value.
                    Ensure all dependent services can handle the change.
                  </p>
                  <Button type="submit" variant="destructive" className="w-full">
                    <RefreshCw className="mr-2 h-4 w-4" />
                    Initiate Rotation
                  </Button>
                </div>
              </form>
            </Form>
          </div>
        </SheetContent>
      </Sheet>
      
      {/* Confirmation dialog */}
      <AlertDialog open={confirmDialog} onOpenChange={setConfirmDialog}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Confirm Secret Rotation</AlertDialogTitle>
            <AlertDialogDescription>
              You are about to rotate the secret <strong>{secret.name}</strong>.
              This will:
              <ul className="list-disc list-inside mt-2 space-y-1">
                <li>Invalidate the current secret immediately</li>
                <li>Update {secret.dependentServices.length} dependent service(s)</li>
                <li>Trigger webhook notifications</li>
              </ul>
              This action cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={loading}>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={executeRotation}
              disabled={loading}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              {loading ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Rotating...
                </>
              ) : (
                'Confirm Rotation'
              )}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  )
}

// Main component
export function EcosystemVault() {
  const [secrets, setSecrets] = React.useState<MaskedSecret[]>([])
  const [loading, setLoading] = React.useState(true)
  const [error, setError] = React.useState<string | null>(null)
  const [revealedSecrets, setRevealedSecrets] = React.useState<Set<string>>(new Set())
  const [categoryFilter, setCategoryFilter] = React.useState<SecretCategory | 'all'>('all')
  
  // Auto-hide revealed secrets after 30 seconds
  React.useEffect(() => {
    if (revealedSecrets.size > 0) {
      const timer = setTimeout(() => {
        setRevealedSecrets(new Set())
      }, 30000)
      return () => clearTimeout(timer)
    }
  }, [revealedSecrets])
  
  // Fetch secrets
  const fetchSecrets = React.useCallback(async () => {
    try {
      setLoading(true)
      setError(null)
      
      // Mock data for demonstration - in production, this would call the admin API
      const mockSecrets: MaskedSecret[] = [
        {
          id: '1',
          name: 'JWT_SECRET',
          maskedValue: 'sk_live_****...****4x2a',
          category: 'authentication',
          status: 'active',
          lastRotated: new Date(Date.now() - 30 * 24 * 60 * 60 * 1000),
          nextRotation: new Date(Date.now() + 60 * 24 * 60 * 60 * 1000),
          dependentServices: ['API Gateway', 'Auth Service'],
          description: 'Main JWT signing secret',
        },
        {
          id: '2',
          name: 'STRIPE_SECRET_KEY',
          maskedValue: 'sk_live_****...****9k3m',
          category: 'payment',
          status: 'active',
          lastRotated: new Date(Date.now() - 15 * 24 * 60 * 60 * 1000),
          nextRotation: new Date(Date.now() + 75 * 24 * 60 * 60 * 1000),
          dependentServices: ['Billing Service', 'Subscription Manager'],
          description: 'Stripe API secret key',
        },
        {
          id: '3',
          name: 'DATABASE_PASSWORD',
          maskedValue: 'pg_****...****xyz1',
          category: 'infrastructure',
          status: 'expired',
          lastRotated: new Date(Date.now() - 120 * 24 * 60 * 60 * 1000),
          nextRotation: new Date(Date.now() - 30 * 24 * 60 * 60 * 1000),
          dependentServices: ['API', 'Worker', 'Scheduler'],
          description: 'PostgreSQL master password',
        },
        {
          id: '4',
          name: 'SENDGRID_API_KEY',
          maskedValue: 'SG.****...****abc2',
          category: 'email',
          status: 'active',
          lastRotated: new Date(Date.now() - 45 * 24 * 60 * 60 * 1000),
          nextRotation: new Date(Date.now() + 45 * 24 * 60 * 60 * 1000),
          dependentServices: ['Email Service', 'Notification Worker'],
          description: 'SendGrid transactional email API key',
        },
        {
          id: '5',
          name: 'CLOUDFLARE_API_TOKEN',
          maskedValue: 'cf_****...****def3',
          category: 'infrastructure',
          status: 'rotating',
          lastRotated: new Date(Date.now() - 1 * 24 * 60 * 60 * 1000),
          nextRotation: new Date(Date.now() + 89 * 24 * 60 * 60 * 1000),
          dependentServices: ['CDN', 'DNS Manager', 'WAF'],
          description: 'Cloudflare API token for DNS and CDN management',
        },
        {
          id: '6',
          name: 'REDIS_PASSWORD',
          maskedValue: 'redis_****...****ghi4',
          category: 'infrastructure',
          status: 'active',
          lastRotated: new Date(Date.now() - 60 * 24 * 60 * 60 * 1000),
          nextRotation: new Date(Date.now() + 30 * 24 * 60 * 60 * 1000),
          dependentServices: ['Cache Layer', 'Session Store', 'Rate Limiter'],
          description: 'Redis cache password',
        },
      ]
      
      setSecrets(mockSecrets)
    } catch (err) {
      console.error('Failed to fetch secrets:', err)
      setError(err instanceof Error ? err.message : 'Failed to load secrets')
    } finally {
      setLoading(false)
    }
  }, [])
  
  React.useEffect(() => {
    fetchSecrets()
  }, [fetchSecrets])
  
  // Handle secret reveal
  const handleReveal = async (secretId: string) => {
    if (revealedSecrets.has(secretId)) {
      // Hide the secret
      const newRevealed = new Set(revealedSecrets)
      newRevealed.delete(secretId)
      setRevealedSecrets(newRevealed)
    } else {
      // In production, this would fetch the actual secret value
      // For now, we'll simulate it
      const secret = secrets.find((s) => s.id === secretId)
      if (secret) {
        // Simulate API call to fetch full value
        const fullValue = `${secret.name}_FULL_VALUE_${Math.random().toString(36).substring(7)}`
        setSecrets((prev) =>
          prev.map((s) =>
            s.id === secretId ? { ...s, fullValue } : s
          )
        )
        setRevealedSecrets((prev) => new Set(prev).add(secretId))
      }
    }
  }
  
  // Handle rotation
  const handleRotate = async (secretId: string, newValue: string, reason?: string) => {
    // In production, this would call the admin API
    console.log('Rotating secret:', secretId, 'Reason:', reason)
    
    // Simulate rotation
    setSecrets((prev) =>
      prev.map((s) =>
        s.id === secretId
          ? {
              ...s,
              status: 'active' as SecretStatus,
              lastRotated: new Date(),
              nextRotation: new Date(Date.now() + 90 * 24 * 60 * 60 * 1000),
              maskedValue: `${s.name.substring(0, 4)}_****...****${newValue.substring(newValue.length - 4)}`,
            }
          : s
      )
    )
  }
  
  // Filter secrets by category
  const filteredSecrets = React.useMemo(() => {
    if (categoryFilter === 'all') return secrets
    return secrets.filter((s) => s.category === categoryFilter)
  }, [secrets, categoryFilter])
  
  // Count by category
  const categoryCounts = React.useMemo(() => {
    const counts: Record<string, number> = { all: secrets.length }
    for (const secret of secrets) {
      counts[secret.category] = (counts[secret.category] || 0) + 1
    }
    return counts
  }, [secrets])
  
  // Count overdue
  const overdueCount = secrets.filter(
    (s) => new Date(s.nextRotation) < new Date() && s.status !== 'revoked'
  ).length
  
  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
        <span className="ml-2 text-muted-foreground">Loading vault...</span>
      </div>
    )
  }
  
  if (error) {
    return (
      <div className="flex flex-col items-center justify-center py-12 text-center">
        <AlertTriangle className="h-12 w-12 text-destructive mb-4" />
        <h3 className="text-lg font-semibold mb-2">Failed to Load Vault</h3>
        <p className="text-muted-foreground mb-4">{error}</p>
        <Button onClick={fetchSecrets} variant="outline">
          <RefreshCw className="mr-2 h-4 w-4" />
          Try Again
        </Button>
      </div>
    )
  }
  
  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold flex items-center gap-2">
            <Key className="h-6 w-6 text-primary" />
            Ecosystem Vault
          </h2>
          <p className="text-muted-foreground">
            Manage platform secrets and API keys
          </p>
        </div>
        <div className="flex items-center gap-2">
          {overdueCount > 0 && (
            <Badge variant="destructive" className="animate-pulse-glow">
              <AlertTriangle className="h-3 w-3 mr-1" />
              {overdueCount} overdue
            </Badge>
          )}
          <Button variant="outline" onClick={fetchSecrets}>
            <RefreshCw className="mr-2 h-4 w-4" />
            Refresh
          </Button>
        </div>
      </div>
      
      {/* Category filters */}
      <div className="flex gap-2">
        <Button
          variant={categoryFilter === 'all' ? 'default' : 'outline'}
          size="sm"
          onClick={() => setCategoryFilter('all')}
        >
          All ({categoryCounts.all})
        </Button>
        {(Object.keys(categoryLabels) as SecretCategory[]).map((category) => (
          <Button
            key={category}
            variant={categoryFilter === category ? 'default' : 'outline'}
            size="sm"
            onClick={() => setCategoryFilter(category)}
          >
            {categoryIcons[category]}
            <span className="ml-1">{categoryLabels[category]}</span>
            <span className="ml-1">({categoryCounts[category] || 0})</span>
          </Button>
        ))}
      </div>
      
      {/* Secrets table */}
      <Card className="border-border">
        <CardContent className="p-0">
          <Table>
            <TableHeader>
              <TableRow className="border-border hover:bg-transparent">
                <TableHead className="w-[200px]">Secret</TableHead>
                <TableHead>Category</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Value</TableHead>
                <TableHead>Last Rotated</TableHead>
                <TableHead>Next Rotation</TableHead>
                <TableHead className="text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {filteredSecrets.map((secret) => {
                const isOverdue = new Date(secret.nextRotation) < new Date() && secret.status !== 'revoked'
                const isRevealed = revealedSecrets.has(secret.id)
                
                return (
                  <TableRow
                    key={secret.id}
                    className={`border-border ${isOverdue ? 'bg-destructive/5' : ''}`}
                  >
                    <TableCell>
                      <div className="flex flex-col">
                        <span className="font-mono font-medium">{secret.name}</span>
                        {secret.description && (
                          <span className="text-xs text-muted-foreground">
                            {secret.description}
                          </span>
                        )}
                      </div>
                    </TableCell>
                    <TableCell>
                      <div className="flex items-center gap-1">
                        {categoryIcons[secret.category]}
                        <span className="text-sm">{categoryLabels[secret.category]}</span>
                      </div>
                    </TableCell>
                    <TableCell>
                      <StatusBadge status={secret.status} />
                    </TableCell>
                    <TableCell>
                      <MaskedValue
                        maskedValue={secret.maskedValue}
                        fullValue={secret.fullValue}
                        onReveal={() => handleReveal(secret.id)}
                        revealed={isRevealed}
                      />
                    </TableCell>
                    <TableCell className="text-sm text-muted-foreground">
                      {new Date(secret.lastRotated).toLocaleDateString()}
                    </TableCell>
                    <TableCell>
                      <div className={`flex items-center gap-1 text-sm ${isOverdue ? 'text-destructive' : 'text-muted-foreground'}`}>
                        {isOverdue && <AlertTriangle className="h-3 w-3" />}
                        {new Date(secret.nextRotation).toLocaleDateString()}
                      </div>
                    </TableCell>
                    <TableCell className="text-right">
                      <RotationSheet secret={secret} onRotate={handleRotate} />
                    </TableCell>
                  </TableRow>
                )
              })}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
      
      {/* Auto-hide notice */}
      {revealedSecrets.size > 0 && (
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <Clock className="h-4 w-4" />
          Revealed secrets will auto-hide in 30 seconds
        </div>
      )}
    </div>
  )
}
