import { NextResponse } from 'next/server'
import { readConsoleApi } from '@/lib/console-runtime.server'

export async function GET() {
  try { readConsoleApi() } catch {
    return NextResponse.json({ status: 'unavailable', error: 'Console configuration unavailable' }, { status: 503, headers: { 'Cache-Control': 'no-store' } })
  }
  return NextResponse.json(
    {
      status: 'healthy',
      timestamp: new Date().toISOString(),
      service: 'dashboard',
      version: process.env.npm_package_version || '0.1.0'
    },
    { status: 200 }
  )
}