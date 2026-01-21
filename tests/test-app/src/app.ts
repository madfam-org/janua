import express from 'express';
import cookieParser from 'cookie-parser';
import helmet from 'helmet';
import cors from 'cors';
import path from 'path';
import dotenv from 'dotenv';
import { JanuaClient } from '@janua/typescript-sdk';

// Load environment variables
dotenv.config();

const app = express();
const PORT = process.env.PORT || 3001;

// Janua SDK client
const janua = new JanuaClient({
  apiUrl: process.env.JANUA_API_URL || 'http://localhost:8000',
  apiKey: process.env.JANUA_API_KEY || 'test-api-key'
});

// Middleware
app.use(helmet({
  contentSecurityPolicy: false, // Disable for dev
}));
app.use(cors());
app.use(express.json());
app.use(express.urlencoded({ extended: true }));
app.use(cookieParser());
app.use(express.static(path.join(__dirname, '../public')));

// View engine setup
app.set('view engine', 'ejs');
app.set('views', path.join(__dirname, '../views'));

// Make janua client available to routes
app.locals.janua = janua;

// Routes
app.get('/', (req, res) => {
  res.render('index', {
    title: 'Janua Test App',
    user: req.cookies.user ? JSON.parse(req.cookies.user) : null
  });
});

app.get('/signup', (req, res) => {
  res.render('signup', { title: 'Sign Up', error: null });
});

app.post('/signup', async (req, res) => {
  try {
    const { email, password, name } = req.body;

    const result = await janua.auth.signUp({
      email,
      password,
      name
    });

    // Store user and tokens in cookies
    res.cookie('access_token', result.tokens.access_token, { httpOnly: true });
    res.cookie('refresh_token', result.tokens.refresh_token, { httpOnly: true });
    res.cookie('user', JSON.stringify(result.user));

    res.redirect('/dashboard');
  } catch (error: any) {
    res.render('signup', {
      title: 'Sign Up',
      error: error.message || 'Signup failed'
    });
  }
});

app.get('/login', (req, res) => {
  res.render('login', { title: 'Login', error: null });
});

app.post('/login', async (req, res) => {
  try {
    const { email, password } = req.body;

    const result = await janua.auth.signIn({
      email,
      password
    });

    // Store user and tokens in cookies
    res.cookie('access_token', result.tokens.access_token, { httpOnly: true });
    res.cookie('refresh_token', result.tokens.refresh_token, { httpOnly: true });
    res.cookie('user', JSON.stringify(result.user));

    res.redirect('/dashboard');
  } catch (error: any) {
    res.render('login', {
      title: 'Login',
      error: error.message || 'Login failed'
    });
  }
});

app.get('/dashboard', (req, res) => {
  const user = req.cookies.user ? JSON.parse(req.cookies.user) : null;

  if (!user) {
    return res.redirect('/login');
  }

  res.render('dashboard', {
    title: 'Dashboard',
    user
  });
});

app.get('/profile', (req, res) => {
  const user = req.cookies.user ? JSON.parse(req.cookies.user) : null;

  if (!user) {
    return res.redirect('/login');
  }

  res.render('profile', {
    title: 'Profile',
    user,
    success: null,
    error: null
  });
});

app.post('/profile', async (req, res) => {
  const user = req.cookies.user ? JSON.parse(req.cookies.user) : null;

  if (!user) {
    return res.redirect('/login');
  }

  try {
    const { name, email } = req.body;
    const accessToken = req.cookies.access_token;

    const updatedUser = await janua.users.updateCurrentUser(
      { name, email },
      { headers: { Authorization: `Bearer ${accessToken}` } }
    );

    res.cookie('user', JSON.stringify(updatedUser));

    res.render('profile', {
      title: 'Profile',
      user: updatedUser,
      success: 'Profile updated successfully',
      error: null
    });
  } catch (error: any) {
    res.render('profile', {
      title: 'Profile',
      user,
      success: null,
      error: error.message || 'Update failed'
    });
  }
});

app.get('/security', (req, res) => {
  const user = req.cookies.user ? JSON.parse(req.cookies.user) : null;

  if (!user) {
    return res.redirect('/login');
  }

  res.render('security', {
    title: 'Security Settings',
    user,
    mfaQrCode: null,
    backupCodes: null,
    success: null,
    error: null
  });
});

app.post('/security/mfa/enable', async (req, res) => {
  const user = req.cookies.user ? JSON.parse(req.cookies.user) : null;

  if (!user) {
    return res.redirect('/login');
  }

  try {
    const accessToken = req.cookies.access_token;

    const mfaSetup = await janua.auth.enableMFA(
      'totp',
      { headers: { Authorization: `Bearer ${accessToken}` } }
    );

    res.render('security', {
      title: 'Security Settings',
      user,
      mfaQrCode: mfaSetup.qr_code,
      backupCodes: mfaSetup.backup_codes,
      success: 'MFA enabled. Scan the QR code with your authenticator app.',
      error: null
    });
  } catch (error: any) {
    res.render('security', {
      title: 'Security Settings',
      user,
      mfaQrCode: null,
      backupCodes: null,
      success: null,
      error: error.message || 'Failed to enable MFA'
    });
  }
});

app.post('/security/mfa/verify', async (req, res) => {
  const user = req.cookies.user ? JSON.parse(req.cookies.user) : null;

  if (!user) {
    return res.redirect('/login');
  }

  try {
    const { code } = req.body;
    const accessToken = req.cookies.access_token;

    await janua.auth.verifyMFA(
      { code },
      { headers: { Authorization: `Bearer ${accessToken}` } }
    );

    res.render('security', {
      title: 'Security Settings',
      user,
      mfaQrCode: null,
      backupCodes: null,
      success: 'MFA verified successfully',
      error: null
    });
  } catch (error: any) {
    res.render('security', {
      title: 'Security Settings',
      user,
      mfaQrCode: null,
      backupCodes: null,
      success: null,
      error: error.message || 'MFA verification failed'
    });
  }
});

app.post('/security/password/change', async (req, res) => {
  const user = req.cookies.user ? JSON.parse(req.cookies.user) : null;

  if (!user) {
    return res.redirect('/login');
  }

  try {
    const { currentPassword, newPassword } = req.body;
    const accessToken = req.cookies.access_token;

    await janua.auth.changePassword(
      { current_password: currentPassword, new_password: newPassword },
      { headers: { Authorization: `Bearer ${accessToken}` } }
    );

    res.render('security', {
      title: 'Security Settings',
      user,
      mfaQrCode: null,
      backupCodes: null,
      success: 'Password changed successfully',
      error: null
    });
  } catch (error: any) {
    res.render('security', {
      title: 'Security Settings',
      user,
      mfaQrCode: null,
      backupCodes: null,
      success: null,
      error: error.message || 'Password change failed'
    });
  }
});

app.get('/passkey/register', (req, res) => {
  const user = req.cookies.user ? JSON.parse(req.cookies.user) : null;

  if (!user) {
    return res.redirect('/login');
  }

  res.render('passkey', {
    title: 'Passkey Registration',
    user,
    success: null,
    error: null
  });
});

app.post('/passkey/register/options', async (req, res) => {
  try {
    const accessToken = req.cookies.access_token;

    const options = await janua.auth.getPasskeyRegistrationOptions(
      { headers: { Authorization: `Bearer ${accessToken}` } }
    );

    res.json(options);
  } catch (error: any) {
    res.status(500).json({ error: error.message || 'Failed to get registration options' });
  }
});

app.post('/passkey/register/verify', async (req, res) => {
  try {
    const { credential } = req.body;
    const accessToken = req.cookies.access_token;

    await janua.auth.verifyPasskeyRegistration(
      credential,
      { headers: { Authorization: `Bearer ${accessToken}` } }
    );

    res.json({ success: true });
  } catch (error: any) {
    res.status(500).json({ error: error.message || 'Passkey registration failed' });
  }
});

app.post('/logout', (req, res) => {
  res.clearCookie('access_token');
  res.clearCookie('refresh_token');
  res.clearCookie('user');
  res.redirect('/');
});

// Error handler
app.use((err: Error, _req: express.Request, res: express.Response, _next: express.NextFunction) => {
  console.error('Error:', err);
  res.status(500).render('error', {
    title: 'Error',
    error: err.message
  });
});

// Start server
app.listen(PORT, () => {
  console.log(`Test app running on http://localhost:${PORT}`);
  console.log(`Janua API URL: ${process.env.JANUA_API_URL || 'http://localhost:8000'}`);
});

export default app;
