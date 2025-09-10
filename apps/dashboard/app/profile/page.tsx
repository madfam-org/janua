'use client'

import { useState, useEffect } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@plinto/ui'
import { Button } from '@plinto/ui'
import { Input } from '@plinto/ui'
import { Label } from '@plinto/ui'
import { Avatar, AvatarFallback, AvatarImage } from '@plinto/ui'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@plinto/ui'
import { Badge } from '@plinto/ui'
import { Separator } from '@plinto/ui'
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
  MapPin
} from 'lucide-react'

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
  ip_address: string | null
  user_agent: string | null
  created_at: string
  last_activity_at: string
  is_current: boolean
}

export default function ProfilePage() {
  const [profile, setProfile] = useState<UserProfile | null>(null)
  const [sessions, setSessions] = useState<UserSession[]>([])
  const [loading, setLoading] = useState(true)
  const [updating, setUpdating] = useState(false)
  const [editMode, setEditMode] = useState(false)
  const [formData, setFormData] = useState({ name: '', avatar_url: '' })
  const [passwordData, setPasswordData] = useState({
    current_password: '',
    new_password: '',
    confirm_password: ''
  })

  // Mock data for beta demonstration
  useEffect(() => {
    // Simulate API call
    setTimeout(() => {
      setProfile({
        id: 'user-123',
        email: 'user@plinto.dev',
        name: 'Beta User',
        avatar_url: null,
        email_verified: true,
        created_at: '2025-09-10T10:00:00Z',
        updated_at: '2025-09-10T15:30:00Z',
        last_login_at: '2025-09-10T23:15:00Z',
        is_active: true
      })

      setSessions([
        {
          id: 'session-1',
          device_name: 'MacBook Pro',
          ip_address: '192.168.1.100',
          user_agent: 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
          created_at: '2025-09-10T10:00:00Z',
          last_activity_at: '2025-09-10T23:15:00Z',
          is_current: true
        },
        {
          id: 'session-2',
          device_name: 'iPhone',
          ip_address: '192.168.1.101',
          user_agent: 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X)',
          created_at: '2025-09-09T14:20:00Z',
          last_activity_at: '2025-09-10T18:45:00Z',
          is_current: false
        }
      ])

      setFormData({
        name: 'Beta User',
        avatar_url: ''
      })

      setLoading(false)
    }, 1000)
  }, [])

  const handleUpdateProfile = async () => {
    setUpdating(true)
    // Simulate API call
    setTimeout(() => {
      if (profile) {
        setProfile({
          ...profile,
          name: formData.name,
          avatar_url: formData.avatar_url || null,
          updated_at: new Date().toISOString()
        })
      }
      setEditMode(false)
      setUpdating(false)
    }, 500)
  }

  const handleChangePassword = async () => {
    if (passwordData.new_password !== passwordData.confirm_password) {
      alert('Passwords do not match')
      return
    }
    
    setUpdating(true)
    // Simulate API call
    setTimeout(() => {
      alert('Password changed successfully')
      setPasswordData({ current_password: '', new_password: '', confirm_password: '' })
      setUpdating(false)
    }, 500)
  }

  const handleRevokeSession = async (sessionId: string) => {
    // Simulate API call
    setTimeout(() => {
      setSessions(sessions.filter(s => s.id !== sessionId))
    }, 300)
  }

  const getDeviceIcon = (userAgent: string | null) => {
    if (!userAgent) return <Monitor className="h-4 w-4" />
    if (userAgent.includes('iPhone') || userAgent.includes('Android')) {
      return <Smartphone className="h-4 w-4" />
    }
    return <Monitor className="h-4 w-4" />
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
      <div className="min-h-screen bg-background flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary mx-auto"></div>
          <p className="mt-2 text-sm text-muted-foreground">Loading profile...</p>
        </div>
      </div>
    )
  }

  if (!profile) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center">
        <div className="text-center">
          <h2 className="text-xl font-semibold mb-2">Profile not found</h2>
          <p className="text-muted-foreground">Unable to load user profile</p>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <header className="border-b">
        <div className="container mx-auto px-4 py-4">
          <div className="flex items-center space-x-4">
            <User className="h-8 w-8 text-primary" />
            <div>
              <h1 className="text-2xl font-bold">Profile Settings</h1>
              <p className="text-sm text-muted-foreground">
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
                  <User className="h-5 w-5" />
                  <span>Profile Information</span>
                </CardTitle>
                <CardDescription>
                  Update your personal information and profile settings
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-6">
                <div className="flex items-center space-x-4">
                  <Avatar className="h-20 w-20">
                    <AvatarImage src={profile.avatar_url || undefined} />
                    <AvatarFallback className="text-lg">
                      {profile.name?.charAt(0) || profile.email.charAt(0).toUpperCase()}
                    </AvatarFallback>
                  </Avatar>
                  <div className="space-y-1">
                    <h3 className="text-lg font-medium">{profile.name || 'No name set'}</h3>
                    <div className="flex items-center space-x-2">
                      <Mail className="h-4 w-4 text-muted-foreground" />
                      <span className="text-sm text-muted-foreground">{profile.email}</span>
                      {profile.email_verified && (
                        <Badge variant="secondary" className="text-xs">
                          <Shield className="h-3 w-3 mr-1" />
                          Verified
                        </Badge>
                      )}
                    </div>
                  </div>
                </div>

                <Separator />

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
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
                      <div className="px-3 py-2 border rounded-md bg-muted">
                        {profile.name || 'No name set'}
                      </div>
                    )}
                  </div>

                  <div className="space-y-2">
                    <Label htmlFor="email">Email Address</Label>
                    <div className="px-3 py-2 border rounded-md bg-muted text-muted-foreground">
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
                      <div className="px-3 py-2 border rounded-md bg-muted">
                        {profile.avatar_url || 'No avatar set'}
                      </div>
                    )}
                  </div>

                  <div className="space-y-2">
                    <Label>Account Status</Label>
                    <div className="px-3 py-2 border rounded-md bg-muted">
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
                      <Edit3 className="h-4 w-4 mr-2" />
                      Edit Profile
                    </Button>
                  )}
                </div>

                <Separator />

                <div className="space-y-4">
                  <h4 className="text-sm font-medium">Account Information</h4>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
                    <div className="flex items-center space-x-2">
                      <Calendar className="h-4 w-4 text-muted-foreground" />
                      <span className="text-muted-foreground">Created:</span>
                      <span>{formatDate(profile.created_at)}</span>
                    </div>
                    <div className="flex items-center space-x-2">
                      <Edit3 className="h-4 w-4 text-muted-foreground" />
                      <span className="text-muted-foreground">Updated:</span>
                      <span>{formatDate(profile.updated_at)}</span>
                    </div>
                    {profile.last_login_at && (
                      <div className="flex items-center space-x-2">
                        <Activity className="h-4 w-4 text-muted-foreground" />
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
                  <Key className="h-5 w-5" />
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
                  <Trash2 className="h-5 w-5 text-destructive" />
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
                <p className="text-xs text-muted-foreground mt-2">
                  This action cannot be undone. All your data will be permanently deleted.
                </p>
              </CardContent>
            </Card>
          </TabsContent>

          {/* Sessions Tab */}
          <TabsContent value="sessions" className="space-y-6">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center space-x-2">
                  <Monitor className="h-5 w-5" />
                  <span>Active Sessions</span>
                </CardTitle>
                <CardDescription>
                  Manage devices that are signed in to your account
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                {sessions.map((session) => (
                  <div key={session.id} className="flex items-center justify-between p-4 border rounded-lg">
                    <div className="flex items-center space-x-4">
                      {getDeviceIcon(session.user_agent)}
                      <div className="space-y-1">
                        <div className="flex items-center space-x-2">
                          <span className="font-medium">
                            {session.device_name || 'Unknown Device'}
                          </span>
                          {session.is_current && (
                            <Badge variant="default" className="text-xs">Current</Badge>
                          )}
                        </div>
                        <div className="flex items-center space-x-4 text-sm text-muted-foreground">
                          <div className="flex items-center space-x-1">
                            <MapPin className="h-3 w-3" />
                            <span>{session.ip_address}</span>
                          </div>
                          <div className="flex items-center space-x-1">
                            <Activity className="h-3 w-3" />
                            <span>Last active {formatDate(session.last_activity_at)}</span>
                          </div>
                        </div>
                      </div>
                    </div>
                    {!session.is_current && (
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => handleRevokeSession(session.id)}
                      >
                        Revoke
                      </Button>
                    )}
                  </div>
                ))}

                <Separator />

                <div className="flex justify-between items-center">
                  <div>
                    <h4 className="text-sm font-medium">Sign out all devices</h4>
                    <p className="text-xs text-muted-foreground">
                      This will sign you out on all devices except this one
                    </p>
                  </div>
                  <Button variant="outline" size="sm">
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