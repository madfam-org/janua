# Troubleshooting Guide

Common issues and solutions for Janua Identity Platform.

## Authentication Issues

### Invalid Credentials Error

**Problem**: User receives "Invalid credentials" error when trying to sign in.

**Solutions**:
1. Verify email and password are correct
2. Check if account is locked (too many failed attempts)
3. Ensure email is verified if email verification is required
4. Check if user exists in the correct tenant

```javascript
// Debug authentication
try {
  const response = await janua.auth.signIn({ email, password });
} catch (error) {
  console.log('Error code:', error.code);
  console.log('Error details:', error.details);
  
  if (error.code === 'ACCOUNT_LOCKED') {
    // Account is locked, show reset password option
  } else if (error.code === 'EMAIL_NOT_VERIFIED') {
    // Email needs verification
  }
}
```

### Session Expired

**Problem**: User gets logged out unexpectedly.

**Solutions**:
1. Check token expiration settings
2. Verify refresh token is working
3. Ensure clock sync between client and server

```javascript
// Handle session expiration
janua.on('session_expired', async () => {
  try {
    await janua.auth.refreshToken();
  } catch (error) {
    // Redirect to login
    window.location.href = '/login';
  }
});
```

### MFA Code Not Working

**Problem**: MFA verification fails with valid code.

**Solutions**:
1. Check time sync on authenticator device
2. Verify challenge ID is correct
3. Ensure code hasn't been used already
4. Try recovery code if available

```javascript
// MFA debugging
const debugMFA = async (code) => {
  const serverTime = await janua.getServerTime();
  const clientTime = Date.now();
  const timeDiff = Math.abs(serverTime - clientTime);
  
  if (timeDiff > 30000) { // 30 seconds
    console.warn('Time sync issue detected');
  }
};
```

## OAuth/Social Login Issues

### Redirect URI Mismatch

**Problem**: OAuth callback fails with "redirect_uri_mismatch" error.

**Solutions**:
1. Verify redirect URI matches exactly in:
   - Client configuration
   - OAuth provider settings
   - Request parameters
2. Check for trailing slashes
3. Ensure protocol matches (http vs https)

```javascript
// Correct redirect URI setup
const janua = new JanuaClient({
  redirectUri: 'https://app.example.com/auth/callback' // Must match exactly
});
```

### State Parameter Invalid

**Problem**: OAuth callback fails with "invalid_state" error.

**Solutions**:
1. Don't modify state parameter
2. Handle callback in same session
3. Check for CSRF token expiration

```javascript
// Proper state handling
const handleOAuthCallback = async (code, state) => {
  // State is verified automatically by SDK
  const response = await janua.auth.handleOAuthCallback(code, state);
};
```

### OAuth Provider Not Configured

**Problem**: Social login button doesn't work.

**Solutions**:
1. Verify provider is enabled in Janua dashboard
2. Check client ID and secret are configured
3. Ensure provider app is not in development mode

## Token Management Issues

### Token Not Refreshing

**Problem**: Access token expires but doesn't refresh automatically.

**Solutions**:
1. Check refresh token is stored
2. Verify refresh endpoint is accessible
3. Ensure refresh token hasn't expired

```javascript
// Manual token refresh
const refreshTokens = async () => {
  try {
    const tokens = await janua.auth.refreshToken();
    console.log('Tokens refreshed successfully');
  } catch (error) {
    if (error.code === 'REFRESH_TOKEN_EXPIRED') {
      // User must sign in again
      redirectToLogin();
    }
  }
};
```

### Token Storage Issues

**Problem**: Tokens not persisting between sessions.

**Solutions**:
1. Check storage implementation
2. Verify cookies are enabled (if using cookies)
3. Check localStorage quota
4. Ensure secure context for secure storage

```javascript
// Custom storage implementation
const secureStorage = {
  getItem: async (key) => {
    // Implement secure retrieval
    return await SecureStore.getItemAsync(key);
  },
  setItem: async (key, value) => {
    // Implement secure storage
    await SecureStore.setItemAsync(key, value);
  },
  removeItem: async (key) => {
    await SecureStore.deleteItemAsync(key);
  }
};

const janua = new JanuaClient({
  storage: secureStorage
});
```

## Network and Connection Issues

### CORS Errors

**Problem**: Browser blocks requests with CORS error.

**Solutions**:
1. Verify allowed origins in Janua configuration
2. Check for preflight request issues
3. Ensure credentials are included correctly

```javascript
// CORS configuration
const janua = new JanuaClient({
  baseURL: 'https://api.janua.dev',
  credentials: 'include', // For cookies
  headers: {
    'Content-Type': 'application/json'
  }
});
```

### Rate Limiting

**Problem**: Requests failing with 429 status code.

**Solutions**:
1. Implement exponential backoff
2. Cache responses when possible
3. Batch operations
4. Check rate limit headers

```javascript
// Rate limit handling
const handleRateLimit = async (fn, ...args) => {
  try {
    return await fn(...args);
  } catch (error) {
    if (error.code === 'RATE_LIMITED') {
      const retryAfter = error.retryAfter || 60;
      await new Promise(resolve => setTimeout(resolve, retryAfter * 1000));
      return handleRateLimit(fn, ...args);
    }
    throw error;
  }
};
```

### Connection Timeouts

**Problem**: Requests timing out in slow network conditions.

**Solutions**:
1. Increase timeout settings
2. Implement retry logic
3. Use connection pooling
4. Check network latency

```javascript
// Timeout configuration
const janua = new JanuaClient({
  timeout: 30000, // 30 seconds
  retryConfig: {
    retries: 3,
    retryDelay: 1000,
    retryOn: [408, 429, 500, 502, 503, 504]
  }
});
```

## Mobile SDK Issues

### Biometric Authentication Not Available

**Problem**: Biometric authentication option not showing.

**Solutions**:
1. Check device capabilities
2. Verify permissions granted
3. Ensure keychain/keystore access
4. Check OS version requirements

```javascript
// React Native biometric check
import * as Keychain from 'react-native-keychain';

const checkBiometric = async () => {
  const biometryType = await Keychain.getSupportedBiometryType();
  
  if (!biometryType) {
    console.log('Biometric not supported');
    return false;
  }
  
  console.log('Biometric type:', biometryType);
  return true;
};
```

### Deep Linking Not Working

**Problem**: OAuth callback not returning to app.

**Solutions**:
1. Verify URL scheme registration
2. Check Android intent filters
3. Ensure iOS universal links configured
4. Test with correct URL format

```bash
# iOS testing
xcrun simctl openurl booted "yourapp://auth/callback?code=test"

# Android testing
adb shell am start -W -a android.intent.action.VIEW \
  -d "yourapp://auth/callback?code=test" com.yourapp
```

### Keychain/Keystore Access Denied

**Problem**: Can't access secure storage.

**Solutions**:
1. Check app entitlements (iOS)
2. Verify keystore configuration (Android)
3. Handle biometric cancellation
4. Implement fallback storage

```javascript
// Fallback storage strategy
const getToken = async () => {
  try {
    // Try secure storage first
    return await Keychain.getInternetCredentials('janua');
  } catch (error) {
    // Fallback to AsyncStorage
    return await AsyncStorage.getItem('janua_token');
  }
};
```

## WebAuthn/Passkeys Issues

### Passkey Registration Fails

**Problem**: Can't register new passkey.

**Solutions**:
1. Check browser compatibility
2. Verify HTTPS context
3. Ensure authenticator available
4. Check relying party ID

```javascript
// WebAuthn compatibility check
if (!window.PublicKeyCredential) {
  console.error('WebAuthn not supported');
  return;
}

// Check if platform authenticator available
const available = await PublicKeyCredential.isUserVerifyingPlatformAuthenticatorAvailable();
if (!available) {
  console.warn('Platform authenticator not available');
}
```

### Passkey Not Recognized

**Problem**: Existing passkey not working for authentication.

**Solutions**:
1. Verify credential ID matches
2. Check user handle correctness
3. Ensure challenge is fresh
4. Verify domain matching

```javascript
// Debug passkey authentication
const debugPasskey = async () => {
  const credentials = await navigator.credentials.get({
    publicKey: {
      challenge: new Uint8Array(32),
      allowCredentials: [{
        id: credentialId,
        type: 'public-key'
      }],
      userVerification: 'preferred'
    }
  });
  
  console.log('Credential used:', credentials.id);
};
```

## Organization Management Issues

### Can't Switch Organizations

**Problem**: User stuck in one organization context.

**Solutions**:
1. Clear organization cache
2. Verify membership status
3. Check role permissions
4. Refresh organization list

```javascript
// Organization switching
const switchOrganization = async (orgId) => {
  // Clear current context
  await janua.clearOrganizationContext();
  
  // Set new organization
  await janua.setOrganization(orgId);
  
  // Refresh user permissions
  await janua.users.refreshPermissions();
};
```

### Invite Links Not Working

**Problem**: Organization invite links expire or don't work.

**Solutions**:
1. Check invite expiration time
2. Verify invite token format
3. Ensure user not already member
4. Check organization settings

```javascript
// Invite handling
const acceptInvite = async (inviteToken) => {
  try {
    const result = await janua.organizations.acceptInvite(inviteToken);
    console.log('Joined organization:', result.organization.name);
  } catch (error) {
    if (error.code === 'INVITE_EXPIRED') {
      // Request new invite
    } else if (error.code === 'ALREADY_MEMBER') {
      // User is already a member
    }
  }
};
```

## Performance Issues

### Slow Authentication

**Problem**: Sign in takes too long.

**Solutions**:
1. Check network latency
2. Optimize password hashing rounds
3. Use connection pooling
4. Implement caching

```javascript
// Performance monitoring
const measureAuthTime = async () => {
  const start = performance.now();
  
  try {
    await janua.auth.signIn({ email, password });
    const duration = performance.now() - start;
    
    if (duration > 3000) {
      console.warn(`Slow authentication: ${duration}ms`);
    }
  } catch (error) {
    // Handle error
  }
};
```

### Memory Leaks

**Problem**: Application memory usage increases over time.

**Solutions**:
1. Remove event listeners
2. Clear intervals/timeouts
3. Dispose of unused resources
4. Implement cleanup

```javascript
// Cleanup on unmount
class AuthComponent {
  constructor() {
    this.refreshInterval = setInterval(() => {
      this.refreshToken();
    }, 30 * 60 * 1000);
    
    janua.on('session_expired', this.handleExpired);
  }
  
  destroy() {
    clearInterval(this.refreshInterval);
    janua.off('session_expired', this.handleExpired);
  }
}
```

## Debugging Tools

### Enable Debug Mode

```javascript
// Enable verbose logging
const janua = new JanuaClient({
  debug: true,
  logLevel: 'verbose'
});

// Custom logger
janua.setLogger({
  log: (...args) => console.log('[Janua]', ...args),
  error: (...args) => console.error('[Janua Error]', ...args),
  warn: (...args) => console.warn('[Janua Warning]', ...args)
});
```

### Network Inspection

```javascript
// Intercept requests
janua.interceptors.request.use(request => {
  console.log('Request:', request);
  return request;
});

// Intercept responses
janua.interceptors.response.use(
  response => {
    console.log('Response:', response);
    return response;
  },
  error => {
    console.error('Error:', error);
    return Promise.reject(error);
  }
);
```

### State Inspection

```javascript
// Get current state
const debugState = () => {
  console.log('User:', janua.currentUser);
  console.log('Authenticated:', janua.isAuthenticated);
  console.log('Organization:', janua.currentOrganization);
  console.log('Permissions:', janua.permissions);
  console.log('Token Expiry:', janua.tokenExpiry);
};
```

## Getting Help

If you continue to experience issues:

1. **Check Documentation**: https://docs.janua.dev
2. **Search Issues**: https://github.com/madfam-io/janua-sdks/issues
3. **Community Forum**: https://community.janua.dev
4. **Contact Support**: support@janua.dev

When reporting issues, include:
- SDK version
- Platform/Browser
- Error messages
- Network logs
- Reproduction steps