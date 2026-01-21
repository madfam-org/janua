/**
 * Insight Engine Service
 * Handles insight generation and management
 * Extracted from AnalyticsReportingService
 */

import crypto from 'crypto';
import { EventEmitter } from 'events';
import {
  Insight,
  InsightDefinition,
  InsightAction
} from '../core/types';

export class InsightEngineService extends EventEmitter {
  private insightDefinitions: Map<string, InsightDefinition> = new Map();
  private insights: Map<string, Insight[]> = new Map();

  constructor() {
    super();
  }

  /**
   * Register an insight definition
   */
  registerInsightDefinition(definition: InsightDefinition): void {
    this.insightDefinitions.set(definition.id, definition);
    this.emit('definition:registered', definition);
  }

  /**
   * Unregister an insight definition
   */
  unregisterInsightDefinition(definitionId: string): boolean {
    const existed = this.insightDefinitions.delete(definitionId);
    if (existed) {
      this.emit('definition:unregistered', { definitionId });
    }
    return existed;
  }

  /**
   * Get insight definition
   */
  getInsightDefinition(definitionId: string): InsightDefinition | undefined {
    return this.insightDefinitions.get(definitionId);
  }

  /**
   * List all insight definitions
   */
  listInsightDefinitions(filter?: {
    type?: InsightDefinition['type'];
    schedule?: InsightDefinition['schedule'];
  }): InsightDefinition[] {
    let definitions = Array.from(this.insightDefinitions.values());

    if (filter?.type) {
      definitions = definitions.filter(d => d.type === filter.type);
    }

    if (filter?.schedule) {
      definitions = definitions.filter(d => d.schedule === filter.schedule);
    }

    return definitions;
  }

  /**
   * Create an insight
   */
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
  ): Insight {
    const definition = this.insightDefinitions.get(definitionId);
    if (!definition) {
      throw new Error(`Insight definition ${definitionId} not found`);
    }

    const insight: Insight = {
      id: crypto.randomUUID(),
      definition_id: definitionId,
      timestamp: new Date(),
      type: definition.type,
      severity: data.severity,
      title: data.title,
      description: data.description,
      data: data.data,
      affected_metrics: data.affectedMetrics,
      recommendations: data.recommendations
    };

    // Store insight
    const key = organizationId || 'global';
    if (!this.insights.has(key)) {
      this.insights.set(key, []);
    }
    this.insights.get(key)!.push(insight);

    this.emit('insight:created', { insight, organizationId });

    return insight;
  }

  /**
   * Get insights for organization or global
   */
  getInsights(filter?: {
    organizationId?: string;
    type?: Insight['type'];
    severity?: Insight['severity'];
    since?: Date;
    limit?: number;
  }): Insight[] {
    const key = filter?.organizationId || 'global';
    let insights = this.insights.get(key) || [];

    // Apply filters
    if (filter?.type) {
      insights = insights.filter(i => i.type === filter.type);
    }

    if (filter?.severity) {
      insights = insights.filter(i => i.severity === filter.severity);
    }

    if (filter?.since) {
      insights = insights.filter(i => i.timestamp >= filter.since);
    }

    // Sort by timestamp descending
    insights.sort((a, b) => b.timestamp.getTime() - a.timestamp.getTime());

    // Apply limit
    if (filter?.limit) {
      insights = insights.slice(0, filter.limit);
    }

    return insights;
  }

  /**
   * Execute insight actions
   */
  async executeInsightActions(insight: Insight, actions: InsightAction[]): Promise<void> {
    for (const action of actions) {
      try {
        switch (action.type) {
          case 'alert':
            this.emit('action:alert', { insight, config: action.config });
            break;

          case 'webhook':
            this.emit('action:webhook', { insight, config: action.config });
            break;

          case 'email':
            this.emit('action:email', { insight, config: action.config });
            break;

          case 'slack':
            this.emit('action:slack', { insight, config: action.config });
            break;
        }

        this.emit('action:executed', {
          insightId: insight.id,
          actionType: action.type
        });
      } catch (error) {
        this.emit('action:failed', {
          insightId: insight.id,
          actionType: action.type,
          error
        });
      }
    }
  }

  /**
   * Get insight statistics
   */
  getInsightStats(organizationId?: string): {
    total: number;
    byType: Record<string, number>;
    bySeverity: Record<string, number>;
    recent: number;
  } {
    const key = organizationId || 'global';
    const insights = this.insights.get(key) || [];

    const now = new Date();
    const last24h = new Date(now.getTime() - 24 * 60 * 60 * 1000);

    const byType: Record<string, number> = {};
    const bySeverity: Record<string, number> = {};
    let recent = 0;

    for (const insight of insights) {
      byType[insight.type] = (byType[insight.type] || 0) + 1;
      bySeverity[insight.severity] = (bySeverity[insight.severity] || 0) + 1;

      if (insight.timestamp >= last24h) {
        recent++;
      }
    }

    return {
      total: insights.length,
      byType,
      bySeverity,
      recent
    };
  }

  /**
   * Clear old insights
   */
  clearOldInsights(beforeDate: Date, organizationId?: string): number {
    const key = organizationId || 'global';
    const insights = this.insights.get(key);

    if (!insights) {
      return 0;
    }

    const before = insights.length;
    const filtered = insights.filter(i => i.timestamp >= beforeDate);
    this.insights.set(key, filtered);

    const removed = before - filtered.length;

    if (removed > 0) {
      this.emit('insights:cleared', {
        organizationId,
        removed,
        beforeDate
      });
    }

    return removed;
  }

  /**
   * Cleanup
   */
  destroy(): void {
    this.removeAllListeners();
  }
}
