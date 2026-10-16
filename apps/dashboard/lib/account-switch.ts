/** Relative-only return paths: an account switch never accepts another origin. */
export function isSafeAccountReturn(path: string): boolean {
  if (!path.startsWith('/') || path.startsWith('//') || path.includes('\\') ||
    Array.from(path).some(character => character.charCodeAt(0) <= 32 || character.charCodeAt(0) === 127)) return false
  if (/^\/(?:%2f|%5c)/i.test(path) || /%5c/i.test(path)) return false
  try { return new URL(path, 'https://dashboard.invalid').origin === 'https://dashboard.invalid' }
  catch { return false }
}

/** Deliberate fresh sign-in, without clearing the current dashboard session. */
export function isAccountSwitchRequest(params: URLSearchParams): boolean {
  const switches = params.getAll('switch_account')
  const redirects = params.getAll('redirect')
  return switches.length === 1 && switches[0] === '1' && redirects.length <= 1 &&
    Array.from(params.keys()).every(key => key === 'switch_account' || key === 'redirect') &&
    (!redirects.length || isSafeAccountReturn(redirects[0]!))
}

export function accountSwitchUrl(returnPath = '/'): string {
  return `/login?${new URLSearchParams({ switch_account: '1', redirect: isSafeAccountReturn(returnPath) ? returnPath : '/' })}`
}
