import { NextRequest, NextResponse } from 'next/server'

// Server-side environment variable (runtime, not baked into build)
// Priority: INTERNAL_API_URL > NEXT_PUBLIC_API_URL > localhost fallback
const API_BASE_URL = process.env.INTERNAL_API_URL || process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

export async function POST(request: NextRequest) {
  try {
    const body = await request.json()
    const { email, password } = body

    if (!email || !password) {
      return NextResponse.json(
        { message: 'Email and password are required' },
        { status: 400 }
      )
    }

    // Forward to the Janua API (v1 versioned endpoint)
    const apiUrl = `${API_BASE_URL}/api/v1/auth/login`

    const apiResponse = await fetch(apiUrl, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ email, password }),
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
        { message: data.detail || data.message || 'Login failed' },
        { status: apiResponse.status }
      )
    }

    // Return the tokens and user data (handle both nested and flat token structures)
    // IMPORTANT: Include refresh_token for SDK token refresh functionality
    return NextResponse.json({
      token: data.tokens?.access_token || data.access_token || data.token,
      refresh_token: data.tokens?.refresh_token || data.refresh_token,
      expires_in: data.tokens?.expires_in || data.expires_in || 900,
      user: data.user || { email, name: email.split('@')[0] },
      message: 'Login successful'
    })

  } catch (error) {
    console.error('Login API error:', error)
    return NextResponse.json(
      { message: 'Internal server error' },
      { status: 500 }
    )
  }
}
