/**
 * Query Engine Service
 * Handles analytics query execution and data processing
 * Extracted from AnalyticsReportingService
 */

import { EventEmitter } from 'events';
import {
  AnalyticsQuery,
  QueryResult,
  QueryFilter,
  TimeSeriesData,
  TimeRange
} from '../core/types';

export interface QueryDataSource {
  getTimeSeries(metric: string, dimensions?: Record<string, string>): Promise<TimeSeriesData[]>;
}

export class QueryEngineService extends EventEmitter {
  constructor(private readonly dataSource: QueryDataSource) {
    super();
  }

  /**
   * Execute analytics query
   */
  async execute(query: AnalyticsQuery): Promise<QueryResult> {
    const startTime = Date.now();

    try {
      // Execute query
      const data = await this.executeQuery(query);

      const result: QueryResult = {
        query,
        data,
        metadata: {
          total_rows: data.length,
          execution_time_ms: Date.now() - startTime,
          cache_hit: false
        }
      };

      // Emit for monitoring
      this.emit('query:executed', {
        query,
        executionTime: result.metadata.execution_time_ms,
        rowCount: result.metadata.total_rows
      });

      return result;
    } catch (error) {
      // Emit error for monitoring
      this.emit('query:failed', { query, error });
      throw error;
    }
  }

  /**
   * Private: Execute query against data source
   */
  private async executeQuery(query: AnalyticsQuery): Promise<any[]> {
    const results: any[] = [];

    // Query each metric
    for (const metric of query.metrics) {
      let data = await this.dataSource.getTimeSeries(metric);

      // Apply filters
      if (query.filters && query.filters.length > 0) {
        data = data.filter(d => this.matchesFilters(d, query.filters!));
      }

      // Apply time range
      data = this.filterByTimeRange(data, query.time_range);

      // Aggregate by granularity
      const aggregated = this.aggregateByGranularity(
        data,
        query.granularity || 'day'
      );

      // Add metric name to results
      const metricResults = aggregated.map(item => ({
        ...item,
        metric
      }));

      results.push(...metricResults);
    }

    // Apply dimensions grouping if specified
    if (query.dimensions && query.dimensions.length > 0) {
      // Group results by dimensions
      const grouped = this.groupByDimensions(results, query.dimensions);
      return this.applyPostProcessing(grouped, query);
    }

    // Apply post-processing (ordering, limit, offset)
    return this.applyPostProcessing(results, query);
  }

  /**
   * Private: Filter data by time range
   */
  private filterByTimeRange(data: TimeSeriesData[], timeRange: TimeRange): TimeSeriesData[] {
    let start: Date, end: Date;

    if (timeRange.type === 'absolute') {
      start = timeRange.absolute!.start;
      end = timeRange.absolute!.end;
    } else {
      end = new Date();
      const value = timeRange.relative!.value;
      const unit = timeRange.relative!.unit;

      start = new Date();
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
    }

    return data.filter(d => d.timestamp >= start && d.timestamp <= end);
  }

  /**
   * Private: Aggregate data by time granularity
   */
  private aggregateByGranularity(
    data: TimeSeriesData[],
    granularity: NonNullable<AnalyticsQuery['granularity']>
  ): any[] {
    const buckets = new Map<string, any>();

    for (const point of data) {
      const bucketKey = this.getBucketKey(point.timestamp, granularity);

      if (!buckets.has(bucketKey)) {
        buckets.set(bucketKey, {
          timestamp: bucketKey,
          value: 0,
          count: 0,
          dimensions: point.dimensions
        });
      }

      const bucket = buckets.get(bucketKey)!;
      bucket.value += point.value;
      bucket.count++;
    }

    return Array.from(buckets.values());
  }

  /**
   * Private: Get bucket key for time aggregation
   */
  private getBucketKey(
    date: Date,
    granularity: NonNullable<AnalyticsQuery['granularity']>
  ): string {
    const d = new Date(date);

    switch (granularity) {
      case 'minute':
        d.setSeconds(0, 0);
        break;
      case 'hour':
        d.setMinutes(0, 0, 0);
        break;
      case 'day':
        d.setHours(0, 0, 0, 0);
        break;
      case 'week': {
        const day = d.getDay();
        d.setDate(d.getDate() - day);
        d.setHours(0, 0, 0, 0);
        break;
      }
      case 'month':
        d.setDate(1);
        d.setHours(0, 0, 0, 0);
        break;
    }

    return d.toISOString();
  }

  /**
   * Private: Check if data matches filters
   */
  private matchesFilters(data: TimeSeriesData, filters: QueryFilter[]): boolean {
    for (const filter of filters) {
      const value = data.dimensions?.[filter.dimension];

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
        case 'gt':
          if (!(value > filter.value)) return false;
          break;
        case 'lt':
          if (!(value < filter.value)) return false;
          break;
        case 'between': {
          const [min, max] = filter.value;
          if (!(value >= min && value <= max)) return false;
          break;
        }
        case 'in':
          if (!filter.value.includes(value)) return false;
          break;
        case 'regex':
          if (!new RegExp(filter.value).test(value)) return false;
          break;
      }
    }

    return true;
  }

  /**
   * Private: Group results by dimensions
   */
  private groupByDimensions(data: any[], dimensions: string[]): any[] {
    const groups = new Map<string, any[]>();

    for (const item of data) {
      // Create dimension key
      const dimKey = dimensions
        .map(dim => `${dim}:${item.dimensions?.[dim] || 'unknown'}`)
        .join('|');

      if (!groups.has(dimKey)) {
        groups.set(dimKey, []);
      }

      groups.get(dimKey)!.push(item);
    }

    // Aggregate each group
    const results: any[] = [];
    for (const [dimKey, items] of groups.entries()) {
      // Parse dimensions back from key
      const dimObj: Record<string, string> = {};
      dimKey.split('|').forEach(part => {
        const [key, val] = part.split(':');
        dimObj[key] = val;
      });

      results.push({
        dimensions: dimObj,
        value: items.reduce((sum, item) => sum + item.value, 0),
        count: items.length,
        items
      });
    }

    return results;
  }

  /**
   * Private: Apply ordering, limit, and offset
   */
  private applyPostProcessing(data: any[], query: AnalyticsQuery): any[] {
    const results = [...data];

    // Apply ordering
    if (query.order_by && query.order_by.length > 0) {
      results.sort((a, b) => {
        for (const order of query.order_by!) {
          const aVal = a[order.field];
          const bVal = b[order.field];
          const direction = order.direction === 'asc' ? 1 : -1;

          if (aVal < bVal) return -direction;
          if (aVal > bVal) return direction;
        }
        return 0;
      });
    }

    // Apply limit and offset
    const offset = query.offset || 0;
    const limit = query.limit || results.length;

    return results.slice(offset, offset + limit);
  }

  /**
   * Cleanup
   */
  destroy(): void {
    this.removeAllListeners();
  }
}
