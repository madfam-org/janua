import { EventEmitter } from 'events';

// Provider interfaces
interface SMSProvider {
  name: string;
  sendSMS(to: string, message: string): Promise<SMSResult>;
  getBalance?(): Promise<number>;
  validateNumber?(number: string): Promise<boolean>;
}

interface SMSResult {
  success: boolean;
  messageId?: string;
  error?: string;
  cost?: number;
  status?: 'queued' | 'sent' | 'delivered' | 'failed';
}

interface SMSConfig {
  provider: 'twilio' | 'aws-sns' | 'messagebird' | 'nexmo' | 'mock';
  apiKey?: string;
  apiSecret?: string;
  accountSid?: string;
  authToken?: string;
  region?: string;
  from?: string;
  sandbox?: boolean;
  rateLimit?: {
    perNumber: number;
    perHour: number;
  };
}

// Twilio Provider
class TwilioProvider implements SMSProvider {
  name = 'twilio';
  private accountSid: string;
  private authToken: string;
  private from: string;
  
  constructor(config: SMSConfig) {
    if (!config.accountSid || !config.authToken || !config.from) {
      throw new Error('Twilio requires accountSid, authToken, and from number');
    }
    this.accountSid = config.accountSid;
    this.authToken = config.authToken;
    this.from = config.from;
  }
  
  async sendSMS(to: string, message: string): Promise<SMSResult> {
    try {
      // Dynamic import to avoid dependency if not used
      const twilio = await import('twilio');
      const client = twilio.default(this.accountSid, this.authToken);
      
      const result = await client.messages.create({
        body: message,
        from: this.from,
        to: to
      });
      
      return {
        success: true,
        messageId: result.sid,
        status: result.status as any
      };
    } catch (error: any) {
      return {
        success: false,
        error: error.message
      };
    }
  }
  
  async validateNumber(number: string): Promise<boolean> {
    try {
      const twilio = await import('twilio');
      const client = twilio.default(this.accountSid, this.authToken);
      
      const lookup = await client.lookups.v1
        .phoneNumbers(number)
        .fetch();
      
      return !!lookup.phoneNumber;
    } catch {
      return false;
    }
  }
}

// AWS SNS Provider
class AWSSNSProvider implements SMSProvider {
  name = 'aws-sns';
  private region: string;
  private accessKeyId?: string;
  private secretAccessKey?: string;
  
  constructor(config: SMSConfig) {
    this.region = config.region || 'us-east-1';
    this.accessKeyId = config.apiKey;
    this.secretAccessKey = config.apiSecret;
  }
  
  async sendSMS(to: string, message: string): Promise<SMSResult> {
    try {
      // Dynamic import
      const AWS = await import('aws-sdk');
      
      const sns = new AWS.SNS({
        region: this.region,
        ...(this.accessKeyId && {
          accessKeyId: this.accessKeyId,
          secretAccessKey: this.secretAccessKey
        })
      });
      
      const result = await sns.publish({
        Message: message,
        PhoneNumber: to,
        MessageAttributes: {
          'AWS.SNS.SMS.SMSType': {
            DataType: 'String',
            StringValue: 'Transactional'
          }
        }
      }).promise();
      
      return {
        success: true,
        messageId: result.MessageId,
        status: 'sent'
      };
    } catch (error: any) {
      return {
        success: false,
        error: error.message
      };
    }
  }
}

// MessageBird Provider
class MessageBirdProvider implements SMSProvider {
  name = 'messagebird';
  private apiKey: string;
  private from: string;
  
  constructor(config: SMSConfig) {
    if (!config.apiKey || !config.from) {
      throw new Error('MessageBird requires apiKey and from number');
    }
    this.apiKey = config.apiKey;
    this.from = config.from;
  }
  
  async sendSMS(to: string, message: string): Promise<SMSResult> {
    try {
      const messagebird = await import('messagebird');
      const client = (messagebird as any)(this.apiKey);
      
      return new Promise((resolve) => {
        client.messages.create({
          originator: this.from,
          recipients: [to],
          body: message
        }, (error: any, response: any) => {
          if (error) {
            resolve({
              success: false,
              error: error.message
            });
          } else {
            resolve({
              success: true,
              messageId: response.id,
              status: 'sent'
            });
          }
        });
      });
    } catch (error: any) {
      return {
        success: false,
        error: error.message
      };
    }
  }
}

// Mock Provider for Testing
class MockProvider implements SMSProvider {
  name = 'mock';
  private sentMessages: Array<{ to: string; message: string; timestamp: Date }> = [];
  
  async sendSMS(to: string, message: string): Promise<SMSResult> {
    // Simulate network delay
    await new Promise(resolve => setTimeout(resolve, 100));
    
    // Extract code from message
    const codeMatch = message.match(/\b\d{6}\b/);
    const code = codeMatch ? codeMatch[0] : null;
    
    // Store for testing
    this.sentMessages.push({
      to,
      message,
      timestamp: new Date()
    });
    
    // Log for development
    if (code) {
      // Verification code logging handled by parent caller
    }
    
    return {
      success: true,
      messageId: `mock-${Date.now()}`,
      status: 'delivered'
    };
  }
  
  getLastMessage(): { to: string; message: string; timestamp: Date } | undefined {
    return this.sentMessages[this.sentMessages.length - 1];
  }
  
  getMessages(): Array<{ to: string; message: string; timestamp: Date }> {
    return [...this.sentMessages];
  }
  
  clearMessages(): void {
    this.sentMessages = [];
  }
}

// Main SMS Service
export class SMSService extends EventEmitter {
  private provider: SMSProvider;
  private config: SMSConfig;
  private rateLimits: Map<string, { count: number; resetAt: Date }> = new Map();
  private templates: Map<string, string> = new Map();
  
  constructor(config: SMSConfig) {
    super();
    this.config = config;
    
    // Initialize provider
    switch (config.provider) {
      case 'twilio':
        this.provider = new TwilioProvider(config);
        break;
      case 'aws-sns':
        this.provider = new AWSSNSProvider(config);
        break;
      case 'messagebird':
        this.provider = new MessageBirdProvider(config);
        break;
      case 'mock':
        this.provider = new MockProvider();
        break;
      default:
        throw new Error(`Unsupported SMS provider: ${config.provider}`);
    }
    
    // Setup default templates
    this.setupTemplates();
  }
  
  private setupTemplates(): void {
    this.templates.set('mfa_code', 'Your verification code is: {code}. Valid for 5 minutes.');
    this.templates.set('password_reset', 'Your password reset code is: {code}. If you didn\'t request this, please ignore.');
    this.templates.set('login_alert', 'New login to your account from {location} at {time}. If this wasn\'t you, please secure your account.');
    this.templates.set('welcome', 'Welcome to {app_name}! Your account has been created successfully.');
    this.templates.set('payment_confirmation', 'Payment of {amount} confirmed. Transaction ID: {transaction_id}');
  }
  
  async sendVerificationCode(
    to: string,
    code: string,
    template: string = 'mfa_code'
  ): Promise<SMSResult> {
    // Format phone number
    const formattedNumber = this.formatPhoneNumber(to);
    
    // Check rate limits
    if (!await this.checkRateLimit(formattedNumber)) {
      return {
        success: false,
        error: 'Rate limit exceeded'
      };
    }
    
    // Get template
    const messageTemplate = this.templates.get(template) || this.templates.get('mfa_code')!;
    const message = messageTemplate.replace('{code}', code);
    
    // Send SMS
    const result = await this.provider.sendSMS(formattedNumber, message);
    
    // Emit event
    this.emit('sms_sent', {
      to: formattedNumber,
      template,
      success: result.success,
      messageId: result.messageId,
      error: result.error
    });
    
    return result;
  }
  
  async sendCustomMessage(to: string, message: string): Promise<SMSResult> {
    const formattedNumber = this.formatPhoneNumber(to);
    
    // Check rate limits
    if (!await this.checkRateLimit(formattedNumber)) {
      return {
        success: false,
        error: 'Rate limit exceeded'
      };
    }
    
    return await this.provider.sendSMS(formattedNumber, message);
  }
  
  async sendTemplatedMessage(
    to: string,
    template: string,
    variables: Record<string, string>
  ): Promise<SMSResult> {
    const formattedNumber = this.formatPhoneNumber(to);
    
    // Get template
    let message = this.templates.get(template);
    if (!message) {
      return {
        success: false,
        error: `Template '${template}' not found`
      };
    }
    
    // Replace variables
    for (const [key, value] of Object.entries(variables)) {
      message = message.replace(`{${key}}`, value);
    }
    
    return await this.sendCustomMessage(formattedNumber, message);
  }
  
  private formatPhoneNumber(number: string): string {
    // Remove all non-digits
    let cleaned = number.replace(/\D/g, '');
    
    // Add country code if missing (assuming US)
    if (cleaned.length === 10) {
      cleaned = '1' + cleaned;
    }
    
    // Add + prefix if missing
    if (!cleaned.startsWith('+')) {
      cleaned = '+' + cleaned;
    }
    
    return cleaned;
  }
  
  private async checkRateLimit(number: string): Promise<boolean> {
    if (!this.config.rateLimit) {
      return true;
    }
    
    const now = new Date();
    const limit = this.rateLimits.get(number);
    
    if (!limit || limit.resetAt < now) {
      // New window
      this.rateLimits.set(number, {
        count: 1,
        resetAt: new Date(now.getTime() + 3600000) // 1 hour
      });
      return true;
    }
    
    if (limit.count >= this.config.rateLimit.perNumber) {
      return false;
    }
    
    limit.count++;
    return true;
  }
  
  async validatePhoneNumber(number: string): Promise<boolean> {
    if (this.provider.validateNumber) {
      return await this.provider.validateNumber(this.formatPhoneNumber(number));
    }
    
    // Basic validation
    const cleaned = number.replace(/\D/g, '');
    return cleaned.length >= 10 && cleaned.length <= 15;
  }
  
  setTemplate(name: string, template: string): void {
    this.templates.set(name, template);
  }
  
  getTemplate(name: string): string | undefined {
    return this.templates.get(name);
  }
  
  // For testing
  getMockProvider(): MockProvider | null {
    if (this.provider instanceof MockProvider) {
      return this.provider;
    }
    return null;
  }
  
  // Cleanup rate limits periodically
  cleanupRateLimits(): void {
    const now = new Date();
    for (const [number, limit] of this.rateLimits.entries()) {
      if (limit.resetAt < now) {
        this.rateLimits.delete(number);
      }
    }
  }
}

// Export factory function
export function createSMSService(config: SMSConfig): SMSService {
  return new SMSService(config);
}