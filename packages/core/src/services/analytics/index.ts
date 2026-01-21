/**
 * Analytics Module - Main Entry Point
 * Provides modular analytics services and backward-compatible facade
 */

// Core Types
export * from './core/types';

// Event Services
export { EventTrackerService } from './events/event-tracker.service';
export { MetricRecorderService } from './events/metric-recorder.service';

// Query Services
export { QueryEngineService } from './query/query-engine.service';
export { QueryCacheService } from './query/query-cache.service';

// Report Services
export { ReportService } from './reports/report.service';
export { ReportExecutorService } from './reports/report-executor.service';
export { ReportSchedulerService } from './reports/report-scheduler.service';

// Dashboard Services
export { DashboardService } from './dashboards/dashboard.service';
export { WidgetExecutorService } from './dashboards/widget-executor.service';

// Analysis Services
export { FunnelAnalyzerService } from './analysis/funnel-analyzer.service';
export { CohortAnalyzerService } from './analysis/cohort-analyzer.service';
export { UserAnalyticsService } from './analysis/user-analytics.service';

// Insight Services
export { InsightEngineService } from './insights/insight-engine.service';
export { AnomalyDetectorService } from './insights/anomaly-detector.service';
export { ForecasterService } from './insights/forecaster.service';

// Backward Compatibility Facade
import { EventEmitter } from 'events';
import { EventTrackerService } from './events/event-tracker.service';
import { MetricRecorderService } from './events/metric-recorder.service';
import { QueryEngineService } from './query/query-engine.service';
import { QueryCacheService } from './query/query-cache.service';
import { ReportService } from './reports/report.service';
import { ReportExecutorService } from './reports/report-executor.service';
import { ReportSchedulerService } from './reports/report-scheduler.service';
import { DashboardService } from './dashboards/dashboard.service';
import { WidgetExecutorService } from './dashboards/widget-executor.service';
import { FunnelAnalyzerService } from './analysis/funnel-analyzer.service';
import { CohortAnalyzerService } from './analysis/cohort-analyzer.service';
import { UserAnalyticsService } from './analysis/user-analytics.service';
import { InsightEngineService } from './insights/insight-engine.service';
import { AnomalyDetectorService } from './insights/anomaly-detector.service';
import { ForecasterService } from './insights/forecaster.service';

import type {
  AnalyticsEvent,
  AnalyticsQuery,
  QueryResult,
  Report,
  Dashboard,
  FunnelAnalysis,
  CohortAnalysis,
  Insight,
  TimeSeriesData,
  AnalyticsConfig,
  TimeRange,
  QueryFilter
} from './core/types';

/**
 * Main Analytics Service - Backward Compatible Facade
 * Maintains the same API as the original AnalyticsReportingService
 * while delegating to modular services internally
 */
export class AnalyticsReportingService extends EventEmitter {
  // Internal services
  private eventTracker: EventTrackerService;
  private metricRecorder: MetricRecorderService;
  private queryEngine: QueryEngineService;
  private queryCache: QueryCacheService;
  private reportService: ReportService;
  private reportExecutor: ReportExecutorService;
  private reportScheduler: ReportSchedulerService;
  private dashboardService: DashboardService;
  private widgetExecutor: WidgetExecutorService;
  private funnelAnalyzer: FunnelAnalyzerService;
  private cohortAnalyzer: CohortAnalyzerService;
  private userAnalytics: UserAnalyticsService;
  private insightEngine: InsightEngineService;
  private anomalyDetector: AnomalyDetectorService;
  private forecaster: ForecasterService;

  constructor(config: AnalyticsConfig = {}) {
    super();

    // Initialize all services
    this.eventTracker = new EventTrackerService(config);
    this.metricRecorder = new MetricRecorderService();
    this.queryCache = new QueryCacheService({
      ttlSeconds: config.cache_ttl,
      maxEntries: 1000
    });

    // Query engine needs data source
    this.queryEngine = new QueryEngineService({
      getTimeSeries: async (metric, dimensions) => {
        return this.metricRecorder.getMetricHistory(metric, dimensions);
      }
    });

    // Report services
    this.reportService = new ReportService();
    this.reportExecutor = new ReportExecutorService(
      this.reportService,
      this.widgetExecutor
    );
    this.reportScheduler = new ReportSchedulerService(this.reportExecutor);

    // Dashboard services
    this.dashboardService = new DashboardService();
    this.widgetExecutor = new WidgetExecutorService(
      this.queryEngine,
      this.metricRecorder
    );

    // Analysis services
    this.funnelAnalyzer = new FunnelAnalyzerService(this.eventTracker);
    this.cohortAnalyzer = new CohortAnalyzerService(this.eventTracker);
    this.userAnalytics = new UserAnalyticsService(this.eventTracker);

    // Insight services
    this.insightEngine = new InsightEngineService();
    this.anomalyDetector = new AnomalyDetectorService(this.insightEngine, {
      minDataPoints: 100,
      zScoreThreshold: 3,
      criticalZScoreThreshold: 4
    });
    this.forecaster = new ForecasterService(this.metricRecorder);

    // Set up event forwarding
    this.setupEventForwarding();

    // Set up metric tracking from events
    this.eventTracker.on('event:metrics', (event: AnalyticsEvent) => {
      this.metricRecorder.updateRealTimeMetrics(event).catch(err => {
        this.emit('error', err);
      });
    });

    // Set up anomaly detection if enabled
    if (config.enable_insights) {
      this.eventTracker.on('event:tracked', async (event: AnalyticsEvent) => {
        try {
          const historical = await this.eventTracker.getEvents({
            event_type: event.event_type,
            organization_id: event.organization_id
          });
          await this.anomalyDetector.detectEventAnomaly(event, historical);
        } catch (err) {
          this.emit('error', err);
        }
      });
    }
  }

  /**
   * Track an analytics event
   */
  async trackEvent(event: Omit<AnalyticsEvent, 'id'>): Promise<void> {
    await this.eventTracker.trackEvent(event);
  }

  /**
   * Record a metric
   */
  async recordMetric(
    metricName: string,
    value: number,
    dimensions?: Record<string, string>
  ): Promise<void> {
    await this.metricRecorder.recordMetric(metricName, value, dimensions);
  }

  /**
   * Execute an analytics query
   */
  async query(query: AnalyticsQuery): Promise<QueryResult> {
    // Check cache first
    const cached = this.queryCache.get(query);
    if (cached) {
      return cached;
    }

    // Execute query
    const result = await this.queryEngine.execute(query);

    // Cache result
    this.queryCache.set(query, result);

    return result;
  }

  /**
   * Create a report
   */
  async createReport(
    report: Omit<Report, 'id' | 'created_at' | 'updated_at'>
  ): Promise<Report> {
    const newReport = await this.reportService.createReport(report);

    // Schedule if needed
    if (newReport.schedule) {
      this.reportScheduler.scheduleReport(newReport);
    }

    return newReport;
  }

  /**
   * Execute a report
   */
  async executeReport(reportId: string): Promise<any> {
    return this.reportExecutor.executeReport(reportId);
  }

  /**
   * Create a dashboard
   */
  async createDashboard(
    dashboard: Omit<Dashboard, 'id' | 'created_at' | 'updated_at'>
  ): Promise<Dashboard> {
    return this.dashboardService.createDashboard(dashboard);
  }

  /**
   * Get dashboard data
   */
  async getDashboardData(dashboardId: string): Promise<any> {
    const dashboard = await this.dashboardService.getDashboard(dashboardId);
    if (!dashboard) {
      throw new Error('Dashboard not found');
    }

    const data: any = {
      dashboard,
      reports: []
    };

    // Execute all reports in the dashboard
    for (const report of dashboard.reports) {
      const reportData = await this.reportExecutor.executeReport(report.id);
      data.reports.push(reportData);
    }

    return data;
  }

  /**
   * Analyze a funnel
   */
  async analyzeFunnel(
    steps: Array<{ name: string; event_type: string; filters?: QueryFilter[] }>,
    timeWindow: number,
    timeRange: TimeRange,
    organizationId?: string
  ): Promise<FunnelAnalysis> {
    return this.funnelAnalyzer.analyzeFunnel(steps, timeWindow, timeRange, organizationId);
  }

  /**
   * Analyze a cohort
   */
  async analyzeCohort(
    cohortDefinition: CohortAnalysis['cohort_definition'],
    retentionMetric: CohortAnalysis['retention_metric'],
    periods: number,
    periodType: CohortAnalysis['period_type'],
    organizationId?: string
  ): Promise<CohortAnalysis> {
    return this.cohortAnalyzer.analyzeCohort(
      cohortDefinition,
      retentionMetric,
      periods,
      periodType,
      organizationId
    );
  }

  /**
   * Get user analytics
   */
  async getUserAnalytics(userId: string, timeRange?: TimeRange): Promise<any> {
    return this.userAnalytics.getUserAnalytics(userId, timeRange);
  }

  /**
   * Get organization analytics
   */
  async getOrganizationAnalytics(
    organizationId: string,
    timeRange?: TimeRange
  ): Promise<any> {
    return this.userAnalytics.getOrganizationAnalytics(organizationId, timeRange);
  }

  /**
   * Generate insights
   */
  async generateInsights(
    organizationId?: string,
    _timeRange?: TimeRange
  ): Promise<Insight[]> {
    // Return recent insights
    return this.insightEngine.getInsights({
      organizationId,
      limit: 50
    });
  }

  /**
   * Forecast a metric
   */
  async forecastMetric(
    metricName: string,
    periods: number,
    periodType: 'hour' | 'day' | 'week' | 'month'
  ): Promise<TimeSeriesData[]> {
    return this.forecaster.forecastMetric(metricName, periods, periodType);
  }

  /**
   * Private: Set up event forwarding from sub-services
   */
  private setupEventForwarding(): void {
    // Forward important events to maintain backward compatibility
    const services = [
      this.eventTracker,
      this.metricRecorder,
      this.queryEngine,
      this.reportExecutor,
      this.insightEngine,
      this.anomalyDetector
    ];

    for (const service of services) {
      service.on('error', (error) => this.emit('error', error));
    }

    // Forward specific events
    this.eventTracker.on('event:tracked', (event) =>
      this.emit('event:tracked', event)
    );
    this.metricRecorder.on('metric:recorded', (metric) =>
      this.emit('metric:recorded', metric)
    );
    this.reportExecutor.on('report:executed', (result) =>
      this.emit('report:executed', result)
    );
    this.anomalyDetector.on('anomaly:detected', (insight) =>
      this.emit('anomaly:detected', insight)
    );
  }

  /**
   * Cleanup all services
   */
  destroy(): void {
    this.eventTracker.destroy();
    this.metricRecorder.destroy();
    this.queryEngine.destroy();
    this.queryCache.destroy();
    this.reportService.destroy();
    this.reportExecutor.destroy();
    this.reportScheduler.destroy();
    this.dashboardService.destroy();
    this.widgetExecutor.destroy();
    this.funnelAnalyzer.destroy();
    this.cohortAnalyzer.destroy();
    this.userAnalytics.destroy();
    this.insightEngine.destroy();
    this.anomalyDetector.destroy();
    this.forecaster.destroy();
    this.removeAllListeners();
  }
}
