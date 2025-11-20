/**
 * Report Executor Service
 * Handles report execution and widget coordination
 * Extracted from AnalyticsReportingService
 */

import { EventEmitter } from 'events';
import {
  Report,
  ReportWidget,
  VisualizationConfig
} from '../core/types';

export interface ReportDataSource {
  getReport(reportId: string): Promise<Report | null>;
}

export interface WidgetExecutor {
  executeWidget(widget: ReportWidget): Promise<any>;
}

export interface ReportExecutionResult {
  reportId: string;
  executedAt: Date;
  executionTimeMs: number;
  widgets: Array<{
    widgetId: string;
    title: string;
    data: any;
    executionTimeMs: number;
    error?: string;
  }>;
  totalRows: number;
  success: boolean;
}

export class ReportExecutorService extends EventEmitter {
  constructor(
    private readonly reportSource: ReportDataSource,
    private readonly widgetExecutor: WidgetExecutor
  ) {
    super();
  }

  /**
   * Execute a report
   */
  async executeReport(reportId: string): Promise<ReportExecutionResult> {
    const startTime = Date.now();

    try {
      const report = await this.reportSource.getReport(reportId);
      if (!report) {
        throw new Error(`Report ${reportId} not found`);
      }

      const result: ReportExecutionResult = {
        reportId,
        executedAt: new Date(),
        executionTimeMs: 0,
        widgets: [],
        totalRows: 0,
        success: true
      };

      // Execute each widget
      for (const widget of report.widgets) {
        const widgetStartTime = Date.now();

        try {
          const widgetData = await this.widgetExecutor.executeWidget(widget);

          result.widgets.push({
            widgetId: widget.id,
            title: widget.title,
            data: widgetData,
            executionTimeMs: Date.now() - widgetStartTime
          });

          // Count rows if data is an array
          if (Array.isArray(widgetData)) {
            result.totalRows += widgetData.length;
          }
        } catch (error) {
          // Widget execution failed - include error but continue
          result.widgets.push({
            widgetId: widget.id,
            title: widget.title,
            data: null,
            executionTimeMs: Date.now() - widgetStartTime,
            error: error instanceof Error ? error.message : 'Unknown error'
          });

          this.emit('widget:failed', {
            reportId,
            widgetId: widget.id,
            error
          });
        }
      }

      result.executionTimeMs = Date.now() - startTime;

      this.emit('report:executed', {
        reportId,
        success: true,
        executionTimeMs: result.executionTimeMs,
        widgetCount: result.widgets.length,
        totalRows: result.totalRows
      });

      return result;
    } catch (error) {
      const executionTimeMs = Date.now() - startTime;

      this.emit('report:failed', {
        reportId,
        error,
        executionTimeMs
      });

      throw error;
    }
  }

  /**
   * Execute multiple reports in parallel
   */
  async executeReports(reportIds: string[]): Promise<ReportExecutionResult[]> {
    const results = await Promise.all(
      reportIds.map(id => this.executeReport(id))
    );

    this.emit('reports:batch_executed', {
      count: results.length,
      successCount: results.filter(r => r.success).length
    });

    return results;
  }

  /**
   * Execute report and format for export
   */
  async executeReportForExport(
    reportId: string,
    format: 'json' | 'csv' | 'pdf' | 'excel'
  ): Promise<{
    result: ReportExecutionResult;
    formatted: any;
  }> {
    const result = await this.executeReport(reportId);

    // Format based on export type
    const formatted = this.formatForExport(result, format);

    this.emit('report:exported', {
      reportId,
      format,
      widgetCount: result.widgets.length,
      totalRows: result.totalRows
    });

    return { result, formatted };
  }

  /**
   * Get report execution summary
   */
  async getExecutionSummary(reportId: string): Promise<{
    reportId: string;
    widgetCount: number;
    estimatedRows: number;
    estimatedTimeMs: number;
  }> {
    const report = await this.reportSource.getReport(reportId);
    if (!report) {
      throw new Error(`Report ${reportId} not found`);
    }

    return {
      reportId,
      widgetCount: report.widgets.length,
      estimatedRows: 0, // Would calculate based on widget metrics
      estimatedTimeMs: report.widgets.length * 100 // Rough estimate
    };
  }

  /**
   * Private: Format execution result for export
   */
  private formatForExport(
    result: ReportExecutionResult,
    format: 'json' | 'csv' | 'pdf' | 'excel'
  ): any {
    switch (format) {
      case 'json':
        return result;

      case 'csv':
        // Convert each widget to CSV rows
        return this.formatAsCSV(result);

      case 'pdf':
        // Return PDF generation metadata
        return {
          title: `Report ${result.reportId}`,
          executedAt: result.executedAt,
          widgets: result.widgets.map(w => ({
            title: w.title,
            data: w.data
          }))
        };

      case 'excel':
        // Return Excel-compatible structure
        return {
          sheets: result.widgets.map(w => ({
            name: w.title.substring(0, 31), // Excel sheet name limit
            data: Array.isArray(w.data) ? w.data : [w.data]
          }))
        };

      default:
        return result;
    }
  }

  /**
   * Private: Format result as CSV
   */
  private formatAsCSV(result: ReportExecutionResult): string {
    const rows: string[] = [];

    // Add header
    rows.push(['Widget', 'Data'].join(','));

    // Add widget data
    for (const widget of result.widgets) {
      if (Array.isArray(widget.data)) {
        for (const item of widget.data) {
          rows.push([
            widget.title,
            JSON.stringify(item)
          ].join(','));
        }
      } else {
        rows.push([
          widget.title,
          JSON.stringify(widget.data)
        ].join(','));
      }
    }

    return rows.join('\n');
  }

  /**
   * Cleanup
   */
  destroy(): void {
    this.removeAllListeners();
  }
}
