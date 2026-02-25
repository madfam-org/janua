/**
 * Typed API wrappers for endpoints without dedicated SDK methods.
 *
 * Uses januaClient.http (HttpClient) which handles auth tokens,
 * refresh, retry, and rate limiting automatically.
 */

import { januaClient } from './janua-client'

// ─── Policies ───────────────────────────────────────────────────────────────

export interface Policy {
  id: string
  name: string
  description?: string
  effect: 'allow' | 'deny'
  resource: string
  actions: string[]
  conditions?: Record<string, unknown>
  is_active: boolean
  created_at: string
  updated_at: string
}

export interface PolicyCreateRequest {
  name: string
  description?: string
  effect: 'allow' | 'deny'
  resource: string
  actions: string[]
  conditions?: Record<string, unknown>
}

export interface PolicyEvaluateRequest {
  user_id?: string
  resource: string
  action: string
  context?: Record<string, unknown>
}

export async function listPolicies(): Promise<Policy[]> {
  const response = await januaClient.http.get<Policy[]>('/api/v1/policies')
  return response.data
}

export async function createPolicy(data: PolicyCreateRequest): Promise<Policy> {
  const response = await januaClient.http.post<Policy>('/api/v1/policies', data)
  return response.data
}

export async function updatePolicy(id: string, data: Partial<PolicyCreateRequest>): Promise<Policy> {
  const response = await januaClient.http.patch<Policy>(`/api/v1/policies/${id}`, data)
  return response.data
}

export async function deletePolicy(id: string): Promise<{ message: string }> {
  const response = await januaClient.http.delete<{ message: string }>(`/api/v1/policies/${id}`)
  return response.data
}

export async function evaluatePolicy(data: PolicyEvaluateRequest): Promise<{ allowed: boolean; reason?: string }> {
  const response = await januaClient.http.post<{ allowed: boolean; reason?: string }>('/api/v1/policies/evaluate', data)
  return response.data
}

// ─── OAuth Clients ──────────────────────────────────────────────────────────

export interface OAuthClient {
  client_id: string
  client_name: string
  client_secret?: string
  redirect_uris: string[]
  grant_types: string[]
  response_types: string[]
  scope: string
  token_endpoint_auth_method: string
  is_active: boolean
  created_at: string
  updated_at: string
}

export interface OAuthClientCreateRequest {
  client_name: string
  redirect_uris: string[]
  grant_types?: string[]
  response_types?: string[]
  scope?: string
  token_endpoint_auth_method?: string
}

export async function listOAuthClients(): Promise<OAuthClient[]> {
  const response = await januaClient.http.get<OAuthClient[]>('/api/v1/oauth/clients')
  return response.data
}

export async function getOAuthClient(clientId: string): Promise<OAuthClient> {
  const response = await januaClient.http.get<OAuthClient>(`/api/v1/oauth/clients/${clientId}`)
  return response.data
}

export async function createOAuthClient(data: OAuthClientCreateRequest): Promise<OAuthClient> {
  const response = await januaClient.http.post<OAuthClient>('/api/v1/oauth/clients', data)
  return response.data
}

export async function updateOAuthClient(clientId: string, data: Partial<OAuthClientCreateRequest>): Promise<OAuthClient> {
  const response = await januaClient.http.patch<OAuthClient>(`/api/v1/oauth/clients/${clientId}`, data)
  return response.data
}

export async function deleteOAuthClient(clientId: string): Promise<{ message: string }> {
  const response = await januaClient.http.delete<{ message: string }>(`/api/v1/oauth/clients/${clientId}`)
  return response.data
}

export async function rotateClientSecret(clientId: string): Promise<{ client_secret: string }> {
  const response = await januaClient.http.post<{ client_secret: string }>(`/api/v1/oauth/clients/${clientId}/rotate`)
  return response.data
}

// ─── Billing ────────────────────────────────────────────────────────────────

export interface BillingPlan {
  id: string
  name: string
  price: number
  interval: string
  features: string[]
}

export interface BillingCurrent {
  plan: BillingPlan
  status: string
  current_period_end: string
  usage: Record<string, unknown>
}

export interface Invoice {
  id: string
  amount: number
  status: string
  created_at: string
  pdf_url?: string
}

export interface PaymentMethod {
  id: string
  type: string
  last4?: string
  brand?: string
  is_default: boolean
}

export async function getBillingCurrent(): Promise<BillingCurrent> {
  const response = await januaClient.http.get<BillingCurrent>('/api/v1/billing/current')
  return response.data
}

export async function getBillingPlans(): Promise<BillingPlan[]> {
  const response = await januaClient.http.get<BillingPlan[]>('/api/v1/billing/plans')
  return response.data
}

export async function getInvoices(): Promise<Invoice[]> {
  const response = await januaClient.http.get<Invoice[]>('/api/v1/billing/invoices')
  return response.data
}

export async function getPaymentMethods(): Promise<PaymentMethod[]> {
  const response = await januaClient.http.get<PaymentMethod[]>('/api/v1/billing/payment-methods')
  return response.data
}

export async function createCheckout(data: { plan_id: string; provider?: string }): Promise<{ checkout_url: string }> {
  const response = await januaClient.http.post<{ checkout_url: string }>('/api/v1/checkout/dhanam', data)
  return response.data
}

// ─── Email Templates ────────────────────────────────────────────────────────

export interface EmailTemplate {
  id: string
  name: string
  subject: string
  body_html: string
  body_text?: string
  variables: string[]
  is_custom: boolean
  updated_at: string
}

export async function listEmailTemplates(): Promise<EmailTemplate[]> {
  const response = await januaClient.http.get<EmailTemplate[]>('/api/v1/email/templates')
  return response.data
}

export async function updateEmailTemplate(id: string, data: Partial<EmailTemplate>): Promise<EmailTemplate> {
  const response = await januaClient.http.put<EmailTemplate>(`/api/v1/email/templates/${id}`, data)
  return response.data
}

export async function resetEmailTemplate(id: string): Promise<EmailTemplate> {
  const response = await januaClient.http.post<EmailTemplate>(`/api/v1/email/templates/${id}/reset`)
  return response.data
}

export async function previewEmailTemplate(id: string): Promise<{ html: string }> {
  const response = await januaClient.http.get<{ html: string }>(`/api/v1/email/templates/${id}/preview`)
  return response.data
}

// ─── System Settings ────────────────────────────────────────────────────────

export interface CorsOrigin {
  id: string
  origin: string
  created_at: string
}

export async function getCorsOrigins(): Promise<CorsOrigin[]> {
  const response = await januaClient.http.get<CorsOrigin[]>('/api/v1/admin/settings/cors')
  return response.data
}

export async function addCorsOrigin(data: { origin: string }): Promise<CorsOrigin> {
  const response = await januaClient.http.post<CorsOrigin>('/api/v1/admin/settings/cors', data)
  return response.data
}

export async function deleteCorsOrigin(originId: string): Promise<{ message: string }> {
  const response = await januaClient.http.delete<{ message: string }>(`/api/v1/admin/settings/cors/${originId}`)
  return response.data
}

export async function getSystemSettings(): Promise<Record<string, unknown>> {
  const response = await januaClient.http.get<Record<string, unknown>>('/api/v1/admin/settings')
  return response.data
}

export async function updateSystemSetting(key: string, data: unknown): Promise<{ message: string }> {
  const response = await januaClient.http.put<{ message: string }>(`/api/v1/admin/settings/${key}`, data)
  return response.data
}

// ─── Roles ──────────────────────────────────────────────────────────────────

export interface Role {
  id: string
  name: string
  description?: string
  permissions: string[]
  is_system: boolean
  created_at: string
  updated_at: string
}

export interface Permission {
  id: string
  name: string
  description?: string
  category: string
}

export async function listRoles(): Promise<Role[]> {
  const response = await januaClient.http.get<Role[]>('/api/v1/roles')
  return response.data
}

export async function listSystemRoles(): Promise<Role[]> {
  const response = await januaClient.http.get<Role[]>('/api/v1/roles/system')
  return response.data
}

export async function listPermissions(): Promise<Permission[]> {
  const response = await januaClient.http.get<Permission[]>('/api/v1/roles/permissions')
  return response.data
}

export async function createRole(data: { name: string; description?: string; permissions: string[] }): Promise<Role> {
  const response = await januaClient.http.post<Role>('/api/v1/roles', data)
  return response.data
}

export async function updateRole(id: string, data: Partial<{ name: string; description: string; permissions: string[] }>): Promise<Role> {
  const response = await januaClient.http.put<Role>(`/api/v1/roles/${id}`, data)
  return response.data
}

export async function deleteRole(id: string): Promise<{ message: string }> {
  const response = await januaClient.http.delete<{ message: string }>(`/api/v1/roles/${id}`)
  return response.data
}

// ─── API Keys ───────────────────────────────────────────────────────────────

export interface ApiKey {
  id: string
  name: string
  key_prefix: string
  permissions: string[]
  expires_at?: string
  last_used_at?: string
  created_at: string
  is_active: boolean
}

export async function listApiKeys(): Promise<ApiKey[]> {
  const response = await januaClient.http.get<ApiKey[]>('/api/v1/api-keys')
  return response.data
}

export async function createApiKey(data: { name: string; permissions?: string[]; expires_in_days?: number }): Promise<ApiKey & { key: string }> {
  const response = await januaClient.http.post<ApiKey & { key: string }>('/api/v1/api-keys', data)
  return response.data
}

export async function revokeApiKey(id: string): Promise<{ message: string }> {
  const response = await januaClient.http.delete<{ message: string }>(`/api/v1/api-keys/${id}`)
  return response.data
}

// ─── Alerts ─────────────────────────────────────────────────────────────────

export interface Alert {
  id: string
  type: string
  severity: string
  message: string
  acknowledged: boolean
  resolved: boolean
  created_at: string
}

export interface AlertChannel {
  id: string
  name: string
  type: string
  config: Record<string, unknown>
  is_active: boolean
}

export interface AlertRule {
  id: string
  name: string
  condition: string
  threshold: number
  channel_id: string
  is_active: boolean
  created_at: string
}

export async function getActiveAlerts(): Promise<Alert[]> {
  const response = await januaClient.http.get<Alert[]>('/api/v1/alerts/active')
  return response.data
}

export async function getAlertChannels(): Promise<AlertChannel[]> {
  const response = await januaClient.http.get<AlertChannel[]>('/api/v1/alerts/channels')
  return response.data
}

export async function getAlertRules(): Promise<AlertRule[]> {
  const response = await januaClient.http.get<AlertRule[]>('/api/v1/alerts/rules')
  return response.data
}

export async function createChannel(data: Partial<AlertChannel>): Promise<AlertChannel> {
  const response = await januaClient.http.post<AlertChannel>('/api/v1/alerts/channels', data)
  return response.data
}

export async function deleteChannel(channelId: string): Promise<{ message: string }> {
  const response = await januaClient.http.delete<{ message: string }>(`/api/v1/alerts/channels/${channelId}`)
  return response.data
}

export async function createRule(data: Partial<AlertRule>): Promise<AlertRule> {
  const response = await januaClient.http.post<AlertRule>('/api/v1/alerts/rules', data)
  return response.data
}

export async function updateRule(ruleId: string, data: Partial<AlertRule>): Promise<AlertRule> {
  const response = await januaClient.http.put<AlertRule>(`/api/v1/alerts/rules/${ruleId}`, data)
  return response.data
}

export async function toggleRule(ruleId: string, isActive: boolean): Promise<AlertRule> {
  const response = await januaClient.http.patch<AlertRule>(`/api/v1/alerts/rules/${ruleId}`, { is_active: isActive })
  return response.data
}

export async function deleteRule(ruleId: string): Promise<{ message: string }> {
  const response = await januaClient.http.delete<{ message: string }>(`/api/v1/alerts/rules/${ruleId}`)
  return response.data
}

export async function acknowledgeAlert(alertId: string): Promise<{ message: string }> {
  const response = await januaClient.http.post<{ message: string }>(`/api/v1/alerts/${alertId}/acknowledge`)
  return response.data
}

export async function resolveAlert(alertId: string): Promise<{ message: string }> {
  const response = await januaClient.http.post<{ message: string }>(`/api/v1/alerts/${alertId}/resolve`)
  return response.data
}

// ─── Branding ───────────────────────────────────────────────────────────────

export interface Branding {
  logo_url?: string
  primary_color?: string
  accent_color?: string
  company_name?: string
  custom_css?: string
}

export interface CustomDomain {
  id: string
  domain: string
  status: 'pending' | 'verified' | 'failed'
  verified_at?: string
  created_at: string
}

export async function getBranding(orgId: string): Promise<Branding> {
  const response = await januaClient.http.get<Branding>(`/api/v1/white-label/branding/${orgId}`)
  return response.data
}

export async function updateBranding(orgId: string, data: Partial<Branding>): Promise<Branding> {
  const response = await januaClient.http.put<Branding>(`/api/v1/white-label/branding/${orgId}`, data)
  return response.data
}

export async function getDomains(orgId: string): Promise<CustomDomain[]> {
  const response = await januaClient.http.get<CustomDomain[]>(`/api/v1/white-label/domains/${orgId}`)
  return response.data
}

export async function addDomain(data: { domain: string; organization_id: string }): Promise<CustomDomain> {
  const response = await januaClient.http.post<CustomDomain>('/api/v1/white-label/domains', data)
  return response.data
}

export async function verifyDomain(domainId: string): Promise<CustomDomain> {
  const response = await januaClient.http.post<CustomDomain>(`/api/v1/white-label/domains/${domainId}/verify`)
  return response.data
}

// ─── Audit Logs ─────────────────────────────────────────────────────────────

export interface AuditLog {
  id: string
  user_id?: string
  user_email?: string
  action: string
  resource_type?: string
  resource_id?: string
  details: Record<string, unknown>
  ip_address?: string
  user_agent?: string
  created_at: string
}

export interface AuditStats {
  total: number
  by_action: Record<string, number>
  by_user: Record<string, number>
}

export async function listAuditLogs(params?: Record<string, string>): Promise<AuditLog[]> {
  const queryString = params ? '?' + new URLSearchParams(params).toString() : ''
  const response = await januaClient.http.get<AuditLog[]>(`/api/v1/audit-logs/${queryString}`)
  return response.data
}

export async function getAuditStats(): Promise<AuditStats> {
  const response = await januaClient.http.get<AuditStats>('/api/v1/audit-logs/stats')
  return response.data
}

export async function listAuditActions(): Promise<string[]> {
  const response = await januaClient.http.get<string[]>('/api/v1/audit-logs/actions/list')
  return response.data
}

export async function exportAuditLogs(params?: Record<string, string>): Promise<Blob> {
  const response = await januaClient.http.post<Blob>('/api/v1/audit-logs/export', params)
  return response.data
}

// ─── Compliance ─────────────────────────────────────────────────────────────

export interface DataSubjectRequest {
  id: string
  type: 'access' | 'deletion' | 'portability' | 'rectification'
  status: string
  user_email: string
  created_at: string
  completed_at?: string
}

export interface Consent {
  purpose: string
  granted: boolean
  updated_at: string
}

export async function getDataSubjectRequests(): Promise<DataSubjectRequest[]> {
  const response = await januaClient.http.get<DataSubjectRequest[]>('/api/v1/compliance/data-subject-requests')
  return response.data
}

export async function createDataSubjectRequest(data: { type: string; reason?: string }): Promise<DataSubjectRequest> {
  const response = await januaClient.http.post<DataSubjectRequest>('/api/v1/compliance/data-subject-requests', data)
  return response.data
}

export async function getConsents(): Promise<Consent[]> {
  const response = await januaClient.http.get<Consent[]>('/api/v1/compliance/consent')
  return response.data
}

export async function updateConsent(purpose: string, data: { granted: boolean }): Promise<Consent> {
  const response = await januaClient.http.put<Consent>(`/api/v1/compliance/consent/${purpose}`, data)
  return response.data
}

export async function withdrawConsent(purpose: string, data?: Record<string, unknown>): Promise<{ message: string }> {
  const response = await januaClient.http.delete<{ message: string }>(`/api/v1/compliance/consent/${purpose}`, { data })
  return response.data
}

export async function getPrivacySettings(): Promise<Record<string, unknown>> {
  const response = await januaClient.http.get<Record<string, unknown>>('/api/v1/compliance/privacy-settings')
  return response.data
}

export async function updatePrivacySettings(data: Record<string, unknown>): Promise<Record<string, unknown>> {
  const response = await januaClient.http.put<Record<string, unknown>>('/api/v1/compliance/privacy-settings', data)
  return response.data
}

// ─── User Actions ───────────────────────────────────────────────────────────

export async function suspendUser(userId: string): Promise<{ message: string }> {
  const response = await januaClient.http.post<{ message: string }>(`/api/v1/users/${userId}/suspend`)
  return response.data
}

export async function reactivateUser(userId: string): Promise<{ message: string }> {
  const response = await januaClient.http.post<{ message: string }>(`/api/v1/users/${userId}/reactivate`)
  return response.data
}

export async function banUser(userId: string): Promise<{ message: string }> {
  const response = await januaClient.http.post<{ message: string }>(`/api/v1/users/${userId}/ban`)
  return response.data
}

export async function unbanUser(userId: string): Promise<{ message: string }> {
  const response = await januaClient.http.post<{ message: string }>(`/api/v1/users/${userId}/unban`)
  return response.data
}

export async function unlockUser(userId: string): Promise<{ message: string }> {
  const response = await januaClient.http.post<{ message: string }>(`/api/v1/admin/users/${userId}/unlock`)
  return response.data
}

export async function resetPassword(userId: string): Promise<{ message: string }> {
  const response = await januaClient.http.post<{ message: string }>(`/api/v1/users/${userId}/reset-password`)
  return response.data
}

export async function deleteUser(userId: string): Promise<{ message: string }> {
  const response = await januaClient.http.delete<{ message: string }>(`/api/v1/admin/users/${userId}`)
  return response.data
}

// ─── Devices ────────────────────────────────────────────────────────────────

export interface Device {
  id: string
  name: string
  type: string
  browser?: string
  os?: string
  is_trusted: boolean
  last_active_at: string
  created_at: string
}

export async function listDevices(): Promise<Device[]> {
  const response = await januaClient.http.get<Device[]>('/api/v1/devices')
  return response.data
}

export async function trustDevice(data: { device_id?: string }): Promise<{ message: string }> {
  const response = await januaClient.http.post<{ message: string }>('/api/v1/devices/trust', data)
  return response.data
}

export async function revokeDevice(deviceId: string): Promise<{ message: string }> {
  const response = await januaClient.http.delete<{ message: string }>(`/api/v1/devices/trusted/${deviceId}`)
  return response.data
}

// ─── Passkeys ───────────────────────────────────────────────────────────────

export interface PasskeyInfo {
  id: string
  name: string
  credential_id: string
  created_at: string
  last_used_at?: string
}

export async function listPasskeys(): Promise<PasskeyInfo[]> {
  const response = await januaClient.http.get<PasskeyInfo[]>('/api/v1/passkeys')
  return response.data
}

export async function deletePasskey(passkeyId: string): Promise<{ message: string }> {
  const response = await januaClient.http.delete<{ message: string }>(`/api/v1/passkeys/${passkeyId}`)
  return response.data
}

export async function registerPasskeyOptions(): Promise<Record<string, unknown>> {
  const response = await januaClient.http.post<Record<string, unknown>>('/api/v1/passkeys/register/options')
  return response.data
}

export async function verifyPasskeyRegistration(data: Record<string, unknown>): Promise<{ message: string }> {
  const response = await januaClient.http.post<{ message: string }>('/api/v1/passkeys/register/verify', data)
  return response.data
}

// ─── MFA ────────────────────────────────────────────────────────────────────

export interface MfaStatus {
  enabled: boolean
  method?: string
  backup_codes_remaining?: number
}

export async function getMfaStatus(): Promise<MfaStatus> {
  const response = await januaClient.http.get<MfaStatus>('/api/v1/mfa/status')
  return response.data
}

export async function enableMfa(data: { password: string }): Promise<{ qr_code: string; secret: string; backup_codes: string[] }> {
  const response = await januaClient.http.post<{ qr_code: string; secret: string; backup_codes: string[] }>('/api/v1/mfa/enable', data)
  return response.data
}

export async function verifyMfa(data: { code: string }): Promise<{ message: string }> {
  const response = await januaClient.http.post<{ message: string }>('/api/v1/mfa/verify', data)
  return response.data
}

export async function disableMfa(data: { password: string; code: string }): Promise<{ message: string }> {
  const response = await januaClient.http.post<{ message: string }>('/api/v1/mfa/disable', data)
  return response.data
}

export async function regenerateBackupCodes(data: { password: string }): Promise<{ backup_codes: string[] }> {
  const response = await januaClient.http.post<{ backup_codes: string[] }>('/api/v1/mfa/backup-codes/regenerate', data)
  return response.data
}

// ─── Profile ────────────────────────────────────────────────────────────────

export async function updateProfile(data: Record<string, unknown>): Promise<Record<string, unknown>> {
  const response = await januaClient.http.patch<Record<string, unknown>>('/api/v1/users/me', data)
  return response.data
}

export async function changePassword(data: { current_password: string; new_password: string }): Promise<{ message: string }> {
  const response = await januaClient.http.post<{ message: string }>('/api/v1/auth/change-password', data)
  return response.data
}

// ─── User Detail (admin) ───────────────────────────────────────────────────

export async function getUserDetail(userId: string): Promise<Record<string, unknown>> {
  const response = await januaClient.http.get<Record<string, unknown>>(`/api/v1/users/${userId}`)
  return response.data
}

export async function getUserSessions(userId: string): Promise<unknown[]> {
  const response = await januaClient.http.get<unknown[]>(`/api/v1/admin/users/${userId}/sessions`)
  return response.data
}

export async function getUserOrganizations(userId: string): Promise<unknown[]> {
  const response = await januaClient.http.get<unknown[]>(`/api/v1/admin/users/${userId}/organizations`)
  return response.data
}

// ─── SCIM (additional wrappers for pages not using SDK) ─────────────────────

export async function getScimConfig(orgId: string): Promise<Record<string, unknown>> {
  const response = await januaClient.http.get<Record<string, unknown>>(`/api/v1/organizations/${orgId}/scim/config`)
  return response.data
}

export async function createScimConfig(orgId: string, data: Record<string, unknown>): Promise<Record<string, unknown>> {
  const response = await januaClient.http.post<Record<string, unknown>>(`/api/v1/organizations/${orgId}/scim/config`, data)
  return response.data
}

export async function updateScimConfig(orgId: string, data: Record<string, unknown>): Promise<Record<string, unknown>> {
  const response = await januaClient.http.put<Record<string, unknown>>(`/api/v1/organizations/${orgId}/scim/config`, data)
  return response.data
}

export async function getScimStatus(orgId: string): Promise<Record<string, unknown>> {
  const response = await januaClient.http.get<Record<string, unknown>>(`/api/v1/organizations/${orgId}/scim/status`)
  return response.data
}

export async function regenerateScimToken(orgId: string): Promise<{ token: string }> {
  const response = await januaClient.http.post<{ token: string }>(`/api/v1/organizations/${orgId}/scim/config/token`)
  return response.data
}

// ─── Invitations (simple wrappers — API resolves org context server-side) ───

export interface InvitationInfo {
  id: string
  email: string
  role: string
  status: string
  message?: string
  expires_at: string
  created_at: string
  accepted_at?: string
  invited_by?: string
  invited_by_email?: string
  invite_url?: string
}

export async function fetchInvitations(): Promise<{ invitations: InvitationInfo[]; total: number }> {
  const response = await januaClient.http.get<{ invitations: InvitationInfo[]; total: number }>('/api/v1/invitations')
  return response.data
}

export async function sendInvitation(data: { email: string; role?: string; message?: string }): Promise<InvitationInfo> {
  const response = await januaClient.http.post<InvitationInfo>('/api/v1/invitations', data)
  return response.data
}

export async function resendInvitation(id: string): Promise<{ message: string }> {
  const response = await januaClient.http.post<{ message: string }>(`/api/v1/invitations/${id}/resend`)
  return response.data
}

export async function revokeInvitation(id: string): Promise<void> {
  await januaClient.http.delete(`/api/v1/invitations/${id}`)
}
