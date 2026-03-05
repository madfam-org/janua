import { cookies } from 'next/headers';
import { NextRequest } from 'next/server';
import { SignJWT, jwtVerify } from 'jose';
import { JanuaClient } from '@janua/typescript-sdk';
import type { User, Session } from '@janua/typescript-sdk';

const COOKIE_NAME = 'janua-session';
const COOKIE_OPTIONS = {
  httpOnly: true,
  secure: process.env.NODE_ENV === 'production',
  sameSite: 'lax' as const,
  path: '/',
  maxAge: 60 * 60 * 24 * 7, // 7 days
};

interface SessionData {
  user: User;
  session: Session;
  accessToken: string;
  refreshToken: string;
}

export class JanuaServerClient {
  private client: JanuaClient;
  private secret: Uint8Array;

  constructor(config: { appId: string; apiKey: string; jwtSecret: string }) {
    this.client = new JanuaClient({
      baseURL: process.env.NEXT_PUBLIC_API_URL!,
      apiKey: config.apiKey,
    });

    this.secret = new TextEncoder().encode(config.jwtSecret);
  }

  private async encryptSession(data: SessionData): Promise<string> {
    const jwt = await new SignJWT({ data })
      .setProtectedHeader({ alg: 'HS256' })
      .setIssuedAt()
      .setExpirationTime('7d')
      .sign(this.secret);
    
    return jwt;
  }

  private async decryptSession(token: string): Promise<SessionData | null> {
    try {
      const { payload } = await jwtVerify(token, this.secret);
      return payload.data as SessionData;
    } catch {
      return null;
    }
  }

  async getSession(): Promise<{ user: User; session: Session } | null> {
    const cookieStore = await cookies();
    const sessionCookie = cookieStore.get(COOKIE_NAME);
    
    if (!sessionCookie) {
      return null;
    }

    const sessionData = await this.decryptSession(sessionCookie.value);
    if (!sessionData) {
      return null;
    }

    return {
      user: sessionData.user,
      session: sessionData.session,
    };
  }

  async requireAuth(): Promise<{ user: User; session: Session }> {
    const session = await this.getSession();
    
    if (!session) {
      throw new Error('Authentication required');
    }

    return session;
  }

  async signIn(email: string, password: string): Promise<{ user: User; session: Session }> {
    const response = await this.client.auth.signIn({ email, password });
    
    const sessionData: SessionData = {
      user: response.user,
      session: {
        id: 'temp',
        user_id: response.user.id,
        is_current: true,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
        expires_at: new Date(Date.now() + 24 * 60 * 60 * 1000).toISOString(),
        last_activity: new Date().toISOString()
      } as any,
      accessToken: response.tokens.access_token,
      refreshToken: response.tokens.refresh_token,
    };

    const encryptedSession = await this.encryptSession(sessionData);
    const cookieStore = await cookies();
    cookieStore.set(COOKIE_NAME, encryptedSession, COOKIE_OPTIONS);

    return {
      user: response.user,
      session: {
        id: 'temp',
        user_id: response.user.id,
        is_current: true,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
        expires_at: new Date(Date.now() + 24 * 60 * 60 * 1000).toISOString(),
        last_activity: new Date().toISOString()
      } as any,
    };
  }

  async signUp(data: {
    email: string;
    password: string;
    firstName?: string;
    lastName?: string;
  }): Promise<{ user: User; session: Session }> {
    const response = await this.client.auth.signUp(data);
    
    const sessionData: SessionData = {
      user: response.user,
      session: {
        id: 'temp',
        user_id: response.user.id,
        is_current: true,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
        expires_at: new Date(Date.now() + 24 * 60 * 60 * 1000).toISOString(),
        last_activity: new Date().toISOString()
      } as any,
      accessToken: response.tokens.access_token,
      refreshToken: response.tokens.refresh_token,
    };

    const encryptedSession = await this.encryptSession(sessionData);
    const cookieStore = await cookies();
    cookieStore.set(COOKIE_NAME, encryptedSession, COOKIE_OPTIONS);

    return {
      user: response.user,
      session: {
        id: 'temp',
        user_id: response.user.id,
        is_current: true,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
        expires_at: new Date(Date.now() + 24 * 60 * 60 * 1000).toISOString(),
        last_activity: new Date().toISOString()
      } as any,
    };
  }

  async handleOAuthCallback(code: string, codeVerifier?: string): Promise<{ user: User; session: Session }> {
    const response = await this.client.auth.handleOAuthCallback(code, codeVerifier || '');

    const sessionData: SessionData = {
      user: response.user,
      session: {
        id: 'temp',
        user_id: response.user.id,
        is_current: true,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
        expires_at: new Date(Date.now() + 24 * 60 * 60 * 1000).toISOString(),
        last_activity: new Date().toISOString()
      } as any,
      accessToken: response.tokens.access_token,
      refreshToken: response.tokens.refresh_token,
    };

    const encryptedSession = await this.encryptSession(sessionData);
    const cookieStore = await cookies();
    cookieStore.set(COOKIE_NAME, encryptedSession, COOKIE_OPTIONS);

    return {
      user: response.user,
      session: sessionData.session,
    };
  }

  async signOut(): Promise<void> {
    const sessionData = await this.getSession();
    
    if (sessionData) {
      try {
        await this.client.auth.signOut();
      } catch {
        // Ignore errors
      }
    }

    const cookieStore = await cookies();
    cookieStore.delete(COOKIE_NAME);
  }

  async updateUser(data: any): Promise<User> {
    const session = await this.requireAuth();
    const updatedUser = await this.client.users.update(session.user.id, data);
    
    // Update session cookie with new user data
    const cookieStore = await cookies();
    const sessionCookie = cookieStore.get(COOKIE_NAME);
    
    if (sessionCookie) {
      const sessionData = await this.decryptSession(sessionCookie.value);
      if (sessionData) {
        sessionData.user = updatedUser;
        const encryptedSession = await this.encryptSession(sessionData);
        cookieStore.set(COOKIE_NAME, encryptedSession, COOKIE_OPTIONS);
      }
    }

    return updatedUser;
  }

  getClient(): JanuaClient {
    return this.client;
  }
}

// Helper functions for server components
export async function getSession(
  appId: string,
  apiKey: string,
  jwtSecret: string
): Promise<{ user: User; session: Session } | null> {
  const client = new JanuaServerClient({ appId, apiKey, jwtSecret });
  return client.getSession();
}

export async function requireAuth(
  appId: string,
  apiKey: string,
  jwtSecret: string
): Promise<{ user: User; session: Session }> {
  const client = new JanuaServerClient({ appId, apiKey, jwtSecret });
  return client.requireAuth();
}

// Helper to validate session in API routes
export async function validateRequest(
  request: NextRequest,
  jwtSecret: string
): Promise<SessionData | null> {
  const sessionCookie = request.cookies.get(COOKIE_NAME);
  
  if (!sessionCookie) {
    return null;
  }

  try {
    const secret = new TextEncoder().encode(jwtSecret);
    const { payload } = await jwtVerify(sessionCookie.value, secret);
    return payload.data as SessionData;
  } catch {
    return null;
  }
}