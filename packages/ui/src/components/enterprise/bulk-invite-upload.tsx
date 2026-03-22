import * as React from 'react'
import { Button } from '../button'
import { Badge } from '../badge'
import { cn } from '../../lib/utils'

export interface BulkInvitationCreate {
  organization_id: string
  invitations: Array<{
    email: string
    role?: string
    message?: string
  }>
  default_role?: string
  default_message?: string
  expires_in?: number
}

export interface BulkInvitationResponse {
  success: boolean
  total: number
  successful: number
  failed: number
  results: Array<{
    email: string
    success: boolean
    invitation_id?: string
    error?: string
  }>
}

export interface BulkInviteUploadProps {
  className?: string
  organizationId: string
  onSubmit?: (bulk: BulkInvitationCreate) => Promise<BulkInvitationResponse>
  onSuccess?: (response: BulkInvitationResponse) => void
  onCancel?: () => void
  onError?: (error: Error) => void
  januaClient?: any
  apiUrl?: string
  defaultRole?: string
  defaultExpiresIn?: number
  maxInvitations?: number
}

interface ParsedInvitation {
  email: string
  role?: string
  message?: string
  isValid: boolean
  error?: string
}

export function BulkInviteUpload({
  className,
  organizationId,
  onSubmit,
  onSuccess,
  onCancel,
  onError,
  januaClient,
  apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000',
  defaultRole = 'member',
  defaultExpiresIn = 7,
  maxInvitations = 100,
}: BulkInviteUploadProps) {
  const [file, setFile] = React.useState<File | null>(null)
  const [csvContent, setCsvContent] = React.useState('')
  const [parsedInvitations, setParsedInvitations] = React.useState<ParsedInvitation[]>([])
  const [isProcessing, setIsProcessing] = React.useState(false)
  const [isSubmitting, setIsSubmitting] = React.useState(false)
  const [error, setError] = React.useState<string | null>(null)
  const [result, setResult] = React.useState<BulkInvitationResponse | null>(null)

  // Form settings
  const [bulkRole, setBulkRole] = React.useState(defaultRole)
  const [bulkMessage, setBulkMessage] = React.useState('')
  const [expiresIn, setExpiresIn] = React.useState(defaultExpiresIn)

  // Validate email
  const isValidEmail = (email: string): boolean => {
    return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)
  }

  // Parse CSV content
  const parseCSV = (content: string): ParsedInvitation[] => {
    const lines = content.trim().split('\n')
    if (lines.length === 0) return []

    const invitations: ParsedInvitation[] = []
    const headers = (lines[0] ?? '').toLowerCase().split(',').map(h => h.trim())

    const emailIndex = headers.indexOf('email')
    const roleIndex = headers.indexOf('role')
    const messageIndex = headers.indexOf('message')

    if (emailIndex === -1) {
      throw new Error('CSV must contain an "email" column')
    }

    for (let i = 1; i < lines.length; i++) {
      const line = lines[i]?.trim() ?? ''
      if (!line) continue

      const values = line.split(',').map(v => v.trim().replace(/^["']|["']$/g, ''))
      const email = values[emailIndex]

      if (!email) {
        invitations.push({
          email: '',
          isValid: false,
          error: `Row ${i + 1}: Missing email`,
        })
        continue
      }

      if (!isValidEmail(email)) {
        invitations.push({
          email,
          isValid: false,
          error: `Invalid email format`,
        })
        continue
      }

      invitations.push({
        email,
        role: roleIndex !== -1 ? values[roleIndex] : undefined,
        message: messageIndex !== -1 ? values[messageIndex] : undefined,
        isValid: true,
      })
    }

    return invitations
  }

  // Handle file upload
  const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const uploadedFile = e.target.files?.[0]
    if (!uploadedFile) return

    setFile(uploadedFile)
    setError(null)
    setResult(null)
    setIsProcessing(true)

    const reader = new FileReader()
    reader.onload = (event) => {
      try {
        const content = event.target?.result as string
        setCsvContent(content)

        const parsed = parseCSV(content)

        if (parsed.length > maxInvitations) {
          setError(`Maximum ${maxInvitations} invitations allowed. Found ${parsed.length}.`)
          setParsedInvitations([])
        } else {
          setParsedInvitations(parsed)
        }
      } catch (err) {
        const error = err instanceof Error ? err : new Error('Failed to parse CSV')
        setError(error.message)
        setParsedInvitations([])
      } finally {
        setIsProcessing(false)
      }
    }

    reader.onerror = () => {
      setError('Failed to read file')
      setIsProcessing(false)
    }

    reader.readAsText(uploadedFile)
  }

  // Handle CSV paste
  const handleCSVPaste = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    const content = e.target.value
    setCsvContent(content)
    setError(null)
    setResult(null)

    if (!content.trim()) {
      setParsedInvitations([])
      return
    }

    setIsProcessing(true)
    try {
      const parsed = parseCSV(content)

      if (parsed.length > maxInvitations) {
        setError(`Maximum ${maxInvitations} invitations allowed. Found ${parsed.length}.`)
        setParsedInvitations([])
      } else {
        setParsedInvitations(parsed)
      }
    } catch (err) {
      const error = err instanceof Error ? err : new Error('Failed to parse CSV')
      setError(error.message)
      setParsedInvitations([])
    } finally {
      setIsProcessing(false)
    }
  }

  // Download CSV template
  const downloadTemplate = () => {
    const template = 'email,role,message\nuser@example.com,member,Welcome to our organization!\n'
    const blob = new Blob([template], { type: 'text/csv' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = 'bulk-invite-template.csv'
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
  }

  // Handle submit
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)

    const validInvitations = parsedInvitations.filter(inv => inv.isValid)

    if (validInvitations.length === 0) {
      setError('No valid invitations to send')
      return
    }

    setIsSubmitting(true)

    try {
      const bulkData: BulkInvitationCreate = {
        organization_id: organizationId,
        invitations: validInvitations.map(inv => ({
          email: inv.email,
          role: inv.role || bulkRole,
          message: inv.message || bulkMessage || undefined,
        })),
        default_role: bulkRole,
        default_message: bulkMessage || undefined,
        expires_in: expiresIn,
      }

      let response: BulkInvitationResponse

      if (januaClient) {
        response = await januaClient.invitations.createBulkInvitations(bulkData)
      } else if (onSubmit) {
        response = await onSubmit(bulkData)
      } else {
        const res = await fetch(`${apiUrl}/api/v1/invitations/bulk`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          credentials: 'include',
          body: JSON.stringify(bulkData),
        })

        if (!res.ok) {
          const errorData = await res.json().catch(() => ({}))
          throw new Error(errorData.detail || 'Failed to send bulk invitations')
        }

        response = await res.json()
      }

      setResult(response)
      onSuccess?.(response)
    } catch (err) {
      const error = err instanceof Error ? err : new Error('Failed to send bulk invitations')
      setError(error.message)
      onError?.(error)
    } finally {
      setIsSubmitting(false)
    }
  }

  // Reset form
  const handleReset = () => {
    setFile(null)
    setCsvContent('')
    setParsedInvitations([])
    setError(null)
    setResult(null)
    setBulkRole(defaultRole)
    setBulkMessage('')
    setExpiresIn(defaultExpiresIn)
  }

  const validCount = parsedInvitations.filter(inv => inv.isValid).length
  const invalidCount = parsedInvitations.filter(inv => !inv.isValid).length

  return (
    <div className={cn('space-y-6', className)}>
      {result ? (
        // Success Results
        <div className="space-y-4">
          <div className="p-6 border border-green-200 bg-green-50 dark:bg-green-900/20 rounded-lg space-y-4">
            <div className="flex items-center gap-2 text-green-800 dark:text-green-200">
              <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              <span className="font-semibold text-lg">Bulk Invitations Sent!</span>
            </div>

            <div className="grid grid-cols-3 gap-4 text-center">
              <div>
                <div className="text-2xl font-bold text-gray-900 dark:text-gray-100">
                  {result.total}
                </div>
                <div className="text-sm text-muted-foreground">Total</div>
              </div>
              <div>
                <div className="text-2xl font-bold text-green-600">
                  {result.successful}
                </div>
                <div className="text-sm text-muted-foreground">Successful</div>
              </div>
              <div>
                <div className="text-2xl font-bold text-red-600">
                  {result.failed}
                </div>
                <div className="text-sm text-muted-foreground">Failed</div>
              </div>
            </div>
          </div>

          {/* Detailed Results */}
          {result.failed > 0 && (
            <div className="border rounded-lg overflow-hidden">
              <div className="bg-gray-50 dark:bg-gray-800 px-4 py-2 font-medium text-sm">
                Failed Invitations
              </div>
              <div className="divide-y max-h-60 overflow-y-auto">
                {result.results
                  .filter(r => !r.success)
                  .map((r, i) => (
                    <div key={i} className="px-4 py-2 text-sm">
                      <div className="font-medium">{r.email}</div>
                      <div className="text-red-600 text-xs">{r.error}</div>
                    </div>
                  ))}
              </div>
            </div>
          )}

          <div className="flex gap-2">
            <Button onClick={handleReset} className="flex-1">
              Send More Invitations
            </Button>
            <Button onClick={onCancel} variant="outline" className="flex-1">
              Done
            </Button>
          </div>
        </div>
      ) : (
        // Upload Form
        <form onSubmit={handleSubmit} className="space-y-6">
          {/* Error */}
          {error && (
            <div className="p-4 border border-red-200 bg-red-50 dark:bg-red-900/20 text-red-800 dark:text-red-200 rounded-md text-sm">
              {error}
            </div>
          )}

          {/* Instructions */}
          <div className="p-4 border rounded-lg bg-blue-50 dark:bg-blue-900/20 space-y-2">
            <div className="flex items-center gap-2">
              <svg className="w-5 h-5 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              <span className="font-semibold text-sm">How to Use Bulk Upload</span>
            </div>
            <ul className="text-sm space-y-1 ml-7 text-muted-foreground">
              <li>• Upload a CSV file or paste CSV content below</li>
              <li>• Required column: <code className="bg-white dark:bg-gray-800 px-1 rounded">email</code></li>
              <li>• Optional columns: <code className="bg-white dark:bg-gray-800 px-1 rounded">role</code>, <code className="bg-white dark:bg-gray-800 px-1 rounded">message</code></li>
              <li>• Maximum {maxInvitations} invitations per upload</li>
            </ul>
            <Button type="button" onClick={downloadTemplate} variant="outline" size="sm">
              <svg className="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
              </svg>
              Download Template
            </Button>
          </div>

          {/* File Upload */}
          <div className="space-y-2">
            <label htmlFor="csvFile" className="block text-sm font-medium">
              Upload CSV File
            </label>
            <input
              id="csvFile"
              type="file"
              accept=".csv,text/csv"
              onChange={handleFileUpload}
              className="w-full px-3 py-2 border rounded-md"
            />
            {file && (
              <p className="text-xs text-green-600">
                Loaded: {file.name}
              </p>
            )}
          </div>

          <div className="text-center text-sm text-muted-foreground">OR</div>

          {/* CSV Paste */}
          <div className="space-y-2">
            <label htmlFor="csvContent" className="block text-sm font-medium">
              Paste CSV Content
            </label>
            <textarea
              id="csvContent"
              value={csvContent}
              onChange={handleCSVPaste}
              placeholder="email,role,message&#10;user1@example.com,member,Welcome!&#10;user2@example.com,admin,Join our team"
              rows={6}
              className="w-full px-3 py-2 border rounded-md font-mono text-xs"
            />
          </div>

          {/* Preview */}
          {parsedInvitations.length > 0 && (
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <label className="block text-sm font-medium">Preview</label>
                <div className="flex gap-2">
                  <Badge variant="default">{validCount} valid</Badge>
                  {invalidCount > 0 && <Badge variant="destructive">{invalidCount} invalid</Badge>}
                </div>
              </div>

              <div className="border rounded-lg overflow-hidden">
                <div className="max-h-40 overflow-y-auto">
                  <table className="w-full text-sm">
                    <thead className="bg-gray-50 dark:bg-gray-800 sticky top-0">
                      <tr>
                        <th className="px-3 py-2 text-left">Email</th>
                        <th className="px-3 py-2 text-left">Role</th>
                        <th className="px-3 py-2 text-left">Status</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y">
                      {parsedInvitations.map((inv, i) => (
                        <tr key={i} className={inv.isValid ? '' : 'bg-red-50 dark:bg-red-900/10'}>
                          <td className="px-3 py-2">{inv.email || '(empty)'}</td>
                          <td className="px-3 py-2 capitalize">{inv.role || bulkRole}</td>
                          <td className="px-3 py-2">
                            {inv.isValid ? (
                              <Badge variant="default" className="text-xs">Valid</Badge>
                            ) : (
                              <Badge variant="destructive" className="text-xs">{inv.error}</Badge>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          )}

          {/* Bulk Settings */}
          {validCount > 0 && (
            <div className="space-y-4 p-4 border rounded-lg">
              <h4 className="font-semibold">Bulk Settings</h4>

              <div className="space-y-2">
                <label htmlFor="bulkRole" className="block text-sm font-medium">
                  Default Role (for entries without role)
                </label>
                <select
                  id="bulkRole"
                  value={bulkRole}
                  onChange={(e) => setBulkRole(e.target.value)}
                  className="w-full px-3 py-2 border rounded-md"
                >
                  <option value="viewer">Viewer</option>
                  <option value="member">Member</option>
                  <option value="admin">Admin</option>
                  <option value="owner">Owner</option>
                </select>
              </div>

              <div className="space-y-2">
                <label htmlFor="bulkMessage" className="block text-sm font-medium">
                  Default Message <span className="text-muted-foreground text-xs">(Optional)</span>
                </label>
                <textarea
                  id="bulkMessage"
                  value={bulkMessage}
                  onChange={(e) => setBulkMessage(e.target.value)}
                  placeholder="Welcome message for all invitations..."
                  rows={2}
                  maxLength={500}
                  className="w-full px-3 py-2 border rounded-md"
                />
              </div>

              <div className="space-y-2">
                <label htmlFor="expiresIn" className="block text-sm font-medium">
                  Invitations Expire In
                </label>
                <select
                  id="expiresIn"
                  value={expiresIn}
                  onChange={(e) => setExpiresIn(Number(e.target.value))}
                  className="w-full px-3 py-2 border rounded-md"
                >
                  <option value="1">1 day</option>
                  <option value="3">3 days</option>
                  <option value="7">7 days (1 week)</option>
                  <option value="14">14 days (2 weeks)</option>
                  <option value="30">30 days (1 month)</option>
                </select>
              </div>
            </div>
          )}

          {/* Actions */}
          <div className="flex gap-3">
            <Button
              type="submit"
              disabled={isSubmitting || isProcessing || validCount === 0}
              className="flex-1"
            >
              {isSubmitting ? (
                <>
                  <svg className="animate-spin -ml-1 mr-2 h-4 w-4" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                  </svg>
                  Sending {validCount} invitation{validCount !== 1 ? 's' : ''}...
                </>
              ) : (
                `Send ${validCount} Invitation${validCount !== 1 ? 's' : ''}`
              )}
            </Button>
            {onCancel && (
              <Button type="button" variant="outline" onClick={onCancel}>
                Cancel
              </Button>
            )}
          </div>
        </form>
      )}
    </div>
  )
}
