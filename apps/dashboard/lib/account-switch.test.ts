import { accountSwitchUrl, isAccountSwitchRequest, isSafeAccountReturn } from './account-switch'

describe('deliberate account switch navigation', () => {
  it('keeps safe local destinations and makes an explicit fresh-login request', () => {
    const url = new URL(accountSwitchUrl('/organizations?view=members'), 'https://dashboard.example.test')
    expect(url.pathname).toBe('/login')
    expect(url.searchParams.get('redirect')).toBe('/organizations?view=members')
    expect(isAccountSwitchRequest(url.searchParams)).toBe(true)
  })

  it.each(['https://foreign.invalid', '//foreign.invalid', '/\\foreign.invalid', '/%2fforeign.invalid', '/%5cforeign.invalid', '/\n/foreign.invalid'])('rejects unsafe return target %s', target => {
    expect(isSafeAccountReturn(target)).toBe(false)
    const params = new URLSearchParams({ switch_account: '1', redirect: target })
    expect(isAccountSwitchRequest(params)).toBe(false)
    expect(new URL(accountSwitchUrl(target), 'https://dashboard.example.test').searchParams.get('redirect')).toBe('/')
  })

  it.each(['switch_account=1&switch_account=1', 'switch_account=1&reason=session_expired', 'switch_account=1&redirect=/&redirect=/profile', 'switch_account=0', 'switch_account=1&role=admin'])('refuses ambiguous or unrelated controls %s', query => {
    expect(isAccountSwitchRequest(new URLSearchParams(query))).toBe(false)
  })
})
