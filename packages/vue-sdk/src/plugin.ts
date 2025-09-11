import { App, reactive, readonly } from 'vue';
import { PlintoClient } from '@plinto/js';
import type { User, Session, PlintoConfig } from '@plinto/js';

export interface PlintoState {
  user: User | null;
  session: Session | null;
  isLoading: boolean;
  isAuthenticated: boolean;
}

export interface PlintoPluginOptions extends PlintoConfig {
  onAuthChange?: (user: User | null) => void;
}

const PLINTO_KEY = Symbol('plinto');

class PlintoVue {
  private client: PlintoClient;
  private state: PlintoState;
  private onAuthChange?: (user: User | null) => void;

  constructor(options: PlintoPluginOptions) {
    const { onAuthChange, ...config } = options;
    
    this.client = new PlintoClient(config);
    this.onAuthChange = onAuthChange;
    
    this.state = reactive({
      user: null,
      session: null,
      isLoading: true,
      isAuthenticated: false,
    });

    this.initialize();
  }

  private async initialize() {
    try {
      // Check for auth params in URL
      if (this.client.hasAuthParams()) {
        await this.client.handleRedirectCallback();
      }

      this.updateAuthState();
    } catch (error) {
      console.error('Failed to initialize Plinto:', error);
    } finally {
      this.state.isLoading = false;
    }

    // Set up periodic auth state check
    setInterval(() => {
      const currentUser = this.client.getUser();
      if (currentUser !== this.state.user) {
        this.updateAuthState();
      }
    }, 1000);
  }

  private updateAuthState() {
    const user = this.client.getUser();
    const session = this.client.getSession();
    
    this.state.user = user;
    this.state.session = session;
    this.state.isAuthenticated = !!user && !!session;

    if (this.onAuthChange) {
      this.onAuthChange(user);
    }
  }

  async signIn(email: string, password: string) {
    const response = await this.client.auth.signIn({ email, password });
    this.updateAuthState();
    return response;
  }

  async signUp(data: {
    email: string;
    password: string;
    firstName?: string;
    lastName?: string;
  }) {
    const response = await this.client.auth.signUp(data);
    this.updateAuthState();
    return response;
  }

  async signOut() {
    await this.client.signOut();
    this.state.user = null;
    this.state.session = null;
    this.state.isAuthenticated = false;

    if (this.onAuthChange) {
      this.onAuthChange(null);
    }
  }

  async updateSession() {
    await this.client.updateSession();
    this.updateAuthState();
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

export const createPlinto = (options: PlintoPluginOptions) => {
  return {
    install(app: App) {
      const plinto = new PlintoVue(options);
      app.provide(PLINTO_KEY, plinto);
      app.config.globalProperties.$plinto = plinto;
    },
  };
};

export { PLINTO_KEY };
export type { PlintoVue };