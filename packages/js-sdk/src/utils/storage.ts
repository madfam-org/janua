export interface StorageAdapter {
  get(key: string): string | null;
  set(key: string, value: string): void;
  remove(key: string): void;
  clear(): void;
}

export class MemoryStorage implements StorageAdapter {
  private store: Map<string, string> = new Map();

  get(key: string): string | null {
    return this.store.get(key) || null;
  }

  set(key: string, value: string): void {
    this.store.set(key, value);
  }

  remove(key: string): void {
    this.store.delete(key);
  }

  clear(): void {
    this.store.clear();
  }
}

export class BrowserStorage implements StorageAdapter {
  private storage: Storage;

  constructor(type: 'local' | 'session' = 'local') {
    if (typeof window === 'undefined') {
      throw new Error('BrowserStorage can only be used in browser environments');
    }
    this.storage = type === 'local' ? window.localStorage : window.sessionStorage;
  }

  get(key: string): string | null {
    try {
      return this.storage.getItem(key);
    } catch {
      return null;
    }
  }

  set(key: string, value: string): void {
    try {
      this.storage.setItem(key, value);
    } catch (error) {
      console.error('Failed to save to storage:', error);
    }
  }

  remove(key: string): void {
    try {
      this.storage.removeItem(key);
    } catch {
      // Ignore errors
    }
  }

  clear(): void {
    try {
      this.storage.clear();
    } catch {
      // Ignore errors
    }
  }
}

export class SecureStorage implements StorageAdapter {
  private adapter: StorageAdapter;
  private prefix: string;

  constructor(adapter: StorageAdapter, prefix = 'plinto_') {
    this.adapter = adapter;
    this.prefix = prefix;
  }

  private getKey(key: string): string {
    return `${this.prefix}${key}`;
  }

  get(key: string): string | null {
    const value = this.adapter.get(this.getKey(key));
    if (!value) return null;

    try {
      const parsed = JSON.parse(value);
      if (parsed.expires && new Date(parsed.expires) < new Date()) {
        this.remove(key);
        return null;
      }
      return parsed.value;
    } catch {
      return value;
    }
  }

  set(key: string, value: string, expiresIn?: number): void {
    let data: any = { value };
    
    if (expiresIn) {
      const expires = new Date();
      expires.setSeconds(expires.getSeconds() + expiresIn);
      data.expires = expires.toISOString();
    }

    this.adapter.set(this.getKey(key), JSON.stringify(data));
  }

  remove(key: string): void {
    this.adapter.remove(this.getKey(key));
  }

  clear(): void {
    // Only clear Plinto-specific keys
    if (this.adapter instanceof BrowserStorage || this.adapter instanceof MemoryStorage) {
      const keysToRemove: string[] = [];
      
      // For browser storage, iterate through all keys
      if (typeof window !== 'undefined' && this.adapter instanceof BrowserStorage) {
        const storage = (this.adapter as any).storage as Storage;
        for (let i = 0; i < storage.length; i++) {
          const key = storage.key(i);
          if (key?.startsWith(this.prefix)) {
            keysToRemove.push(key);
          }
        }
        keysToRemove.forEach(key => storage.removeItem(key));
      } else {
        // For memory storage, just clear all
        this.adapter.clear();
      }
    }
  }
}

export function createStorage(): StorageAdapter {
  if (typeof window !== 'undefined') {
    try {
      // Test if localStorage is available
      const test = '__plinto_test__';
      window.localStorage.setItem(test, test);
      window.localStorage.removeItem(test);
      return new SecureStorage(new BrowserStorage('local'));
    } catch {
      // Fall back to session storage
      try {
        return new SecureStorage(new BrowserStorage('session'));
      } catch {
        // Fall back to memory storage
        return new SecureStorage(new MemoryStorage());
      }
    }
  }
  
  // Node.js environment
  return new SecureStorage(new MemoryStorage());
}