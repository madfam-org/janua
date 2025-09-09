import { v4 as uuidv4 } from 'uuid';
import bcrypt from 'bcryptjs';

interface User {
  id: string;
  email: string;
  password: string;
  name?: string;
  email_verified: boolean;
  created_at: string;
  updated_at: string;
  metadata?: Record<string, any>;
  mfa_enabled?: boolean;
  mfa_secret?: string;
}

interface Session {
  id: string;
  user_id: string;
  token: string;
  refresh_token: string;
  created_at: string;
  expires_at: string;
  last_active: string;
  ip_address?: string;
  user_agent?: string;
}

interface Organization {
  id: string;
  name: string;
  slug: string;
  created_at: string;
  updated_at: string;
  owner_id: string;
}

interface OrganizationMember {
  id: string;
  organization_id: string;
  user_id: string;
  role: string;
  joined_at: string;
}

class MockDatabase {
  private users: Map<string, User> = new Map();
  private sessions: Map<string, Session> = new Map();
  private organizations: Map<string, Organization> = new Map();
  private organizationMembers: Map<string, OrganizationMember> = new Map();
  private emailToUser: Map<string, string> = new Map();
  private tokenToSession: Map<string, string> = new Map();
  private verificationTokens: Map<string, { userId: string; expires: Date }> = new Map();
  private resetTokens: Map<string, { userId: string; expires: Date }> = new Map();

  init() {
    // Create demo user
    this.createUser({
      email: 'demo@plinto.dev',
      password: 'DemoPassword123!',
      name: 'Demo User',
      email_verified: true
    });
  }

  // User methods
  async createUser(data: {
    email: string;
    password: string;
    name?: string;
    email_verified?: boolean;
  }): Promise<User> {
    if (this.emailToUser.has(data.email)) {
      throw new Error('Email already exists');
    }

    const hashedPassword = await bcrypt.hash(data.password, 10);
    const user: User = {
      id: uuidv4(),
      email: data.email,
      password: hashedPassword,
      name: data.name,
      email_verified: data.email_verified || false,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString()
    };

    this.users.set(user.id, user);
    this.emailToUser.set(user.email, user.id);

    // Create default organization for user
    const org = await this.createOrganization({
      name: `${data.name || data.email}'s Organization`,
      owner_id: user.id
    });

    return user;
  }

  async getUserByEmail(email: string): Promise<User | null> {
    const userId = this.emailToUser.get(email);
    if (!userId) return null;
    return this.users.get(userId) || null;
  }

  async getUserById(id: string): Promise<User | null> {
    return this.users.get(id) || null;
  }

  async updateUser(id: string, data: Partial<User>): Promise<User | null> {
    const user = this.users.get(id);
    if (!user) return null;

    const updated = {
      ...user,
      ...data,
      id: user.id, // Prevent ID change
      email: user.email, // Prevent email change without verification
      updated_at: new Date().toISOString()
    };

    this.users.set(id, updated);
    return updated;
  }

  async deleteUser(id: string): Promise<boolean> {
    const user = this.users.get(id);
    if (!user) return false;

    this.users.delete(id);
    this.emailToUser.delete(user.email);
    
    // Delete all user sessions
    for (const [sessionId, session] of this.sessions) {
      if (session.user_id === id) {
        this.sessions.delete(sessionId);
        this.tokenToSession.delete(session.token);
      }
    }

    return true;
  }

  async verifyPassword(email: string, password: string): Promise<boolean> {
    const user = await this.getUserByEmail(email);
    if (!user) return false;
    return bcrypt.compare(password, user.password);
  }

  async changePassword(userId: string, newPassword: string): Promise<boolean> {
    const user = this.users.get(userId);
    if (!user) return false;

    const hashedPassword = await bcrypt.hash(newPassword, 10);
    user.password = hashedPassword;
    user.updated_at = new Date().toISOString();
    
    this.users.set(userId, user);
    return true;
  }

  // Session methods
  createSession(userId: string, token: string, refreshToken: string): Session {
    const session: Session = {
      id: uuidv4(),
      user_id: userId,
      token,
      refresh_token: refreshToken,
      created_at: new Date().toISOString(),
      expires_at: new Date(Date.now() + 3600000).toISOString(), // 1 hour
      last_active: new Date().toISOString()
    };

    this.sessions.set(session.id, session);
    this.tokenToSession.set(token, session.id);
    
    return session;
  }

  getSessionByToken(token: string): Session | null {
    const sessionId = this.tokenToSession.get(token);
    if (!sessionId) return null;
    
    const session = this.sessions.get(sessionId);
    if (!session) return null;
    
    // Check if expired
    if (new Date(session.expires_at) < new Date()) {
      this.deleteSession(sessionId);
      return null;
    }
    
    // Update last active
    session.last_active = new Date().toISOString();
    this.sessions.set(sessionId, session);
    
    return session;
  }

  getUserSessions(userId: string): Session[] {
    const userSessions: Session[] = [];
    for (const session of this.sessions.values()) {
      if (session.user_id === userId) {
        userSessions.push(session);
      }
    }
    return userSessions;
  }

  deleteSession(sessionId: string): boolean {
    const session = this.sessions.get(sessionId);
    if (!session) return false;
    
    this.sessions.delete(sessionId);
    this.tokenToSession.delete(session.token);
    return true;
  }

  deleteUserSessions(userId: string): void {
    for (const [sessionId, session] of this.sessions) {
      if (session.user_id === userId) {
        this.deleteSession(sessionId);
      }
    }
  }

  // Organization methods
  async createOrganization(data: {
    name: string;
    slug?: string;
    owner_id: string;
  }): Promise<Organization> {
    const org: Organization = {
      id: uuidv4(),
      name: data.name,
      slug: data.slug || data.name.toLowerCase().replace(/\s+/g, '-'),
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
      owner_id: data.owner_id
    };

    this.organizations.set(org.id, org);

    // Add owner as member
    const member: OrganizationMember = {
      id: uuidv4(),
      organization_id: org.id,
      user_id: data.owner_id,
      role: 'owner',
      joined_at: new Date().toISOString()
    };
    this.organizationMembers.set(member.id, member);

    return org;
  }

  getUserOrganizations(userId: string): Organization[] {
    const userOrgs: Organization[] = [];
    
    for (const member of this.organizationMembers.values()) {
      if (member.user_id === userId) {
        const org = this.organizations.get(member.organization_id);
        if (org) userOrgs.push(org);
      }
    }
    
    return userOrgs;
  }

  getOrganization(id: string): Organization | null {
    return this.organizations.get(id) || null;
  }

  // Token methods
  createVerificationToken(userId: string): string {
    const token = uuidv4();
    this.verificationTokens.set(token, {
      userId,
      expires: new Date(Date.now() + 15 * 60 * 1000) // 15 minutes
    });
    return token;
  }

  verifyEmailToken(token: string): string | null {
    const data = this.verificationTokens.get(token);
    if (!data) return null;
    
    if (data.expires < new Date()) {
      this.verificationTokens.delete(token);
      return null;
    }
    
    this.verificationTokens.delete(token);
    
    // Mark user as verified
    const user = this.users.get(data.userId);
    if (user) {
      user.email_verified = true;
      user.updated_at = new Date().toISOString();
      this.users.set(data.userId, user);
    }
    
    return data.userId;
  }

  createResetToken(email: string): string | null {
    const userId = this.emailToUser.get(email);
    if (!userId) return null;
    
    const token = uuidv4();
    this.resetTokens.set(token, {
      userId,
      expires: new Date(Date.now() + 30 * 60 * 1000) // 30 minutes
    });
    
    return token;
  }

  verifyResetToken(token: string): string | null {
    const data = this.resetTokens.get(token);
    if (!data) return null;
    
    if (data.expires < new Date()) {
      this.resetTokens.delete(token);
      return null;
    }
    
    return data.userId;
  }

  consumeResetToken(token: string): string | null {
    const userId = this.verifyResetToken(token);
    if (userId) {
      this.resetTokens.delete(token);
    }
    return userId;
  }

  // MFA methods
  enableMFA(userId: string, secret: string): boolean {
    const user = this.users.get(userId);
    if (!user) return false;
    
    user.mfa_enabled = true;
    user.mfa_secret = secret;
    user.updated_at = new Date().toISOString();
    
    this.users.set(userId, user);
    return true;
  }

  disableMFA(userId: string): boolean {
    const user = this.users.get(userId);
    if (!user) return false;
    
    user.mfa_enabled = false;
    user.mfa_secret = undefined;
    user.updated_at = new Date().toISOString();
    
    this.users.set(userId, user);
    return true;
  }

  getMFASecret(userId: string): string | null {
    const user = this.users.get(userId);
    return user?.mfa_secret || null;
  }

  isMFAEnabled(userId: string): boolean {
    const user = this.users.get(userId);
    return user?.mfa_enabled || false;
  }
}

export const db = new MockDatabase();