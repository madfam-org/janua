import { januaClient } from './janua-client'
import { activeSessionCount, organizationCount, personalSessionActivities, type PersonalDashboardStats } from './dashboard-data'

/** These API endpoints remain scoped to the current user even for operators. */
export async function getPersonalDashboardStats(): Promise<PersonalDashboardStats> {
  const [organizations, sessions] = await Promise.allSettled([
    januaClient.http.get<unknown>('/api/v1/organizations/').then(response => organizationCount(response.data)),
    januaClient.http.get<unknown>('/api/v1/sessions/').then(response => activeSessionCount(response.data)),
  ])
  return {
    organizations: organizations.status === 'fulfilled' ? organizations.value : null,
    activeSessions: sessions.status === 'fulfilled' ? sessions.value : null,
  }
}

export async function getPersonalSessionActivity() {
  const response = await januaClient.http.get<unknown>('/api/v1/sessions/activity/recent?limit=10')
  return personalSessionActivities(response.data)
}
