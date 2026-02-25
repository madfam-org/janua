'use client'

import { useState, useEffect, useCallback } from 'react'
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
  ShieldCheck,
  ShieldOff,
  Key,
  KeyRound,
  Fingerprint,
  Trash2,
  Edit3,
  Calendar,
  Activity,
  Monitor,
  Smartphone,
  Tablet,
  MapPin,
  Loader2,
  AlertCircle,
  RefreshCw,
  Lock,
  LogOut,
  Plus,
  Download,
  Copy,
  Check,
  CheckCircle2,
  XCircle,
  Globe,
  Clock,
  Eye,
  EyeOff,
} from 'lucide-react'
import { januaClient } from '@/lib/janua-client'
import {
  updateProfile,
  changePassword,
  enableMfa,
  verifyMfa,
  disableMfa,
  listPasskeys,
  deletePasskey,
  registerPasskeyOptions,
  verifyPasskeyRegistration,
  listDevices,
  trustDevice,
  revokeDevice,
} from '@/lib/api'

// ---------------------------------------------------------------------------
// Type definitions
// ---------------------------------------------------------------------------

interface UserProfile {
  id: string
  email: string
  first_name: string | null
  last_name: string | null
  username: string | null
  phone_number: string | null
  name: string | null
  avatar_url: string | null
  email_verified: boolean
  mfa_enabled: boolean
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

interface Passkey {
  id: string
  name: string
  credential_id: string
  created_at: string
  last_used_at: string | null
  aaguid: string | null
}

interface TrustedDevice {
  id: string
  device_name: string
  os: string | null
  browser: string | null
  location: string | null
  ip_address: string | null
  trusted_at: string
  last_used_at: string | null
  is_current: boolean
}

interface MfaSetupResponse {
  qr_code: string
  secret: string
  issuer: string
  account_name: string
}

interface MfaVerifyResponse {
  success: boolean
  backup_codes: string[]
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function formatDate(dateString: string): string {
  return new Date(dateString).toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

function formatRelativeTime(dateString: string): string {
  const date = new Date(dateString)
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffMins = Math.floor(diffMs / 60000)
  const diffHours = Math.floor(diffMins / 60)
  const diffDays = Math.floor(diffHours / 24)

  if (diffMins < 1) return 'Just now'
  if (diffMins < 60) return `${diffMins}m ago`
  if (diffHours < 24) return `${diffHours}h ago`
  if (diffDays < 7) return `${diffDays}d ago`
  return formatDate(dateString)
}

function getDeviceIcon(deviceType: string | null, userAgent: string | null) {
  const type = deviceType?.toLowerCase() || ''
  const ua = userAgent?.toLowerCase() || ''

  if (type === 'mobile' || ua.includes('iphone') || ua.includes('android')) {
    return <Smartphone className="size-4" />
  }
  if (type === 'tablet' || ua.includes('ipad')) {
    return <Tablet className="size-4" />
  }
  return <Monitor className="size-4" />
}

function getInitials(profile: UserProfile): string {
  if (profile.first_name && profile.last_name) {
    return `${profile.first_name[0]}${profile.last_name[0]}`.toUpperCase()
  }
  if (profile.name) return profile.name.charAt(0).toUpperCase()
  return profile.email.charAt(0).toUpperCase()
}

function getDisplayName(profile: UserProfile): string {
  if (profile.first_name && profile.last_name) {
    return `${profile.first_name} ${profile.last_name}`
  }
  return profile.name || profile.username || 'No name set'
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export default function ProfilePage() {
  // Profile state
  const [profile, setProfile] = useState<UserProfile | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // Profile edit state
  const [editMode, setEditMode] = useState(false)
  const [saving, setSaving] = useState(false)
  const [profileForm, setProfileForm] = useState({
    first_name: '',
    last_name: '',
    username: '',
    phone_number: '',
  })

  // Password state
  const [passwordForm, setPasswordForm] = useState({
    current_password: '',
    new_password: '',
    confirm_password: '',
  })
  const [showPasswords, setShowPasswords] = useState({
    current: false,
    new_password: false,
    confirm: false,
  })
  const [changingPassword, setChangingPassword] = useState(false)
  const [passwordMessage, setPasswordMessage] = useState<{
    type: 'success' | 'error'
    text: string
  } | null>(null)

  // MFA state
  const [mfaSetup, setMfaSetup] = useState<MfaSetupResponse | null>(null)
  const [mfaStep, setMfaStep] = useState<'idle' | 'qr' | 'verify' | 'backup'>('idle')
  const [mfaCode, setMfaCode] = useState('')
  const [backupCodes, setBackupCodes] = useState<string[]>([])
  const [mfaLoading, setMfaLoading] = useState(false)
  const [mfaError, setMfaError] = useState<string | null>(null)

  // Passkey state
  const [passkeys, setPasskeys] = useState<Passkey[]>([])
  const [passkeysLoading, setPasskeysLoading] = useState(false)
  const [registeringPasskey, setRegisteringPasskey] = useState(false)
  const [passkeyName, setPasskeyName] = useState('')
  const [showPasskeyNameInput, setShowPasskeyNameInput] = useState(false)

  // Session state
  const [sessions, setSessions] = useState<UserSession[]>([])
  const [sessionsLoading, setSessionsLoading] = useState(false)
  const [revokingSession, setRevokingSession] = useState<string | null>(null)
  const [revokingAll, setRevokingAll] = useState(false)

  // Device state
  const [devices, setDevices] = useState<TrustedDevice[]>([])
  const [devicesLoading, setDevicesLoading] = useState(false)
  const [trustingDevice, setTrustingDevice] = useState(false)
  const [revokingDevice, setRevokingDevice] = useState<string | null>(null)

  // Toast-like notification state
  const [notification, setNotification] = useState<{
    type: 'success' | 'error'
    text: string
  } | null>(null)

  const showNotification = useCallback(
    (type: 'success' | 'error', text: string) => {
      setNotification({ type, text })
      setTimeout(() => setNotification(null), 5000)
    },
    [],
  )

  // -------------------------------------------------------------------------
  // Data fetching
  // -------------------------------------------------------------------------

  const fetchProfile = useCallback(async () => {
    try {
      const data = await januaClient.auth.getCurrentUser() as Record<string, any>

      const userProfile: UserProfile = {
        id: data.id || data.sub,
        email: data.email,
        first_name: data.first_name || null,
        last_name: data.last_name || null,
        username: data.username || null,
        phone_number: data.phone_number || null,
        name: data.name || data.full_name || null,
        avatar_url: data.avatar_url || data.picture || null,
        email_verified: data.email_verified ?? true,
        mfa_enabled: data.mfa_enabled ?? false,
        created_at: data.created_at || new Date().toISOString(),
        updated_at: data.updated_at || new Date().toISOString(),
        last_login_at: data.last_login_at || data.last_sign_in_at || null,
        is_active: data.is_active ?? true,
      }

      setProfile(userProfile)
      setProfileForm({
        first_name: userProfile.first_name || '',
        last_name: userProfile.last_name || '',
        username: userProfile.username || '',
        phone_number: userProfile.phone_number || '',
      })

      return userProfile
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to load profile'
      setError(message)
      return null
    }
  }, [])

  const fetchSessions = useCallback(async () => {
    setSessionsLoading(true)
    try {
      const data = await januaClient.sessions.listSessions() as unknown as SessionsResponse
      setSessions(data.sessions || [])
    } catch (err) {
      console.error('Failed to fetch sessions:', err)
    } finally {
      setSessionsLoading(false)
    }
  }, [])

  const fetchPasskeys = useCallback(async () => {
    setPasskeysLoading(true)
    try {
      const data = await listPasskeys()
      setPasskeys(Array.isArray(data) ? data : (data as any).passkeys || [])
    } catch (err) {
      console.error('Failed to fetch passkeys:', err)
    } finally {
      setPasskeysLoading(false)
    }
  }, [])

  const fetchDevices = useCallback(async () => {
    setDevicesLoading(true)
    try {
      const data = await listDevices()
      setDevices(Array.isArray(data) ? data : (data as any).devices || [])
    } catch (err) {
      console.error('Failed to fetch devices:', err)
    } finally {
      setDevicesLoading(false)
    }
  }, [])

  useEffect(() => {
    const init = async () => {
      setLoading(true)
      setError(null)
      await Promise.all([fetchProfile(), fetchSessions()])
      setLoading(false)
    }
    init()
  }, [fetchProfile, fetchSessions])

  // -------------------------------------------------------------------------
  // Profile actions
  // -------------------------------------------------------------------------

  const handleSaveProfile = async () => {
    if (!profile) return
    setSaving(true)
    try {
      const updated = await updateProfile({
        first_name: profileForm.first_name || null,
        last_name: profileForm.last_name || null,
        username: profileForm.username || null,
        phone_number: profileForm.phone_number || null,
      }) as Record<string, any>

      setProfile((prev) =>
        prev
          ? {
              ...prev,
              first_name: updated.first_name ?? profileForm.first_name ?? prev.first_name,
              last_name: updated.last_name ?? profileForm.last_name ?? prev.last_name,
              username: updated.username ?? profileForm.username ?? prev.username,
              phone_number: updated.phone_number ?? profileForm.phone_number ?? prev.phone_number,
              updated_at: new Date().toISOString(),
            }
          : prev,
      )
      setEditMode(false)
      showNotification('success', 'Profile updated successfully')
    } catch (err) {
      showNotification(
        'error',
        err instanceof Error ? err.message : 'Failed to update profile',
      )
    } finally {
      setSaving(false)
    }
  }

  // -------------------------------------------------------------------------
  // Password actions
  // -------------------------------------------------------------------------

  const handleChangePassword = async () => {
    setPasswordMessage(null)

    if (!passwordForm.new_password) {
      setPasswordMessage({ type: 'error', text: 'New password is required' })
      return
    }
    if (passwordForm.new_password.length < 8) {
      setPasswordMessage({
        type: 'error',
        text: 'Password must be at least 8 characters',
      })
      return
    }
    if (passwordForm.new_password !== passwordForm.confirm_password) {
      setPasswordMessage({ type: 'error', text: 'Passwords do not match' })
      return
    }

    setChangingPassword(true)
    try {
      await changePassword({
        current_password: passwordForm.current_password,
        new_password: passwordForm.new_password,
      })

      setPasswordForm({
        current_password: '',
        new_password: '',
        confirm_password: '',
      })
      setPasswordMessage({
        type: 'success',
        text: 'Password changed successfully',
      })
    } catch (err) {
      setPasswordMessage({
        type: 'error',
        text: err instanceof Error ? err.message : 'Failed to change password',
      })
    } finally {
      setChangingPassword(false)
    }
  }

  // -------------------------------------------------------------------------
  // MFA actions
  // -------------------------------------------------------------------------

  const handleEnableMfa = async () => {
    setMfaLoading(true)
    setMfaError(null)
    try {
      const data = await enableMfa({ password: '' }) as unknown as MfaSetupResponse
      setMfaSetup(data)
      setMfaStep('qr')
    } catch (err) {
      setMfaError(
        err instanceof Error ? err.message : 'Failed to start MFA setup',
      )
    } finally {
      setMfaLoading(false)
    }
  }

  const handleVerifyMfa = async () => {
    if (mfaCode.length !== 6) {
      setMfaError('Please enter a 6-digit code')
      return
    }

    setMfaLoading(true)
    setMfaError(null)
    try {
      const data = await verifyMfa({ code: mfaCode }) as unknown as MfaVerifyResponse
      setBackupCodes(data.backup_codes || [])
      setMfaStep('backup')
      setProfile((prev) => (prev ? { ...prev, mfa_enabled: true } : prev))
      showNotification('success', 'MFA enabled successfully')
    } catch (err) {
      setMfaError(
        err instanceof Error ? err.message : 'Failed to verify MFA code',
      )
    } finally {
      setMfaLoading(false)
    }
  }

  const handleDisableMfa = async () => {
    if (!confirm('Are you sure you want to disable multi-factor authentication? This will make your account less secure.')) {
      return
    }

    setMfaLoading(true)
    setMfaError(null)
    try {
      await disableMfa({ password: '', code: '' })

      setProfile((prev) => (prev ? { ...prev, mfa_enabled: false } : prev))
      setMfaStep('idle')
      setMfaSetup(null)
      setMfaCode('')
      setBackupCodes([])
      showNotification('success', 'MFA disabled')
    } catch (err) {
      setMfaError(
        err instanceof Error ? err.message : 'Failed to disable MFA',
      )
    } finally {
      setMfaLoading(false)
    }
  }

  const handleCancelMfaSetup = () => {
    setMfaStep('idle')
    setMfaSetup(null)
    setMfaCode('')
    setMfaError(null)
    setBackupCodes([])
  }

  const handleDownloadBackupCodes = () => {
    const content = [
      'Janua Backup Codes',
      '==================',
      `Generated: ${new Date().toISOString()}`,
      `Account: ${profile?.email}`,
      '',
      'Keep these codes in a safe place. Each code can only be used once.',
      '',
      ...backupCodes.map((code, i) => `${i + 1}. ${code}`),
    ].join('\n')

    const blob = new Blob([content], { type: 'text/plain' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = 'janua-backup-codes.txt'
    a.click()
    URL.revokeObjectURL(url)
  }

  const [copiedCode, setCopiedCode] = useState<number | null>(null)

  const handleCopyBackupCodes = () => {
    const text = backupCodes.join('\n')
    navigator.clipboard.writeText(text).then(() => {
      setCopiedCode(-1)
      setTimeout(() => setCopiedCode(null), 2000)
    })
  }

  // -------------------------------------------------------------------------
  // Passkey actions
  // -------------------------------------------------------------------------

  const handleRegisterPasskey = async () => {
    setRegisteringPasskey(true)
    try {
      // Step 1: Get registration options from server
      const options = await registerPasskeyOptions() as Record<string, any>

      // Step 2: Create credential with WebAuthn API
      const publicKeyOptions: PublicKeyCredentialCreationOptions = {
        challenge: Uint8Array.from(atob(options.challenge), (c) => c.charCodeAt(0)),
        rp: {
          name: options.rp?.name || 'Janua',
          id: options.rp?.id || window.location.hostname,
        },
        user: {
          id: Uint8Array.from(atob(options.user?.id || ''), (c) => c.charCodeAt(0)),
          name: options.user?.name || profile?.email || '',
          displayName: options.user?.displayName || getDisplayName(profile!),
        },
        pubKeyCredParams: options.pubKeyCredParams || [
          { alg: -7, type: 'public-key' },
          { alg: -257, type: 'public-key' },
        ],
        timeout: options.timeout || 60000,
        authenticatorSelection: options.authenticatorSelection || {
          authenticatorAttachment: 'platform',
          residentKey: 'preferred',
          userVerification: 'preferred',
        },
        attestation: options.attestation || 'none',
        excludeCredentials: (options.excludeCredentials || []).map(
          (cred: { id: string; type: string; transports?: string[] }) => ({
            id: Uint8Array.from(atob(cred.id), (c) => c.charCodeAt(0)),
            type: cred.type,
            transports: cred.transports,
          }),
        ),
      }

      const credential = (await navigator.credentials.create({
        publicKey: publicKeyOptions,
      })) as PublicKeyCredential | null

      if (!credential) {
        throw new Error('Passkey registration was cancelled')
      }

      const attestationResponse = credential.response as AuthenticatorAttestationResponse

      // Step 3: Send credential to server for verification
      const uint8ToBase64 = (buffer: ArrayBuffer): string => {
        const bytes = new Uint8Array(buffer)
        let binary = ''
        for (let i = 0; i < bytes.byteLength; i++) {
          binary += String.fromCharCode(bytes[i]!)
        }
        return btoa(binary)
      }

      const verifyBody = {
        id: credential.id,
        rawId: uint8ToBase64(credential.rawId),
        type: credential.type,
        response: {
          attestationObject: uint8ToBase64(attestationResponse.attestationObject),
          clientDataJSON: uint8ToBase64(attestationResponse.clientDataJSON),
        },
        name: passkeyName || 'My Passkey',
      }

      await verifyPasskeyRegistration(verifyBody)

      showNotification('success', 'Passkey registered successfully')
      setShowPasskeyNameInput(false)
      setPasskeyName('')
      await fetchPasskeys()
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to register passkey'
      if (!message.includes('cancelled') && !message.includes('AbortError')) {
        showNotification('error', message)
      }
    } finally {
      setRegisteringPasskey(false)
    }
  }

  const handleDeletePasskey = async (passkeyId: string) => {
    if (!confirm('Are you sure you want to remove this passkey?')) return

    try {
      await deletePasskey(passkeyId)

      setPasskeys((prev) => prev.filter((p) => p.id !== passkeyId))
      showNotification('success', 'Passkey removed')
    } catch (err) {
      showNotification(
        'error',
        err instanceof Error ? err.message : 'Failed to remove passkey',
      )
    }
  }

  // -------------------------------------------------------------------------
  // Session actions
  // -------------------------------------------------------------------------

  const handleRevokeSession = async (sessionId: string) => {
    setRevokingSession(sessionId)
    try {
      await januaClient.sessions.revokeSession(sessionId)
      setSessions((prev) => prev.filter((s) => s.id !== sessionId))
      showNotification('success', 'Session revoked')
    } catch (err) {
      showNotification(
        'error',
        err instanceof Error ? err.message : 'Failed to revoke session',
      )
    } finally {
      setRevokingSession(null)
    }
  }

  const handleRevokeAllSessions = async () => {
    if (!confirm('Sign out of all other devices? Your current session will remain active.')) {
      return
    }

    setRevokingAll(true)
    try {
      await januaClient.sessions.revokeAllSessions()
      await fetchSessions()
      showNotification('success', 'All other sessions revoked')
    } catch (err) {
      showNotification(
        'error',
        err instanceof Error ? err.message : 'Failed to revoke sessions',
      )
    } finally {
      setRevokingAll(false)
    }
  }

  // -------------------------------------------------------------------------
  // Device actions
  // -------------------------------------------------------------------------

  const handleTrustDevice = async () => {
    setTrustingDevice(true)
    try {
      await trustDevice({})

      showNotification('success', 'Device trusted successfully')
      await fetchDevices()
    } catch (err) {
      showNotification(
        'error',
        err instanceof Error ? err.message : 'Failed to trust device',
      )
    } finally {
      setTrustingDevice(false)
    }
  }

  const handleRevokeDeviceTrust = async (deviceId: string) => {
    if (!confirm('Remove trust from this device? It will need to be re-verified on next login.')) {
      return
    }

    setRevokingDevice(deviceId)
    try {
      await revokeDevice(deviceId)
      setDevices((prev) => prev.filter((d) => d.id !== deviceId))
      showNotification('success', 'Device trust revoked')
    } catch (err) {
      showNotification(
        'error',
        err instanceof Error ? err.message : 'Failed to revoke device trust',
      )
    } finally {
      setRevokingDevice(null)
    }
  }

  // -------------------------------------------------------------------------
  // Tab change handler -- lazy load data for Security and Devices tabs
  // -------------------------------------------------------------------------

  const handleTabChange = (value: string) => {
    if (value === 'security') {
      fetchPasskeys()
    }
    if (value === 'sessions') {
      fetchSessions()
    }
    if (value === 'devices') {
      fetchDevices()
    }
  }

  // -------------------------------------------------------------------------
  // Loading / error states
  // -------------------------------------------------------------------------

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
          <Button
            onClick={() => {
              setError(null)
              setLoading(true)
              Promise.all([fetchProfile(), fetchSessions()]).finally(() =>
                setLoading(false),
              )
            }}
            variant="outline"
          >
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

  // -------------------------------------------------------------------------
  // Render
  // -------------------------------------------------------------------------

  return (
    <div className="bg-background min-h-screen">
      {/* Notification banner */}
      {notification && (
        <div
          className={`fixed right-4 top-4 z-50 flex items-center gap-2 rounded-lg border px-4 py-3 shadow-lg transition-all ${
            notification.type === 'success'
              ? 'border-green-200 bg-green-50 text-green-800 dark:border-green-800 dark:bg-green-950 dark:text-green-200'
              : 'border-red-200 bg-red-50 text-red-800 dark:border-red-800 dark:bg-red-950 dark:text-red-200'
          }`}
          role="status"
          aria-live="polite"
        >
          {notification.type === 'success' ? (
            <CheckCircle2 className="size-4 shrink-0" />
          ) : (
            <XCircle className="size-4 shrink-0" />
          )}
          <span className="text-sm font-medium">{notification.text}</span>
          <button
            onClick={() => setNotification(null)}
            className="ml-2 opacity-60 hover:opacity-100"
            aria-label="Dismiss notification"
          >
            <XCircle className="size-3.5" />
          </button>
        </div>
      )}

      {/* Header */}
      <header className="border-b">
        <div className="container mx-auto p-4">
          <div className="flex items-center space-x-4">
            <User className="text-primary size-8" />
            <div>
              <h1 className="text-2xl font-bold">Profile Settings</h1>
              <p className="text-muted-foreground text-sm">
                Manage your account, security, and connected devices
              </p>
            </div>
          </div>
        </div>
      </header>

      <div className="container mx-auto px-4 py-8">
        <Tabs
          defaultValue="profile"
          className="w-full"
          onValueChange={handleTabChange}
        >
          <TabsList className="grid w-full grid-cols-4">
            <TabsTrigger value="profile">
              <User className="mr-2 hidden size-4 sm:inline-block" />
              Profile
            </TabsTrigger>
            <TabsTrigger value="security">
              <Shield className="mr-2 hidden size-4 sm:inline-block" />
              Security
            </TabsTrigger>
            <TabsTrigger value="sessions">
              <Monitor className="mr-2 hidden size-4 sm:inline-block" />
              Sessions
            </TabsTrigger>
            <TabsTrigger value="devices">
              <Smartphone className="mr-2 hidden size-4 sm:inline-block" />
              Devices
            </TabsTrigger>
          </TabsList>

          {/* ============================================================= */}
          {/* TAB 1: PROFILE INFO                                           */}
          {/* ============================================================= */}
          <TabsContent value="profile" className="space-y-6">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center space-x-2">
                  <User className="size-5" />
                  <span>Profile Information</span>
                </CardTitle>
                <CardDescription>
                  Your personal information and account details
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-6">
                {/* Avatar and identity */}
                <div className="flex items-center space-x-4">
                  <Avatar className="size-20">
                    <AvatarImage
                      src={profile.avatar_url || undefined}
                      alt={`${getDisplayName(profile)} avatar`}
                    />
                    <AvatarFallback className="text-lg">
                      {getInitials(profile)}
                    </AvatarFallback>
                  </Avatar>
                  <div className="space-y-1">
                    <h3 className="text-lg font-medium">
                      {getDisplayName(profile)}
                    </h3>
                    <div className="flex items-center space-x-2">
                      <Mail className="text-muted-foreground size-4" />
                      <span className="text-muted-foreground text-sm">
                        {profile.email}
                      </span>
                      {profile.email_verified ? (
                        <Badge
                          variant="secondary"
                          className="text-xs"
                        >
                          <CheckCircle2 className="mr-1 size-3" />
                          Verified
                        </Badge>
                      ) : (
                        <Badge variant="destructive" className="text-xs">
                          <AlertCircle className="mr-1 size-3" />
                          Unverified
                        </Badge>
                      )}
                    </div>
                    {profile.username && (
                      <p className="text-muted-foreground text-sm">
                        @{profile.username}
                      </p>
                    )}
                  </div>
                </div>

                <Separator />

                {/* Editable fields */}
                <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                  <div className="space-y-2">
                    <Label htmlFor="first_name">First Name</Label>
                    {editMode ? (
                      <Input
                        id="first_name"
                        value={profileForm.first_name}
                        onChange={(e) =>
                          setProfileForm({
                            ...profileForm,
                            first_name: e.target.value,
                          })
                        }
                        placeholder="Enter first name"
                      />
                    ) : (
                      <div className="bg-muted rounded-md border px-3 py-2 text-sm">
                        {profile.first_name || 'Not set'}
                      </div>
                    )}
                  </div>

                  <div className="space-y-2">
                    <Label htmlFor="last_name">Last Name</Label>
                    {editMode ? (
                      <Input
                        id="last_name"
                        value={profileForm.last_name}
                        onChange={(e) =>
                          setProfileForm({
                            ...profileForm,
                            last_name: e.target.value,
                          })
                        }
                        placeholder="Enter last name"
                      />
                    ) : (
                      <div className="bg-muted rounded-md border px-3 py-2 text-sm">
                        {profile.last_name || 'Not set'}
                      </div>
                    )}
                  </div>

                  <div className="space-y-2">
                    <Label htmlFor="username">Username</Label>
                    {editMode ? (
                      <Input
                        id="username"
                        value={profileForm.username}
                        onChange={(e) =>
                          setProfileForm({
                            ...profileForm,
                            username: e.target.value,
                          })
                        }
                        placeholder="Enter username"
                      />
                    ) : (
                      <div className="bg-muted rounded-md border px-3 py-2 text-sm">
                        {profile.username || 'Not set'}
                      </div>
                    )}
                  </div>

                  <div className="space-y-2">
                    <Label htmlFor="phone_number">Phone Number</Label>
                    {editMode ? (
                      <Input
                        id="phone_number"
                        type="tel"
                        value={profileForm.phone_number}
                        onChange={(e) =>
                          setProfileForm({
                            ...profileForm,
                            phone_number: e.target.value,
                          })
                        }
                        placeholder="+1 (555) 123-4567"
                      />
                    ) : (
                      <div className="bg-muted rounded-md border px-3 py-2 text-sm">
                        {profile.phone_number || 'Not set'}
                      </div>
                    )}
                  </div>

                  <div className="space-y-2">
                    <Label>Email Address</Label>
                    <div className="bg-muted text-muted-foreground rounded-md border px-3 py-2 text-sm">
                      {profile.email}
                    </div>
                  </div>

                  <div className="space-y-2">
                    <Label>Account Status</Label>
                    <div className="bg-muted rounded-md border px-3 py-2">
                      <Badge
                        variant={profile.is_active ? 'default' : 'destructive'}
                      >
                        {profile.is_active ? 'Active' : 'Inactive'}
                      </Badge>
                    </div>
                  </div>
                </div>

                {/* Action buttons */}
                <div className="flex items-center space-x-2">
                  {editMode ? (
                    <>
                      <Button onClick={handleSaveProfile} disabled={saving}>
                        {saving ? (
                          <>
                            <Loader2 className="mr-2 size-4 animate-spin" />
                            Saving...
                          </>
                        ) : (
                          'Save Changes'
                        )}
                      </Button>
                      <Button
                        variant="outline"
                        onClick={() => {
                          setEditMode(false)
                          setProfileForm({
                            first_name: profile.first_name || '',
                            last_name: profile.last_name || '',
                            username: profile.username || '',
                            phone_number: profile.phone_number || '',
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

                {/* Account metadata */}
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
                        <span className="text-muted-foreground">
                          Last Login:
                        </span>
                        <span>{formatDate(profile.last_login_at)}</span>
                      </div>
                    )}
                    <div className="flex items-center space-x-2">
                      <Shield className="text-muted-foreground size-4" />
                      <span className="text-muted-foreground">MFA:</span>
                      <Badge
                        variant={
                          profile.mfa_enabled ? 'default' : 'secondary'
                        }
                        className="text-xs"
                      >
                        {profile.mfa_enabled ? 'Enabled' : 'Disabled'}
                      </Badge>
                    </div>
                  </div>
                </div>
              </CardContent>
            </Card>
          </TabsContent>

          {/* ============================================================= */}
          {/* TAB 2: SECURITY                                               */}
          {/* ============================================================= */}
          <TabsContent value="security" className="space-y-6">
            {/* ------ MFA Section ------ */}
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center space-x-2">
                  <ShieldCheck className="size-5" />
                  <span>Multi-Factor Authentication</span>
                </CardTitle>
                <CardDescription>
                  Add an extra layer of security with a time-based one-time
                  password (TOTP) authenticator app
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                {/* Status display */}
                <div className="flex items-center justify-between rounded-lg border p-4">
                  <div className="flex items-center space-x-3">
                    {profile.mfa_enabled ? (
                      <ShieldCheck className="size-5 text-green-600 dark:text-green-400" />
                    ) : (
                      <ShieldOff className="size-5 text-amber-600 dark:text-amber-400" />
                    )}
                    <div>
                      <p className="font-medium">
                        {profile.mfa_enabled
                          ? 'MFA is enabled'
                          : 'MFA is not enabled'}
                      </p>
                      <p className="text-muted-foreground text-sm">
                        {profile.mfa_enabled
                          ? 'Your account is protected with a TOTP authenticator'
                          : 'Enable MFA to add an extra security layer to your account'}
                      </p>
                    </div>
                  </div>
                  {mfaStep === 'idle' && (
                    <Button
                      variant={profile.mfa_enabled ? 'destructive' : 'default'}
                      size="sm"
                      onClick={
                        profile.mfa_enabled ? handleDisableMfa : handleEnableMfa
                      }
                      disabled={mfaLoading}
                    >
                      {mfaLoading ? (
                        <Loader2 className="mr-2 size-4 animate-spin" />
                      ) : profile.mfa_enabled ? (
                        <ShieldOff className="mr-2 size-4" />
                      ) : (
                        <ShieldCheck className="mr-2 size-4" />
                      )}
                      {profile.mfa_enabled ? 'Disable MFA' : 'Enable MFA'}
                    </Button>
                  )}
                </div>

                {mfaError && (
                  <div className="flex items-center gap-2 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-800 dark:border-red-800 dark:bg-red-950 dark:text-red-200">
                    <AlertCircle className="size-4 shrink-0" />
                    {mfaError}
                  </div>
                )}

                {/* MFA Setup Wizard: QR Code step */}
                {mfaStep === 'qr' && mfaSetup && (
                  <div className="space-y-4 rounded-lg border bg-muted/30 p-6">
                    <h4 className="font-medium">
                      Step 1: Scan QR Code
                    </h4>
                    <p className="text-muted-foreground text-sm">
                      Scan this QR code with your authenticator app (Google
                      Authenticator, Authy, 1Password, etc.)
                    </p>
                    <div className="flex flex-col items-center gap-4 sm:flex-row sm:items-start">
                      <div className="flex items-center justify-center rounded-lg border bg-white p-2">
                        <img
                          src={mfaSetup.qr_code}
                          alt="MFA QR Code - scan with your authenticator app"
                          className="size-48"
                          width={192}
                          height={192}
                        />
                      </div>
                      <div className="w-full space-y-3">
                        <div>
                          <p className="text-muted-foreground mb-1 text-xs font-medium uppercase tracking-wide">
                            Or enter this secret manually
                          </p>
                          <div className="flex items-center gap-2">
                            <code className="flex-1 rounded border bg-muted px-3 py-2 font-mono text-sm break-all">
                              {mfaSetup.secret}
                            </code>
                            <Button
                              variant="outline"
                              size="sm"
                              onClick={() => {
                                navigator.clipboard.writeText(mfaSetup.secret)
                                showNotification('success', 'Secret copied')
                              }}
                              aria-label="Copy secret to clipboard"
                            >
                              <Copy className="size-4" />
                            </Button>
                          </div>
                        </div>
                        <div className="text-muted-foreground text-xs">
                          <p>
                            <strong>Issuer:</strong> {mfaSetup.issuer}
                          </p>
                          <p>
                            <strong>Account:</strong> {mfaSetup.account_name}
                          </p>
                        </div>
                      </div>
                    </div>
                    <div className="flex gap-2">
                      <Button onClick={() => setMfaStep('verify')}>
                        Next: Verify Code
                      </Button>
                      <Button variant="outline" onClick={handleCancelMfaSetup}>
                        Cancel
                      </Button>
                    </div>
                  </div>
                )}

                {/* MFA Setup Wizard: Verify step */}
                {mfaStep === 'verify' && (
                  <div className="space-y-4 rounded-lg border bg-muted/30 p-6">
                    <h4 className="font-medium">
                      Step 2: Verify Code
                    </h4>
                    <p className="text-muted-foreground text-sm">
                      Enter the 6-digit code from your authenticator app to
                      confirm setup
                    </p>
                    <div className="flex items-end gap-3">
                      <div className="w-full max-w-xs space-y-2">
                        <Label htmlFor="mfa-code">Verification Code</Label>
                        <Input
                          id="mfa-code"
                          value={mfaCode}
                          onChange={(e) => {
                            const val = e.target.value
                              .replace(/\D/g, '')
                              .slice(0, 6)
                            setMfaCode(val)
                          }}
                          placeholder="000000"
                          maxLength={6}
                          className="font-mono text-lg tracking-widest"
                          autoComplete="one-time-code"
                          inputMode="numeric"
                          pattern="[0-9]*"
                          aria-describedby="mfa-code-help"
                          onKeyDown={(e) => {
                            if (e.key === 'Enter' && mfaCode.length === 6) {
                              handleVerifyMfa()
                            }
                          }}
                        />
                        <p
                          id="mfa-code-help"
                          className="text-muted-foreground text-xs"
                        >
                          Enter the 6-digit code displayed in your
                          authenticator app
                        </p>
                      </div>
                      <Button
                        onClick={handleVerifyMfa}
                        disabled={mfaCode.length !== 6 || mfaLoading}
                      >
                        {mfaLoading ? (
                          <Loader2 className="mr-2 size-4 animate-spin" />
                        ) : (
                          <Check className="mr-2 size-4" />
                        )}
                        Verify
                      </Button>
                    </div>
                    <div className="flex gap-2">
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => setMfaStep('qr')}
                      >
                        Back to QR Code
                      </Button>
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={handleCancelMfaSetup}
                      >
                        Cancel Setup
                      </Button>
                    </div>
                  </div>
                )}

                {/* MFA Setup Wizard: Backup codes step */}
                {mfaStep === 'backup' && backupCodes.length > 0 && (
                  <div className="space-y-4 rounded-lg border border-green-200 bg-green-50/50 p-6 dark:border-green-800 dark:bg-green-950/30">
                    <div className="flex items-center gap-2">
                      <CheckCircle2 className="size-5 text-green-600 dark:text-green-400" />
                      <h4 className="font-medium">
                        MFA Enabled - Save Your Backup Codes
                      </h4>
                    </div>
                    <p className="text-muted-foreground text-sm">
                      Save these backup codes in a secure location. Each code
                      can only be used once to sign in if you lose access to your
                      authenticator app.
                    </p>
                    <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 md:grid-cols-4">
                      {backupCodes.map((code, index) => (
                        <div
                          key={index}
                          className="rounded border bg-white px-3 py-2 text-center font-mono text-sm dark:bg-gray-900"
                        >
                          {code}
                        </div>
                      ))}
                    </div>
                    <div className="flex flex-wrap gap-2">
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={handleDownloadBackupCodes}
                      >
                        <Download className="mr-2 size-4" />
                        Download Codes
                      </Button>
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={handleCopyBackupCodes}
                      >
                        {copiedCode === -1 ? (
                          <Check className="mr-2 size-4" />
                        ) : (
                          <Copy className="mr-2 size-4" />
                        )}
                        {copiedCode === -1 ? 'Copied' : 'Copy All'}
                      </Button>
                      <Button
                        size="sm"
                        onClick={() => {
                          setMfaStep('idle')
                          setBackupCodes([])
                          setMfaCode('')
                          setMfaSetup(null)
                        }}
                      >
                        Done
                      </Button>
                    </div>
                    <p className="text-xs font-medium text-amber-700 dark:text-amber-400">
                      Warning: These codes will not be shown again. Store them
                      securely now.
                    </p>
                  </div>
                )}
              </CardContent>
            </Card>

            {/* ------ Passkeys Section ------ */}
            <Card>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <div>
                    <CardTitle className="flex items-center space-x-2">
                      <Fingerprint className="size-5" />
                      <span>Passkeys</span>
                    </CardTitle>
                    <CardDescription>
                      Use biometrics or hardware security keys for passwordless
                      sign-in
                    </CardDescription>
                  </div>
                  <Button
                    size="sm"
                    onClick={() => {
                      if (showPasskeyNameInput) {
                        handleRegisterPasskey()
                      } else {
                        setShowPasskeyNameInput(true)
                      }
                    }}
                    disabled={registeringPasskey}
                  >
                    {registeringPasskey ? (
                      <Loader2 className="mr-2 size-4 animate-spin" />
                    ) : (
                      <Plus className="mr-2 size-4" />
                    )}
                    {registeringPasskey ? 'Registering...' : 'Add Passkey'}
                  </Button>
                </div>
              </CardHeader>
              <CardContent className="space-y-4">
                {/* Passkey name input */}
                {showPasskeyNameInput && !registeringPasskey && (
                  <div className="flex items-end gap-3 rounded-lg border bg-muted/30 p-4">
                    <div className="w-full max-w-xs space-y-2">
                      <Label htmlFor="passkey-name">Passkey Name</Label>
                      <Input
                        id="passkey-name"
                        value={passkeyName}
                        onChange={(e) => setPasskeyName(e.target.value)}
                        placeholder="e.g., MacBook Pro, iPhone"
                        onKeyDown={(e) => {
                          if (e.key === 'Enter') handleRegisterPasskey()
                        }}
                      />
                    </div>
                    <Button onClick={handleRegisterPasskey} size="sm">
                      Register
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => {
                        setShowPasskeyNameInput(false)
                        setPasskeyName('')
                      }}
                    >
                      Cancel
                    </Button>
                  </div>
                )}

                {/* Passkeys list */}
                {passkeysLoading ? (
                  <div className="flex items-center justify-center py-8">
                    <Loader2 className="text-muted-foreground size-6 animate-spin" />
                    <span className="text-muted-foreground ml-2 text-sm">
                      Loading passkeys...
                    </span>
                  </div>
                ) : passkeys.length === 0 ? (
                  <div className="text-muted-foreground py-8 text-center">
                    <Fingerprint className="mx-auto mb-2 size-8 opacity-40" />
                    <p className="text-sm">No passkeys registered</p>
                    <p className="text-xs">
                      Add a passkey for faster, more secure sign-in
                    </p>
                  </div>
                ) : (
                  passkeys.map((passkey) => (
                    <div
                      key={passkey.id}
                      className="flex items-center justify-between rounded-lg border p-4"
                    >
                      <div className="flex items-center space-x-3">
                        <KeyRound className="text-muted-foreground size-5" />
                        <div>
                          <p className="font-medium">{passkey.name}</p>
                          <div className="text-muted-foreground flex items-center gap-3 text-xs">
                            <span className="flex items-center gap-1">
                              <Calendar className="size-3" />
                              Added {formatDate(passkey.created_at)}
                            </span>
                            {passkey.last_used_at && (
                              <span className="flex items-center gap-1">
                                <Clock className="size-3" />
                                Last used{' '}
                                {formatRelativeTime(passkey.last_used_at)}
                              </span>
                            )}
                          </div>
                        </div>
                      </div>
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => handleDeletePasskey(passkey.id)}
                      >
                        <Trash2 className="mr-2 size-4" />
                        Remove
                      </Button>
                    </div>
                  ))
                )}
              </CardContent>
            </Card>

            {/* ------ Password Change Section ------ */}
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center space-x-2">
                  <Lock className="size-5" />
                  <span>Change Password</span>
                </CardTitle>
                <CardDescription>
                  Update your password to keep your account secure
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                {passwordMessage && (
                  <div
                    className={`flex items-center gap-2 rounded-lg border p-3 text-sm ${
                      passwordMessage.type === 'success'
                        ? 'border-green-200 bg-green-50 text-green-800 dark:border-green-800 dark:bg-green-950 dark:text-green-200'
                        : 'border-red-200 bg-red-50 text-red-800 dark:border-red-800 dark:bg-red-950 dark:text-red-200'
                    }`}
                    role="alert"
                  >
                    {passwordMessage.type === 'success' ? (
                      <CheckCircle2 className="size-4 shrink-0" />
                    ) : (
                      <AlertCircle className="size-4 shrink-0" />
                    )}
                    {passwordMessage.text}
                  </div>
                )}

                <div className="space-y-2">
                  <Label htmlFor="current-password">Current Password</Label>
                  <div className="relative">
                    <Input
                      id="current-password"
                      type={showPasswords.current ? 'text' : 'password'}
                      value={passwordForm.current_password}
                      onChange={(e) =>
                        setPasswordForm({
                          ...passwordForm,
                          current_password: e.target.value,
                        })
                      }
                      placeholder="Enter current password"
                      autoComplete="current-password"
                    />
                    <button
                      type="button"
                      onClick={() =>
                        setShowPasswords((p) => ({
                          ...p,
                          current: !p.current,
                        }))
                      }
                      className="text-muted-foreground hover:text-foreground absolute right-3 top-1/2 -translate-y-1/2"
                      aria-label={
                        showPasswords.current
                          ? 'Hide current password'
                          : 'Show current password'
                      }
                    >
                      {showPasswords.current ? (
                        <EyeOff className="size-4" />
                      ) : (
                        <Eye className="size-4" />
                      )}
                    </button>
                  </div>
                </div>

                <div className="space-y-2">
                  <Label htmlFor="new-password">New Password</Label>
                  <div className="relative">
                    <Input
                      id="new-password"
                      type={showPasswords.new_password ? 'text' : 'password'}
                      value={passwordForm.new_password}
                      onChange={(e) =>
                        setPasswordForm({
                          ...passwordForm,
                          new_password: e.target.value,
                        })
                      }
                      placeholder="Enter new password"
                      autoComplete="new-password"
                    />
                    <button
                      type="button"
                      onClick={() =>
                        setShowPasswords((p) => ({
                          ...p,
                          new_password: !p.new_password,
                        }))
                      }
                      className="text-muted-foreground hover:text-foreground absolute right-3 top-1/2 -translate-y-1/2"
                      aria-label={
                        showPasswords.new_password
                          ? 'Hide new password'
                          : 'Show new password'
                      }
                    >
                      {showPasswords.new_password ? (
                        <EyeOff className="size-4" />
                      ) : (
                        <Eye className="size-4" />
                      )}
                    </button>
                  </div>
                </div>

                <div className="space-y-2">
                  <Label htmlFor="confirm-password">Confirm New Password</Label>
                  <div className="relative">
                    <Input
                      id="confirm-password"
                      type={showPasswords.confirm ? 'text' : 'password'}
                      value={passwordForm.confirm_password}
                      onChange={(e) =>
                        setPasswordForm({
                          ...passwordForm,
                          confirm_password: e.target.value,
                        })
                      }
                      placeholder="Confirm new password"
                      autoComplete="new-password"
                    />
                    <button
                      type="button"
                      onClick={() =>
                        setShowPasswords((p) => ({
                          ...p,
                          confirm: !p.confirm,
                        }))
                      }
                      className="text-muted-foreground hover:text-foreground absolute right-3 top-1/2 -translate-y-1/2"
                      aria-label={
                        showPasswords.confirm
                          ? 'Hide confirm password'
                          : 'Show confirm password'
                      }
                    >
                      {showPasswords.confirm ? (
                        <EyeOff className="size-4" />
                      ) : (
                        <Eye className="size-4" />
                      )}
                    </button>
                  </div>
                </div>

                <Button
                  onClick={handleChangePassword}
                  disabled={
                    changingPassword ||
                    !passwordForm.current_password ||
                    !passwordForm.new_password ||
                    !passwordForm.confirm_password
                  }
                >
                  {changingPassword ? (
                    <>
                      <Loader2 className="mr-2 size-4 animate-spin" />
                      Updating...
                    </>
                  ) : (
                    <>
                      <Key className="mr-2 size-4" />
                      Change Password
                    </>
                  )}
                </Button>
              </CardContent>
            </Card>
          </TabsContent>

          {/* ============================================================= */}
          {/* TAB 3: SESSIONS                                               */}
          {/* ============================================================= */}
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
                      Manage devices and browsers that are signed in to your
                      account
                    </CardDescription>
                  </div>
                  <div className="flex gap-2">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={fetchSessions}
                      disabled={sessionsLoading}
                    >
                      {sessionsLoading ? (
                        <Loader2 className="mr-2 size-4 animate-spin" />
                      ) : (
                        <RefreshCw className="mr-2 size-4" />
                      )}
                      Refresh
                    </Button>
                  </div>
                </div>
              </CardHeader>
              <CardContent className="space-y-4">
                {sessionsLoading && sessions.length === 0 ? (
                  <div className="flex items-center justify-center py-8">
                    <Loader2 className="text-muted-foreground size-6 animate-spin" />
                    <span className="text-muted-foreground ml-2 text-sm">
                      Loading sessions...
                    </span>
                  </div>
                ) : sessions.length === 0 ? (
                  <div className="text-muted-foreground py-8 text-center">
                    <Monitor className="mx-auto mb-2 size-8 opacity-40" />
                    <p className="text-sm">No active sessions found</p>
                  </div>
                ) : (
                  sessions.map((session) => (
                    <div
                      key={session.id}
                      className={`flex items-center justify-between rounded-lg border p-4 ${
                        session.is_current
                          ? 'border-primary/30 bg-primary/5'
                          : ''
                      }`}
                    >
                      <div className="flex items-center space-x-4">
                        <div className="text-muted-foreground">
                          {getDeviceIcon(
                            session.device_type,
                            session.user_agent,
                          )}
                        </div>
                        <div className="space-y-1">
                          <div className="flex flex-wrap items-center gap-2">
                            <span className="font-medium">
                              {session.device_name ||
                                (session.browser && session.os
                                  ? `${session.browser} on ${session.os}`
                                  : session.device_type || 'Unknown Device')}
                            </span>
                            {session.is_current && (
                              <Badge variant="default" className="text-xs">
                                Current Session
                              </Badge>
                            )}
                            {session.revoked && (
                              <Badge
                                variant="destructive"
                                className="text-xs"
                              >
                                Revoked
                              </Badge>
                            )}
                          </div>
                          <div className="text-muted-foreground flex flex-wrap items-center gap-3 text-xs">
                            {session.ip_address && (
                              <span className="flex items-center gap-1">
                                <Globe className="size-3" />
                                {session.ip_address}
                              </span>
                            )}
                            {session.browser && (
                              <span className="flex items-center gap-1">
                                <Monitor className="size-3" />
                                {session.browser}
                              </span>
                            )}
                            <span className="flex items-center gap-1">
                              <Activity className="size-3" />
                              Last active{' '}
                              {formatRelativeTime(session.last_activity_at)}
                            </span>
                          </div>
                        </div>
                      </div>
                      {!session.is_current && !session.revoked && (
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => handleRevokeSession(session.id)}
                          disabled={revokingSession === session.id}
                        >
                          {revokingSession === session.id ? (
                            <Loader2 className="mr-2 size-4 animate-spin" />
                          ) : (
                            <LogOut className="mr-2 size-4" />
                          )}
                          Revoke
                        </Button>
                      )}
                    </div>
                  ))
                )}

                {sessions.length > 1 && (
                  <>
                    <Separator />
                    <div className="flex items-center justify-between">
                      <div>
                        <h4 className="text-sm font-medium">
                          Sign out all other devices
                        </h4>
                        <p className="text-muted-foreground text-xs">
                          This will revoke all sessions except your current one
                        </p>
                      </div>
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={handleRevokeAllSessions}
                        disabled={revokingAll}
                      >
                        {revokingAll ? (
                          <Loader2 className="mr-2 size-4 animate-spin" />
                        ) : (
                          <LogOut className="mr-2 size-4" />
                        )}
                        Sign Out All Others
                      </Button>
                    </div>
                  </>
                )}
              </CardContent>
            </Card>
          </TabsContent>

          {/* ============================================================= */}
          {/* TAB 4: DEVICES                                                */}
          {/* ============================================================= */}
          <TabsContent value="devices" className="space-y-6">
            <Card>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <div>
                    <CardTitle className="flex items-center space-x-2">
                      <Smartphone className="size-5" />
                      <span>Trusted Devices</span>
                    </CardTitle>
                    <CardDescription>
                      Manage devices that are trusted for sign-in. Trusted
                      devices may skip MFA verification.
                    </CardDescription>
                  </div>
                  <div className="flex gap-2">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={fetchDevices}
                      disabled={devicesLoading}
                    >
                      {devicesLoading ? (
                        <Loader2 className="mr-2 size-4 animate-spin" />
                      ) : (
                        <RefreshCw className="mr-2 size-4" />
                      )}
                      Refresh
                    </Button>
                    <Button
                      size="sm"
                      onClick={handleTrustDevice}
                      disabled={trustingDevice}
                    >
                      {trustingDevice ? (
                        <Loader2 className="mr-2 size-4 animate-spin" />
                      ) : (
                        <Plus className="mr-2 size-4" />
                      )}
                      Trust This Device
                    </Button>
                  </div>
                </div>
              </CardHeader>
              <CardContent className="space-y-4">
                {devicesLoading && devices.length === 0 ? (
                  <div className="flex items-center justify-center py-8">
                    <Loader2 className="text-muted-foreground size-6 animate-spin" />
                    <span className="text-muted-foreground ml-2 text-sm">
                      Loading devices...
                    </span>
                  </div>
                ) : devices.length === 0 ? (
                  <div className="text-muted-foreground py-8 text-center">
                    <Smartphone className="mx-auto mb-2 size-8 opacity-40" />
                    <p className="text-sm">No trusted devices</p>
                    <p className="text-xs">
                      Trust this device to skip MFA on future sign-ins
                    </p>
                  </div>
                ) : (
                  devices.map((device) => (
                    <div
                      key={device.id}
                      className={`flex items-center justify-between rounded-lg border p-4 ${
                        device.is_current
                          ? 'border-primary/30 bg-primary/5'
                          : ''
                      }`}
                    >
                      <div className="flex items-center space-x-4">
                        <div className="text-muted-foreground">
                          {getDeviceIcon(
                            device.os?.toLowerCase().includes('android') ||
                              device.os?.toLowerCase().includes('ios')
                              ? 'mobile'
                              : null,
                            device.browser,
                          )}
                        </div>
                        <div className="space-y-1">
                          <div className="flex flex-wrap items-center gap-2">
                            <span className="font-medium">
                              {device.device_name}
                            </span>
                            {device.is_current && (
                              <Badge variant="default" className="text-xs">
                                Current Device
                              </Badge>
                            )}
                            <Badge
                              variant="secondary"
                              className="text-xs"
                            >
                              <ShieldCheck className="mr-1 size-3" />
                              Trusted
                            </Badge>
                          </div>
                          <div className="text-muted-foreground flex flex-wrap items-center gap-3 text-xs">
                            {device.os && (
                              <span className="flex items-center gap-1">
                                <Monitor className="size-3" />
                                {device.os}
                                {device.browser ? ` / ${device.browser}` : ''}
                              </span>
                            )}
                            {device.location && (
                              <span className="flex items-center gap-1">
                                <MapPin className="size-3" />
                                {device.location}
                              </span>
                            )}
                            {device.ip_address && (
                              <span className="flex items-center gap-1">
                                <Globe className="size-3" />
                                {device.ip_address}
                              </span>
                            )}
                            <span className="flex items-center gap-1">
                              <ShieldCheck className="size-3" />
                              Trusted{' '}
                              {formatRelativeTime(device.trusted_at)}
                            </span>
                            {device.last_used_at && (
                              <span className="flex items-center gap-1">
                                <Activity className="size-3" />
                                Last used{' '}
                                {formatRelativeTime(device.last_used_at)}
                              </span>
                            )}
                          </div>
                        </div>
                      </div>
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => handleRevokeDeviceTrust(device.id)}
                        disabled={revokingDevice === device.id}
                      >
                        {revokingDevice === device.id ? (
                          <Loader2 className="mr-2 size-4 animate-spin" />
                        ) : (
                          <ShieldOff className="mr-2 size-4" />
                        )}
                        Revoke Trust
                      </Button>
                    </div>
                  ))
                )}
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>
      </div>
    </div>
  )
}
