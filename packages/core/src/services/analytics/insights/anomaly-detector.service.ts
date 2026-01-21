/**
 * Anomaly Detector Service
 * Handles anomaly detection in metrics and events
 * Extracted from AnalyticsReportingService
 */

// crypto import removed - not currently used
import { EventEmitter } from 'events';
import {
  Insight,
  AnalyticsEvent,
  TimeSeriesData
} from '../core/types';

export interface InsightCreator {
  createInsight(
    definitionId: string,
    data: {
      severity: Insight['severity'];
      title: string;
      description: string;
      data: Record<string, any>;
      affectedMetrics?: string[];
      recommendations?: string[];
    },
    organizationId?: string
  ): Insight;
}

export class AnomalyDetectorService extends EventEmitter {
  constructor(
    private readonly insightCreator: InsightCreator,
    private readonly config: {
      minDataPoints?: number;
      zScoreThreshold?: number;
      criticalZScoreThreshold?: number;
    } = {}
  ) {
    super();
  }

  /**
   * Detect anomalies in an event
   */
  async detectEventAnomaly(
    event: AnalyticsEvent,
    historicalEvents: AnalyticsEvent[]
  ): Promise<Insight | null> {
    const minDataPoints = this.config.minDataPoints || 100;

    if (historicalEvents.length < minDataPoints) {
      return null; // Not enough data
    }

    // Calculate statistics from recent history
    const values = historicalEvents
      .slice(-minDataPoints)
      .map(e => e.properties.value || 1);

    const stats = this.calculateStatistics(values);
    const currentValue = event.properties.value || 1;
    const zScore = Math.abs((currentValue - stats.mean) / stats.stdDev);

    const threshold = this.config.zScoreThreshold || 3;
    const criticalThreshold = this.config.criticalZScoreThreshold || 4;

    if (zScore > threshold) {
      const severity: Insight['severity'] = zScore > criticalThreshold ? 'critical' : 'warning';

      const insight = this.insightCreator.createInsight(
        'anomaly_detection',
        {
          severity,
          title: `Anomaly detected in ${event.event_type}`,
          description: `Value ${currentValue} is ${zScore.toFixed(1)} standard deviations from mean (${stats.mean.toFixed(2)})`,
          data: {
            event_type: event.event_type,
            value: currentValue,
            mean: stats.mean,
            std_dev: stats.stdDev,
            z_score: zScore,
            threshold
          },
          recommendations: [
            zScore > criticalThreshold
              ? 'Investigate immediately - significant deviation detected'
              : 'Monitor the situation - unusual pattern detected'
          ]
        },
        event.organization_id
      );

      this.emit('anomaly:detected', {
        insight,
        event,
        zScore,
        severity
      });

      return insight;
    }

    return null;
  }

  /**
   * Detect anomalies in time series data
   */
  async detectTimeSeriesAnomaly(
    metric: string,
    timeSeries: TimeSeriesData[],
    threshold?: number
  ): Promise<Insight[]> {
    const insights: Insight[] = [];
    const minDataPoints = this.config.minDataPoints || 30;

    if (timeSeries.length < minDataPoints) {
      return insights;
    }

    // Use a sliding window approach
    const windowSize = Math.min(minDataPoints, timeSeries.length);

    for (let i = windowSize; i < timeSeries.length; i++) {
      const window = timeSeries.slice(i - windowSize, i);
      const values = window.map(d => d.value);
      const stats = this.calculateStatistics(values);

      const currentPoint = timeSeries[i];
      const zScore = Math.abs((currentPoint.value - stats.mean) / stats.stdDev);

      const effectiveThreshold = threshold || this.config.zScoreThreshold || 3;

      if (zScore > effectiveThreshold) {
        const severity: Insight['severity'] = zScore > (this.config.criticalZScoreThreshold || 4)
          ? 'critical'
          : 'warning';

        const insight = this.insightCreator.createInsight(
          'anomaly_detection',
          {
            severity,
            title: `Anomaly detected in metric ${metric}`,
            description: `Value ${currentPoint.value.toFixed(2)} at ${currentPoint.timestamp.toISOString()} is ${zScore.toFixed(1)} standard deviations from mean`,
            data: {
              metric,
              timestamp: currentPoint.timestamp,
              value: currentPoint.value,
              mean: stats.mean,
              std_dev: stats.stdDev,
              z_score: zScore
            },
            affectedMetrics: [metric]
          }
        );

        insights.push(insight);
      }
    }

    if (insights.length > 0) {
      this.emit('anomalies:detected', {
        metric,
        count: insights.length
      });
    }

    return insights;
  }

  /**
   * Detect threshold violations
   */
  async detectThresholdViolation(
    metric: string,
    value: number,
    thresholds: {
      warning?: number;
      critical?: number;
    },
    organizationId?: string
  ): Promise<Insight | null> {
    if (thresholds.critical && value >= thresholds.critical) {
      const insight = this.insightCreator.createInsight(
        'threshold_violation',
        {
          severity: 'critical',
          title: `Critical threshold exceeded for ${metric}`,
          description: `Metric ${metric} value ${value} exceeds critical threshold ${thresholds.critical}`,
          data: {
            metric,
            value,
            threshold: thresholds.critical,
            type: 'critical'
          },
          affectedMetrics: [metric],
          recommendations: [
            'Immediate action required - critical threshold exceeded'
          ]
        },
        organizationId
      );

      this.emit('threshold:critical', { insight, metric, value });
      return insight;
    }

    if (thresholds.warning && value >= thresholds.warning) {
      const insight = this.insightCreator.createInsight(
        'threshold_violation',
        {
          severity: 'warning',
          title: `Warning threshold exceeded for ${metric}`,
          description: `Metric ${metric} value ${value} exceeds warning threshold ${thresholds.warning}`,
          data: {
            metric,
            value,
            threshold: thresholds.warning,
            type: 'warning'
          },
          affectedMetrics: [metric],
          recommendations: [
            'Monitor closely - warning threshold exceeded'
          ]
        },
        organizationId
      );

      this.emit('threshold:warning', { insight, metric, value });
      return insight;
    }

    return null;
  }

  /**
   * Detect sudden changes (spikes or drops)
   */
  async detectSuddenChange(
    metric: string,
    timeSeries: TimeSeriesData[],
    changeThresholdPercent: number = 50
  ): Promise<Insight[]> {
    const insights: Insight[] = [];

    if (timeSeries.length < 2) {
      return insights;
    }

    for (let i = 1; i < timeSeries.length; i++) {
      const previous = timeSeries[i - 1].value;
      const current = timeSeries[i].value;

      if (previous === 0) continue;

      const percentChange = Math.abs(((current - previous) / previous) * 100);

      if (percentChange >= changeThresholdPercent) {
        const isIncrease = current > previous;
        const severity: Insight['severity'] = percentChange >= 100 ? 'critical' : 'warning';

        const insight = this.insightCreator.createInsight(
          'sudden_change',
          {
            severity,
            title: `Sudden ${isIncrease ? 'spike' : 'drop'} in ${metric}`,
            description: `Metric ${metric} ${isIncrease ? 'increased' : 'decreased'} by ${percentChange.toFixed(1)}%`,
            data: {
              metric,
              timestamp: timeSeries[i].timestamp,
              previous_value: previous,
              current_value: current,
              percent_change: percentChange,
              direction: isIncrease ? 'increase' : 'decrease'
            },
            affectedMetrics: [metric]
          }
        );

        insights.push(insight);
      }
    }

    return insights;
  }

  /**
   * Private: Calculate statistics
   */
  private calculateStatistics(values: number[]): {
    mean: number;
    variance: number;
    stdDev: number;
    min: number;
    max: number;
  } {
    const n = values.length;
    const mean = values.reduce((a, b) => a + b, 0) / n;
    const variance = values.reduce((a, b) => a + Math.pow(b - mean, 2), 0) / n;
    const stdDev = Math.sqrt(variance);
    const min = Math.min(...values);
    const max = Math.max(...values);

    return { mean, variance, stdDev, min, max };
  }

  /**
   * Cleanup
   */
  destroy(): void {
    this.removeAllListeners();
  }
}
