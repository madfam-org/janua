import { NextResponse } from 'next/server'

export async function GET() {
  return NextResponse.json({
    status: 'healthy',
    service: 'janua-admin',
    timestamp: new Date().toISOString(),
  })
}
