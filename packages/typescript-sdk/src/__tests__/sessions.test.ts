/**
 * Tests for Sessions module
 *
 * Regression: All paths must include the `/api/v1` prefix. Prior versions
 * accidentally called `/sessions/...` which 404'd against `api.janua.dev`.
 * See branch fix/admin-endpoints-three-fixes.
 */

import { Sessions } from '../sessions';
import type { HttpClient } from '../http-client';

describe('Sessions', () => {
  let sessions: Sessions;
  let mockHttpClient: jest.Mocked<HttpClient>;

  beforeEach(() => {
    mockHttpClient = {
      request: jest.fn().mockResolvedValue({ data: {} }),
    } as any;

    sessions = new Sessions(mockHttpClient);
  });

  describe('URL prefixing (regression: 404 on app.janua.dev Sessions tab)', () => {
    it('listSessions hits /api/v1/sessions', async () => {
      mockHttpClient.request.mockResolvedValueOnce({
        data: { data: [], total: 0, page: 1, per_page: 20 },
      } as any);

      await sessions.listSessions();

      expect(mockHttpClient.request).toHaveBeenCalledWith({
        method: 'GET',
        url: '/api/v1/sessions',
        params: undefined,
      });
    });

    it('listSessions forwards params', async () => {
      mockHttpClient.request.mockResolvedValueOnce({
        data: { data: [], total: 0, page: 1, per_page: 20 },
      } as any);

      await sessions.listSessions({ page: 2, per_page: 10 });

      expect(mockHttpClient.request).toHaveBeenCalledWith({
        method: 'GET',
        url: '/api/v1/sessions',
        params: { page: 2, per_page: 10 },
      });
    });

    it('getCurrentSession hits /api/v1/sessions/current', async () => {
      mockHttpClient.request.mockResolvedValueOnce({
        data: { session: { id: 's1', revoked: false } },
      } as any);

      await sessions.getCurrentSession();

      expect(mockHttpClient.request).toHaveBeenCalledWith({
        method: 'GET',
        url: '/api/v1/sessions/current',
      });
    });

    it('getSession hits /api/v1/sessions/{id}', async () => {
      const id = '11111111-2222-3333-4444-555555555555';
      mockHttpClient.request.mockResolvedValueOnce({
        data: { session: { id, revoked: false } },
      } as any);

      await sessions.getSession(id);

      expect(mockHttpClient.request).toHaveBeenCalledWith({
        method: 'GET',
        url: `/api/v1/sessions/${id}`,
      });
    });

    it('revokeSession hits DELETE /api/v1/sessions/{id}', async () => {
      const id = '11111111-2222-3333-4444-555555555555';

      await sessions.revokeSession(id);

      expect(mockHttpClient.request).toHaveBeenCalledWith({
        method: 'DELETE',
        url: `/api/v1/sessions/${id}`,
      });
    });

    it('revokeAllSessions hits POST /api/v1/sessions/revoke-all', async () => {
      mockHttpClient.request.mockResolvedValueOnce({
        data: { revokedCount: 3 },
      } as any);

      await sessions.revokeAllSessions();

      expect(mockHttpClient.request).toHaveBeenCalledWith({
        method: 'POST',
        url: '/api/v1/sessions/revoke-all',
      });
    });

    it('refreshSession hits POST /api/v1/sessions/refresh', async () => {
      mockHttpClient.request.mockResolvedValueOnce({
        data: { session: { id: 's1', revoked: false } },
      } as any);

      await sessions.refreshSession();

      expect(mockHttpClient.request).toHaveBeenCalledWith({
        method: 'POST',
        url: '/api/v1/sessions/refresh',
      });
    });

    it('refresh() alias delegates to refreshSession()', async () => {
      mockHttpClient.request.mockResolvedValueOnce({
        data: { session: { id: 's1', revoked: false } },
      } as any);

      await sessions.refresh();

      expect(mockHttpClient.request).toHaveBeenCalledWith({
        method: 'POST',
        url: '/api/v1/sessions/refresh',
      });
    });
  });

  describe('verifySession', () => {
    it('returns valid=true when session exists and is not revoked', async () => {
      const id = '11111111-2222-3333-4444-555555555555';
      mockHttpClient.request.mockResolvedValueOnce({
        data: { session: { id, revoked: false } },
      } as any);

      const result = await sessions.verifySession(id);

      expect(result.valid).toBe(true);
      expect(result.session?.id).toBe(id);
    });

    it('returns valid=false when session is revoked', async () => {
      const id = '11111111-2222-3333-4444-555555555555';
      mockHttpClient.request.mockResolvedValueOnce({
        data: { session: { id, revoked: true } },
      } as any);

      const result = await sessions.verifySession(id);

      expect(result.valid).toBe(false);
    });

    it('returns valid=false when getSession throws', async () => {
      const id = '11111111-2222-3333-4444-555555555555';
      mockHttpClient.request.mockRejectedValueOnce(new Error('Not found'));

      const result = await sessions.verifySession(id);

      expect(result.valid).toBe(false);
      expect(result.session).toBeUndefined();
    });
  });
});
