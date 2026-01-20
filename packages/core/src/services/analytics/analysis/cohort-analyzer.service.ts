/**
 * Cohort Analyzer Service
 * Handles cohort analysis and retention tracking
 * Extracted from AnalyticsReportingService
 */

import crypto from 'crypto';
import { EventEmitter } from 'events';
import {
  CohortAnalysis,
  CohortData,
  TimeRange,
  QueryFilter,
  AnalyticsEvent
} from '../core/types';

export interface EventSource {
  getEvents(filter: {
    event_type?: string;
    time_range?: { start: Date; end: Date };
    organization_id?: string;
  }): Promise<AnalyticsEvent[]>;
}

export class CohortAnalyzerService extends EventEmitter {
  constructor(private readonly eventSource: EventSource) {
    super();
  }

  /**
   * Analyze cohort retention
   */
  async analyzeCohort(
    cohortDefinition: CohortAnalysis['cohort_definition'],
    retentionMetric: CohortAnalysis['retention_metric'],
    periods: number,
    periodType: CohortAnalysis['period_type'],
    organizationId?: string
  ): Promise<CohortAnalysis> {
    const startTime = Date.now();

    const analysis: CohortAnalysis = {
      id: crypto.randomUUID(),
      name: `Cohort ${new Date().toISOString()}`,
      cohort_definition: cohortDefinition,
      retention_metric: retentionMetric,
      periods,
      period_type: periodType,
      data: []
    };

    // Get cohorts based on definition
    const cohorts = await this.getCohorts(
      cohortDefinition,
      periodType,
      organizationId
    );

    for (const cohort of cohorts) {
      const cohortData: CohortData = {
        cohort_date: cohort.date,
        cohort_size: cohort.users.size,
        retention: []
      };

      // Calculate retention for each period
      for (let period = 0; period < periods; period++) {
        const periodStart = this.addPeriods(cohort.date, period, periodType);
        const periodEnd = this.addPeriods(cohort.date, period + 1, periodType);

        const retainedUsers = await this.getRetainedUsers(
          cohort.users,
          retentionMetric,
          periodStart,
          periodEnd,
          organizationId
        );

        const retentionRate = cohort.users.size > 0
          ? retainedUsers.size / cohort.users.size
          : 0;
        cohortData.retention.push(retentionRate);
      }

      analysis.data.push(cohortData);
    }

    const executionTime = Date.now() - startTime;

    this.emit('cohort:analyzed', {
      cohortId: analysis.id,
      cohortsCount: analysis.data.length,
      periods: analysis.periods,
      executionTimeMs: executionTime
    });

    return analysis;
  }

  /**
   * Get cohort retention summary
   */
  async getCohortRetentionSummary(
    cohortAnalysis: CohortAnalysis
  ): Promise<{
    averageRetention: number[];
    bestCohort: { date: Date; retention: number[] } | null;
    worstCohort: { date: Date; retention: number[] } | null;
  }> {
    if (cohortAnalysis.data.length === 0) {
      return {
        averageRetention: [],
        bestCohort: null,
        worstCohort: null
      };
    }

    // Calculate average retention across all cohorts
    const averageRetention: number[] = [];
    for (let period = 0; period < cohortAnalysis.periods; period++) {
      const retentionValues = cohortAnalysis.data.map(c => c.retention[period]);
      const avg = retentionValues.reduce((a, b) => a + b, 0) / retentionValues.length;
      averageRetention.push(avg);
    }

    // Find best and worst cohorts based on final period retention
    let bestCohort = cohortAnalysis.data[0];
    let worstCohort = cohortAnalysis.data[0];

    for (const cohort of cohortAnalysis.data) {
      const finalRetention = cohort.retention[cohort.retention.length - 1];
      const bestFinal = bestCohort.retention[bestCohort.retention.length - 1];
      const worstFinal = worstCohort.retention[worstCohort.retention.length - 1];

      if (finalRetention > bestFinal) {
        bestCohort = cohort;
      }
      if (finalRetention < worstFinal) {
        worstCohort = cohort;
      }
    }

    return {
      averageRetention,
      bestCohort: {
        date: bestCohort.cohort_date,
        retention: bestCohort.retention
      },
      worstCohort: {
        date: worstCohort.cohort_date,
        retention: worstCohort.retention
      }
    };
  }

  /**
   * Compare cohorts
   */
  async compareCohorts(
    cohort1Date: Date,
    cohort2Date: Date,
    cohortAnalysis: CohortAnalysis
  ): Promise<{
    cohort1: CohortData | null;
    cohort2: CohortData | null;
    difference: number[];
  }> {
    const cohort1 = cohortAnalysis.data.find(
      c => c.cohort_date.getTime() === cohort1Date.getTime()
    );
    const cohort2 = cohortAnalysis.data.find(
      c => c.cohort_date.getTime() === cohort2Date.getTime()
    );

    const difference: number[] = [];

    if (cohort1 && cohort2) {
      for (let i = 0; i < Math.min(cohort1.retention.length, cohort2.retention.length); i++) {
        difference.push(cohort1.retention[i] - cohort2.retention[i]);
      }
    }

    return {
      cohort1: cohort1 || null,
      cohort2: cohort2 || null,
      difference
    };
  }

  /**
   * Private: Get cohorts based on definition
   */
  private async getCohorts(
    definition: CohortAnalysis['cohort_definition'],
    periodType: CohortAnalysis['period_type'],
    organizationId?: string
  ): Promise<Array<{ date: Date; users: Set<string> }>> {
    const { start, end } = this.getTimeRangeDates(definition.time_range);

    // Get all events matching the cohort definition
    const events = await this.eventSource.getEvents({
      event_type: definition.event,
      time_range: { start, end },
      organization_id: organizationId
    });

    // Apply filters if specified
    let filteredEvents = events;
    if (definition.filters && definition.filters.length > 0) {
      filteredEvents = events.filter(event =>
        this.matchesFilters(event, definition.filters!)
      );
    }

    // Group users by cohort period
    const cohortMap = new Map<string, Set<string>>();

    for (const event of filteredEvents) {
      if (!event.user_id) continue;

      const cohortDate = this.getCohortDate(event.timestamp, periodType);
      const cohortKey = cohortDate.toISOString();

      if (!cohortMap.has(cohortKey)) {
        cohortMap.set(cohortKey, new Set());
      }

      cohortMap.get(cohortKey)!.add(event.user_id);
    }

    // Convert to array
    return Array.from(cohortMap.entries()).map(([dateStr, users]) => ({
      date: new Date(dateStr),
      users
    }));
  }

  /**
   * Private: Get retained users for a cohort in a period
   */
  private async getRetainedUsers(
    cohortUsers: Set<string>,
    metric: CohortAnalysis['retention_metric'],
    start: Date,
    end: Date,
    organizationId?: string
  ): Promise<Set<string>> {
    const events = await this.eventSource.getEvents({
      event_type: metric.event,
      time_range: { start, end },
      organization_id: organizationId
    });

    const retainedUsers = new Set<string>();

    for (const event of events) {
      if (event.user_id && cohortUsers.has(event.user_id)) {
        retainedUsers.add(event.user_id);
      }
    }

    return retainedUsers;
  }

  /**
   * Private: Get cohort date based on period type
   */
  private getCohortDate(
    date: Date,
    periodType: CohortAnalysis['period_type']
  ): Date {
    const cohortDate = new Date(date);

    switch (periodType) {
      case 'day':
        cohortDate.setHours(0, 0, 0, 0);
        break;
      case 'week': {
        const dayOfWeek = cohortDate.getDay();
        cohortDate.setDate(cohortDate.getDate() - dayOfWeek);
        cohortDate.setHours(0, 0, 0, 0);
        break;
      }
      case 'month':
        cohortDate.setDate(1);
        cohortDate.setHours(0, 0, 0, 0);
        break;
    }

    return cohortDate;
  }

  /**
   * Private: Add periods to a date
   */
  private addPeriods(
    date: Date,
    periods: number,
    periodType: CohortAnalysis['period_type']
  ): Date {
    const result = new Date(date);

    switch (periodType) {
      case 'day':
        result.setDate(result.getDate() + periods);
        break;
      case 'week':
        result.setDate(result.getDate() + periods * 7);
        break;
      case 'month':
        result.setMonth(result.getMonth() + periods);
        break;
    }

    return result;
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
