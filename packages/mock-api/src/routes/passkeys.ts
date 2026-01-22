import { Router, Request, Response } from 'express';

export const passkeysRouter = Router();

// Get passkeys for user
passkeysRouter.get('/', (req: Request, res: Response) => {
  const _userId = (req as any).userId;
  
  // Mock passkeys
  res.json([
    {
      id: 'passkey-1',
      name: 'Chrome on MacBook',
      lastUsed: new Date().toISOString(),
      createdAt: new Date().toISOString()
    }
  ]);
});

// Register passkey - start
passkeysRouter.post('/register/start', (req: Request, res: Response) => {
  const userId = (req as any).userId || 'anonymous';
  
  // Mock WebAuthn registration challenge
  res.json({
    challenge: Buffer.from(Math.random().toString()).toString('base64'),
    rp: {
      name: 'Janua',
      id: 'localhost'
    },
    user: {
      id: Buffer.from(userId).toString('base64'),
      name: 'user@example.com',
      displayName: 'Test User'
    },
    pubKeyCredParams: [
      { alg: -7, type: 'public-key' },
      { alg: -257, type: 'public-key' }
    ],
    authenticatorSelection: {
      authenticatorAttachment: 'platform',
      userVerification: 'preferred'
    },
    timeout: 60000,
    attestation: 'direct'
  });
});

// Register passkey - finish
passkeysRouter.post('/register/finish', (req: Request, res: Response) => {
  const { credential, name } = req.body;
  
  if (!credential) {
    return res.status(400).json({ error: 'Credential is required' });
  }
  
  // Mock storing the passkey
  res.json({
    id: 'passkey-' + Math.random().toString(36).substring(7),
    name: name || 'New Passkey',
    createdAt: new Date().toISOString()
  });
});

// Authenticate with passkey - start
passkeysRouter.post('/authenticate/start', (req: Request, res: Response) => {
  // Mock WebAuthn authentication challenge
  res.json({
    challenge: Buffer.from(Math.random().toString()).toString('base64'),
    rpId: 'localhost',
    allowCredentials: [],
    userVerification: 'preferred',
    timeout: 60000
  });
});

// Authenticate with passkey - finish
passkeysRouter.post('/authenticate/finish', (req: Request, res: Response) => {
  const { credential } = req.body;
  
  if (!credential) {
    return res.status(400).json({ error: 'Credential is required' });
  }
  
  // Mock successful authentication
  res.json({
    token: 'mock-jwt-token-' + Math.random().toString(36).substring(7),
    user: {
      id: 'user-1',
      email: 'user@example.com',
      name: 'Test User'
    }
  });
});

// Delete passkey
passkeysRouter.delete('/:id', (req: Request, res: Response) => {
  const passkeyId = req.params.id;
  
  res.json({
    message: 'Passkey deleted successfully',
    id: passkeyId
  });
});