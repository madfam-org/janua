import * as React from 'react'
import { Button } from '../button'
import { Input } from '../input'
import { Label } from '../label'
import { Card } from '../card'
import { Badge } from '../badge'
import { Tabs, TabsList, TabsTrigger, TabsContent } from '../tabs'
import { Avatar, AvatarImage, AvatarFallback } from '../avatar'
import { cn } from '../../lib/utils'

export interface UserProfileProps {
  /** Optional custom class name */
  className?: string
  /** User data */
  user: {
    id: string
    email: string
    firstName?: string
    lastName?: string
    username?: string
    avatarUrl?: string
    phone?: string
    emailVerified?: boolean
    phoneVerified?: boolean
    twoFactorEnabled?: boolean
    createdAt?: Date
  }
  /** Callback to update profile */
  onUpdateProfile?: (data: {
    firstName?: string
    lastName?: string
    username?: string
    phone?: string
  }) => Promise<void>
  /** Callback to upload avatar */
  onUploadAvatar?: (file: File) => Promise<string>
  /** Callback to update email */
  onUpdateEmail?: (email: string) => Promise<void>
  /** Callback to update password */
  onUpdatePassword?: (currentPassword: string, newPassword: string) => Promise<void>
  /** Callback to enable/disable MFA */
  onToggleMFA?: (enabled: boolean) => Promise<void>
  /** Callback to delete account */
  onDeleteAccount?: () => Promise<void>
  /** Callback on error */
  onError?: (error: Error) => void
  /** Show security tab */
  showSecurityTab?: boolean
  /** Show danger zone */
  showDangerZone?: boolean
}

export function UserProfile({
  className,
  user,
  onUpdateProfile,
  onUploadAvatar,
  onUpdateEmail,
  onUpdatePassword,
  onToggleMFA,
  onDeleteAccount,
  onError,
  showSecurityTab = true,
  showDangerZone = true,
}: UserProfileProps) {
  const [activeTab, setActiveTab] = React.useState<'profile' | 'security' | 'account'>('profile')
  const [isLoading, setIsLoading] = React.useState(false)
  const [error, setError] = React.useState<string | null>(null)

  // Profile form state
  const [firstName, setFirstName] = React.useState(user.firstName || '')
  const [lastName, setLastName] = React.useState(user.lastName || '')
  const [username, setUsername] = React.useState(user.username || '')
  const [phone, setPhone] = React.useState(user.phone || '')
  const [isSavingProfile, setIsSavingProfile] = React.useState(false)

  // Email update state
  const [newEmail, setNewEmail] = React.useState('')
  const [isUpdatingEmail, setIsUpdatingEmail] = React.useState(false)

  // Password update state
  const [currentPassword, setCurrentPassword] = React.useState('')
  const [newPassword, setNewPassword] = React.useState('')
  const [confirmPassword, setConfirmPassword] = React.useState('')
  const [isUpdatingPassword, setIsUpdatingPassword] = React.useState(false)

  // Delete account state
  const [deleteConfirmation, setDeleteConfirmation] = React.useState('')
  const [isDeleting, setIsDeleting] = React.useState(false)

  const handleSaveProfile = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!onUpdateProfile) return

    setIsSavingProfile(true)
    setError(null)

    try {
      await onUpdateProfile({
        firstName,
        lastName,
        username,
        phone,
      })
    } catch (err) {
      const error = err instanceof Error ? err : new Error('Failed to update profile')
      setError(error.message)
      onError?.(error)
    } finally {
      setIsSavingProfile(false)
    }
  }

  const handleAvatarUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file || !onUploadAvatar) return

    setIsLoading(true)
    setError(null)

    try {
      await onUploadAvatar(file)
    } catch (err) {
      const error = err instanceof Error ? err : new Error('Failed to upload avatar')
      setError(error.message)
      onError?.(error)
    } finally {
      setIsLoading(false)
    }
  }

  const handleUpdateEmail = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!onUpdateEmail || !newEmail) return

    setIsUpdatingEmail(true)
    setError(null)

    try {
      await onUpdateEmail(newEmail)
      setNewEmail('')
    } catch (err) {
      const error = err instanceof Error ? err : new Error('Failed to update email')
      setError(error.message)
      onError?.(error)
    } finally {
      setIsUpdatingEmail(false)
    }
  }

  const handleUpdatePassword = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!onUpdatePassword) return

    if (newPassword !== confirmPassword) {
      setError('Passwords do not match')
      return
    }

    if (newPassword.length < 8) {
      setError('Password must be at least 8 characters')
      return
    }

    setIsUpdatingPassword(true)
    setError(null)

    try {
      await onUpdatePassword(currentPassword, newPassword)
      setCurrentPassword('')
      setNewPassword('')
      setConfirmPassword('')
    } catch (err) {
      const error = err instanceof Error ? err : new Error('Failed to update password')
      setError(error.message)
      onError?.(error)
    } finally {
      setIsUpdatingPassword(false)
    }
  }

  const handleToggleMFA = async () => {
    if (!onToggleMFA) return

    setIsLoading(true)
    setError(null)

    try {
      await onToggleMFA(!user.twoFactorEnabled)
    } catch (err) {
      const error = err instanceof Error ? err : new Error('Failed to toggle MFA')
      setError(error.message)
      onError?.(error)
    } finally {
      setIsLoading(false)
    }
  }

  const handleDeleteAccount = async () => {
    if (!onDeleteAccount || deleteConfirmation !== 'DELETE') return

    setIsDeleting(true)
    setError(null)

    try {
      await onDeleteAccount()
    } catch (err) {
      const error = err instanceof Error ? err : new Error('Failed to delete account')
      setError(error.message)
      onError?.(error)
    } finally {
      setIsDeleting(false)
    }
  }

  const getUserInitials = () => {
    if (user.firstName && user.lastName) {
      return `${user.firstName[0]}${user.lastName[0]}`.toUpperCase()
    }
    return user.email.slice(0, 2).toUpperCase()
  }

  return (
    <Card className={cn('w-full max-w-4xl mx-auto p-6', className)}>
      {/* Header */}
      <div className="mb-6">
        <h2 className="text-2xl font-bold">Profile settings</h2>
        <p className="text-sm text-muted-foreground mt-1">
          Manage your personal information and account settings
        </p>
      </div>

      {/* Error Message */}
      {error && (
        <div className="bg-destructive/15 text-destructive text-sm p-3 rounded-md mb-6">
          {error}
        </div>
      )}

      {/* Tabs */}
      <Tabs value={activeTab} onValueChange={(v) => setActiveTab(v as any)}>
        <TabsList className="mb-6">
          <TabsTrigger value="profile">Profile</TabsTrigger>
          {showSecurityTab && <TabsTrigger value="security">Security</TabsTrigger>}
          <TabsTrigger value="account">Account</TabsTrigger>
        </TabsList>

        {/* Profile Tab */}
        <TabsContent value="profile">
          <form onSubmit={handleSaveProfile} className="space-y-6">
            {/* Avatar */}
            <div>
              <Label>Profile photo</Label>
              <div className="flex items-center gap-4 mt-2">
                <Avatar className="w-20 h-20">
                  <AvatarImage src={user.avatarUrl} alt={user.firstName || user.email} />
                  <AvatarFallback>{getUserInitials()}</AvatarFallback>
                </Avatar>
                {onUploadAvatar && (
                  <div>
                    <input
                      type="file"
                      id="avatar-upload"
                      accept="image/*"
                      onChange={handleAvatarUpload}
                      className="hidden"
                    />
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      onClick={() => document.getElementById('avatar-upload')?.click()}
                      disabled={isLoading}
                    >
                      Change photo
                    </Button>
                    <p className="text-xs text-muted-foreground mt-1">
                      PNG, JPG up to 2MB
                    </p>
                  </div>
                )}
              </div>
            </div>

            {/* Name */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="firstName">First name</Label>
                <Input
                  id="firstName"
                  value={firstName}
                  onChange={(e) => setFirstName(e.target.value)}
                  disabled={isSavingProfile}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="lastName">Last name</Label>
                <Input
                  id="lastName"
                  value={lastName}
                  onChange={(e) => setLastName(e.target.value)}
                  disabled={isSavingProfile}
                />
              </div>
            </div>

            {/* Username */}
            <div className="space-y-2">
              <Label htmlFor="username">Username (optional)</Label>
              <Input
                id="username"
                value={username}
                onChange={(e) => setUsername(e.target.value.toLowerCase().replace(/[^a-z0-9_]/g, ''))}
                disabled={isSavingProfile}
                pattern="[a-z0-9_]+"
                placeholder="username"
              />
              <p className="text-xs text-muted-foreground">
                Lowercase letters, numbers, and underscores only
              </p>
            </div>

            {/* Phone */}
            <div className="space-y-2">
              <Label htmlFor="phone">Phone number (optional)</Label>
              <Input
                id="phone"
                type="tel"
                value={phone}
                onChange={(e) => setPhone(e.target.value)}
                disabled={isSavingProfile}
                placeholder="+1 (555) 123-4567"
              />
            </div>

            {onUpdateProfile && (
              <Button type="submit" disabled={isSavingProfile}>
                {isSavingProfile ? 'Saving...' : 'Save changes'}
              </Button>
            )}
          </form>
        </TabsContent>

        {/* Security Tab */}
        {showSecurityTab && (
          <TabsContent value="security">
            <div className="space-y-6">
              {/* Email */}
              <div className="pb-6 border-b">
                <h3 className="font-medium mb-2">Email address</h3>
                <div className="flex items-center gap-2 mb-4">
                  <p className="text-sm text-muted-foreground">{user.email}</p>
                  {user.emailVerified ? (
                    <Badge variant="default" className="text-xs">Verified</Badge>
                  ) : (
                    <Badge variant="secondary" className="text-xs">Unverified</Badge>
                  )}
                </div>
                {onUpdateEmail && (
                  <form onSubmit={handleUpdateEmail} className="flex gap-2">
                    <Input
                      type="email"
                      placeholder="New email address"
                      value={newEmail}
                      onChange={(e) => setNewEmail(e.target.value)}
                      disabled={isUpdatingEmail}
                      required
                    />
                    <Button type="submit" disabled={isUpdatingEmail || !newEmail}>
                      {isUpdatingEmail ? 'Updating...' : 'Update email'}
                    </Button>
                  </form>
                )}
              </div>

              {/* Password */}
              {onUpdatePassword && (
                <div className="pb-6 border-b">
                  <h3 className="font-medium mb-4">Change password</h3>
                  <form onSubmit={handleUpdatePassword} className="space-y-4">
                    <div className="space-y-2">
                      <Label htmlFor="currentPassword">Current password</Label>
                      <Input
                        id="currentPassword"
                        type="password"
                        value={currentPassword}
                        onChange={(e) => setCurrentPassword(e.target.value)}
                        disabled={isUpdatingPassword}
                        required
                      />
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="newPassword">New password</Label>
                      <Input
                        id="newPassword"
                        type="password"
                        value={newPassword}
                        onChange={(e) => setNewPassword(e.target.value)}
                        disabled={isUpdatingPassword}
                        required
                        minLength={8}
                      />
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="confirmPassword">Confirm new password</Label>
                      <Input
                        id="confirmPassword"
                        type="password"
                        value={confirmPassword}
                        onChange={(e) => setConfirmPassword(e.target.value)}
                        disabled={isUpdatingPassword}
                        required
                        minLength={8}
                      />
                    </div>
                    <Button type="submit" disabled={isUpdatingPassword}>
                      {isUpdatingPassword ? 'Updating...' : 'Update password'}
                    </Button>
                  </form>
                </div>
              )}

              {/* Two-Factor Authentication */}
              {onToggleMFA && (
                <div>
                  <h3 className="font-medium mb-2">Two-factor authentication</h3>
                  <div className="flex items-center justify-between py-3">
                    <div>
                      <p className="text-sm font-medium">
                        {user.twoFactorEnabled ? 'Enabled' : 'Disabled'}
                      </p>
                      <p className="text-sm text-muted-foreground">
                        {user.twoFactorEnabled
                          ? 'Your account is protected with 2FA'
                          : 'Add an extra layer of security to your account'}
                      </p>
                    </div>
                    <Button
                      variant={user.twoFactorEnabled ? 'outline' : 'default'}
                      onClick={handleToggleMFA}
                      disabled={isLoading}
                    >
                      {user.twoFactorEnabled ? 'Disable' : 'Enable'}
                    </Button>
                  </div>
                </div>
              )}
            </div>
          </TabsContent>
        )}

        {/* Account Tab */}
        <TabsContent value="account">
          <div className="space-y-6">
            {/* Account Information */}
            <div className="pb-6 border-b">
              <h3 className="font-medium mb-4">Account information</h3>
              <dl className="space-y-2">
                <div className="flex justify-between text-sm">
                  <dt className="text-muted-foreground">Account ID</dt>
                  <dd className="font-mono">{user.id}</dd>
                </div>
                {user.createdAt && (
                  <div className="flex justify-between text-sm">
                    <dt className="text-muted-foreground">Member since</dt>
                    <dd>{new Date(user.createdAt).toLocaleDateString()}</dd>
                  </div>
                )}
                <div className="flex justify-between text-sm">
                  <dt className="text-muted-foreground">Email status</dt>
                  <dd>
                    {user.emailVerified ? (
                      <Badge variant="default" className="text-xs">Verified</Badge>
                    ) : (
                      <Badge variant="secondary" className="text-xs">Unverified</Badge>
                    )}
                  </dd>
                </div>
                {user.phone && (
                  <div className="flex justify-between text-sm">
                    <dt className="text-muted-foreground">Phone status</dt>
                    <dd>
                      {user.phoneVerified ? (
                        <Badge variant="default" className="text-xs">Verified</Badge>
                      ) : (
                        <Badge variant="secondary" className="text-xs">Unverified</Badge>
                      )}
                    </dd>
                  </div>
                )}
              </dl>
            </div>

            {/* Delete Account */}
            {showDangerZone && onDeleteAccount && (
              <div className="border border-destructive rounded-lg p-6">
                <h3 className="text-lg font-semibold text-destructive mb-2">
                  Delete account
                </h3>
                <p className="text-sm text-muted-foreground mb-4">
                  Once you delete your account, there is no going back. This will permanently
                  delete your account and all associated data.
                </p>

                <div className="space-y-4">
                  <div>
                    <Label htmlFor="delete-confirm">
                      Type <code className="text-sm bg-muted px-1 py-0.5 rounded">DELETE</code> to confirm
                    </Label>
                    <Input
                      id="delete-confirm"
                      value={deleteConfirmation}
                      onChange={(e) => setDeleteConfirmation(e.target.value)}
                      disabled={isDeleting}
                      placeholder="DELETE"
                    />
                  </div>

                  <Button
                    variant="destructive"
                    onClick={handleDeleteAccount}
                    disabled={deleteConfirmation !== 'DELETE' || isDeleting}
                  >
                    {isDeleting ? 'Deleting...' : 'Delete account'}
                  </Button>
                </div>
              </div>
            )}
          </div>
        </TabsContent>
      </Tabs>
    </Card>
  )
}
