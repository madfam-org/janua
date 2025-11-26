/**
 * Organization profile component
 *
 * Re-exports from the decomposed module for backward compatibility.
 * For new code, import directly from './organization-profile/index'
 */

export {
  OrganizationProfile,
  GeneralSettingsTab,
  MembersTab,
  DangerZoneTab,
  useOrganizationApi,
} from './organization-profile/index'

export type {
  OrganizationMember,
  Organization,
  UserRole,
  OrganizationApiConfig,
  OrganizationCallbacks,
  GeneralSettingsTabProps,
  MembersTabProps,
  DangerZoneTabProps,
} from './organization-profile/index'

// Re-export the main props type with original name for backward compatibility
export type { OrganizationProfileProps } from './organization-profile/organization-profile'
