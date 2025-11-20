/**
 * User Analytics Service
 * Handles user and organization analytics
 * Extracted from AnalyticsReportingService
 */

import { EventEmitter } from 'events';
import {
  AnalyticsEvent,
  TimeRange,
  Location,
  DeviceInfo
} from '../core/types';

export interface EventSource {
  getEvents(filter: {
    user_id?: string;
    organization_id?: string;
    time_range?: { start: Date; end: Date };
  }): Promise<AnalyticsEvent[]>;
}

export interface UserAnalytics {
  user_id: string;
  total_events: number;
  first_seen?: Date;
  last_seen?: Date;
  event_types: Record<string, number>;
  sessions_count: number;
  devices: DeviceInfo[];
  locations: Location[];
}

export interface OrganizationAnalytics {
  organization_id: string;
  total_events: number;
  unique_users: number;
  event_types: Record<string, number>;
  top_users: Array<{ user_id: string; count: number }>;
  usage_by_hour: Record<number, number>;
  usage_by_day: Record<string, number>;
}

export class UserAnalyticsService extends EventEmitter {
  constructor(private readonly eventSource: EventSource) {
    super();
  }

  /**
   * Get analytics for a specific user
   */
  async getUserAnalytics(
    userId: string,
    timeRange?: TimeRange
  ): Promise<UserAnalytics> {
    const startTime = Date.now();

    const filter: any = { user_id: userId };
    if (timeRange) {
      filter.time_range = this.getTimeRangeDates(timeRange);
    }

    const events = await this.eventSource.getEvents(filter);

    // Sort events by timestamp
    events.sort((a, b) => a.timestamp.getTime() - b.timestamp.getTime());

    const analytics: UserAnalytics = {
      user_id: userId,
      total_events: events.length,
      first_seen: events[0]?.timestamp,
      last_seen: events[events.length - 1]?.timestamp,
      event_types: this.groupBy(events, 'event_type'),
      sessions_count: new Set(events.map(e => e.session_id).filter(id => id)).size,
      devices: this.extractDevices(events),
      locations: this.extractLocations(events)
    };

    const executionTime = Date.now() - startTime;

    this.emit('user:analyzed', {
      userId,
      eventCount: analytics.total_events,
      executionTimeMs: executionTime
    });

    return analytics;
  }

  /**
   * Get analytics for an organization
   */
  async getOrganizationAnalytics(
    organizationId: string,
    timeRange?: TimeRange
  ): Promise<OrganizationAnalytics> {
    const startTime = Date.now();

    const filter: any = { organization_id: organizationId };
    if (timeRange) {
      filter.time_range = this.getTimeRangeDates(timeRange);
    }

    const events = await this.eventSource.getEvents(filter);

    const users = new Set(events.map(e => e.user_id).filter(id => id));

    const analytics: OrganizationAnalytics = {
      organization_id: organizationId,
      total_events: events.length,
      unique_users: users.size,
      event_types: this.groupBy(events, 'event_type'),
      top_users: this.getTopUsers(events),
      usage_by_hour: this.getUsageByHour(events),
      usage_by_day: this.getUsageByDay(events)
    };

    const executionTime = Date.now() - startTime;

    this.emit('organization:analyzed', {
      organizationId,
      eventCount: analytics.total_events,
      uniqueUsers: analytics.unique_users,
      executionTimeMs: executionTime
    });

    return analytics;
  }

  /**
   * Compare user activity between two time periods
   */
  async compareUserActivity(
    userId: string,
    period1: TimeRange,
    period2: TimeRange
  ): Promise<{
    period1: UserAnalytics;
    period2: UserAnalytics;
    change: {
      events: number;
      eventTypes: Record<string, number>;
    };
  }> {
    const [analytics1, analytics2] = await Promise.all([
      this.getUserAnalytics(userId, period1),
      this.getUserAnalytics(userId, period2)
    ]);

    const eventChange = analytics2.total_events - analytics1.total_events;
    const eventTypeChange: Record<string, number> = {};

    // Calculate change in event types
    const allEventTypes = new Set([
      ...Object.keys(analytics1.event_types),
      ...Object.keys(analytics2.event_types)
    ]);

    for (const eventType of allEventTypes) {
      const count1 = analytics1.event_types[eventType] || 0;
      const count2 = analytics2.event_types[eventType] || 0;
      eventTypeChange[eventType] = count2 - count1;
    }

    return {
      period1: analytics1,
      period2: analytics2,
      change: {
        events: eventChange,
        eventTypes: eventTypeChange
      }
    };
  }

  /**
   * Get user engagement score
   */
  async getUserEngagementScore(
    userId: string,
    timeRange: TimeRange
  ): Promise<{
    score: number;
    factors: {
      frequency: number;
      recency: number;
      diversity: number;
    };
  }> {
    const analytics = await this.getUserAnalytics(userId, timeRange);
    const { start, end } = this.getTimeRangeDates(timeRange);
    const periodDays = (end.getTime() - start.getTime()) / (1000 * 60 * 60 * 24);

    // Frequency score (0-100): events per day
    const eventsPerDay = analytics.total_events / periodDays;
    const frequencyScore = Math.min(100, eventsPerDay * 10);

    // Recency score (0-100): how recently the user was active
    const daysSinceLastEvent = analytics.last_seen
      ? (Date.now() - analytics.last_seen.getTime()) / (1000 * 60 * 60 * 24)
      : periodDays;
    const recencyScore = Math.max(0, 100 - (daysSinceLastEvent / periodDays) * 100);

    // Diversity score (0-100): variety of event types
    const eventTypeCount = Object.keys(analytics.event_types).length;
    const diversityScore = Math.min(100, eventTypeCount * 20);

    // Overall score (weighted average)
    const score = (frequencyScore * 0.4 + recencyScore * 0.4 + diversityScore * 0.2);

    return {
      score: Math.round(score),
      factors: {
        frequency: Math.round(frequencyScore),
        recency: Math.round(recencyScore),
        diversity: Math.round(diversityScore)
      }
    };
  }

  /**
   * Private: Group items by a key
   */
  private groupBy(items: any[], key: string): Record<string, number> {
    const groups: Record<string, number> = {};

    for (const item of items) {
      const value = item[key];
      groups[value] = (groups[value] || 0) + 1;
    }

    return groups;
  }

  /**
   * Private: Extract unique devices from events
   */
  private extractDevices(events: AnalyticsEvent[]): DeviceInfo[] {
    const devices = new Map<string, DeviceInfo>();

    for (const event of events) {
      if (event.context.device) {
        const key = `${event.context.device.type}:${event.context.device.browser}:${event.context.device.os}`;
        devices.set(key, event.context.device);
      }
    }

    return Array.from(devices.values());
  }

  /**
   * Private: Extract unique locations from events
   */
  private extractLocations(events: AnalyticsEvent[]): Location[] {
    const locations = new Map<string, Location>();

    for (const event of events) {
      if (event.context.location) {
        const key = `${event.context.location.country}:${event.context.location.city || ''}`;
        locations.set(key, event.context.location);
      }
    }

    return Array.from(locations.values());
  }

  /**
   * Private: Get top users by event count
   */
  private getTopUsers(events: AnalyticsEvent[]): Array<{ user_id: string; count: number }> {
    const userCounts = new Map<string, number>();

    for (const event of events) {
      if (event.user_id) {
        userCounts.set(event.user_id, (userCounts.get(event.user_id) || 0) + 1);
      }
    }

    return Array.from(userCounts.entries())
      .map(([user_id, count]) => ({ user_id, count }))
      .sort((a, b) => b.count - a.count)
      .slice(0, 10);
  }

  /**
   * Private: Get usage distribution by hour of day
   */
  private getUsageByHour(events: AnalyticsEvent[]): Record<number, number> {
    const usage: Record<number, number> = {};

    // Initialize all hours
    for (let hour = 0; hour < 24; hour++) {
      usage[hour] = 0;
    }

    for (const event of events) {
      const hour = new Date(event.timestamp).getHours();
      usage[hour]++;
    }

    return usage;
  }

  /**
   * Private: Get usage distribution by day
   */
  private getUsageByDay(events: AnalyticsEvent[]): Record<string, number> {
    const usage: Record<string, number> = {};

    for (const event of events) {
      const day = new Date(event.timestamp).toISOString().split('T')[0];
      usage[day] = (usage[day] || 0) + 1;
    }

    return usage;
  }

  /**
   * Private: Get date range from TimeRange
   */
  private getTimeRangeDates(timeRange: TimeRange): { start: Date; end: Date } {
    if (timeRange.type === 'absolute') {
      return {
        start: timeRange.absolute!.start,
        end: timeRange.absolute!.end
      };
    } else {
      const end = new Date();
      const start = new Date();
      const { value, unit } = timeRange.relative!;

      switch (unit) {
        case 'minutes':
          start.setMinutes(start.getMinutes() - value);
          break;
        case 'hours':
          start.setHours(start.getHours() - value);
          break;
        case 'days':
          start.setDate(start.getDate() - value);
          break;
        case 'weeks':
          start.setDate(start.getDate() - value * 7);
          break;
        case 'months':
          start.setMonth(start.getMonth() - value);
          break;
      }

      return { start, end };
    }
  }

  /**
   * Cleanup
   */
  destroy(): void {
    this.removeAllListeners();
  }
}
