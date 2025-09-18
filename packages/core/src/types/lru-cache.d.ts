/**
 * Type definitions for lru-cache
 * Proper long-term solution for missing type definitions
 */

declare module 'lru-cache' {
  export interface LRUCacheOptions<K = any, V = any> {
    max?: number;
    ttl?: number;
    ttlResolution?: number;
    ttlAutopurge?: boolean;
    updateAgeOnGet?: boolean;
    updateAgeOnHas?: boolean;
    allowStale?: boolean;
    dispose?: (value: V, key: K, reason: 'evict' | 'set' | 'delete') => void;
    disposeAfter?: (value: V, key: K, reason: 'evict' | 'set' | 'delete') => void;
    noDisposeOnSet?: boolean;
    noUpdateTTL?: boolean;
    maxSize?: number;
    maxEntrySize?: number;
    sizeCalculation?: (value: V, key: K) => number;
    fetchMethod?: (key: K, staleValue: V | undefined, options: any) => Promise<V> | V;
    fetchContext?: any;
    noDeleteOnFetchRejection?: boolean;
    allowStaleOnFetchRejection?: boolean;
    allowStaleOnFetchAbort?: boolean;
    ignoreFetchAbort?: boolean;
  }

  export default class LRUCache<K = any, V = any> {
    constructor(options?: LRUCacheOptions<K, V> | number);

    // Core methods
    set(key: K, value: V, options?: { ttl?: number; noDisposeOnSet?: boolean }): this;
    get(key: K, options?: { allowStale?: boolean; updateAgeOnGet?: boolean }): V | undefined;
    has(key: K, options?: { updateAgeOnHas?: boolean }): boolean;
    delete(key: K): boolean;
    clear(): void;

    // Utility methods
    peek(key: K, options?: { allowStale?: boolean }): V | undefined;
    forEach(fn: (value: V, key: K, cache: this) => void, thisp?: any): void;
    rforEach(fn: (value: V, key: K, cache: this) => void, thisp?: any): void;
    keys(): Generator<K>;
    rkeys(): Generator<K>;
    values(): Generator<V>;
    rvalues(): Generator<V>;
    entries(): Generator<[K, V]>;
    rentries(): Generator<[K, V]>;
    find(fn: (value: V, key: K, cache: this) => boolean, getOptions?: any): V | undefined;
    dump(): Array<[K, V, number, number]>;
    load(arr: Array<[K, V, number, number]>): void;

    // TTL management
    purgeStale(): boolean;
    getRemainingTTL(key: K): number;

    // Fetch method support
    fetch(key: K, options?: any): Promise<V | undefined>;

    // Size management
    calculatedSize: number;
    size: number;
    max: number;
    maxSize: number;
    lengthCalculator: (value: V, key: K) => number;

    // Event emitters
    on(event: string, listener: Function): this;
    once(event: string, listener: Function): this;
    off(event: string, listener: Function): this;
    removeAllListeners(event?: string): this;

    // Info methods
    info(key: K): {
      value: V;
      ttl: number;
      size: number;
      start: number;
    } | undefined;
  }
}