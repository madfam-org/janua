/**
 * Event Tracker Service
 * Handles analytics event recording and management
 * Extracted from AnalyticsReportingService
 */

import crypto from 'crypto';
import { EventEmitter } from 'events';
import {
  AnalyticsEvent,
  AnalyticsConfig
} from '../core/types';

export class EventTrackerService extends EventEmitter {
  private events: Map<string, AnalyticsEvent[]> = new Map();
  private batchQueue: AnalyticsEvent[] = [];
  private batchTimer?: NodeJS.Timeout;

  constructor(private readonly config: AnalyticsConfig = {}) {
    super();

    // Start batch processor if enabled
    if (config.batch_size) {
      this.startBatchProcessor();
    }
  }

  /**
   * Track an analytics event
   */
  async trackEvent(event: Omit<AnalyticsEvent, 'id'>): Promise<void> {
    const fullEvent: AnalyticsEvent = {
      ...event,
      id: crypto.randomUUID(),
    };

    // Store event
    const key = this.getEventKey(fullEvent);
    const existing = this.events.get(key) || [];
    existing.push(fullEvent);
    this.events.set(key, existing);

    // Add to batch queue
    if (this.config.batch_size) {
      this.batchQueue.push(fullEvent);

      if (this.batchQueue.length >= this.config.batch_size) {
        await this.processBatch();
      }
    }

    // Emit event for real-time processing
    if (this.config.enable_realtime) {
      this.emit('event:tracked', fullEvent);
    }

    // Emit for metrics update
    this.emit('event:metrics', fullEvent);
  }

  /**
   * Get events by filters
   */
  async getEvents(filter: {
    user_id?: string;
    organization_id?: string;
    event_type?: string;
    category?: AnalyticsEvent['event_category'];
    time_range?: { start: Date; end: Date };
  }): Promise<AnalyticsEvent[]> {
    let results: AnalyticsEvent[] = [];

    // Gather all events
    for (const events of this.events.values()) {
      results.push(...events);
    }

    // Apply filters
    if (filter.user_id) {
      results = results.filter(e => e.user_id === filter.user_id);
    }

    if (filter.organization_id) {
      results = results.filter(e => e.organization_id === filter.organization_id);
    }

    if (filter.event_type) {
      results = results.filter(e => e.event_type === filter.event_type);
    }

    if (filter.category) {
      results = results.filter(e => e.event_category === filter.category);
    }

    if (filter.time_range) {
      results = results.filter(
        e => e.timestamp >= filter.time_range!.start && e.timestamp <= filter.time_range!.end
      );
    }

    return results;
  }

  /**
   * Get event count
   */
  getEventCount(): number {
    let count = 0;
    for (const events of this.events.values()) {
      count += events.length;
    }
    return count;
  }

  /**
   * Clear events (for cleanup/testing)
   */
  clearEvents(before?: Date): void {
    if (before) {
      for (const [key, events] of this.events.entries()) {
        const filtered = events.filter(e => e.timestamp >= before);
        if (filtered.length > 0) {
          this.events.set(key, filtered);
        } else {
          this.events.delete(key);
        }
      }
    } else {
      this.events.clear();
    }
  }

  /**
   * Private: Get event storage key
   */
  private getEventKey(event: AnalyticsEvent): string {
    const date = new Date(event.timestamp);
    const dateKey = `${date.getFullYear()}-${date.getMonth() + 1}-${date.getDate()}`;
    return `${event.event_category}:${dateKey}`;
  }

  /**
   * Private: Start batch processor
   */
  private startBatchProcessor(): void {
    const interval = this.config.batch_interval || 60000; // Default 1 minute

    this.batchTimer = setInterval(async () => {
      if (this.batchQueue.length > 0) {
        await this.processBatch();
      }
    }, interval);
  }

  /**
   * Private: Process batch of events
   */
  private async processBatch(): Promise<void> {
    if (this.batchQueue.length === 0) {
      return;
    }

    const batch = [...this.batchQueue];
    this.batchQueue = [];

    try {
      // Emit batch for processing (could be persisted to database, sent to external service, etc.)
      this.emit('batch:processed', batch);
    } catch (error) {
      // Re-queue on error
      this.batchQueue.unshift(...batch);
      throw error;
    }
  }

  /**
   * Cleanup
   */
  destroy(): void {
    if (this.batchTimer) {
      clearInterval(this.batchTimer);
    }
    this.removeAllListeners();
  }
}
