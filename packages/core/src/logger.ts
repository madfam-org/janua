/**
 * Structured logging utilities for Plinto
 * Replaces console.log with structured, level-based logging
 */

export enum LogLevel {
  DEBUG = 'debug',
  INFO = 'info',
  WARN = 'warn',
  ERROR = 'error',
}

export interface LogContext {
  [key: string]: any;
}

export interface LogEntry {
  timestamp: string;
  level: LogLevel;
  message: string;
  context?: LogContext;
  error?: Error;
}

export class Logger {
  private context: LogContext = {};
  private minLevel: LogLevel;

  constructor(minLevel: LogLevel = LogLevel.INFO) {
    this.minLevel = minLevel;
  }

  /**
   * Set persistent context for all log entries
   */
  setContext(context: LogContext): void {
    this.context = { ...this.context, ...context };
  }

  /**
   * Clear persistent context
   */
  clearContext(): void {
    this.context = {};
  }

  /**
   * Check if log level should be output
   */
  private shouldLog(level: LogLevel): boolean {
    const levels = [LogLevel.DEBUG, LogLevel.INFO, LogLevel.WARN, LogLevel.ERROR];
    return levels.indexOf(level) >= levels.indexOf(this.minLevel);
  }

  /**
   * Format log entry as JSON
   */
  private format(entry: LogEntry): string {
    return JSON.stringify(entry);
  }

  /**
   * Output log entry
   */
  private output(level: LogLevel, message: string, context?: LogContext, error?: Error): void {
    if (!this.shouldLog(level)) return;

    const entry: LogEntry = {
      timestamp: new Date().toISOString(),
      level,
      message,
      context: { ...this.context, ...context },
      error: error ? {
        name: error.name,
        message: error.message,
        stack: error.stack,
      } as any : undefined,
    };

    const formatted = this.format(entry);

    // Output to appropriate stream
    if (level === LogLevel.ERROR || level === LogLevel.WARN) {
      console.error(formatted);
    } else {
      console.log(formatted);
    }
  }

  /**
   * Log debug message
   */
  debug(message: string, context?: LogContext): void {
    this.output(LogLevel.DEBUG, message, context);
  }

  /**
   * Log info message
   */
  info(message: string, context?: LogContext): void {
    this.output(LogLevel.INFO, message, context);
  }

  /**
   * Log warning message
   */
  warn(message: string, context?: LogContext, error?: Error): void {
    this.output(LogLevel.WARN, message, context, error);
  }

  /**
   * Log error message
   */
  error(message: string, context?: LogContext, error?: Error): void {
    this.output(LogLevel.ERROR, message, context, error);
  }

  /**
   * Create child logger with additional context
   */
  child(context: LogContext): Logger {
    const child = new Logger(this.minLevel);
    child.setContext({ ...this.context, ...context });
    return child;
  }
}

/**
 * Default logger instance
 */
export const logger = new Logger(
  process.env.NODE_ENV === 'production' ? LogLevel.INFO : LogLevel.DEBUG
);

/**
 * Create a logger for a specific module
 */
export function createLogger(module: string): Logger {
  return logger.child({ module });
}
