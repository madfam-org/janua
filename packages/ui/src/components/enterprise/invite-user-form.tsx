import * as React from 'react'
import { Button } from '../button'
import { cn } from '../../lib/utils'

export interface InvitationCreate {
  organization_id: string
  email: string
  role?: string
  message?: string
  expires_in?: number
}

export interface Invitation {
  id: string
  organization_id: string
  email: string
  role: string
  status: 'pending' | 'accepted' | 'expired' | 'revoked'
  invited_by: string
  message?: string
  expires_at: string
  created_at: string
  invite_url: string
  email_sent: boolean
}

export interface InviteUserFormProps {
  className?: string
  organizationId: string
  onSubmit?: (invitation: InvitationCreate) => Promise<Invitation>
  onSuccess?: (invitation: Invitation) => void
  onCancel?: () => void
  onError?: (error: Error) => void
  plintoClient?: any
  apiUrl?: string
  defaultRole?: string
  defaultExpiresIn?: number
}

export function InviteUserForm({
  className,
  organizationId,
  onSubmit,
  onSuccess,
  onCancel,
  onError,
  plintoClient,
  apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000',
  defaultRole = 'member',
  defaultExpiresIn = 7,
}: InviteUserFormProps) {
  const [email, setEmail] = React.useState('')
  const [role, setRole] = React.useState(defaultRole)
  const [message, setMessage] = React.useState('')
  const [expiresIn, setExpiresIn] = React.useState(defaultExpiresIn)
  const [isSubmitting, setIsSubmitting] = React.useState(false)
  const [error, setError] = React.useState<string | null>(null)
  const [success, setSuccess] = React.useState(false)
  const [createdInvitation, setCreatedInvitation] = React.useState<Invitation | null>(null)

  // Validate email
  const isValidEmail = (email: string) => {
    return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)
  }

  // Handle submit
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()

    // Validation
    if (!email || !isValidEmail(email)) {
      setError('Please enter a valid email address')
      return
    }

    if (message.length > 500) {
      setError('Message must be 500 characters or less')
      return
    }

    setIsSubmitting(true)
    setError(null)
    setSuccess(false)

    try {
      const invitationData: InvitationCreate = {
        organization_id: organizationId,
        email: email.trim(),
        role,
        message: message.trim() || undefined,
        expires_in: expiresIn,
      }

      let invitation: Invitation

      if (plintoClient) {
        invitation = await plintoClient.invitations.createInvitation(invitationData)
      } else if (onSubmit) {
        invitation = await onSubmit(invitationData)
      } else {
        const res = await fetch(`${apiUrl}/api/v1/invitations`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          credentials: 'include',
          body: JSON.stringify(invitationData),
        })

        if (!res.ok) {
          const errorData = await res.json().catch(() => ({}))
          throw new Error(errorData.detail || 'Failed to create invitation')
        }

        invitation = await res.json()
      }

      setCreatedInvitation(invitation)
      setSuccess(true)
      onSuccess?.(invitation)

      // Reset form
      setEmail('')
      setMessage('')
      setRole(defaultRole)
      setExpiresIn(defaultExpiresIn)
    } catch (err) {
      const error = err instanceof Error ? err : new Error('Failed to create invitation')
      setError(error.message)
      onError?.(error)
    } finally {
      setIsSubmitting(false)
    }
  }

  // Copy invite URL
  const copyInviteUrl = () => {
    if (createdInvitation) {
      navigator.clipboard.writeText(createdInvitation.invite_url)
    }
  }

  // Handle cancel
  const handleCancel = () => {
    setEmail('')
    setMessage('')
    setRole(defaultRole)
    setExpiresIn(defaultExpiresIn)
    setError(null)
    setSuccess(false)
    setCreatedInvitation(null)
    onCancel?.()
  }

  return (
    <div className={cn('space-y-4', className)}>
      {success && createdInvitation ? (
        // Success state
        <div className="p-6 border border-green-200 bg-green-50 dark:bg-green-900/20 rounded-lg space-y-4">
          <div className="flex items-center gap-2 text-green-800 dark:text-green-200">
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <span className="font-semibold">Invitation sent successfully!</span>
          </div>

          <div className="space-y-2">
            <div className="text-sm">
              <span className="font-medium">Email:</span> {createdInvitation.email}
            </div>
            <div className="text-sm">
              <span className="font-medium">Role:</span>{' '}
              <span className="capitalize">{createdInvitation.role}</span>
            </div>
            <div className="text-sm">
              <span className="font-medium">Expires:</span>{' '}
              {new Date(createdInvitation.expires_at).toLocaleDateString()}
            </div>
          </div>

          <div className="space-y-2">
            <label className="text-sm font-medium">Invitation URL</label>
            <div className="flex gap-2">
              <input
                type="text"
                value={createdInvitation.invite_url}
                readOnly
                className="flex-1 px-3 py-2 border rounded-md bg-white dark:bg-gray-800 text-sm"
              />
              <Button onClick={copyInviteUrl} variant="outline">
                Copy
              </Button>
            </div>
          </div>

          <div className="flex gap-2">
            <Button onClick={() => setSuccess(false)} className="flex-1">
              Send Another
            </Button>
            <Button onClick={handleCancel} variant="outline" className="flex-1">
              Done
            </Button>
          </div>
        </div>
      ) : (
        // Form
        <form onSubmit={handleSubmit} className="space-y-4">
          {/* Error */}
          {error && (
            <div className="p-4 border border-red-200 bg-red-50 dark:bg-red-900/20 text-red-800 dark:text-red-200 rounded-md text-sm">
              {error}
            </div>
          )}

          {/* Email */}
          <div className="space-y-2">
            <label htmlFor="email" className="block text-sm font-medium">
              Email Address <span className="text-red-500">*</span>
            </label>
            <input
              id="email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="user@example.com"
              required
              className="w-full px-3 py-2 border rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>

          {/* Role */}
          <div className="space-y-2">
            <label htmlFor="role" className="block text-sm font-medium">
              Role <span className="text-red-500">*</span>
            </label>
            <select
              id="role"
              value={role}
              onChange={(e) => setRole(e.target.value)}
              className="w-full px-3 py-2 border rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="viewer">Viewer - Can view only</option>
              <option value="member">Member - Can view and edit</option>
              <option value="admin">Admin - Full access except billing</option>
              <option value="owner">Owner - Full access including billing</option>
            </select>
            <p className="text-xs text-muted-foreground">
              {role === 'viewer' && 'Read-only access to organization resources'}
              {role === 'member' && 'Can create, edit, and delete resources'}
              {role === 'admin' && 'Can manage members and organization settings'}
              {role === 'owner' && 'Full administrative access including billing'}
            </p>
          </div>

          {/* Message */}
          <div className="space-y-2">
            <label htmlFor="message" className="block text-sm font-medium">
              Personal Message <span className="text-muted-foreground text-xs">(Optional)</span>
            </label>
            <textarea
              id="message"
              value={message}
              onChange={(e) => setMessage(e.target.value)}
              placeholder="Add a personal message to the invitation email..."
              rows={3}
              maxLength={500}
              className="w-full px-3 py-2 border rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none"
            />
            <p className="text-xs text-muted-foreground text-right">
              {message.length}/500 characters
            </p>
          </div>

          {/* Expiration */}
          <div className="space-y-2">
            <label htmlFor="expiresIn" className="block text-sm font-medium">
              Invitation Expires In
            </label>
            <select
              id="expiresIn"
              value={expiresIn}
              onChange={(e) => setExpiresIn(Number(e.target.value))}
              className="w-full px-3 py-2 border rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="1">1 day</option>
              <option value="3">3 days</option>
              <option value="7">7 days (1 week)</option>
              <option value="14">14 days (2 weeks)</option>
              <option value="30">30 days (1 month)</option>
            </select>
          </div>

          {/* Preview */}
          <div className="p-4 bg-gray-50 dark:bg-gray-800 border rounded-md space-y-2">
            <h4 className="text-sm font-medium">Invitation Preview</h4>
            <div className="text-sm space-y-1">
              <div>
                <span className="font-medium">To:</span> {email || '(not set)'}
              </div>
              <div>
                <span className="font-medium">Role:</span>{' '}
                <span className="capitalize">{role}</span>
              </div>
              <div>
                <span className="font-medium">Valid for:</span> {expiresIn} day{expiresIn !== 1 ? 's' : ''}
              </div>
              {message && (
                <div>
                  <span className="font-medium">Message:</span>
                  <div className="mt-1 text-muted-foreground italic">"{message}"</div>
                </div>
              )}
            </div>
          </div>

          {/* Actions */}
          <div className="flex gap-3">
            <Button
              type="submit"
              disabled={isSubmitting || !email}
              className="flex-1"
            >
              {isSubmitting ? (
                <>
                  <svg className="animate-spin -ml-1 mr-2 h-4 w-4" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                  </svg>
                  Sending...
                </>
              ) : (
                'Send Invitation'
              )}
            </Button>
            {onCancel && (
              <Button type="button" variant="outline" onClick={handleCancel}>
                Cancel
              </Button>
            )}
          </div>
        </form>
      )}
    </div>
  )
}
