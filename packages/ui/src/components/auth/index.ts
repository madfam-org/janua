// Core Auth Components
export * from './sign-in'
export * from './sign-up'
export * from './user-button'
export * from './mfa-setup'
export * from './mfa-challenge'
export * from './backup-codes'

// Shared Sub-Components (Phase 2)
export * from './social-icons'
export * from './social-buttons'
export * from './auth-card'
export * from './divider'
export * from './password-input'

// SSO & Passkey Components (Phase 5)
export * from './janua-sso-button'
export * from './sso-email-detector'
export * from './passkey-button'
export * from './magic-link-form'

// Organization switcher exports (has its own Organization interface)
export {
  OrganizationSwitcher,
  type OrganizationSwitcherProps,
  type Organization as SwitcherOrganization
} from './organization-switcher'
// Organization profile exports (has its own Organization type)
export {
  OrganizationProfile,
  GeneralSettingsTab,
  MembersTab,
  DangerZoneTab,
  useOrganizationApi,
  type OrganizationMember,
  type Organization,
  type UserRole,
  type OrganizationApiConfig,
  type OrganizationCallbacks,
  type GeneralSettingsTabProps,
  type MembersTabProps,
  type DangerZoneTabProps,
  type OrganizationProfileProps
} from './organization-profile'
export * from './user-profile'
export * from './password-reset'
export * from './email-verification'
export * from './phone-verification'
export * from './session-management'
export * from './device-management'
export * from './audit-log'

// Enterprise Components
export * from '../enterprise/invitation-list'
// Note: invite-user-form exports conflicting 'Invitation' interface
// Export everything from invite-user-form except 'Invitation' to avoid naming collision
export { InviteUserForm, type InvitationCreate, type InviteUserFormProps } from '../enterprise/invite-user-form'
export * from '../enterprise/invitation-accept'
export { SSOProviderList, type SSOProviderListProps } from '../enterprise/sso-provider-list'
export { SSOProviderForm, type SSOProviderFormProps, type SSOConfiguration, type SSOConfigurationCreate } from '../enterprise/sso-provider-form'
export { SAMLConfigForm, type SAMLConfigFormProps } from '../enterprise/saml-config-form'
export { BulkInviteUpload, type BulkInviteUploadProps, type BulkInvitationResponse } from '../enterprise/bulk-invite-upload'
export { SSOTestConnection, type SSOTestConnectionProps, type SSOTestRequest, type SSOTestResponse } from '../enterprise/sso-test-connection'
