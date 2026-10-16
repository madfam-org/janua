'use client'

import { Suspense, useCallback, useEffect, useRef, useState } from 'react'
import Link from 'next/link'
import { useSearchParams } from 'next/navigation'
import { useJanua } from '@janua/nextjs/app/client'
import { useAuth } from '@/lib/auth'
import { browserConsoleConfig } from '@janua/ui/console-runtime'

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i
const TOKEN = /^[A-Za-z0-9_-]{32,128}$/
const UNKNOWN = 'The acceptance result is unconfirmed. Do not submit again. Check the invitation status without sending another acceptance.'

type Phase = 'loading' | 'ready' | 'blocked' | 'sending' | 'unknown' | 'accepted'
type NativeSelf = { id: string; email: string; status: string; is_service_account: boolean }
type Invitation = { valid: boolean; email: string; organization_id: string; organization_name: string; role: string }
type Verification = { self: NativeSelf; invitation: Invitation; bearer: string; marker: string }

function apiEndpoint(baseURL: string): string {
  const base = new URL(baseURL)
  const declared = new URL(browserConsoleConfig('dashboard').apiOrigin)
  if (base.href !== declared.href || base.protocol !== 'https:' || base.username || base.password ||
      base.pathname !== '/' || base.search || base.hash) {
    throw new Error('The configured API address cannot be used for invitation acceptance.')
  }
  return new URL('/api/v1/invitations/accept', base).href
}

async function invitationMarker(token: string, endpoint: string): Promise<string> {
  const hash = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(`${endpoint}\n${token}`))
  return `janua.invitation.accept.${Array.from(new Uint8Array(hash), byte => byte.toString(16).padStart(2, '0')).join('')}`
}

function nativeSelf(value: unknown): NativeSelf {
  const self = value as Partial<NativeSelf> | null
  if (!self || typeof self.id !== 'string' || !UUID.test(self.id) ||
      typeof self.email !== 'string' || self.email.length > 254 ||
      self.status !== 'active' || self.is_service_account !== false) {
    throw new Error('An active human account must be verified before accepting this invitation.')
  }
  return self as NativeSelf
}

function nativeInvitation(value: unknown): Invitation {
  const invitation = value as Partial<Invitation> | null
  if (!invitation || typeof invitation.valid !== 'boolean' ||
      typeof invitation.email !== 'string' || invitation.email.length > 254 ||
      typeof invitation.organization_id !== 'string' || !UUID.test(invitation.organization_id)) {
    throw new Error('The invitation could not be verified.')
  }
  if (invitation.valid && (typeof invitation.organization_name !== 'string' ||
      invitation.organization_name.length > 200 ||
      !['owner', 'admin', 'member', 'viewer'].includes(invitation.role || ''))) {
    throw new Error('The invitation details could not be verified.')
  }
  return invitation as Invitation
}

function InvitationForm() {
  const searchParams = useSearchParams()
  const tokens = searchParams.getAll('token')
  const token = tokens.length === 1 && TOKEN.test(tokens[0] || '') ? tokens[0]! : null
  const { client } = useJanua()
  const auth = useAuth()
  const currentAuth = useRef(auth)
  currentAuth.current = auth
  const [phase, setPhase] = useState<Phase>('loading')
  const [message, setMessage] = useState('Verifying your account and invitation…')
  const [verification, setVerification] = useState<Verification | null>(null)
  const busy = useRef(false)
  const attempted = useRef(false)

  const verify = useCallback(async (): Promise<Verification> => {
    if (!token) throw new Error('This invitation link is missing a valid token.')
    const endpoint = apiEndpoint(client.getConfig().baseURL)
    const before = await client.getAccessToken()
    if (!before) throw new Error('Sign in to the invited account to continue.')
    const self = nativeSelf(await client.users.getCurrentUser())
    const after = await client.getAccessToken()
    const now = currentAuth.current
    if (before !== after || !now.isAuthenticated || now.user?.id !== self.id ||
        now.user?.email !== self.email) {
      throw new Error('Your session changed. Reload this page to verify your account before continuing.')
    }
    const invitation = nativeInvitation(await client.invitations.validateToken(token))
    if (invitation.email !== self.email) {
      throw new Error('This invitation belongs to a different account. Sign in with the invited account.')
    }
    if (await client.getAccessToken() !== before) {
      throw new Error('Your session changed. Reload this page to verify your account before continuing.')
    }
    return { self, invitation, bearer: before, marker: await invitationMarker(token, endpoint) }
  }, [client, token])

  useEffect(() => {
    let cancelled = false
    if (auth.isLoading) return
    setVerification(null)
    if (!auth.isAuthenticated) {
      setPhase(attempted.current ? 'unknown' : 'blocked')
      setMessage(attempted.current ? UNKNOWN : 'Sign in to the invited account to continue.')
      return
    }
    setPhase('loading')
    verify().then(result => {
      if (cancelled) return
      setVerification(result)
      if (sessionStorage.getItem(result.marker) !== null || attempted.current) {
        attempted.current = true
        setPhase('unknown')
        setMessage(UNKNOWN)
      } else if (!result.invitation.valid) {
        setPhase('blocked')
        setMessage('This invitation is no longer pending. No acceptance was sent from this page.')
      } else {
        setPhase('ready')
        setMessage('Verify the account and organization below, then accept once.')
      }
    }).catch(() => {
      if (!cancelled) {
        setPhase(attempted.current ? 'unknown' : 'blocked')
        setMessage(attempted.current ? UNKNOWN : 'Your account or invitation could not be verified. Sign in with the invited account and reload this page.')
      }
    })
    return () => { cancelled = true }
  }, [auth.isAuthenticated, auth.isLoading, auth.user?.id, auth.user?.email, verify])

  async function accept(event: React.FormEvent) {
    event.preventDefault()
    if (busy.current || attempted.current || phase !== 'ready' || !verification || !token) return
    busy.current = true
    setPhase('sending')
    setMessage('Verifying your account before submitting…')
    let timer: ReturnType<typeof setTimeout> | undefined
    try {
      const fresh = await verify()
      if (!fresh.invitation.valid || fresh.self.id !== verification.self.id ||
          fresh.bearer !== verification.bearer ||
          fresh.invitation.organization_id !== verification.invitation.organization_id ||
          fresh.invitation.role !== verification.invitation.role ||
          !currentAuth.current.isAuthenticated || currentAuth.current.user?.id !== fresh.self.id ||
          currentAuth.current.user?.email !== fresh.self.email) {
        throw new Error('Account or invitation changed before submission.')
      }
      // Retain uncertainty before transport. If storage is unavailable, no POST
      // is sent. Reloading this tab cannot silently replay an unknown attempt.
      if (sessionStorage.getItem(fresh.marker) !== null) {
        attempted.current = true
        throw new Error('An earlier acceptance attempt is retained.')
      }
      sessionStorage.setItem(fresh.marker, 'unconfirmed')
      attempted.current = true
      const controller = new AbortController()
      timer = setTimeout(() => controller.abort(), 10_000)
      setMessage('Submitting once…')
      // The SDK retries mutations, including after 401. This bounded page-only
      // transport deliberately uses the verified provider token without retry.
      const response = await fetch(apiEndpoint(client.getConfig().baseURL), {
        method: 'POST', credentials: 'omit', redirect: 'error', cache: 'no-store',
        referrerPolicy: 'no-referrer', signal: controller.signal,
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${fresh.bearer}` },
        body: JSON.stringify({ token }),
      })
      if (!response.ok) throw new Error('Acceptance unconfirmed.')
      const text = await response.text()
      if (text.length > 8192) throw new Error('Acceptance unconfirmed.')
      const receipt = JSON.parse(text)
      if (receipt?.success !== true || receipt.user_id !== fresh.self.id ||
          receipt.organization_id !== fresh.invitation.organization_id || receipt.is_new_user !== false ||
          await client.getAccessToken() !== fresh.bearer ||
          !currentAuth.current.isAuthenticated || currentAuth.current.user?.id !== fresh.self.id ||
          currentAuth.current.user?.email !== fresh.self.email) {
        throw new Error('Acceptance unconfirmed.')
      }
      setPhase('accepted')
      setMessage('Invitation accepted. The API confirmed acceptance for this account and organization.')
    } catch {
      setPhase(attempted.current ? 'unknown' : 'blocked')
      setMessage(attempted.current ? UNKNOWN : 'Your account or invitation changed, or the attempt could not be retained. No acceptance was sent. Reload to verify before continuing.')
    } finally {
      if (timer) clearTimeout(timer)
      busy.current = false
    }
  }

  async function checkStatus() {
    if (busy.current) return
    busy.current = true
    setMessage('Checking account and invitation status without sending acceptance…')
    try {
      const result = await verify()
      setVerification(result)
      setMessage(result.invitation.valid
        ? 'The invitation is still pending. The previous acceptance remains unconfirmed; no second acceptance will be sent.'
        : 'The invitation is no longer pending. This read does not confirm active membership or simulator access. Ask an organization administrator to verify the result.')
    } catch {
      setMessage('The result remains unconfirmed. Account or invitation status could not be verified. No second acceptance was sent.')
    } finally {
      busy.current = false
    }
  }

  const returnPath = token ? `/invitations/accept?${new URLSearchParams({ token })}` : '/invitations/accept'
  const loginPath = `/login?${new URLSearchParams({ redirect: returnPath, reason: 'session_expired' })}`
  return (
    <main className="mx-auto max-w-lg space-y-6 p-6">
      <h1 className="text-2xl font-semibold">Accept organization invitation</h1>
      <p role="status" aria-live="polite">{message}</p>
      {verification && (
        <dl className="space-y-2 break-words">
          <dt className="font-medium">Signed-in account</dt><dd>{verification.self.email}</dd>
          <dt className="font-medium">Organization</dt><dd>{verification.invitation.organization_name || 'Invitation organization'}</dd>
          {verification.invitation.valid && <><dt className="font-medium">Role</dt><dd>{verification.invitation.role}</dd></>}
        </dl>
      )}
      {(phase === 'ready' || phase === 'sending') && (
        <form onSubmit={accept}>
          <button className="rounded bg-primary px-4 py-2 text-primary-foreground disabled:opacity-50" type="submit" disabled={phase === 'sending'}>
            {phase === 'sending' ? 'Submitting…' : 'Accept invitation'}
          </button>
        </form>
      )}
      {phase === 'unknown' && <button className="rounded border px-4 py-2" type="button" onClick={checkStatus}>Check invitation status</button>}
      {(phase === 'blocked' || phase === 'unknown') && token && <Link href={loginPath} referrerPolicy="no-referrer">Sign in with the invited account</Link>}
      {phase === 'accepted' && <Link href="/">Continue to dashboard</Link>}
      <p className="text-sm text-muted-foreground">Acceptance joins the organization. Simulator access and task accreditation are verified separately.</p>
    </main>
  )
}

export default function InvitationAcceptPage() {
  return <Suspense fallback={<p role="status">Loading invitation…</p>}><InvitationForm /></Suspense>
}
