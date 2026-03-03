import { App, reactive, readonly } from 'vue';
import { JanuaClient } from '@janua/typescript-sdk';
import type { User, Session, JanuaConfig } from '@janua/typescript-sdk';

export interface JanuaState {
  user: User | null;
  session: Session | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  error: Error | null;
}

export interface JanuaPluginOptions extends JanuaConfig {
  onAuthChange?: (user: User | null) => void;
  /** Polling interval in ms for auth state checks (default: 60000) */
  pollInterval?: number;
}

const JANUA_KEY = Symbol('janua');

export class JanuaVue {
  private client: JanuaClient;
  private state: JanuaState;
  private onAuthChange?: (user: User | null) => void;
  private pollIntervalId: ReturnType<typeof setInterval> | null = null;

  constructor(options: JanuaPluginOptions) {
    const { onAuthChange, pollInterval, ...config } = options;

    this.client = new JanuaClient(config);
    this.onAuthChange = onAuthChange;

    this.state = reactive({
      user: null,
      session: null,
      isLoading: true,
      isAuthenticated: false,
      error: null,
    });

    this.initialize(pollInterval);
  }

  private async initialize(pollInterval = 60_000) {
    // SSR guard: skip browser-only logic on server
    if (typeof window === 'undefined') {
      this.state.isLoading = false;
      return;
    }

    try {
      // Check for OAuth callback parameters in URL
      const urlParams = new URLSearchParams(window.location.search);
      if (urlParams.has('code') && urlParams.has('state')) {
        const code = urlParams.get('code')!;
        const state = urlParams.get('state')!;
        await this.client.auth.handleOAuthCallback(code, state);
        // Clean OAuth params from URL
        window.history.replaceState({}, '', window.location.pathname);
      }

      await this.updateAuthState();
    } catch (error) {
      this.state.error = error instanceof Error ? error : new Error(String(error));
    } finally {
      this.state.isLoading = false;
    }

    // Set up periodic auth state check (60s default, not 1s)
    this.pollIntervalId = setInterval(async () => {
      try {
        await this.updateAuthState();
      } catch {
        // Polling errors are non-fatal
      }
    }, pollInterval);
  }

  /**
   * Clean up intervals and resources. Called on app unmount.
   */
  destroy() {
    if (this.pollIntervalId !== null) {
      clearInterval(this.pollIntervalId);
      this.pollIntervalId = null;
    }
  }

  private async updateAuthState() {
    const user = await this.client.getCurrentUser();
    const session = user ? {
      accessToken: await this.client.getAccessToken(),
      refreshToken: await this.client.getRefreshToken()
    } as any : null;

    this.state.user = user;
    this.state.session = session;
    this.state.isAuthenticated = !!user && !!session;

    if (this.onAuthChange) {
      this.onAuthChange(user);
    }
  }

  async signIn(email: string, password: string) {
    this.state.error = null;
    try {
      const response = await this.client.auth.signIn({ email, password });
      await this.updateAuthState();
      return response;
    } catch (error) {
      this.state.error = error instanceof Error ? error : new Error(String(error));
      throw error;
    }
  }

  async signUp(data: {
    email: string;
    password: string;
    firstName?: string;
    lastName?: string;
  }) {
    this.state.error = null;
    try {
      const response = await this.client.auth.signUp(data);
      await this.updateAuthState();
      return response;
    } catch (error) {
      this.state.error = error instanceof Error ? error : new Error(String(error));
      throw error;
    }
  }

  async signOut() {
    await this.client.signOut();
    this.state.user = null;
    this.state.session = null;
    this.state.isAuthenticated = false;
    this.state.error = null;

    if (this.onAuthChange) {
      this.onAuthChange(null);
    }
  }

  async updateSession() {
    await this.client.auth.getCurrentUser();
    await this.updateAuthState();
  }

  getClient() {
    return this.client;
  }

  getState() {
    return readonly(this.state);
  }

  getUser() {
    return this.state.user;
  }

  getSession() {
    return this.state.session;
  }

  isAuthenticated() {
    return this.state.isAuthenticated;
  }
}

export const createJanua = (options: JanuaPluginOptions) => {
  return {
    install(app: App) {
      const janua = new JanuaVue(options);
      app.provide(JANUA_KEY, janua);
      app.config.globalProperties.$janua = janua;

      // Hook cleanup into app.unmount to prevent memory leaks
      const origUnmount = app.unmount.bind(app);
      app.unmount = () => {
        janua.destroy();
        origUnmount();
      };
    },
  };
};

export { JANUA_KEY };
export type { JanuaVue as JanuaVueType };
