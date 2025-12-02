# Janua React Native SDK Example

This example app demonstrates all features of the Janua React Native SDK including:

## Features Demonstrated

- **Email/Password Authentication**
  - Sign up with email and password
  - Sign in with existing credentials
  - Password reset flow

- **Social Authentication**
  - Google OAuth integration
  - GitHub OAuth integration
  - Deep linking for OAuth callbacks

- **Multi-Factor Authentication (MFA)**
  - Enable TOTP-based MFA
  - QR code generation for authenticator apps
  - Recovery codes
  - MFA verification

- **Biometric Authentication**
  - Face ID (iOS)
  - Touch ID (iOS)
  - Fingerprint (Android)
  - Secure credential storage

- **Session Management**
  - List active sessions
  - View session details (device, location, time)
  - Revoke individual sessions
  - Revoke all sessions

- **Organization Management**
  - List user organizations
  - Create new organizations
  - View organization roles

## Setup

1. Install dependencies:
```bash
npm install
# or
yarn install
```

2. Configure your Janua credentials in `App.tsx`:
```typescript
const janua = new JanuaClient({
  baseURL: 'https://api.janua.dev',
  tenantId: 'YOUR_TENANT_ID',
  clientId: 'YOUR_CLIENT_ID',
  redirectUri: 'janua-example://auth/callback',
});
```

3. Configure deep linking for OAuth:

### iOS (Info.plist)
```xml
<key>CFBundleURLTypes</key>
<array>
  <dict>
    <key>CFBundleURLSchemes</key>
    <array>
      <string>janua-example</string>
    </array>
  </dict>
</array>
```

### Android (AndroidManifest.xml)
```xml
<intent-filter>
  <action android:name="android.intent.action.VIEW" />
  <category android:name="android.intent.category.DEFAULT" />
  <category android:name="android.intent.category.BROWSABLE" />
  <data android:scheme="janua-example" />
</intent-filter>
```

4. Run the app:
```bash
# iOS
npm run ios

# Android
npm run android

# Web (Expo)
npm run web
```

## Architecture

The example app demonstrates best practices for:

- **State Management**: Using React hooks for authentication state
- **Error Handling**: Proper error boundaries and user feedback
- **Security**: Secure token storage with Keychain/Keystore
- **UX Patterns**: Loading states, form validation, error messages
- **Deep Linking**: OAuth callback handling
- **Biometric Security**: Platform-specific biometric authentication

## Code Structure

```
example/
├── App.tsx              # Main application component
├── package.json         # Dependencies
├── README.md           # This file
└── tsconfig.json       # TypeScript configuration
```

## Key Implementation Details

### Secure Token Storage
Tokens are stored using platform-specific secure storage:
- iOS: Keychain Services
- Android: Android Keystore

### Biometric Authentication
The app checks for biometric support and enables:
- Face ID/Touch ID on iOS
- Fingerprint/Face recognition on Android

### OAuth Flow
1. User initiates social login
2. App opens authorization URL in browser
3. User authorizes the app
4. Browser redirects back to app with code
5. App exchanges code for tokens
6. User is authenticated

### Session Management
The app demonstrates comprehensive session management:
- Real-time session listing
- Device and location information
- Individual session revocation
- Bulk session termination

## Troubleshooting

### Biometric Authentication Not Working
- Ensure device has biometric hardware
- Check that biometric authentication is enabled in device settings
- Verify app has necessary permissions

### OAuth Callbacks Not Working
- Verify deep linking configuration
- Check redirect URI matches your Janua app settings
- Ensure URL schemes are properly registered

### Build Issues
- Clear Metro bundler cache: `npx react-native start --reset-cache`
- Rebuild native dependencies: `cd ios && pod install`
- Clean build folders: `cd android && ./gradlew clean`

## Support

For issues or questions:
- GitHub Issues: https://github.com/madfam-io/janua-sdks
- Documentation: https://docs.janua.dev
- Support: support@janua.dev