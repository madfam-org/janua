/**
 * Configuration Service
 *
 * Centralized configuration management with environment-based settings
 */

export interface DatabaseConfig {
  host: string;
  port: number;
  username: string;
  password: string;
  database: string;
  ssl?: boolean;
}

export interface RedisConfig {
  host: string;
  port: number;
  password?: string;
  db?: number;
}

export interface SecurityConfig {
  jwtSecret: string;
  encryptionKey: string;
  sessionSecret: string;
  maxLoginAttempts: number;
  lockoutDuration: number;
}

export interface SecretsRotationConfig {
  rotationInterval: string;
  keyType: 'jwt' | 'api' | 'encryption' | 'signing';
  algorithm: string;
  keySize: number;
  gracePeriod: number;
  notificationChannels: string[];
}

export interface SecretsConfig {
  rotation?: SecretsRotationConfig[];
}

export interface AppConfig {
  environment: 'development' | 'staging' | 'production';
  port: number;
  database: DatabaseConfig;
  redis: RedisConfig;
  security: SecurityConfig;
  secrets?: SecretsConfig;
  enableClustering?: boolean;
  logLevel: 'debug' | 'info' | 'warn' | 'error';
  monitoringInterval?: number;
}

export class ConfigService {
  private static instance: ConfigService;
  private config: AppConfig;

  private constructor() {
    this.config = this.loadConfig();
  }

  public static getInstance(): ConfigService {
    if (!ConfigService.instance) {
      ConfigService.instance = new ConfigService();
    }
    return ConfigService.instance;
  }

  private loadConfig(): AppConfig {
    return {
      environment: (process.env.NODE_ENV as any) || 'development',
      port: parseInt(process.env.PORT || '3000'),
      database: {
        host: process.env.DB_HOST || 'localhost',
        port: parseInt(process.env.DB_PORT || '5432'),
        username: process.env.DB_USERNAME || 'postgres',
        password: process.env.DB_PASSWORD || '',
        database: process.env.DB_NAME || 'plinto',
        ssl: process.env.DB_SSL === 'true'
      },
      redis: {
        host: process.env.REDIS_HOST || 'localhost',
        port: parseInt(process.env.REDIS_PORT || '6379'),
        password: process.env.REDIS_PASSWORD,
        db: parseInt(process.env.REDIS_DB || '0')
      },
      security: {
        jwtSecret: process.env.JWT_SECRET || 'dev-secret',
        encryptionKey: process.env.ENCRYPTION_KEY || 'dev-encryption-key',
        sessionSecret: process.env.SESSION_SECRET || 'dev-session-secret',
        maxLoginAttempts: parseInt(process.env.MAX_LOGIN_ATTEMPTS || '5'),
        lockoutDuration: parseInt(process.env.LOCKOUT_DURATION || '900000') // 15 minutes
      },
      enableClustering: process.env.ENABLE_CLUSTERING === 'true',
      logLevel: (process.env.LOG_LEVEL as any) || 'info'
    };
  }

  public get<K extends keyof AppConfig>(key: K): AppConfig[K] {
    return this.config[key];
  }

  public getAll(): AppConfig {
    return { ...this.config };
  }

  public isDevelopment(): boolean {
    return this.config.environment === 'development';
  }

  public isProduction(): boolean {
    return this.config.environment === 'production';
  }

  public isStaging(): boolean {
    return this.config.environment === 'staging';
  }
}

export const config = ConfigService.getInstance();