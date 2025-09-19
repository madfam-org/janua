"use strict";
/**
 * Event emitter utility for pub/sub pattern implementation
 */
Object.defineProperty(exports, "__esModule", { value: true });
exports.EventEmitter = void 0;
class EventEmitter {
    constructor() {
        this.events = new Map();
    }
    /**
     * Subscribe to an event
     */
    on(event, listener) {
        if (!this.events.has(event)) {
            this.events.set(event, new Set());
        }
        this.events.get(event).add(listener);
        // Return unsubscribe function
        return () => this.off(event, listener);
    }
    /**
     * Subscribe to an event once
     */
    once(event, listener) {
        const onceWrapper = (data) => {
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
    off(event, listener) {
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
    emit(event, data) {
        const listeners = this.events.get(event);
        if (listeners) {
            listeners.forEach(listener => {
                try {
                    listener(data);
                }
                catch (error) {
                    // Silently handle event listener errors in production
                    // Consider implementing proper error reporting if needed
                }
            });
        }
    }
    /**
     * Remove all listeners for a specific event or all events
     */
    removeAllListeners(event) {
        if (event) {
            this.events.delete(event);
        }
        else {
            this.events.clear();
        }
    }
    /**
     * Get the number of listeners for an event
     */
    listenerCount(event) {
        const listeners = this.events.get(event);
        return listeners ? listeners.size : 0;
    }
    /**
     * Get all event names that have listeners
     */
    eventNames() {
        return Array.from(this.events.keys());
    }
}
exports.EventEmitter = EventEmitter;
//# sourceMappingURL=event-utils.js.map