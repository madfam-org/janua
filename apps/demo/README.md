# Janua Demo App

Interactive demo application showcasing Janua's authentication features.

## Quick Start

```bash
npm install
npm run dev
```

Opens at [http://localhost:4105](http://localhost:4105).

## Features

- Email/password authentication flow
- OAuth provider integration (Google, GitHub)
- Multi-factor authentication (TOTP)
- WebAuthn/Passkey registration and login
- Session management
- Organization switching

## Configuration

Set the API URL in `.env.local`:

```
NEXT_PUBLIC_JANUA_API_URL=http://localhost:4100
```

## Related

- [API Documentation](../api/docs/)
- [React SDK](../../packages/react-sdk/)
- [TypeScript SDK](../../packages/typescript-sdk/)
