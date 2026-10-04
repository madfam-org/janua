import { AuthenticationError } from './errors';
import type { TokenResponse } from './types';
import type { SessionSnapshot, TokenManager } from './utils/token-utils';

const flights = new WeakMap<object, { snapshot: SessionSnapshot; promise: Promise<TokenResponse> }>();

function currentTokens(snapshot: SessionSnapshot): TokenResponse {
  if (!snapshot.tokens?.access_token || !snapshot.tokens.refresh_token) {
    throw new AuthenticationError('No refresh token available');
  }
  return {
    access_token: snapshot.tokens.access_token,
    refresh_token: snapshot.tokens.refresh_token,
    expires_in: Math.max(0, Math.floor(((snapshot.tokens.expires_at ?? 0) - Date.now()) / 1000)),
    token_type: 'bearer',
  };
}

/** One rotation per stored session, shared by Auth, timers and both HTTP adapters. */
export async function refreshSession(
  manager: TokenManager,
  transport: (refreshToken: string) => Promise<TokenResponse>,
  accepted: (tokens: TokenResponse) => void,
  expired: () => void,
  expected?: SessionSnapshot,
  explicitRefreshToken?: string,
): Promise<TokenResponse> {
  const snapshot = expected ?? await manager.captureSession();
  const refreshToken = snapshot.tokens?.refresh_token;
  if (!refreshToken) throw new AuthenticationError('No refresh token available');
  if (explicitRefreshToken && explicitRefreshToken !== refreshToken) {
    throw new AuthenticationError('Refresh token does not match the current session');
  }
  const active = flights.get(manager.coordinationScope);
  if (active && manager.sameSession(active.snapshot, snapshot)) return active.promise;

  const promise = manager.withSessionLock(async () => {
    // Another tab may have rotated while we waited for its Web Lock.
    const current = await manager.captureSession();
    if (!manager.sameSession(snapshot, current)) throw new AuthenticationError('Session changed during refresh');
    if (current.tokens?.refresh_token !== refreshToken || current.tokens?.access_token !== snapshot.tokens?.access_token) {
      return currentTokens(current);
    }
    try {
      const tokens = await transport(refreshToken); // Deliberately one attempt.
      if (!tokens.access_token || !tokens.refresh_token || !Number.isFinite(tokens.expires_in) || tokens.expires_in <= 0) {
        throw new AuthenticationError('Invalid refresh response');
      }
      const stored = await manager.acceptRefresh(snapshot, {
        access_token: tokens.access_token, refresh_token: tokens.refresh_token,
        expires_at: Date.now() + tokens.expires_in * 1000,
      });
      if (!stored) throw new AuthenticationError('Session changed during refresh');
      accepted(tokens); // Exactly once, only after the accepted rotation is stored.
      return tokens;
    } catch (error) {
      if (await manager.discardRefresh(snapshot)) expired();
      // A refresh failure must not be retried by an outer request retry loop.
      throw error instanceof AuthenticationError ? error : new AuthenticationError('Refresh failed; sign in again');
    }
  });
  const flight = { snapshot, promise };
  flights.set(manager.coordinationScope, flight);
  try { return await promise; }
  finally { if (flights.get(manager.coordinationScope) === flight) flights.delete(manager.coordinationScope); }
}
