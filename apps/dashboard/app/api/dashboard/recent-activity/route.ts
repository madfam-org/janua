import { NextRequest, NextResponse } from 'next/server'
import { personalSessionActivities } from '@/lib/dashboard-data'
import { DashboardProxyError, fetchAccountData } from '@/lib/dashboard-proxy'

export async function GET(request: NextRequest) {
  try {
    const data = await fetchAccountData(request, '/api/v1/sessions/activity/recent?limit=10')
    return NextResponse.json({ activities: personalSessionActivities(data) }, { headers: { 'Cache-Control': 'no-store' } })
  } catch (error) {
    return NextResponse.json({ message: 'Your session activity is unavailable' }, {
      status: error instanceof DashboardProxyError ? error.status : 503,
      headers: { 'Cache-Control': 'no-store' },
    })
  }
}
