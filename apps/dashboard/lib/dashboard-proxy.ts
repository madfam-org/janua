import { NextRequest } from 'next/server'

export class DashboardProxyError extends Error {
  constructor(public readonly status: number) { super('Account data unavailable') }
}

/** Server-side compatibility routes may call only fixed account-scoped paths. */
export async function fetchAccountData(request: NextRequest, path: string): Promise<unknown> {
  const authorization = request.headers.get('authorization')
  if (!authorization?.startsWith('Bearer ')) throw new DashboardProxyError(401)
  const api = (process.env.INTERNAL_API_URL || process.env.NEXT_PUBLIC_API_URL || 'https://api.janua.dev').replace(/\/$/, '')
  try {
    const response = await fetch(`${api}${path}`, {
      headers: { Authorization: authorization },
      cache: 'no-store',
      redirect: 'error',
      signal: AbortSignal.timeout(5000),
    })
    if (!response.ok) throw new DashboardProxyError([401, 403].includes(response.status) ? response.status : 503)
    return await response.json()
  } catch (error) {
    throw error instanceof DashboardProxyError ? error : new DashboardProxyError(503)
  }
}
