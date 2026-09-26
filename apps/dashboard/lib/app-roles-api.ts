/**
 * Delegated application-role administration.
 *
 * Wraps `/api/v1/organizations/{orgId}/app-roles[/{app}[/grant|/revoke]]`: a member
 * holding `<app>:admin` in an organization manages roles OF THAT APP in THAT
 * organization. The API is the authority; this module only calls it.
 *
 * A granted or revoked role reaches the member's token at their next sign-in or
 * token refresh, not instantly.
 */

import { januaClient } from './janua-client'

export interface AppRoleMember {
  user_id: string
  email: string | null
  name: string | null
}

export interface DelegatedAppRoleGrant {
  id: string
  user_id: string
  email: string | null
  name: string | null
  role: string
  claim_value: string
  granted_by: string | null
  granted_at: string | null
}

export interface DelegatedAppRoleList {
  organization_id: string
  app: string
  caller_user_id: string
  caller_roles: string[]
  grants: DelegatedAppRoleGrant[]
  members: AppRoleMember[]
}

export interface MyAppRoles {
  organization_id: string
  user_id: string
  claim_values: string[]
  administered_apps: string[]
}

export interface AppRoleChange {
  id: string | null
  organization_id: string
  user_id: string
  app: string
  role: string
  claim_value: string
  granted_at: string | null
  revoked_at: string | null
  changed: boolean
}

function basePath(orgId: string): string {
  return `/api/v1/organizations/${encodeURIComponent(orgId)}/app-roles`
}

/** The dashboard route of the delegated admin page for one app. */
export function appRolesAdminPath(orgId: string, app: string): string {
  return `/organizations/${encodeURIComponent(orgId)}/app-roles/${encodeURIComponent(app)}`
}

export async function getMyAppRoles(orgId: string): Promise<MyAppRoles> {
  const response = await januaClient.http.get<MyAppRoles>(basePath(orgId))
  return response.data
}

export async function listAppRoleGrants(orgId: string, app: string): Promise<DelegatedAppRoleList> {
  const response = await januaClient.http.get<DelegatedAppRoleList>(
    `${basePath(orgId)}/${encodeURIComponent(app)}`,
  )
  return response.data
}

export async function grantAppRole(
  orgId: string,
  app: string,
  target: { user_id: string } | { email: string },
  role: string,
): Promise<AppRoleChange> {
  const response = await januaClient.http.post<AppRoleChange>(
    `${basePath(orgId)}/${encodeURIComponent(app)}/grant`,
    { ...target, role },
  )
  return response.data
}

export async function revokeAppRole(
  orgId: string,
  app: string,
  userId: string,
  role: string,
): Promise<AppRoleChange> {
  const response = await januaClient.http.post<AppRoleChange>(
    `${basePath(orgId)}/${encodeURIComponent(app)}/revoke`,
    { user_id: userId, role },
  )
  return response.data
}

/** HTTP status of a failed SDK call, when the error carries one. */
export function errorStatus(err: unknown): number | undefined {
  if (err && typeof err === 'object') {
    const e = err as { statusCode?: unknown; status?: unknown }
    if (typeof e.statusCode === 'number') return e.statusCode
    if (typeof e.status === 'number') return e.status
  }
  return undefined
}
