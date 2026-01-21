import { Router, Request, Response } from 'express';

export const mfaRouter = Router();

// Get MFA status
mfaRouter.get('/status', (_req: Request, res: Response) => {
  res.json({
    enabled: false,
    methods: [],
    backupCodesRemaining: 0
  });
});

// Enable MFA
mfaRouter.post('/enable', (req: Request, res: Response) => {
  const { method } = req.body;
  
  if (!method || !['totp', 'sms'].includes(method)) {
    return res.status(400).json({ error: 'Invalid MFA method' });
  }
  
  // Generate secret for TOTP
  const secret = 'MOCK_SECRET_' + Math.random().toString(36).substring(7);
  
  res.json({
    method,
    secret,
    qrCode: `otpauth://totp/Janua:user@example.com?secret=${secret}&issuer=Janua`,
    backupCodes: [
      'BACKUP-1234-5678',
      'BACKUP-2345-6789',
      'BACKUP-3456-7890'
    ]
  });
});

// Verify MFA code
mfaRouter.post('/verify', (req: Request, res: Response) => {
  const { code } = req.body;
  
  if (!code) {
    return res.status(400).json({ error: 'Code is required' });
  }
  
  // Mock verification - accept any 6-digit code
  if (code.length === 6 && /^\d+$/.test(code)) {
    res.json({ valid: true });
  } else {
    res.status(400).json({ error: 'Invalid code' });
  }
});

// Disable MFA
mfaRouter.post('/disable', (_req: Request, res: Response) => {
  res.json({
    message: 'MFA disabled successfully'
  });
});

// Generate backup codes
mfaRouter.post('/backup-codes', (_req: Request, res: Response) => {
  const codes = Array.from({ length: 8 }, () => 
    'BACKUP-' + Math.random().toString(36).substring(2, 6).toUpperCase() + 
    '-' + Math.random().toString(36).substring(2, 6).toUpperCase()
  );
  
  res.json({ codes });
});