import express, { Express, Request, Response, NextFunction } from 'express';
import cors from 'cors';
import cookieParser from 'cookie-parser';
import rateLimit from 'express-rate-limit';
import { authRouter } from './routes/auth';
import { usersRouter } from './routes/users';
import { sessionsRouter } from './routes/sessions';
import { organizationsRouter } from './routes/organizations';
import { mfaRouter } from './routes/mfa';
import { passkeysRouter } from './routes/passkeys';
import { db } from './database';
import { authenticateToken } from './middleware/auth';

const app: Express = express();
const PORT = process.env.PORT || 8000;

// Middleware
app.use(cors({
  origin: true,
  credentials: true
}));
app.use(express.json());
app.use(express.urlencoded({ extended: true }));
app.use(cookieParser());

// Rate limiting
const limiter = rateLimit({
  windowMs: 15 * 60 * 1000, // 15 minutes
  max: 100, // Limit each IP to 100 requests per windowMs
  message: 'Too many requests from this IP, please try again later.'
});

app.use('/api/v1/auth', limiter);

// Health check endpoints
app.get('/health', (req: Request, res: Response) => {
  res.json({ status: 'healthy', timestamp: new Date().toISOString() });
});

app.get('/ready', (req: Request, res: Response) => {
  res.json({ 
    status: 'ready',
    database: true,
    redis: true,
    timestamp: new Date().toISOString()
  });
});

// JWKS endpoint
app.get('/.well-known/jwks.json', (req: Request, res: Response) => {
  res.json({
    keys: [
      {
        kty: 'RSA',
        use: 'sig',
        kid: 'mock-key-1',
        alg: 'RS256',
        n: 'mock-modulus',
        e: 'AQAB'
      }
    ]
  });
});

// OpenID Configuration
app.get('/.well-known/openid-configuration', (req: Request, res: Response) => {
  res.json({
    issuer: `http://localhost:${PORT}`,
    authorization_endpoint: `http://localhost:${PORT}/authorize`,
    token_endpoint: `http://localhost:${PORT}/api/v1/auth/token`,
    userinfo_endpoint: `http://localhost:${PORT}/api/v1/users/me`,
    jwks_uri: `http://localhost:${PORT}/.well-known/jwks.json`,
    response_types_supported: ['code', 'token', 'id_token'],
    subject_types_supported: ['public'],
    id_token_signing_alg_values_supported: ['RS256'],
    scopes_supported: ['openid', 'profile', 'email'],
    token_endpoint_auth_methods_supported: ['client_secret_post', 'client_secret_basic'],
    claims_supported: ['sub', 'email', 'email_verified', 'name', 'given_name', 'family_name']
  });
});

// API Routes
app.use('/api/v1/auth', authRouter);
app.use('/api/v1/users', authenticateToken, usersRouter);
app.use('/api/v1/sessions', authenticateToken, sessionsRouter);
app.use('/api/v1/organizations', authenticateToken, organizationsRouter);
app.use('/api/v1/mfa', authenticateToken, mfaRouter);
app.use('/api/v1/passkeys', passkeysRouter);

// Error handling middleware
app.use((err: any, req: Request, res: Response, next: NextFunction) => {
  console.error(err.stack);
  
  if (err.name === 'UnauthorizedError') {
    return res.status(401).json({ error: 'Unauthorized' });
  }
  
  if (err.name === 'ValidationError') {
    return res.status(400).json({ error: err.message });
  }
  
  res.status(500).json({ error: 'Internal server error' });
});

// 404 handler
app.use((req: Request, res: Response) => {
  res.status(404).json({ error: 'Not found' });
});

// Start server
app.listen(PORT, () => {
  console.log(`🚀 Mock API server running at http://localhost:${PORT}`);
  console.log(`📚 API documentation at http://localhost:${PORT}/api-docs`);
  console.log(`🔑 JWKS endpoint at http://localhost:${PORT}/.well-known/jwks.json`);
  
  // Initialize database
  db.init();
  console.log('📦 In-memory database initialized');
});