import { NextRequest, NextResponse } from 'next/server'

// Server-side environment variable (runtime, not baked into build)
const API_BASE_URL = process.env.INTERNAL_API_URL || process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

export async function GET(request: NextRequest) {
  try {
    const authHeader = request.headers.get('authorization')
    
    if (!authHeader) {
      return NextResponse.json(
        { message: 'Authorization required' },
        { status: 401 }
      )
    }

    // Forward the request to the API
    const apiResponse = await fetch(`${API_BASE_URL}/api/audit/recent`, {
      method: 'GET',
      headers: {
        'Authorization': authHeader,
        'Content-Type': 'application/json',
      },
    })

    if (!apiResponse.ok) {
      const errorData = await apiResponse.json().catch(() => ({}))
      return NextResponse.json(
        { message: errorData.message || 'Failed to fetch recent activity' },
        { status: apiResponse.status }
      )
    }

    const data = await apiResponse.json()
    
    // Transform audit logs to activity format
    const activities = (data.logs || data.activities || []).map((log: any, index: number) => ({
      id: log.id || index.toString(),
      user: log.actor_email || log.user || 'Unknown user',
      action: formatAction(log.action, log.metadata),
      timestamp: formatTimestamp(log.occurred_at || log.timestamp),
      type: mapActionType(log.action)
    }))

    return NextResponse.json({ activities })

  } catch (error) {
    console.error('Recent activity API error:', error)
    return NextResponse.json(
      { message: 'Internal server error' },
      { status: 500 }
    )
  }
}

function formatAction(action: string, metadata?: any): string {
  switch (action) {
    case 'login_success':
      return metadata?.auth_method === 'passkey' ? 'Signed in with passkey' : 'Signed in with password'
    case 'login_failure':
      return 'Failed login attempt'
    case 'user_create':
      return 'Created new account'
    case 'session_expired':
      return 'Session expired'
    case 'logout':
      return 'Signed out'
    default:
      return action.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())
  }
}

function formatTimestamp(timestamp: string): string {
  if (!timestamp) return 'Unknown time'
  
  try {
    const date = new Date(timestamp)
    const now = new Date()
    const diffMs = now.getTime() - date.getTime()
    const diffMins = Math.floor(diffMs / (1000 * 60))
    
    if (diffMins < 1) return 'Just now'
    if (diffMins < 60) return `${diffMins} minute${diffMins === 1 ? '' : 's'} ago`
    
    const diffHours = Math.floor(diffMins / 60)
    if (diffHours < 24) return `${diffHours} hour${diffHours === 1 ? '' : 's'} ago`
    
    const diffDays = Math.floor(diffHours / 24)
    return `${diffDays} day${diffDays === 1 ? '' : 's'} ago`
  } catch {
    return 'Unknown time'
  }
}

function mapActionType(action: string): 'signin' | 'signup' | 'passkey' | 'session' | 'error' {
  if (action?.includes('login_success')) return 'signin'
  if (action?.includes('passkey')) return 'passkey'
  if (action?.includes('user_create') || action?.includes('signup')) return 'signup'
  if (action?.includes('session') || action?.includes('logout')) return 'session'
  if (action?.includes('failure') || action?.includes('error')) return 'error'
  return 'signin'
}