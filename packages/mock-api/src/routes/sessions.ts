import { Router, Request, Response } from 'express';
import { db } from '../database';

export const sessionsRouter = Router();

// Get all sessions for current user
sessionsRouter.get('/', (req: Request, res: Response) => {
  const userId = (req as any).userId;
  const sessions = db.getUserSessions(userId);
  
  res.json(sessions);
});

// Get current session
sessionsRouter.get('/current', (req: Request, res: Response) => {
  const userId = (req as any).userId;
  const sessionId = (req as any).sessionId || 'current-session';
  
  res.json({
    id: sessionId,
    userId,
    active: true,
    createdAt: new Date().toISOString(),
    lastAccessedAt: new Date().toISOString(),
    userAgent: req.headers['user-agent'],
    ipAddress: req.ip
  });
});

// Verify session
sessionsRouter.post('/verify', (req: Request, res: Response) => {
  const userId = (req as any).userId;
  
  res.json({
    valid: true,
    userId,
    expiresAt: new Date(Date.now() + 24 * 60 * 60 * 1000).toISOString()
  });
});

// Revoke session
sessionsRouter.delete('/:id', (req: Request, res: Response) => {
  const _userId = (req as any).userId;
  const sessionId = req.params.id;

  // In a real app, you'd invalidate the session here
  res.json({
    message: 'Session revoked successfully',
    sessionId
  });
});