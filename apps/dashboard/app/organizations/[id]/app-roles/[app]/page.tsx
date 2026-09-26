'use client'

import { useCallback, useEffect, useMemo, useState } from 'react'
import { useParams, useRouter } from 'next/navigation'
import {
  Badge,
  Button,
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
  Input,
} from '@janua/ui'
import { AlertCircle, ArrowLeft, KeyRound, Loader2, RefreshCw, ShieldOff, UserPlus } from 'lucide-react'
import {
  errorStatus,
  grantAppRole,
  listAppRoleGrants,
  revokeAppRole,
  type AppRoleMember,
  type DelegatedAppRoleList,
} from '@/lib/app-roles-api'

const ADMIN_ROLE = 'admin'
const ROLE_SHAPE = /^[^\s:]{1,64}$/

type LoadFailure = { kind: 'no-membership' | 'not-admin' | 'error'; message: string }

function describeMember(member: { name: string | null; email: string | null; user_id: string }) {
  return member.name ? `${member.name} (${member.email ?? member.user_id})` : member.email ?? member.user_id
}

function toLoadFailure(err: unknown, app: string): LoadFailure {
  const status = errorStatus(err)
  if (status === 404) {
    return { kind: 'no-membership', message: 'You are not an active member of this organization.' }
  }
  if (status === 403) {
    return {
      kind: 'not-admin',
      message: `Managing these roles requires the ${app}:${ADMIN_ROLE} role in this organization.`,
    }
  }
  return {
    kind: 'error',
    message: err instanceof Error ? err.message : 'The request failed.',
  }
}

// The SDK does not surface janua's error envelope text, so action failures are
// explained from the status code, which the API keeps meaningful per route.
function actionFailureMessage(err: unknown, action: 'grant' | 'revoke'): string {
  switch (errorStatus(err)) {
    case 403:
      return 'Not allowed: your own admin role can only be changed by another admin of this app, and only admins of this app can change its roles.'
    case 404:
      return 'That person is not an active member of this organization.'
    case 409:
      return action === 'revoke'
        ? 'Refused: this would leave the organization with no admin for this app.'
        : 'More than one member matches; pick the member from the list.'
    case 422:
      return 'The role is not valid: no spaces or colons, at most 64 characters.'
    case 429:
      return 'Too many changes in a short time. Wait a minute and try again.'
    default:
      return err instanceof Error ? err.message : `Could not ${action} the role.`
  }
}

export default function AppRolesAdminPage() {
  const params = useParams()
  const router = useRouter()
  const orgId = params.id as string
  const app = decodeURIComponent(params.app as string)

  const [data, setData] = useState<DelegatedAppRoleList | null>(null)
  const [loading, setLoading] = useState(true)
  const [failure, setFailure] = useState<LoadFailure | null>(null)
  const [busy, setBusy] = useState<string | null>(null)
  const [notice, setNotice] = useState<{ tone: 'ok' | 'error'; text: string } | null>(null)

  const [grantUserId, setGrantUserId] = useState('')
  const [grantRole, setGrantRole] = useState('')

  const load = useCallback(async () => {
    setLoading(true)
    setFailure(null)
    try {
      setData(await listAppRoleGrants(orgId, app))
    } catch (err) {
      setData(null)
      setFailure(toLoadFailure(err, app))
    } finally {
      setLoading(false)
    }
  }, [orgId, app])

  useEffect(() => {
    load()
  }, [load])

  const knownRoles = useMemo(() => {
    const roles = new Set<string>([ADMIN_ROLE])
    data?.grants.forEach((g) => roles.add(g.role))
    return Array.from(roles).sort()
  }, [data])

  const memberById = useMemo(() => {
    const map = new Map<string, AppRoleMember>()
    data?.members.forEach((m) => map.set(m.user_id, m))
    return map
  }, [data])

  const roleValid = ROLE_SHAPE.test(grantRole.trim())
  const selfAdminGrant =
    !!data && grantUserId === data.caller_user_id && grantRole.trim() === ADMIN_ROLE

  const handleGrant = async () => {
    if (!grantUserId || !roleValid || selfAdminGrant) return
    const role = grantRole.trim()
    setBusy('grant')
    setNotice(null)
    try {
      const result = await grantAppRole(orgId, app, { user_id: grantUserId }, role)
      const who = memberById.get(grantUserId)
      const label = who ? describeMember(who) : grantUserId
      setNotice({
        tone: 'ok',
        text: result.changed
          ? `Granted ${result.claim_value} to ${label}. It reaches their token at their next sign-in or token refresh.`
          : `${label} already has ${result.claim_value}.`,
      })
      setGrantRole('')
      await load()
    } catch (err) {
      setNotice({ tone: 'error', text: actionFailureMessage(err, 'grant') })
    } finally {
      setBusy(null)
    }
  }

  const handleRevoke = async (userId: string, role: string, label: string) => {
    setBusy(`revoke-${userId}-${role}`)
    setNotice(null)
    try {
      const result = await revokeAppRole(orgId, app, userId, role)
      setNotice({
        tone: 'ok',
        text: result.changed
          ? `Revoked ${result.claim_value} from ${label}. It leaves their token at their next sign-in or token refresh.`
          : `${label} no longer had ${result.claim_value}.`,
      })
      await load()
    } catch (err) {
      setNotice({ tone: 'error', text: actionFailureMessage(err, 'revoke') })
    } finally {
      setBusy(null)
    }
  }

  const header = (
    <div className="flex items-center gap-4">
      <Button
        variant="ghost"
        size="icon"
        onClick={() => router.push(`/organizations/${orgId}`)}
        aria-label="Back to organization"
      >
        <ArrowLeft className="size-4" />
      </Button>
      <div>
        <div className="flex items-center gap-3">
          <h2 className="text-2xl font-bold">App roles</h2>
          <Badge variant="outline">{app}</Badge>
        </div>
        <p className="text-muted-foreground">
          Grant and revoke <code>{app}:*</code> roles for members of this organization.
        </p>
      </div>
    </div>
  )

  if (loading && !data) {
    return (
      <div className="space-y-6">
        {header}
        <div className="flex items-center justify-center py-12">
          <Loader2 className="text-muted-foreground size-8 animate-spin" />
          <span className="text-muted-foreground ml-2">Loading app roles...</span>
        </div>
      </div>
    )
  }

  if (failure || !data) {
    const title =
      failure?.kind === 'not-admin'
        ? 'You cannot manage this app'
        : failure?.kind === 'no-membership'
          ? 'Organization not available'
          : 'Could not load app roles'
    return (
      <div className="space-y-6">
        {header}
        <div className="flex flex-col items-center justify-center py-12 text-center">
          {failure?.kind === 'not-admin' ? (
            <ShieldOff className="text-muted-foreground mb-4 size-12" />
          ) : (
            <AlertCircle className="text-destructive mb-4 size-12" />
          )}
          <h3 className="mb-2 text-lg font-semibold">{title}</h3>
          <p className="text-muted-foreground mb-4">{failure?.message}</p>
          {failure?.kind === 'error' && (
            <Button onClick={load} variant="outline">
              <RefreshCw className="mr-2 size-4" />
              Try Again
            </Button>
          )}
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {header}

      {notice && (
        <div
          role="status"
          className={
            notice.tone === 'ok'
              ? 'rounded-md border border-green-500/40 bg-green-500/10 px-4 py-3 text-sm'
              : 'border-destructive/40 bg-destructive/10 text-destructive rounded-md border px-4 py-3 text-sm'
          }
        >
          {notice.text}
        </div>
      )}

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Grant a role</CardTitle>
          <CardDescription>
            Roles are strings the app defines (for example <code>viewer</code> or <code>admin</code>).
            Changes reach a member&apos;s token at their next sign-in or token refresh.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid gap-3 md:grid-cols-[2fr_1fr_auto] md:items-end">
            <div className="space-y-1">
              <label htmlFor="grant-member" className="text-sm font-medium">
                Member
              </label>
              <select
                id="grant-member"
                value={grantUserId}
                onChange={(e) => setGrantUserId(e.target.value)}
                className="border-input bg-background ring-offset-background focus-visible:ring-ring flex h-10 w-full rounded-md border px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2"
              >
                <option value="">Select a member…</option>
                {data.members.map((m) => (
                  <option key={m.user_id} value={m.user_id}>
                    {describeMember(m)}
                  </option>
                ))}
              </select>
            </div>
            <div className="space-y-1">
              <label htmlFor="grant-role" className="text-sm font-medium">
                Role
              </label>
              <Input
                id="grant-role"
                list="known-app-roles"
                placeholder="viewer"
                value={grantRole}
                onChange={(e) => setGrantRole(e.target.value)}
              />
              <datalist id="known-app-roles">
                {knownRoles.map((r) => (
                  <option key={r} value={r} />
                ))}
              </datalist>
            </div>
            <Button
              onClick={handleGrant}
              disabled={!grantUserId || !roleValid || selfAdminGrant || busy !== null}
            >
              {busy === 'grant' ? (
                <Loader2 className="mr-2 size-4 animate-spin" />
              ) : (
                <UserPlus className="mr-2 size-4" />
              )}
              Grant
            </Button>
          </div>
          {grantRole.trim() !== '' && !roleValid && (
            <p className="text-destructive mt-2 text-xs">
              A role has no spaces or colons and is at most 64 characters.
            </p>
          )}
          {selfAdminGrant && (
            <p className="text-muted-foreground mt-2 text-xs">
              You cannot change your own admin role; another admin of this app must do it.
            </p>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Current grants</CardTitle>
          <CardDescription>
            Live <code>{app}:*</code> roles in this organization ({data.grants.length}).
          </CardDescription>
        </CardHeader>
        <CardContent>
          {data.grants.length === 0 ? (
            <p className="text-muted-foreground text-sm">No member holds a role in this app.</p>
          ) : (
            <ul className="divide-y">
              {data.grants.map((g) => {
                const label = describeMember(g)
                const isSelfAdmin = g.user_id === data.caller_user_id && g.role === ADMIN_ROLE
                return (
                  <li key={g.id} className="flex items-center justify-between gap-4 py-3">
                    <div className="min-w-0">
                      <p className="truncate text-sm font-medium">{label}</p>
                      <p className="text-muted-foreground text-xs">
                        {g.granted_at ? `Granted ${new Date(g.granted_at).toLocaleString()}` : 'Granted'}
                      </p>
                    </div>
                    <div className="flex shrink-0 items-center gap-3">
                      <Badge variant={g.role === ADMIN_ROLE ? 'default' : 'secondary'}>
                        <KeyRound className="mr-1 size-3" />
                        {g.claim_value}
                      </Badge>
                      <Button
                        variant="outline"
                        size="sm"
                        disabled={isSelfAdmin || busy !== null}
                        title={isSelfAdmin ? 'Another admin of this app must change your admin role' : undefined}
                        onClick={() => handleRevoke(g.user_id, g.role, label)}
                      >
                        {busy === `revoke-${g.user_id}-${g.role}` && (
                          <Loader2 className="mr-2 size-4 animate-spin" />
                        )}
                        Revoke
                      </Button>
                    </div>
                  </li>
                )
              })}
            </ul>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
