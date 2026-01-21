'use client'

import { useState, useEffect } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@janua/ui'
import { Button } from '@janua/ui'
import { Input } from '@janua/ui'
import { Label } from '@janua/ui'
import { Avatar, AvatarFallback, AvatarImage } from '@janua/ui'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@janua/ui'
import { Badge } from '@janua/ui'
import { Separator } from '@janua/ui'
import {
  User,
  Mail,
  Shield,
  Key,
  Trash2,
  Edit3,
  Calendar,
  Activity,
  Monitor,
  Smartphone,
  MapPin,
  Loader2,
  AlertCircle,
  RefreshCw
} from 'lucide-react'
import { apiCall } from '../../lib/auth'

// API base URL for production
const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'https://api.janua.dev'

interface UserProfile {
  id: string
  email: string
  name: string | null
  avatar_url: string | null
  email_verified: boolean
  created_at: string
  updated_at: string
  last_login_at: string | null
  is_active: boolean
}

interface UserSession {
  id: string
  device_name: string | null
  device_type: string | null
  browser: string | null
  os: string | null
  ip_address: string | null
  user_agent: string | null
  created_at: string
  last_activity_at: string
  expires_at: string
  is_current: boolean
  revoked: boolean
}

interface SessionsResponse {
  sessions: UserSession[]
  total: number
}

export default function ProfilePage() {
  const [profile, setProfile] = useState<UserProfile | null>(null)
  const [sessions, setSessions] = useState<UserSession[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [updating, setUpdating] = useState(false)
  const [editMode, setEditMode] = useState(false)
  const [formData, setFormData] = useState({ name: '', avatar_url: '' })
  const [passwordData, setPasswordData] = useState({
    current_password: '',
    new_password: '',
    confirm_password: ''
  })

  useEffect(() => {
    fetchProfileData()
  }, [])

  const fetchProfileData = async () => {
    try {
      setLoading(true)
      setError(null)

      // Fetch profile and sessions in parallel
      const [profileResponse, sessionsResponse] = await Promise.all([
        apiCall(`${API_BASE_URL}/api/v1/auth/me`),
        apiCall(`${API_BASE_URL}/api/v1/sessions/`)
      ])

      if (!profileResponse.ok) {
        throw new Error('Failed to fetch profile')
      }

      const profileData = await profileResponse.json()

      // Transform API response to match our interface
      const userProfile: UserProfile = {
        id: profileData.id || profileData.sub,
        email: profileData.email,
        name: profileData.name || profileData.full_name || null,
        avatar_url: profileData.avatar_url || profileData.picture || null,
        email_verified: profileData.email_verified ?? true,
        created_at: profileData.created_at || new Date().toISOString(),
        updated_at: profileData.updated_at || new Date().toISOString(),
        last_login_at: profileData.last_login_at || profileData.last_sign_in_at || null,
        is_active: profileData.is_active ?? true
      }

      setProfile(userProfile)
      setFormData({
        name: userProfile.name || '',
        avatar_url: userProfile.avatar_url || ''
      })

      // Handle sessions response
      if (sessionsResponse.ok) {
        const sessionsData: SessionsResponse = await sessionsResponse.json()
        setSessions(sessionsData.sessions || [])
      }
    } catch (err) {
      console.error('Failed to fetch profile data:', err)
      setError(err instanceof Error ? err.message : 'Failed to load profile')
    } finally {
      setLoading(false)
    }
  }

  const handleUpdateProfile = async () => {
    if (!profile) return

    setUpdating(true)
    try {
      const response = await apiCall(`${API_BASE_URL}/api/v1/auth/me`, {
        method: 'PATCH',
        body: JSON.stringify({
          name: formData.name,
          avatar_url: formData.avatar_url || null
        })
      })

      if (!response.ok) {
        throw new Error('Failed to update profile')
      }

      const updatedData = await response.json()
      setProfile({
        ...profile,
        name: updatedData.name || formData.name,
        avatar_url: updatedData.avatar_url || formData.avatar_url || null,
        updated_at: new Date().toISOString()
      })
      setEditMode(false)
    } catch (err) {
      console.error('Failed to update profile:', err)
      alert(err instanceof Error ? err.message : 'Failed to update profile')
    } finally {
      setUpdating(false)
    }
  }

  const handleChangePassword = async () => {
    if (passwordData.new_password !== passwordData.confirm_password) {
      alert('Passwords do not match')
      return
    }

    setUpdating(true)
    try {
      const response = await apiCall(`${API_BASE_URL}/api/v1/auth/change-password`, {
        method: 'POST',
        body: JSON.stringify({
          current_password: passwordData.current_password,
          new_password: passwordData.new_password
        })
      })

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}))
        throw new Error(errorData.detail || 'Failed to change password')
      }

      alert('Password changed successfully')
      setPasswordData({ current_password: '', new_password: '', confirm_password: '' })
    } catch (err) {
      console.error('Failed to change password:', err)
      alert(err instanceof Error ? err.message : 'Failed to change password')
    } finally {
      setUpdating(false)
    }
  }

  const handleRevokeSession = async (sessionId: string) => {
    try {
      const response = await apiCall(`${API_BASE_URL}/api/v1/sessions/${sessionId}`, {
        method: 'DELETE'
      })

      if (!response.ok) {
        throw new Error('Failed to revoke session')
      }

      setSessions(sessions.filter(s => s.id !== sessionId))
    } catch (err) {
      console.error('Failed to revoke session:', err)
      alert(err instanceof Error ? err.message : 'Failed to revoke session')
    }
  }

  const handleRevokeAllSessions = async () => {
    try {
      const response = await apiCall(`${API_BASE_URL}/api/v1/sessions/`, {
        method: 'DELETE'
      })

      if (!response.ok) {
        throw new Error('Failed to revoke sessions')
      }

      // Refresh sessions list - should only show current session
      const sessionsResponse = await apiCall(`${API_BASE_URL}/api/v1/sessions/`)
      if (sessionsResponse.ok) {
        const sessionsData: SessionsResponse = await sessionsResponse.json()
        setSessions(sessionsData.sessions || [])
      }
    } catch (err) {
      console.error('Failed to revoke all sessions:', err)
      alert(err instanceof Error ? err.message : 'Failed to revoke sessions')
    }
  }

  const getDeviceIcon = (session: UserSession) => {
    const deviceType = session.device_type?.toLowerCase() || ''
    const userAgent = session.user_agent?.toLowerCase() || ''

    if (deviceType === 'mobile' || userAgent.includes('iphone') || userAgent.includes('android')) {
      return <Smartphone className="size-4" />
    }
    return <Monitor className="size-4" />
  }

  const getDeviceName = (session: UserSession) => {
    if (session.device_name) return session.device_name
    if (session.browser && session.os) return `${session.browser} on ${session.os}`
    if (session.device_type) return session.device_type
    return 'Unknown Device'
  }

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    })
  }

  if (loading) {
    return (
      <div className="bg-background flex min-h-screen items-center justify-center">
        <div className="text-center">
          <Loader2 className="text-muted-foreground mx-auto size-8 animate-spin" />
          <p className="text-muted-foreground mt-2 text-sm">Loading profile...</p>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="bg-background flex min-h-screen items-center justify-center">
        <div className="text-center">
          <AlertCircle className="text-destructive mx-auto mb-4 size-12" />
          <h2 className="mb-2 text-xl font-semibold">Failed to Load Profile</h2>
          <p className="text-muted-foreground mb-4">{error}</p>
          <Button onClick={fetchProfileData} variant="outline">
            <RefreshCw className="mr-2 size-4" />
            Try Again
          </Button>
        </div>
      </div>
    )
  }

  if (!profile) {
    return (
      <div className="bg-background flex min-h-screen items-center justify-center">
        <div className="text-center">
          <h2 className="mb-2 text-xl font-semibold">Profile not found</h2>
          <p className="text-muted-foreground">Unable to load user profile</p>
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
            <User className="text-primary size-8" />
            <div>
              <h1 className="text-2xl font-bold">Profile Settings</h1>
              <p className="text-muted-foreground text-sm">
                Manage your account and security settings
              </p>
            </div>
          </div>
        </div>
      </header>

      <div className="container mx-auto px-4 py-8">
        <Tabs defaultValue="profile" className="w-full">
          <TabsList className="grid w-full grid-cols-3">
            <TabsTrigger value="profile">Profile</TabsTrigger>
            <TabsTrigger value="security">Security</TabsTrigger>
            <TabsTrigger value="sessions">Sessions</TabsTrigger>
          </TabsList>

          {/* Profile Tab */}
          <TabsContent value="profile" className="space-y-6">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center space-x-2">
                  <User className="size-5" />
                  <span>Profile Information</span>
                </CardTitle>
                <CardDescription>
                  Update your personal information and profile settings
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-6">
                <div className="flex items-center space-x-4">
                  <Avatar className="size-20">
                    <AvatarImage src={profile.avatar_url || undefined} />
                    <AvatarFallback className="text-lg">
                      {profile.name?.charAt(0) || profile.email.charAt(0).toUpperCase()}
                    </AvatarFallback>
                  </Avatar>
                  <div className="space-y-1">
                    <h3 className="text-lg font-medium">{profile.name || 'No name set'}</h3>
                    <div className="flex items-center space-x-2">
                      <Mail className="text-muted-foreground size-4" />
                      <span className="text-muted-foreground text-sm">{profile.email}</span>
                      {profile.email_verified && (
                        <Badge variant="secondary" className="text-xs">
                          <Shield className="mr-1 size-3" />
                          Verified
                        </Badge>
                      )}
                    </div>
                  </div>
                </div>

                <Separator />

                <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                  <div className="space-y-2">
                    <Label htmlFor="name">Display Name</Label>
                    {editMode ? (
                      <Input
                        id="name"
                        value={formData.name}
                        onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                        placeholder="Enter your name"
                      />
                    ) : (
                      <div className="bg-muted rounded-md border px-3 py-2">
                        {profile.name || 'No name set'}
                      </div>
                    )}
                  </div>

                  <div className="space-y-2">
                    <Label htmlFor="email">Email Address</Label>
                    <div className="bg-muted text-muted-foreground rounded-md border px-3 py-2">
                      {profile.email}
                    </div>
                  </div>

                  <div className="space-y-2">
                    <Label htmlFor="avatar">Avatar URL</Label>
                    {editMode ? (
                      <Input
                        id="avatar"
                        value={formData.avatar_url}
                        onChange={(e) => setFormData({ ...formData, avatar_url: e.target.value })}
                        placeholder="https://example.com/avatar.jpg"
                      />
                    ) : (
                      <div className="bg-muted rounded-md border px-3 py-2">
                        {profile.avatar_url || 'No avatar set'}
                      </div>
                    )}
                  </div>

                  <div className="space-y-2">
                    <Label>Account Status</Label>
                    <div className="bg-muted rounded-md border px-3 py-2">
                      <Badge variant={profile.is_active ? "default" : "destructive"}>
                        {profile.is_active ? "Active" : "Inactive"}
                      </Badge>
                    </div>
                  </div>
                </div>

                <div className="flex items-center space-x-2">
                  {editMode ? (
                    <>
                      <Button onClick={handleUpdateProfile} disabled={updating}>
                        {updating ? 'Saving...' : 'Save Changes'}
                      </Button>
                      <Button
                        variant="outline"
                        onClick={() => {
                          setEditMode(false)
                          setFormData({
                            name: profile.name || '',
                            avatar_url: profile.avatar_url || ''
                          })
                        }}
                      >
                        Cancel
                      </Button>
                    </>
                  ) : (
                    <Button onClick={() => setEditMode(true)}>
                      <Edit3 className="mr-2 size-4" />
                      Edit Profile
                    </Button>
                  )}
                </div>

                <Separator />

                <div className="space-y-4">
                  <h4 className="text-sm font-medium">Account Information</h4>
                  <div className="grid grid-cols-1 gap-4 text-sm md:grid-cols-2">
                    <div className="flex items-center space-x-2">
                      <Calendar className="text-muted-foreground size-4" />
                      <span className="text-muted-foreground">Created:</span>
                      <span>{formatDate(profile.created_at)}</span>
                    </div>
                    <div className="flex items-center space-x-2">
                      <Edit3 className="text-muted-foreground size-4" />
                      <span className="text-muted-foreground">Updated:</span>
                      <span>{formatDate(profile.updated_at)}</span>
                    </div>
                    {profile.last_login_at && (
                      <div className="flex items-center space-x-2">
                        <Activity className="text-muted-foreground size-4" />
                        <span className="text-muted-foreground">Last Login:</span>
                        <span>{formatDate(profile.last_login_at)}</span>
                      </div>
                    )}
                  </div>
                </div>
              </CardContent>
            </Card>
          </TabsContent>

          {/* Security Tab */}
          <TabsContent value="security" className="space-y-6">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center space-x-2">
                  <Key className="size-5" />
                  <span>Change Password</span>
                </CardTitle>
                <CardDescription>
                  Update your password to keep your account secure
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="space-y-2">
                  <Label htmlFor="current-password">Current Password</Label>
                  <Input
                    id="current-password"
                    type="password"
                    value={passwordData.current_password}
                    onChange={(e) => setPasswordData({ ...passwordData, current_password: e.target.value })}
                    placeholder="Enter current password"
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="new-password">New Password</Label>
                  <Input
                    id="new-password"
                    type="password"
                    value={passwordData.new_password}
                    onChange={(e) => setPasswordData({ ...passwordData, new_password: e.target.value })}
                    placeholder="Enter new password"
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="confirm-password">Confirm New Password</Label>
                  <Input
                    id="confirm-password"
                    type="password"
                    value={passwordData.confirm_password}
                    onChange={(e) => setPasswordData({ ...passwordData, confirm_password: e.target.value })}
                    placeholder="Confirm new password"
                  />
                </div>
                <Button onClick={handleChangePassword} disabled={updating}>
                  {updating ? 'Updating...' : 'Change Password'}
                </Button>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="flex items-center space-x-2">
                  <Trash2 className="text-destructive size-5" />
                  <span>Danger Zone</span>
                </CardTitle>
                <CardDescription>
                  Irreversible and destructive actions
                </CardDescription>
              </CardHeader>
              <CardContent>
                <Button variant="destructive" size="sm">
                  Delete Account
                </Button>
                <p className="text-muted-foreground mt-2 text-xs">
                  This action cannot be undone. All your data will be permanently deleted.
                </p>
              </CardContent>
            </Card>
          </TabsContent>

          {/* Sessions Tab */}
          <TabsContent value="sessions" className="space-y-6">
            <Card>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <div>
                    <CardTitle className="flex items-center space-x-2">
                      <Monitor className="size-5" />
                      <span>Active Sessions</span>
                    </CardTitle>
                    <CardDescription>
                      Manage devices that are signed in to your account
                    </CardDescription>
                  </div>
                  <Button variant="outline" size="sm" onClick={fetchProfileData}>
                    <RefreshCw className="mr-2 size-4" />
                    Refresh
                  </Button>
                </div>
              </CardHeader>
              <CardContent className="space-y-4">
                {sessions.length === 0 ? (
                  <div className="text-muted-foreground py-8 text-center">
                    No active sessions found
                  </div>
                ) : (
                  sessions.map((session) => (
                    <div key={session.id} className="flex items-center justify-between rounded-lg border p-4">
                      <div className="flex items-center space-x-4">
                        {getDeviceIcon(session)}
                        <div className="space-y-1">
                          <div className="flex items-center space-x-2">
                            <span className="font-medium">
                              {getDeviceName(session)}
                            </span>
                            {session.is_current && (
                              <Badge variant="default" className="text-xs">Current</Badge>
                            )}
                            {session.revoked && (
                              <Badge variant="destructive" className="text-xs">Revoked</Badge>
                            )}
                          </div>
                          <div className="text-muted-foreground flex items-center space-x-4 text-sm">
                            {session.ip_address && (
                              <div className="flex items-center space-x-1">
                                <MapPin className="size-3" />
                                <span>{session.ip_address}</span>
                              </div>
                            )}
                            <div className="flex items-center space-x-1">
                              <Activity className="size-3" />
                              <span>Last active {formatDate(session.last_activity_at)}</span>
                            </div>
                          </div>
                        </div>
                      </div>
                      {!session.is_current && !session.revoked && (
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => handleRevokeSession(session.id)}
                        >
                          Revoke
                        </Button>
                      )}
                    </div>
                  ))
                )}

                <Separator />

                <div className="flex items-center justify-between">
                  <div>
                    <h4 className="text-sm font-medium">Sign out all devices</h4>
                    <p className="text-muted-foreground text-xs">
                      This will sign you out on all devices except this one
                    </p>
                  </div>
                  <Button variant="outline" size="sm" onClick={handleRevokeAllSessions}>
                    Sign Out All
                  </Button>
                </div>
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>
      </div>
    </div>
  )
}
