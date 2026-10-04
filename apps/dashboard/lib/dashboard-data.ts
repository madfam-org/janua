/** Account-scoped dashboard contracts; never infer totals from missing data. */
export interface PersonalDashboardStats {
  organizations: number | null
  activeSessions: number | null
}

export interface PersonalSessionActivity {
  id: string
  action: 'Session started' | 'Session active'
  timestamp: string | null
  device: string
  revoked: boolean
}

export function organizationCount(data: unknown): number {
  const result = data as { organizations?: unknown; total?: unknown } | null
  if (!result || !Array.isArray(result.organizations) || typeof result.total !== 'number' || !Number.isSafeInteger(result.total) || result.total < result.organizations.length) {
    throw new Error('Organization data unavailable')
  }
  return result.total
}

export function activeSessionCount(data: unknown): number {
  const result = data as { sessions?: unknown; total?: unknown } | null
  if (!result || !Array.isArray(result.sessions) || typeof result.total !== 'number' || !Number.isSafeInteger(result.total) || result.total < 0) {
    throw new Error('Session data unavailable')
  }
  return result.total
}

export function personalSessionActivities(data: unknown): PersonalSessionActivity[] {
  const result = data as { activities?: unknown } | null
  if (!result || !Array.isArray(result.activities)) throw new Error('Session activity unavailable')
  return result.activities.map((item: unknown) => {
    const activity = item as Record<string, unknown> | null
    if (!activity || typeof activity.session_id !== 'string' || !['session_created', 'session_active'].includes(String(activity.activity_type))) {
      throw new Error('Session activity unavailable')
    }
    return {
      id: activity.session_id,
      action: activity.activity_type === 'session_created' ? 'Session started' : 'Session active',
      timestamp: typeof activity.timestamp === 'string' && Number.isFinite(Date.parse(activity.timestamp)) ? activity.timestamp : null,
      device: typeof activity.device === 'string' ? activity.device : 'Device unavailable',
      revoked: activity.revoked === true,
    }
  })
}
