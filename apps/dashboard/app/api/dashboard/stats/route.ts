import { NextRequest, NextResponse } from 'next/server'
import { activeSessionCount, organizationCount } from '@/lib/dashboard-data'
import { DashboardProxyError, fetchAccountData } from '@/lib/dashboard-proxy'

export async function GET(request: NextRequest) {
  try {
    const [organizations, sessions] = await Promise.all([
      fetchAccountData(request, '/api/v1/organizations/'),
      fetchAccountData(request, '/api/v1/sessions/'),
    ])
    return NextResponse.json({ organizations: organizationCount(organizations), activeSessions: activeSessionCount(sessions) }, { headers: { 'Cache-Control': 'no-store' } })
  } catch (error) {
    return NextResponse.json({ message: 'Account overview unavailable' }, {
      status: error instanceof DashboardProxyError ? error.status : 503,
      headers: { 'Cache-Control': 'no-store' },
    })
  }
}
