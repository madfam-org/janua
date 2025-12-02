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

    // Forward the request to the Janua API (v1 versioned endpoint)
    const apiUrl = `${API_BASE_URL}/api/v1/dashboard/stats`

    const apiResponse = await fetch(apiUrl, {
      method: 'GET',
      headers: {
        'Authorization': authHeader,
        'Content-Type': 'application/json',
      },
    })

    // Parse response safely
    const responseText = await apiResponse.text()
    let data
    try {
      data = JSON.parse(responseText)
    } catch {
      console.error('Failed to parse API response:', responseText)
      return NextResponse.json(
        { message: 'API returned invalid response' },
        { status: 500 }
      )
    }

    if (!apiResponse.ok) {
      return NextResponse.json(
        { message: data.detail || data.message || 'Failed to fetch stats' },
        { status: apiResponse.status }
      )
    }
    
    // Transform data to expected format if needed
    const transformedData = {
      total_users: data.total_users || 0,
      users_change: data.users_change || '+0%',
      active_sessions: data.active_sessions || 0,
      sessions_change: data.sessions_change || '+0%',
      total_organizations: data.total_organizations || 0,
      organizations_change: data.organizations_change || '+0%',
      auth_events: data.auth_events || 0,
      auth_events_change: data.auth_events_change || '+0%',
    }

    return NextResponse.json(transformedData)

  } catch (error) {
    console.error('Stats API error:', error)
    return NextResponse.json(
      { message: 'Internal server error' },
      { status: 500 }
    )
  }
}