/**
 * Members tab for organization profile
 */

import * as React from 'react'
import { Button } from '../../button'
import { Input } from '../../input'
import { Badge } from '../../badge'
import type { OrganizationMember } from './types'

export interface MembersTabProps {
  members: OrganizationMember[] | undefined
  isLoading: boolean
  canManageMembers: boolean
  onInviteMember?: (email: string, role: 'admin' | 'member') => Promise<void>
  onUpdateMemberRole?: (memberId: string, role: 'admin' | 'member') => Promise<void>
  onRemoveMember?: (memberId: string) => Promise<void>
  onMembersChange?: (members: OrganizationMember[]) => void
  onError?: (error: Error) => void
}

export function MembersTab({
  members,
  isLoading,
  canManageMembers,
  onInviteMember,
  onUpdateMemberRole,
  onRemoveMember,
  onMembersChange,
  onError,
}: MembersTabProps) {
  const [inviteEmail, setInviteEmail] = React.useState('')
  const [inviteRole, setInviteRole] = React.useState<'admin' | 'member'>('member')
  const [isInviting, setIsInviting] = React.useState(false)
  const [error, setError] = React.useState<string | null>(null)

  const getMemberInitials = (member: OrganizationMember) => {
    if (member.name) {
      return member.name
        .split(' ')
        .map((word) => word[0])
        .join('')
        .toUpperCase()
        .slice(0, 2)
    }
    return member.email.slice(0, 2).toUpperCase()
  }

  const handleInvite = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!inviteEmail || !onInviteMember) return

    setIsInviting(true)
    setError(null)

    try {
      await onInviteMember(inviteEmail, inviteRole)
      setInviteEmail('')
      setInviteRole('member')
    } catch (err) {
      const error = err instanceof Error ? err : new Error('Failed to invite member')
      setError(error.message)
      onError?.(error)
    } finally {
      setIsInviting(false)
    }
  }

  const handleUpdateRole = async (memberId: string, role: 'admin' | 'member') => {
    if (!onUpdateMemberRole) return

    try {
      await onUpdateMemberRole(memberId, role)
      // Update local state
      if (members && onMembersChange) {
        onMembersChange(members.map((m) => (m.id === memberId ? { ...m, role } : m)))
      }
    } catch (err) {
      const error = err instanceof Error ? err : new Error('Failed to update member role')
      setError(error.message)
      onError?.(error)
    }
  }

  const handleRemove = async (memberId: string) => {
    if (!onRemoveMember) return

    try {
      await onRemoveMember(memberId)
      // Update local state
      if (members && onMembersChange) {
        onMembersChange(members.filter((m) => m.id !== memberId))
      }
    } catch (err) {
      const error = err instanceof Error ? err : new Error('Failed to remove member')
      setError(error.message)
      onError?.(error)
    }
  }

  return (
    <div className="space-y-6">
      {error && (
        <div className="bg-destructive/15 text-destructive text-sm p-3 rounded-md">
          {error}
        </div>
      )}

      {/* Invite Member */}
      {canManageMembers && onInviteMember && (
        <form onSubmit={handleInvite} className="space-y-4 pb-6 border-b">
          <h3 className="font-medium">Invite member</h3>
          <div className="flex gap-3">
            <Input
              type="email"
              placeholder="email@example.com"
              value={inviteEmail}
              onChange={(e) => setInviteEmail(e.target.value)}
              disabled={isInviting}
              required
              className="flex-1"
            />
            <select
              value={inviteRole}
              onChange={(e) => setInviteRole(e.target.value as 'admin' | 'member')}
              disabled={isInviting}
              className="px-3 py-2 border rounded-md"
            >
              <option value="member">Member</option>
              <option value="admin">Admin</option>
            </select>
            <Button type="submit" disabled={isInviting || !inviteEmail}>
              {isInviting ? 'Inviting...' : 'Invite'}
            </Button>
          </div>
        </form>
      )}

      {/* Members List */}
      <div>
        <h3 className="font-medium mb-4">
          Members ({members?.length || 0})
        </h3>

        {isLoading ? (
          <div className="flex items-center justify-center py-8">
            <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-primary"></div>
          </div>
        ) : members && members.length > 0 ? (
          <div className="space-y-3">
            {members.map((member) => (
              <div
                key={member.id}
                className="flex items-center justify-between py-3 px-4 border rounded-lg"
              >
                <div className="flex items-center gap-3 flex-1 min-w-0">
                  <div className="w-10 h-10 rounded-full bg-primary/10 flex items-center justify-center overflow-hidden shrink-0">
                    {member.avatarUrl ? (
                      <img
                        src={member.avatarUrl}
                        alt={member.name || member.email}
                        className="w-full h-full object-cover"
                      />
                    ) : (
                      <span className="text-sm font-semibold text-primary">
                        {getMemberInitials(member)}
                      </span>
                    )}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-medium truncate">
                        {member.name || member.email}
                      </span>
                      <Badge
                        variant={member.role === 'owner' ? 'default' : 'secondary'}
                        className="text-xs capitalize shrink-0"
                      >
                        {member.role}
                      </Badge>
                      {member.status === 'invited' && (
                        <Badge variant="outline" className="text-xs shrink-0">
                          Invited
                        </Badge>
                      )}
                    </div>
                    <p className="text-xs text-muted-foreground truncate">
                      {member.email}
                    </p>
                  </div>
                </div>

                {canManageMembers && member.role !== 'owner' && (
                  <div className="flex items-center gap-2 shrink-0">
                    {onUpdateMemberRole && (
                      <select
                        value={member.role}
                        onChange={(e) => handleUpdateRole(member.id, e.target.value as 'admin' | 'member')}
                        className="text-sm px-2 py-1 border rounded"
                      >
                        <option value="member">Member</option>
                        <option value="admin">Admin</option>
                      </select>
                    )}
                    {onRemoveMember && (
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => handleRemove(member.id)}
                      >
                        Remove
                      </Button>
                    )}
                  </div>
                )}
              </div>
            ))}
          </div>
        ) : (
          <p className="text-sm text-muted-foreground text-center py-8">
            No members yet
          </p>
        )}
      </div>
    </div>
  )
}
