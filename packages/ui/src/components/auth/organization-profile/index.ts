/**
 * Organization profile module exports
 */

// Main component
export { OrganizationProfile } from './organization-profile'

// Sub-components (for customization)
export { GeneralSettingsTab } from './general-settings-tab'
export { MembersTab } from './members-tab'
export { DangerZoneTab } from './danger-zone-tab'

// Hooks
export { useOrganizationApi } from './use-organization-api'

// Types
export type {
  OrganizationMember,
  Organization,
  UserRole,
  OrganizationApiConfig,
  OrganizationCallbacks,
} from './types'

export type { GeneralSettingsTabProps } from './general-settings-tab'
export type { MembersTabProps } from './members-tab'
export type { DangerZoneTabProps } from './danger-zone-tab'
