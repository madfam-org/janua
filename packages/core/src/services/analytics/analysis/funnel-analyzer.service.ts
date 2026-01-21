/**
 * Funnel Analyzer Service
 * Handles funnel analysis for user journey tracking
 * Extracted from AnalyticsReportingService
 */

import crypto from 'crypto';
import { EventEmitter } from 'events';
import {
  FunnelAnalysis,
  QueryFilter,
  TimeRange,
  AnalyticsEvent
} from '../core/types';

// FunnelStep is used for type checking in method signatures

export interface EventSource {
  getEvents(filter: {
    event_type?: string;
    time_range?: { start: Date; end: Date };
    organization_id?: string;
  }): Promise<AnalyticsEvent[]>;
}

export class FunnelAnalyzerService extends EventEmitter {
  constructor(private readonly eventSource: EventSource) {
    super();
  }

  /**
   * Analyze funnel conversion
   */
  async analyzeFunnel(
    steps: Array<{
      name: string;
      event_type: string;
      filters?: QueryFilter[];
    }>,
    timeWindow: number,
    timeRange: TimeRange,
    organizationId?: string
  ): Promise<FunnelAnalysis> {
    const startTime = Date.now();

    const analysis: FunnelAnalysis = {
      id: crypto.randomUUID(),
      name: `Funnel ${new Date().toISOString()}`,
      steps: [],
      time_window: timeWindow,
      created_at: new Date(),
      conversion_rate: 0,
      drop_off_rates: []
    };

    let previousStepUsers = new Set<string>();

    for (let i = 0; i < steps.length; i++) {
      const step = steps[i];
      const stepUsers = await this.getFunnelStepUsers(
        step,
        timeRange,
        organizationId
      );

      let currentStepUsers: Set<string>;
      if (i === 0) {
        currentStepUsers = stepUsers;
      } else {
        // Only users who completed previous step
        currentStepUsers = new Set(
          Array.from(stepUsers).filter(userId => previousStepUsers.has(userId))
        );
      }

      const conversionRate = i === 0 ? 1 : currentStepUsers.size / previousStepUsers.size;

      analysis.steps.push({
        name: step.name,
        event_type: step.event_type,
        filters: step.filters,
        users_count: currentStepUsers.size,
        conversion_rate: conversionRate
      });

      if (i > 0) {
        analysis.drop_off_rates.push(1 - conversionRate);
      }

      previousStepUsers = currentStepUsers;
    }

    // Overall conversion rate
    if (analysis.steps.length > 0) {
      const firstStep = analysis.steps[0];
      const lastStep = analysis.steps[analysis.steps.length - 1];
      analysis.conversion_rate = lastStep.users_count / firstStep.users_count;
    }

    const executionTime = Date.now() - startTime;

    this.emit('funnel:analyzed', {
      funnelId: analysis.id,
      stepsCount: analysis.steps.length,
      conversionRate: analysis.conversion_rate,
      executionTimeMs: executionTime
    });

    return analysis;
  }

  /**
   * Get conversion path for a specific user
   */
  async getUserConversionPath(
    userId: string,
    steps: Array<{ event_type: string }>,
    timeRange: TimeRange
  ): Promise<{
    userId: string;
    completedSteps: string[];
    abandonedAt?: number;
    conversionTime?: number;
  }> {
    const { start, end } = this.getTimeRangeDates(timeRange);
    const completedSteps: string[] = [];
    let firstEventTime: Date | null = null;
    let lastEventTime: Date | null = null;

    for (const step of steps) {
      const events = await this.eventSource.getEvents({
        event_type: step.event_type,
        time_range: { start, end }
      });

      const userEvent = events.find(e => e.user_id === userId);
      if (userEvent) {
        completedSteps.push(step.event_type);
        if (!firstEventTime) firstEventTime = userEvent.timestamp;
        lastEventTime = userEvent.timestamp;
      } else {
        break; // User abandoned funnel
      }
    }

    const result: any = {
      userId,
      completedSteps
    };

    if (completedSteps.length < steps.length) {
      result.abandonedAt = completedSteps.length;
    }

    if (firstEventTime && lastEventTime) {
      result.conversionTime = lastEventTime.getTime() - firstEventTime.getTime();
    }

    return result;
  }

  /**
   * Get drop-off analysis for specific step
   */
  async analyzeStepDropOff(
    funnelSteps: Array<{ event_type: string }>,
    stepIndex: number,
    timeRange: TimeRange,
    organizationId?: string
  ): Promise<{
    stepName: string;
    usersReached: number;
    usersContinued: number;
    dropOffRate: number;
    dropOffReasons?: Array<{ reason: string; count: number }>;
  }> {
    if (stepIndex >= funnelSteps.length - 1) {
      throw new Error('Cannot analyze drop-off for last step');
    }

    const currentStep = funnelSteps[stepIndex];
    const nextStep = funnelSteps[stepIndex + 1];

    const currentStepUsers = await this.getFunnelStepUsers(
      { event_type: currentStep.event_type, name: currentStep.event_type },
      timeRange,
      organizationId
    );

    const nextStepUsers = await this.getFunnelStepUsers(
      { event_type: nextStep.event_type, name: nextStep.event_type },
      timeRange,
      organizationId
    );

    const usersContinued = Array.from(nextStepUsers).filter(userId =>
      currentStepUsers.has(userId)
    ).length;

    const dropOffRate = 1 - usersContinued / currentStepUsers.size;

    return {
      stepName: currentStep.event_type,
      usersReached: currentStepUsers.size,
      usersContinued,
      dropOffRate
    };
  }

  /**
   * Private: Get users who completed a funnel step
   */
  private async getFunnelStepUsers(
    step: { event_type: string; filters?: QueryFilter[]; name: string },
    timeRange: TimeRange,
    organizationId?: string
  ): Promise<Set<string>> {
    const { start, end } = this.getTimeRangeDates(timeRange);

    const events = await this.eventSource.getEvents({
      event_type: step.event_type,
      time_range: { start, end },
      organization_id: organizationId
    });

    // Apply filters if specified
    let filteredEvents = events;
    if (step.filters && step.filters.length > 0) {
      filteredEvents = events.filter(event =>
        this.matchesFilters(event, step.filters!)
      );
    }

    // Extract unique user IDs
    const users = new Set<string>();
    for (const event of filteredEvents) {
      if (event.user_id) {
        users.add(event.user_id);
      }
    }

    return users;
  }

  /**
   * Private: Check if event matches filters
   */
  private matchesFilters(event: AnalyticsEvent, filters: QueryFilter[]): boolean {
    for (const filter of filters) {
      const value = event.properties[filter.dimension];

      switch (filter.operator) {
        case 'equals':
          if (value !== filter.value) return false;
          break;
        case 'not_equals':
          if (value === filter.value) return false;
          break;
        case 'contains':
          if (!value?.includes(filter.value)) return false;
          break;
        case 'in':
          if (!filter.value.includes(value)) return false;
          break;
      }
    }

    return true;
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
