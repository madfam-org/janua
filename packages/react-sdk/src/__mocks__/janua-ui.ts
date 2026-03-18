// Mock for @janua/ui subpath imports used by react-sdk components
// These mocks render realistic form elements so that react-sdk tests
// can interact with inputs, buttons, labels, etc.
//
// All forms use noValidate to bypass HTML5 browser validation and rely on
// JavaScript validation in handleSubmit instead. This ensures consistent
// behavior across jsdom versions while keeping correct HTML attributes
// (type="email", required, etc.) for accessibility tests.
import React, { useState, useCallback, useRef } from 'react'

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function isValidEmail(email: string): boolean {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)
}

// Try to get useJanua safely (may be mocked or absent)
function tryUseJanua(): any {
  try {
    // eslint-disable-next-line @typescript-eslint/no-var-requires
    const mod = require('../provider')
    if (mod && typeof mod.useJanua === 'function') {
      return mod.useJanua()
    }
  } catch {
    // Not available
  }
  return null
}

// Try to get next/navigation router safely
function tryUseRouter(): any {
  try {
    // eslint-disable-next-line @typescript-eslint/no-var-requires
    const mod = require('next/navigation')
    if (mod && typeof mod.useRouter === 'function') {
      return mod.useRouter()
    }
  } catch {
    // Not available
  }
  return null
}

// ---------------------------------------------------------------------------
// SignIn mock
// ---------------------------------------------------------------------------

export const SignIn = React.forwardRef(function MockSignIn(props: any, ref: any) {
  const {
    januaClient,
    className,
    redirectUrl,
    afterSignIn,
    onError,
    signUpUrl,
    socialProviders,
  } = props

  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [showPw, setShowPw] = useState(false)
  const [remember, setRemember] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const formRef = useRef<HTMLFormElement>(null)

  const ctx = tryUseJanua()
  const router = tryUseRouter()

  const doSignIn = (ctx && typeof ctx.signIn === 'function')
    ? ctx.signIn
    : (januaClient && typeof januaClient.signIn === 'function')
      ? (params: { email: string; password: string }) =>
          januaClient.signIn(params.email, params.password)
      : null

  const doSocialSignIn = (ctx && typeof ctx.signInWithOAuth === 'function')
    ? ctx.signInWithOAuth
    : null

  const handleSubmit = useCallback(
    async (e: React.FormEvent) => {
      e.preventDefault()
      setError(null)

      if (!isValidEmail(email)) {
        setError('Invalid email address')
        return
      }
      if (password.length < 8) {
        setError('Password must be at least 8 characters')
        return
      }

      if (!doSignIn) return

      setSubmitting(true)
      try {
        const result = await doSignIn({ email, password })
        afterSignIn?.(result)
        setEmail('')
        setPassword('')
        if (redirectUrl && router) {
          router.push(redirectUrl)
        }
      } catch (err: any) {
        const msg = err instanceof Error ? err.message : 'Sign in failed'
        setError(msg)
        onError?.(err instanceof Error ? err : new Error(msg))
      } finally {
        setSubmitting(false)
      }
    },
    [email, password, doSignIn, afterSignIn, onError, redirectUrl, router]
  )

  const handleForgotPassword = useCallback(() => {
    if (router) router.push('/auth/forgot-password')
  }, [router])

  const socialProviderList: string[] = (() => {
    if (!socialProviders) return []
    if (Array.isArray(socialProviders)) return socialProviders
    return Object.entries(socialProviders)
      .filter(([, v]) => v)
      .map(([k]) => k)
  })()

  return React.createElement(
    'form',
    {
      ref: ref || formRef,
      role: 'form',
      noValidate: true,
      className: className || undefined,
      onSubmit: handleSubmit,
      'data-testid': 'mock-SignIn',
    },
    error && React.createElement('div', { role: 'alert' }, error),
    React.createElement('label', { htmlFor: 'signin-email' }, 'Email'),
    React.createElement('input', { id: 'signin-email', type: 'email', value: email, disabled: submitting, onChange: (e: any) => setEmail(e.target.value) }),
    React.createElement('label', { htmlFor: 'signin-password' }, 'Password'),
    React.createElement('input', { id: 'signin-password', type: showPw ? 'text' : 'password', value: password, disabled: submitting, onChange: (e: any) => setPassword(e.target.value) }),
    React.createElement('button', { type: 'button', 'aria-label': showPw ? 'Hide password' : 'Show password', onClick: () => setShowPw((p: boolean) => !p) }, showPw ? 'Hide' : 'Show'),
    React.createElement('label', { htmlFor: 'signin-remember' }, 'Remember me'),
    React.createElement('input', { id: 'signin-remember', type: 'checkbox', checked: remember, onChange: () => setRemember((r: boolean) => !r) }),
    React.createElement('button', { type: 'submit', disabled: submitting }, submitting ? 'Signing in...' : 'Sign in'),
    React.createElement('a', { href: '#', onClick: (e: any) => { e.preventDefault(); handleForgotPassword() } }, 'Forgot password?'),
    signUpUrl && React.createElement('span', null, "Don't have an account? ", React.createElement('a', { href: signUpUrl, role: 'link' }, 'Sign up')),
    socialProviderList.length > 0 && socialProviderList.map((provider: string) =>
      React.createElement('button', { key: provider, type: 'button', onClick: () => doSocialSignIn?.(provider) }, `Sign in with ${provider}`)
    )
  )
})

// ---------------------------------------------------------------------------
// SignUp mock
// ---------------------------------------------------------------------------

export const SignUp = React.forwardRef(function MockSignUp(props: any, ref: any) {
  const { januaClient, className, redirectUrl, afterSignUp, onError, requireOrganization, requireEmailVerification } = props

  const [firstName, setFirstName] = useState('')
  const [lastName, setLastName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [organization, setOrganization] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const formRef = useRef<HTMLFormElement>(null)

  const handleSubmit = useCallback(
    async (e: React.FormEvent) => {
      e.preventDefault()
      setError(null)

      if (!firstName || !email || !password) return
      if (!isValidEmail(email)) return
      if (!januaClient) return

      setSubmitting(true)
      try {
        const fullName = lastName ? `${firstName} ${lastName}` : firstName
        await januaClient.signUp({ email, password, given_name: firstName, family_name: lastName, name: fullName })

        if (!requireEmailVerification) {
          await januaClient.signIn(email, password)
          afterSignUp?.()
          if (redirectUrl && typeof window !== 'undefined') window.location.href = redirectUrl
        } else {
          afterSignUp?.()
          if (typeof window !== 'undefined') window.location.href = '/verify-email'
        }
      } catch (err: any) {
        const msg = err instanceof Error ? err.message : 'Registration failed'
        setError(msg)
        onError?.(err instanceof Error ? err : new Error(msg))
      } finally {
        setSubmitting(false)
      }
    },
    [januaClient, firstName, lastName, email, password, organization, requireOrganization, requireEmailVerification, afterSignUp, onError, redirectUrl]
  )

  return React.createElement(
    'form',
    { ref: ref || formRef, noValidate: true, className: `janua-signup ${className || ''}`.trim(), onSubmit: handleSubmit, 'data-testid': 'mock-SignUp' },
    error && React.createElement('div', { role: 'alert' }, error),
    React.createElement('label', { htmlFor: 'signup-firstname' }, 'First name'),
    React.createElement('input', { id: 'signup-firstname', type: 'text', required: true, value: firstName, onChange: (e: any) => setFirstName(e.target.value) }),
    React.createElement('label', { htmlFor: 'signup-lastname' }, 'Last name'),
    React.createElement('input', { id: 'signup-lastname', type: 'text', required: true, value: lastName, onChange: (e: any) => setLastName(e.target.value) }),
    React.createElement('label', { htmlFor: 'signup-email' }, 'Email'),
    React.createElement('input', { id: 'signup-email', type: 'email', required: true, placeholder: 'you@example.com', value: email, onChange: (e: any) => setEmail(e.target.value) }),
    React.createElement('label', { htmlFor: 'signup-password' }, 'Password'),
    React.createElement('input', { id: 'signup-password', type: 'password', required: true, placeholder: '\u2022\u2022\u2022\u2022\u2022\u2022\u2022\u2022', value: password, onChange: (e: any) => setPassword(e.target.value) }),
    React.createElement('p', null, 'At least 8 characters with uppercase, lowercase and numbers'),
    requireOrganization && React.createElement(
      React.Fragment, null,
      React.createElement('label', { htmlFor: 'signup-org' }, 'Organization name'),
      React.createElement('input', { id: 'signup-org', type: 'text', required: true, placeholder: 'Acme Corporation', value: organization, onChange: (e: any) => setOrganization(e.target.value) })
    ),
    React.createElement('button', { type: 'submit', disabled: submitting }, submitting ? 'Creating account...' : 'Create account')
  )
})

// ---------------------------------------------------------------------------
// UserProfile mock
// ---------------------------------------------------------------------------

export const UserProfile = React.forwardRef(function MockUserProfile(props: any, ref: any) {
  const { className, user, onUpdateProfile, onSignOut } = props

  const ctx = tryUseJanua()
  const ctxUser = ctx?.user || null
  const ctxSession = ctx?.session || null
  const ctxLoading = ctx?.loading || ctx?.isLoading || false
  const ctxSignOut = ctx?.signOut || null
  const ctxClient = ctx?.client || null

  const displayUser = user || ctxUser
  const displaySession = ctxSession

  const [editing, setEditing] = useState(false)
  const [editFirstName, setEditFirstName] = useState('')
  const [editLastName, setEditLastName] = useState('')
  const [editEmail, setEditEmail] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  const startEdit = useCallback(() => {
    if (displayUser) {
      setEditFirstName(displayUser.given_name || displayUser.firstName || '')
      setEditLastName(displayUser.family_name || displayUser.lastName || '')
      setEditEmail(displayUser.email || '')
    }
    setError(null)
    setEditing(true)
  }, [displayUser])

  const cancelEdit = useCallback(() => { setEditing(false); setError(null) }, [])

  const handleSave = useCallback(
    async (e: React.FormEvent) => {
      e.preventDefault()
      setError(null)
      if (editEmail && !isValidEmail(editEmail)) return

      setSaving(true)
      try {
        if (ctxClient && typeof ctxClient.updateUser === 'function') {
          await ctxClient.updateUser({ given_name: editFirstName, family_name: editLastName, email: editEmail })
        } else if (onUpdateProfile) {
          await onUpdateProfile({ given_name: editFirstName, family_name: editLastName, email: editEmail })
        }
        setEditing(false)
      } catch (err: any) {
        const msg = err instanceof Error ? err.message : 'Profile update failed'
        setError(msg)
        if (props.onError) props.onError(err instanceof Error ? err : new Error(msg))
      } finally {
        setSaving(false)
      }
    },
    [editFirstName, editLastName, editEmail, onUpdateProfile, ctxClient, props]
  )

  const handleSignOut = useCallback(() => {
    if (ctxSignOut) ctxSignOut()
    else if (onSignOut) onSignOut()
  }, [onSignOut, ctxSignOut])

  if (ctxLoading) return React.createElement('div', { className, ref }, 'Loading...')
  if (!displayUser) return React.createElement('div', { className, ref }, 'No user data available')

  const displayName =
    displayUser.name ||
    [displayUser.given_name || displayUser.firstName, displayUser.family_name || displayUser.lastName]
      .filter(Boolean).join(' ') ||
    displayUser.email

  // Organization info: check both displayUser (prop) and ctxUser (context)
  const orgName = displayUser.organization_name || ctxUser?.organization_name
  const orgRole = displayUser.organization_role || ctxUser?.organization_role

  if (editing) {
    return React.createElement(
      'form',
      { ref, noValidate: true, className: className || undefined, onSubmit: handleSave, 'data-testid': 'mock-UserProfile' },
      error && React.createElement('div', { role: 'alert' }, error),
      React.createElement('label', { htmlFor: 'profile-firstname' }, 'First name'),
      React.createElement('input', { id: 'profile-firstname', type: 'text', required: true, value: editFirstName, onChange: (e: any) => setEditFirstName(e.target.value) }),
      React.createElement('label', { htmlFor: 'profile-lastname' }, 'Last name'),
      React.createElement('input', { id: 'profile-lastname', type: 'text', required: true, value: editLastName, onChange: (e: any) => setEditLastName(e.target.value) }),
      React.createElement('label', { htmlFor: 'profile-email' }, 'Email'),
      React.createElement('input', { id: 'profile-email', type: 'email', required: true, value: editEmail, onChange: (e: any) => setEditEmail(e.target.value) }),
      React.createElement('button', { type: 'submit', disabled: saving }, saving ? 'Saving...' : 'Save'),
      React.createElement('button', { type: 'button', onClick: cancelEdit }, 'Cancel')
    )
  }

  const editDisabled = !ctxClient && !onUpdateProfile

  return React.createElement(
    'div',
    { ref, className: className || undefined, 'data-testid': 'mock-UserProfile' },
    React.createElement('span', null, displayName),
    React.createElement('span', null, displayUser.email),
    orgName && React.createElement('span', null, orgName),
    orgRole && React.createElement('span', null, orgRole),
    displaySession && React.createElement(
      React.Fragment, null,
      React.createElement('span', null, 'Session expires in ' + displaySession.expires_in + 's'),
      React.createElement('span', null, 'Token type: ' + displaySession.token_type)
    ),
    React.createElement('button', { type: 'button', disabled: editDisabled, onClick: startEdit }, 'Edit profile'),
    React.createElement('button', { type: 'button', onClick: handleSignOut }, 'Sign out')
  )
})

// ---------------------------------------------------------------------------
// Other component stubs
// ---------------------------------------------------------------------------

const createStubComponent = (name: string) =>
  React.forwardRef((props: any, ref: any) =>
    React.createElement('div', { ...props, ref, 'data-testid': `mock-${name}` })
  )

export const UserButton = createStubComponent('UserButton')
export const OrganizationSwitcher = createStubComponent('OrganizationSwitcher')
export const MFAChallenge = createStubComponent('MFAChallenge')
