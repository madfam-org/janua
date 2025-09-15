/**
 * Event emitter utility for pub/sub pattern implementation
 */

export class EventEmitter<T extends Record<string, any> = Record<string, any>> {
  private events: Map<keyof T, Set<Function>> = new Map();

  /**
   * Subscribe to an event
   */
  on<K extends keyof T>(event: K, listener: (data: T[K]) => void): () => void {
    if (!this.events.has(event)) {
      this.events.set(event, new Set());
    }
    this.events.get(event)!.add(listener);

    // Return unsubscribe function
    return () => this.off(event, listener);
  }

  /**
   * Subscribe to an event once
   */
  once<K extends keyof T>(event: K, listener: (data: T[K]) => void): () => void {
    const onceWrapper = (data: T[K]) => {
      listener(data);
      this.off(event, onceWrapper);
    };
    this.on(event, onceWrapper);
    
    // Return unsubscribe function
    return () => this.off(event, onceWrapper);
  }

  /**
   * Unsubscribe from an event
   */
  off<K extends keyof T>(event: K, listener: Function): void {
    const listeners = this.events.get(event);
    if (listeners) {
      listeners.delete(listener);
      if (listeners.size === 0) {
        this.events.delete(event);
      }
    }
  }

  /**
   * Emit an event
   */
  emit<K extends keyof T>(event: K, data: T[K]): void {
    const listeners = this.events.get(event);
    if (listeners) {
      listeners.forEach(listener => {
        try {
          listener(data);
        } catch (error) {
          console.error(`Error in event listener for ${String(event)}:`, error);
        }
      });
    }
  }

  /**
   * Remove all listeners for a specific event or all events
   */
  removeAllListeners(event?: keyof T): void {
    if (event) {
      this.events.delete(event);
    } else {
      this.events.clear();
    }
  }

  /**
   * Get the number of listeners for an event
   */
  listenerCount(event: keyof T): number {
    const listeners = this.events.get(event);
    return listeners ? listeners.size : 0;
  }

  /**
   * Get all event names that have listeners
   */
  eventNames(): (keyof T)[] {
    return Array.from(this.events.keys());
  }
}