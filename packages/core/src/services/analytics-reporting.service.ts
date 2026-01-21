/**
 * Advanced Analytics and Reporting Service
 * Provides comprehensive analytics, reporting, and business intelligence capabilities
 */

import { EventEmitter } from 'events';
import crypto from 'crypto';

export interface AnalyticsEvent {
  id: string;
  event_type: string;
  event_category: 'user' | 'system' | 'security' | 'business' | 'performance';
  timestamp: Date;
  user_id?: string;
  organization_id?: string;
  session_id?: string;
  properties: Record<string, any>;
  context: {
    ip_address?: string;
    user_agent?: string;
    location?: Location;
    device?: DeviceInfo;
    referrer?: string;
    utm_params?: Record<string, string>;
  };
}

export interface Location {
  country: string;
  city?: string;
  region?: string;
  latitude?: number;
  longitude?: number;
  timezone?: string;
}

export interface DeviceInfo {
  type: 'desktop' | 'mobile' | 'tablet' | 'bot';
  browser?: string;
  browser_version?: string;
  os?: string;
  os_version?: string;
  device_model?: string;
}

export interface MetricDefinition {
  id: string;
  name: string;
  description: string;
  type: 'counter' | 'gauge' | 'histogram' | 'summary';
  unit?: string;
  aggregation: 'sum' | 'avg' | 'min' | 'max' | 'count' | 'percentile';
  dimensions?: string[];
  retention_days: number;
}

export interface TimeSeriesData {
  metric: string;
  timestamp: Date;
  value: number;
  dimensions?: Record<string, string>;
}

export interface Report {
  id: string;
  name: string;
  description?: string;
  type: 'dashboard' | 'scheduled' | 'adhoc' | 'realtime';
  created_by: string;
  created_at: Date;
  updated_at: Date;
  schedule?: ReportSchedule;
  widgets: ReportWidget[];
  filters: ReportFilter[];
  access_control?: AccessControl;
}

export interface ReportSchedule {
  frequency: 'hourly' | 'daily' | 'weekly' | 'monthly';
  time?: string; // HH:MM format
  day_of_week?: number; // 0-6 for weekly
  day_of_month?: number; // 1-31 for monthly
  timezone: string;
  recipients: string[];
  format: 'pdf' | 'csv' | 'excel' | 'json';
}

export interface ReportWidget {
  id: string;
  type: 'chart' | 'table' | 'metric' | 'map' | 'funnel' | 'cohort' | 'heatmap';
  title: string;
  metric_id: string;
  visualization: VisualizationConfig;
  time_range: TimeRange;
  filters?: Record<string, any>;
  position: { x: number; y: number; width: number; height: number };
}

export interface VisualizationConfig {
  chart_type?: 'line' | 'bar' | 'pie' | 'donut' | 'area' | 'scatter' | 'bubble';
  colors?: string[];
  legend?: boolean;
  axis_labels?: { x?: string; y?: string };
  stacked?: boolean;
  show_values?: boolean;
  animation?: boolean;
}

export interface TimeRange {
  type: 'relative' | 'absolute';
  relative?: {
    value: number;
    unit: 'minutes' | 'hours' | 'days' | 'weeks' | 'months';
  };
  absolute?: {
    start: Date;
    end: Date;
  };
}

export interface ReportFilter {
  field: string;
  operator: 'equals' | 'not_equals' | 'contains' | 'gt' | 'lt' | 'between' | 'in';
  value: any;
}

export interface AccessControl {
  visibility: 'private' | 'organization' | 'public';
  roles?: string[];
  users?: string[];
  teams?: string[];
}

export interface AnalyticsQuery {
  metrics: string[];
  dimensions?: string[];
  filters?: QueryFilter[];
  time_range: TimeRange;
  granularity?: 'minute' | 'hour' | 'day' | 'week' | 'month';
  order_by?: { field: string; direction: 'asc' | 'desc' }[];
  limit?: number;
  offset?: number;
}

export interface QueryFilter {
  dimension: string;
  operator: 'equals' | 'not_equals' | 'contains' | 'gt' | 'lt' | 'between' | 'in' | 'regex';
  value: any;
}

export interface QueryResult {
  query: AnalyticsQuery;
  data: any[];
  metadata: {
    total_rows: number;
    execution_time_ms: number;
    cache_hit: boolean;
    warnings?: string[];
  };
}

export interface Dashboard {
  id: string;
  name: string;
  description?: string;
  organization_id: string;
  owner_id: string;
  reports: Report[];
  layout: DashboardLayout;
  refresh_interval?: number; // seconds
  created_at: Date;
  updated_at: Date;
  shared_with?: AccessControl;
}

export interface DashboardLayout {
  type: 'grid' | 'freeform' | 'responsive';
  columns?: number;
  rows?: number;
  widgets: Array<{
    report_id: string;
    widget_id: string;
    position: { x: number; y: number; width: number; height: number };
  }>;
}

export interface InsightDefinition {
  id: string;
  name: string;
  description: string;
  type: 'anomaly' | 'trend' | 'forecast' | 'correlation' | 'segmentation';
  algorithm: string;
  parameters: Record<string, any>;
  schedule: 'realtime' | 'hourly' | 'daily';
  threshold?: number;
  actions?: InsightAction[];
}

export interface InsightAction {
  type: 'alert' | 'webhook' | 'email' | 'slack';
  config: Record<string, any>;
}

export interface Insight {
  id: string;
  definition_id: string;
  timestamp: Date;
  type: InsightDefinition['type'];
  severity: 'info' | 'warning' | 'critical';
  title: string;
  description: string;
  data: Record<string, any>;
  affected_metrics?: string[];
  recommendations?: string[];
}

export interface FunnelAnalysis {
  id: string;
  name: string;
  steps: FunnelStep[];
  time_window: number; // minutes
  created_at: Date;
  conversion_rate: number;
  drop_off_rates: number[];
}

export interface FunnelStep {
  name: string;
  event_type: string;
  filters?: QueryFilter[];
  users_count: number;
  conversion_rate: number;
}

export interface CohortAnalysis {
  id: string;
  name: string;
  cohort_definition: {
    event: string;
    time_range: TimeRange;
    filters?: QueryFilter[];
  };
  retention_metric: {
    event: string;
    aggregation: 'count' | 'sum' | 'avg';
  };
  periods: number;
  period_type: 'day' | 'week' | 'month';
  data: CohortData[];
}

export interface CohortData {
  cohort_date: Date;
  cohort_size: number;
  retention: number[]; // Retention percentages for each period
}

export class AnalyticsReportingService extends EventEmitter {
  private events: Map<string, AnalyticsEvent[]> = new Map();
  private metrics: Map<string, MetricDefinition> = new Map();
  private timeSeries: Map<string, TimeSeriesData[]> = new Map();
  private reports: Map<string, Report> = new Map();
  private dashboards: Map<string, Dashboard> = new Map();
  private insights: Map<string, Insight[]> = new Map();
  private insightDefinitions: Map<string, InsightDefinition> = new Map();
  private queryCache: Map<string, { result: QueryResult; expires: Date }> = new Map();

  constructor(
    private readonly config: {
      max_events_per_batch?: number;
      batch_interval_ms?: number;
      retention_days?: number;
      cache_ttl_seconds?: number;
      enable_real_time?: boolean;
      anomaly_detection?: boolean;
      forecasting?: boolean;
    } = {}
  ) {
    super();
    this.initializeDefaultMetrics();
    this.startBatchProcessor();
    this.startInsightEngine();
  }

  /**
   * Track analytics event
   */
  async trackEvent(event: Omit<AnalyticsEvent, 'id'>): Promise<void> {
    const fullEvent: AnalyticsEvent = {
      ...event,
      id: crypto.randomUUID(),
      timestamp: event.timestamp || new Date()
    };

    // Store event
    const key = `${event.organization_id || 'global'}:${event.event_type}`;
    if (!this.events.has(key)) {
      this.events.set(key, []);
    }
    this.events.get(key)!.push(fullEvent);

    // Update real-time metrics
    await this.updateRealTimeMetrics(fullEvent);

    // Check for anomalies
    if (this.config.anomaly_detection) {
      await this.detectAnomalies(fullEvent);
    }

    // Emit for real-time processing
    if (this.config.enable_real_time) {
      this.emit('event:tracked', fullEvent);
    }
  }

  /**
   * Record metric
   */
  async recordMetric(
    metric_name: string,
    value: number,
    dimensions?: Record<string, string>
  ): Promise<void> {
    const metric = this.metrics.get(metric_name);
    if (!metric) {
      throw new Error(`Metric ${metric_name} not defined`);
    }

    const dataPoint: TimeSeriesData = {
      metric: metric_name,
      timestamp: new Date(),
      value,
      dimensions
    };

    // Store time series data
    const key = this.getTimeSeriesKey(metric_name, dimensions);
    if (!this.timeSeries.has(key)) {
      this.timeSeries.set(key, []);
    }
    this.timeSeries.get(key)!.push(dataPoint);

    // Emit for real-time dashboards
    this.emit('metric:recorded', dataPoint);
  }

  /**
   * Query analytics data
   */
  async query(query: AnalyticsQuery): Promise<QueryResult> {
    const startTime = Date.now();

    // Check cache
    const cacheKey = this.getQueryCacheKey(query);
    const cached = this.queryCache.get(cacheKey);
    if (cached && cached.expires > new Date()) {
      return {
        ...cached.result,
        metadata: {
          ...cached.result.metadata,
          cache_hit: true
        }
      };
    }

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

    // Cache result
    this.queryCache.set(cacheKey, {
      result,
      expires: new Date(Date.now() + (this.config.cache_ttl_seconds || 300) * 1000)
    });

    return result;
  }

  /**
   * Create report
   */
  async createReport(report: Omit<Report, 'id' | 'created_at' | 'updated_at'>): Promise<Report> {
    const fullReport: Report = {
      ...report,
      id: crypto.randomUUID(),
      created_at: new Date(),
      updated_at: new Date()
    };

    this.reports.set(fullReport.id, fullReport);

    // Schedule if needed
    if (fullReport.schedule) {
      await this.scheduleReport(fullReport);
    }

    this.emit('report:created', fullReport);

    return fullReport;
  }

  /**
   * Execute report
   */
  async executeReport(report_id: string): Promise<any> {
    const report = this.reports.get(report_id);
    if (!report) {
      throw new Error('Report not found');
    }

    const results: any = {
      report_id,
      executed_at: new Date(),
      widgets: []
    };

    // Execute each widget
    for (const widget of report.widgets) {
      const widgetResult = await this.executeWidget(widget);
      results.widgets.push({
        widget_id: widget.id,
        title: widget.title,
        data: widgetResult
      });
    }

    this.emit('report:executed', { report_id, results });

    return results;
  }

  /**
   * Create dashboard
   */
  async createDashboard(
    dashboard: Omit<Dashboard, 'id' | 'created_at' | 'updated_at'>
  ): Promise<Dashboard> {
    const fullDashboard: Dashboard = {
      ...dashboard,
      id: crypto.randomUUID(),
      created_at: new Date(),
      updated_at: new Date()
    };

    this.dashboards.set(fullDashboard.id, fullDashboard);

    this.emit('dashboard:created', fullDashboard);

    return fullDashboard;
  }

  /**
   * Get dashboard data
   */
  async getDashboardData(dashboard_id: string): Promise<any> {
    const dashboard = this.dashboards.get(dashboard_id);
    if (!dashboard) {
      throw new Error('Dashboard not found');
    }

    const data: any = {
      dashboard,
      reports: []
    };

    // Get data for each report
    for (const report of dashboard.reports) {
      const reportData = await this.executeReport(report.id);
      data.reports.push(reportData);
    }

    return data;
  }

  /**
   * Perform funnel analysis
   */
  async analyzeFunnel(
    steps: Array<{ name: string; event_type: string; filters?: QueryFilter[] }>,
    time_window: number,
    time_range: TimeRange
  ): Promise<FunnelAnalysis> {
    const analysis: FunnelAnalysis = {
      id: crypto.randomUUID(),
      name: `Funnel ${new Date().toISOString()}`,
      steps: [],
      time_window,
      created_at: new Date(),
      conversion_rate: 0,
      drop_off_rates: []
    };

    let previousStepUsers = new Set<string>();
    
    for (let i = 0; i < steps.length; i++) {
      const step = steps[i];
      const stepUsers = await this.getFunnelStepUsers(step, time_range);
      
      let currentStepUsers: Set<string>;
      if (i === 0) {
        currentStepUsers = stepUsers;
      } else {
        // Only users who completed previous step
        currentStepUsers = new Set(
          Array.from(stepUsers).filter(userId => previousStepUsers.has(userId))
        );
      }

      const conversion_rate = i === 0 
        ? 1 
        : currentStepUsers.size / previousStepUsers.size;

      analysis.steps.push({
        name: step.name,
        event_type: step.event_type,
        filters: step.filters,
        users_count: currentStepUsers.size,
        conversion_rate
      });

      if (i > 0) {
        analysis.drop_off_rates.push(1 - conversion_rate);
      }

      previousStepUsers = currentStepUsers;
    }

    // Overall conversion rate
    if (analysis.steps.length > 0) {
      const firstStep = analysis.steps[0];
      const lastStep = analysis.steps[analysis.steps.length - 1];
      analysis.conversion_rate = lastStep.users_count / firstStep.users_count;
    }

    return analysis;
  }

  /**
   * Perform cohort analysis
   */
  async analyzeCohort(
    cohort_definition: CohortAnalysis['cohort_definition'],
    retention_metric: CohortAnalysis['retention_metric'],
    periods: number,
    period_type: CohortAnalysis['period_type']
  ): Promise<CohortAnalysis> {
    const analysis: CohortAnalysis = {
      id: crypto.randomUUID(),
      name: `Cohort ${new Date().toISOString()}`,
      cohort_definition,
      retention_metric,
      periods,
      period_type,
      data: []
    };

    // Get cohorts
    const cohorts = await this.getCohorts(cohort_definition, period_type);

    for (const cohort of cohorts) {
      const cohortData: CohortData = {
        cohort_date: cohort.date,
        cohort_size: cohort.users.size,
        retention: []
      };

      // Calculate retention for each period
      for (let period = 0; period < periods; period++) {
        const periodStart = this.addPeriods(cohort.date, period, period_type);
        const periodEnd = this.addPeriods(cohort.date, period + 1, period_type);
        
        const retainedUsers = await this.getRetainedUsers(
          cohort.users,
          retention_metric,
          periodStart,
          periodEnd
        );

        const retentionRate = retainedUsers.size / cohort.users.size;
        cohortData.retention.push(retentionRate);
      }

      analysis.data.push(cohortData);
    }

    return analysis;
  }

  /**
   * Generate insights
   */
  async generateInsights(
    organization_id?: string,
    time_range?: TimeRange
  ): Promise<Insight[]> {
    const insights: Insight[] = [];

    for (const definition of this.insightDefinitions.values()) {
      const insight = await this.generateInsight(definition, organization_id, time_range);
      if (insight) {
        insights.push(insight);
        
        // Store insight
        const key = organization_id || 'global';
        if (!this.insights.has(key)) {
          this.insights.set(key, []);
        }
        this.insights.get(key)!.push(insight);

        // Execute actions
        if (definition.actions) {
          await this.executeInsightActions(insight, definition.actions);
        }
      }
    }

    return insights;
  }

  /**
   * Forecast metric
   */
  async forecastMetric(
    metric_name: string,
    periods: number,
    period_type: 'hour' | 'day' | 'week' | 'month'
  ): Promise<TimeSeriesData[]> {
    if (!this.config.forecasting) {
      throw new Error('Forecasting not enabled');
    }

    const historicalData = await this.getMetricHistory(metric_name);
    
    // Simple linear regression for demo
    // In production, use proper time series forecasting (ARIMA, Prophet, etc.)
    const forecast = this.performLinearRegression(historicalData, periods, period_type);

    return forecast;
  }

  /**
   * Get user analytics
   */
  async getUserAnalytics(user_id: string, time_range?: TimeRange): Promise<any> {
    const events = await this.getUserEvents(user_id, time_range);
    
    return {
      user_id,
      total_events: events.length,
      first_seen: events[0]?.timestamp,
      last_seen: events[events.length - 1]?.timestamp,
      event_types: this.groupBy(events, 'event_type'),
      sessions_count: new Set(events.map(e => e.session_id)).size,
      devices: this.extractDevices(events),
      locations: this.extractLocations(events)
    };
  }

  /**
   * Get organization analytics
   */
  async getOrganizationAnalytics(
    organization_id: string,
    time_range?: TimeRange
  ): Promise<any> {
    const events = await this.getOrganizationEvents(organization_id, time_range);
    const users = new Set(events.map(e => e.user_id).filter(id => id));

    return {
      organization_id,
      total_events: events.length,
      unique_users: users.size,
      event_types: this.groupBy(events, 'event_type'),
      top_users: this.getTopUsers(events),
      usage_by_hour: this.getUsageByHour(events),
      usage_by_day: this.getUsageByDay(events)
    };
  }

  /**
   * Private: Initialize default metrics
   */
  private initializeDefaultMetrics(): void {
    const defaultMetrics: MetricDefinition[] = [
      {
        id: 'api_requests',
        name: 'API Requests',
        description: 'Total API requests',
        type: 'counter',
        aggregation: 'sum',
        dimensions: ['endpoint', 'method', 'status'],
        retention_days: 90
      },
      {
        id: 'response_time',
        name: 'Response Time',
        description: 'API response time in milliseconds',
        type: 'histogram',
        unit: 'ms',
        aggregation: 'percentile',
        dimensions: ['endpoint'],
        retention_days: 30
      },
      {
        id: 'active_users',
        name: 'Active Users',
        description: 'Number of active users',
        type: 'gauge',
        aggregation: 'count',
        dimensions: ['organization'],
        retention_days: 365
      },
      {
        id: 'revenue',
        name: 'Revenue',
        description: 'Total revenue',
        type: 'counter',
        unit: 'USD',
        aggregation: 'sum',
        dimensions: ['plan', 'billing_cycle'],
        retention_days: 999
      }
    ];

    for (const metric of defaultMetrics) {
      this.metrics.set(metric.id, metric);
    }
  }

  /**
   * Private: Execute query
   */
  private async executeQuery(query: AnalyticsQuery): Promise<any[]> {
    // Simplified query execution
    // In production, use proper data warehouse or analytics database
    
    const results: any[] = [];
    
    for (const metric of query.metrics) {
      const timeSeriesKey = this.getTimeSeriesKey(metric);
      const data = this.timeSeries.get(timeSeriesKey) || [];
      
      // Apply filters
      let filtered = data;
      if (query.filters) {
        filtered = data.filter(d => this.matchesFilters(d, query.filters!));
      }

      // Apply time range
      filtered = this.filterByTimeRange(filtered, query.time_range);

      // Aggregate by granularity
      const aggregated = this.aggregateByGranularity(filtered, query.granularity || 'day');

      results.push(...aggregated);
    }

    // Apply ordering
    if (query.order_by) {
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
   * Private: Execute widget
   */
  private async executeWidget(widget: ReportWidget): Promise<any> {
    const metric = this.metrics.get(widget.metric_id);
    if (!metric) {
      throw new Error(`Metric ${widget.metric_id} not found`);
    }

    const query: AnalyticsQuery = {
      metrics: [widget.metric_id],
      time_range: widget.time_range,
      filters: widget.filters ? Object.entries(widget.filters).map(([k, v]) => ({
        dimension: k,
        operator: 'equals' as const,
        value: v
      })) : undefined
    };

    const result = await this.query(query);

    // Format for visualization
    return this.formatForVisualization(result.data, widget.visualization);
  }

  /**
   * Private: Update real-time metrics
   */
  private async updateRealTimeMetrics(event: AnalyticsEvent): Promise<void> {
    // Update relevant metrics based on event type
    switch (event.event_category) {
      case 'user':
        await this.recordMetric('active_users', 1, {
          organization: event.organization_id || 'unknown'
        });
        break;
      case 'performance':
        if (event.properties.response_time) {
          await this.recordMetric('response_time', event.properties.response_time, {
            endpoint: event.properties.endpoint
          });
        }
        break;
      case 'business':
        if (event.properties.revenue) {
          await this.recordMetric('revenue', event.properties.revenue, {
            plan: event.properties.plan,
            billing_cycle: event.properties.billing_cycle
          });
        }
        break;
    }
  }

  /**
   * Private: Detect anomalies
   */
  private async detectAnomalies(event: AnalyticsEvent): Promise<void> {
    // Simple anomaly detection using standard deviation
    // In production, use proper anomaly detection algorithms
    
    const key = `${event.event_type}:${event.organization_id || 'global'}`;
    const events = this.events.get(key) || [];
    
    if (events.length < 100) return; // Need enough data
    
    // Calculate statistics
    const values = events.slice(-100).map(e => e.properties.value || 1);
    const mean = values.reduce((a, b) => a + b, 0) / values.length;
    const variance = values.reduce((a, b) => a + Math.pow(b - mean, 2), 0) / values.length;
    const stdDev = Math.sqrt(variance);
    
    const currentValue = event.properties.value || 1;
    const zScore = Math.abs((currentValue - mean) / stdDev);
    
    if (zScore > 3) { // 3 standard deviations
      const insight: Insight = {
        id: crypto.randomUUID(),
        definition_id: 'anomaly_detection',
        timestamp: new Date(),
        type: 'anomaly',
        severity: zScore > 4 ? 'critical' : 'warning',
        title: `Anomaly detected in ${event.event_type}`,
        description: `Value ${currentValue} is ${zScore.toFixed(1)} standard deviations from mean`,
        data: {
          event_type: event.event_type,
          value: currentValue,
          mean,
          std_dev: stdDev,
          z_score: zScore
        }
      };

      this.emit('anomaly:detected', insight);
    }
  }

  /**
   * Private: Helper functions
   */
  private getTimeSeriesKey(metric: string, dimensions?: Record<string, string>): string {
    if (!dimensions) return metric;
    
    const dimStr = Object.entries(dimensions)
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([k, v]) => `${k}:${v}`)
      .join(',');
    
    return `${metric}:${dimStr}`;
  }

  private getQueryCacheKey(query: AnalyticsQuery): string {
    return crypto.createHash('md5')
      .update(JSON.stringify(query))
      .digest('hex');
  }

  private matchesFilters(data: any, filters: QueryFilter[]): boolean {
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

  private aggregateByGranularity(
    data: TimeSeriesData[],
    granularity: AnalyticsQuery['granularity']
  ): any[] {
    const buckets = new Map<string, any>();
    
    for (const point of data) {
      const bucketKey = this.getBucketKey(point.timestamp, granularity);
      
      if (!buckets.has(bucketKey)) {
        buckets.set(bucketKey, {
          timestamp: bucketKey,
          value: 0,
          count: 0
        });
      }
      
      const bucket = buckets.get(bucketKey)!;
      bucket.value += point.value;
      bucket.count++;
    }
    
    return Array.from(buckets.values());
  }

  private getBucketKey(date: Date, granularity: string | undefined): string {
    const defaultGranularity = granularity || 'day';
    const d = new Date(date);
    
    switch (defaultGranularity) {
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

  private formatForVisualization(data: any[], _config: VisualizationConfig): any {
    // Format data based on chart type
    return data;
  }

  private async scheduleReport(_report: Report): Promise<void> {
    // Schedule report execution
    // In production, use proper job scheduler
  }

  private async getFunnelStepUsers(
    _step: { event_type: string; filters?: QueryFilter[] },
    _timeRange: TimeRange
  ): Promise<Set<string>> {
    // Get users who performed the event
    const users = new Set<string>();

    // Implementation would query actual event data

    return users;
  }

  private async getCohorts(
    _definition: CohortAnalysis['cohort_definition'],
    _periodType: string
  ): Promise<Array<{ date: Date; users: Set<string> }>> {
    // Get cohorts based on definition
    return [];
  }

  private addPeriods(date: Date, periods: number, periodType: string): Date {
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

  private async getRetainedUsers(
    _cohortUsers: Set<string>,
    _metric: CohortAnalysis['retention_metric'],
    _start: Date,
    _end: Date
  ): Promise<Set<string>> {
    // Get users who performed retention event
    return new Set();
  }

  private async generateInsight(
    _definition: InsightDefinition,
    _organizationId?: string,
    _timeRange?: TimeRange
  ): Promise<Insight | null> {
    // Generate insight based on definition
    return null;
  }

  private async executeInsightActions(
    insight: Insight,
    actions: InsightAction[]
  ): Promise<void> {
    for (const action of actions) {
      switch (action.type) {
        case 'alert':
          this.emit('alert:triggered', { insight, config: action.config });
          break;
        case 'webhook':
          // Send webhook
          break;
        case 'email':
          // Send email
          break;
        case 'slack':
          // Send Slack notification
          break;
      }
    }
  }

  private async getMetricHistory(metricName: string): Promise<TimeSeriesData[]> {
    const key = this.getTimeSeriesKey(metricName);
    return this.timeSeries.get(key) || [];
  }

  private performLinearRegression(
    _data: TimeSeriesData[],
    _periods: number,
    _periodType: string
  ): TimeSeriesData[] {
    // Simple linear regression for demo
    const forecast: TimeSeriesData[] = [];

    // Implementation would use proper forecasting

    return forecast;
  }

  private async getUserEvents(userId: string, _timeRange?: TimeRange): Promise<AnalyticsEvent[]> {
    const allEvents: AnalyticsEvent[] = [];

    for (const events of this.events.values()) {
      const userEvents = events.filter(e => e.user_id === userId);
      allEvents.push(...userEvents);
    }

    return allEvents;
  }

  private async getOrganizationEvents(
    organizationId: string,
    _timeRange?: TimeRange
  ): Promise<AnalyticsEvent[]> {
    const allEvents: AnalyticsEvent[] = [];
    
    for (const events of this.events.values()) {
      const orgEvents = events.filter(e => e.organization_id === organizationId);
      allEvents.push(...orgEvents);
    }
    
    return allEvents;
  }

  private groupBy(items: any[], key: string): Record<string, number> {
    const groups: Record<string, number> = {};
    
    for (const item of items) {
      const value = item[key];
      groups[value] = (groups[value] || 0) + 1;
    }
    
    return groups;
  }

  private extractDevices(events: AnalyticsEvent[]): any[] {
    const devices = new Map<string, any>();
    
    for (const event of events) {
      if (event.context.device) {
        const key = `${event.context.device.type}:${event.context.device.browser}`;
        devices.set(key, event.context.device);
      }
    }
    
    return Array.from(devices.values());
  }

  private extractLocations(events: AnalyticsEvent[]): any[] {
    const locations = new Map<string, any>();
    
    for (const event of events) {
      if (event.context.location) {
        const key = `${event.context.location.country}:${event.context.location.city}`;
        locations.set(key, event.context.location);
      }
    }
    
    return Array.from(locations.values());
  }

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

  private getUsageByHour(events: AnalyticsEvent[]): Record<number, number> {
    const usage: Record<number, number> = {};
    
    for (let hour = 0; hour < 24; hour++) {
      usage[hour] = 0;
    }
    
    for (const event of events) {
      const hour = new Date(event.timestamp).getHours();
      usage[hour]++;
    }
    
    return usage;
  }

  private getUsageByDay(events: AnalyticsEvent[]): Record<string, number> {
    const usage: Record<string, number> = {};
    
    for (const event of events) {
      const day = new Date(event.timestamp).toISOString().split('T')[0];
      usage[day] = (usage[day] || 0) + 1;
    }
    
    return usage;
  }

  /**
   * Private: Start batch processor
   */
  private startBatchProcessor(): void {
    setInterval(() => {
      this.processBatch();
    }, this.config.batch_interval_ms || 5000);
  }

  private async processBatch(): Promise<void> {
    // Process batched events
    // In production, write to data warehouse
  }

  /**
   * Private: Start insight engine
   */
  private startInsightEngine(): void {
    // Initialize default insight definitions
    this.initializeInsightDefinitions();

    // Start insight generation
    setInterval(() => {
      this.generateInsights();
    }, 3600000); // Every hour
  }

  private initializeInsightDefinitions(): void {
    const definitions: InsightDefinition[] = [
      {
        id: 'traffic_spike',
        name: 'Traffic Spike Detection',
        description: 'Detect unusual spikes in traffic',
        type: 'anomaly',
        algorithm: 'zscore',
        parameters: { threshold: 3 },
        schedule: 'realtime'
      },
      {
        id: 'revenue_forecast',
        name: 'Revenue Forecast',
        description: 'Forecast next month revenue',
        type: 'forecast',
        algorithm: 'linear_regression',
        parameters: { periods: 30 },
        schedule: 'daily'
      }
    ];

    for (const def of definitions) {
      this.insightDefinitions.set(def.id, def);
    }
  }
}

// Export factory function
export function createAnalyticsReportingService(config?: any): AnalyticsReportingService {
  return new AnalyticsReportingService(config);
}