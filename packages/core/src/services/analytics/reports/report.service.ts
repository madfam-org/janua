/**
 * Report Service
 * Handles report CRUD operations
 * Extracted from AnalyticsReportingService
 */

import crypto from 'crypto';
import { EventEmitter } from 'events';
import {
  Report,
  ReportFilter,
  AccessControl
} from '../core/types';

export class ReportService extends EventEmitter {
  private reports: Map<string, Report> = new Map();

  constructor() {
    super();
  }

  /**
   * Create a new report
   */
  async createReport(
    report: Omit<Report, 'id' | 'created_at' | 'updated_at'>
  ): Promise<Report> {
    const fullReport: Report = {
      ...report,
      id: crypto.randomUUID(),
      created_at: new Date(),
      updated_at: new Date()
    };

    this.reports.set(fullReport.id, fullReport);

    // Emit event for downstream processing (e.g., scheduling)
    this.emit('report:created', fullReport);

    return fullReport;
  }

  /**
   * Get report by ID
   */
  async getReport(reportId: string): Promise<Report | null> {
    const report = this.reports.get(reportId);
    return report || null;
  }

  /**
   * List all reports
   */
  async listReports(filter?: {
    createdBy?: string;
    type?: Report['type'];
    organizationId?: string;
  }): Promise<Report[]> {
    let reports = Array.from(this.reports.values());

    if (filter?.createdBy) {
      reports = reports.filter(r => r.created_by === filter.createdBy);
    }

    if (filter?.type) {
      reports = reports.filter(r => r.type === filter.type);
    }

    // Sort by updated_at descending
    reports.sort((a, b) => b.updated_at.getTime() - a.updated_at.getTime());

    return reports;
  }

  /**
   * Update report
   */
  async updateReport(
    reportId: string,
    updates: Partial<Omit<Report, 'id' | 'created_at' | 'created_by'>>
  ): Promise<Report> {
    const report = this.reports.get(reportId);
    if (!report) {
      throw new Error(`Report ${reportId} not found`);
    }

    const updatedReport: Report = {
      ...report,
      ...updates,
      id: report.id,
      created_at: report.created_at,
      created_by: report.created_by,
      updated_at: new Date()
    };

    this.reports.set(reportId, updatedReport);

    this.emit('report:updated', {
      reportId,
      oldReport: report,
      newReport: updatedReport
    });

    return updatedReport;
  }

  /**
   * Delete report
   */
  async deleteReport(reportId: string): Promise<boolean> {
    const report = this.reports.get(reportId);
    if (!report) {
      return false;
    }

    this.reports.delete(reportId);

    this.emit('report:deleted', { reportId, report });

    return true;
  }

  /**
   * Check if user has access to report
   */
  async checkAccess(
    reportId: string,
    userId: string,
    userRoles: string[] = []
  ): Promise<boolean> {
    const report = this.reports.get(reportId);
    if (!report) {
      return false;
    }

    // If no access control, default to creator only
    if (!report.access_control) {
      return report.created_by === userId;
    }

    const ac = report.access_control;

    // Public reports
    if (ac.visibility === 'public') {
      return true;
    }

    // Creator always has access
    if (report.created_by === userId) {
      return true;
    }

    // Check explicit users
    if (ac.users?.includes(userId)) {
      return true;
    }

    // Check roles
    if (ac.roles && userRoles.some(role => ac.roles!.includes(role))) {
      return true;
    }

    return false;
  }

  /**
   * Get reports accessible to user
   */
  async getAccessibleReports(
    userId: string,
    userRoles: string[] = []
  ): Promise<Report[]> {
    const reports = Array.from(this.reports.values());
    const accessible: Report[] = [];

    for (const report of reports) {
      if (await this.checkAccess(report.id, userId, userRoles)) {
        accessible.push(report);
      }
    }

    return accessible;
  }

  /**
   * Get report count
   */
  getReportCount(): number {
    return this.reports.size;
  }

  /**
   * Get reports by type
   */
  async getReportsByType(type: Report['type']): Promise<Report[]> {
    return Array.from(this.reports.values()).filter(r => r.type === type);
  }

  /**
   * Clone report
   */
  async cloneReport(
    reportId: string,
    userId: string,
    newName?: string
  ): Promise<Report> {
    const original = this.reports.get(reportId);
    if (!original) {
      throw new Error(`Report ${reportId} not found`);
    }

    const cloned: Omit<Report, 'id' | 'created_at' | 'updated_at'> = {
      ...original,
      name: newName || `${original.name} (Copy)`,
      created_by: userId,
      type: 'adhoc' // Cloned reports are ad-hoc by default
    };

    const newReport = await this.createReport(cloned);

    this.emit('report:cloned', {
      originalId: reportId,
      newId: newReport.id
    });

    return newReport;
  }

  /**
   * Cleanup
   */
  destroy(): void {
    this.removeAllListeners();
  }
}
