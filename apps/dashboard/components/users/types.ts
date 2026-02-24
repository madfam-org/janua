// User types for the data table

export type UserStatus = 'active' | 'inactive' | 'banned' | 'suspended' | 'pending'
export type UserRole = 'owner' | 'admin' | 'member' | 'viewer'

export interface User {
  id: string
  email: string
  firstName: string
  lastName: string
  status: UserStatus
  role: UserRole
  mfaEnabled: boolean
  lastSignIn: string | null
  createdAt: string
  sessionsCount: number
  authMethods: string[]
  emailVerified?: boolean
  phoneNumber?: string
  avatarUrl?: string
  organizations?: number
  isAdmin?: boolean
  lockedOut?: boolean
}

export type UserActionType =
  | 'reset_password'
  | 'suspend'
  | 'reactivate'
  | 'ban'
  | 'unban'
  | 'unlock'
  | 'view_sessions'
  | 'view_detail'
  | 'delete'
  | 'change_role'

export interface UserAction {
  type: UserActionType
  userId: string
  userName?: string
}

export interface PaginatedResponse<T> {
  items: T[]
  total: number
  page: number
  per_page: number
  pages: number
}
