import { NextResponse } from 'next/server'
import { readConsoleApi } from '@/lib/console-runtime.server'

export async function GET() {
  try { readConsoleApi() } catch {
    return NextResponse.json({ status: 'unavailable', error: 'Console configuration unavailable' }, { status: 503, headers: { 'Cache-Control': 'no-store' } })
  }
  return NextResponse.json({
    status: 'healthy',
    service: 'janua-admin',
    timestamp: new Date().toISOString(),
  })
}
