import { EventEmitter } from 'events';
import { RedisService, getRedis } from './redis.service';

// Payment Provider Types
export type PaymentProvider = 'conekta' | 'fungies' | 'stripe';
export type PaymentStatus = 'pending' | 'processing' | 'succeeded' | 'failed' | 'canceled' | 'refunded';
export type Currency = 'MXN' | 'USD' | 'EUR' | 'GBP' | 'CAD' | 'AUD' | 'JPY' | 'BRL' | 'ARS' | 'COP' | 'CLP' | 'PEN' | 'CHF' | 'NOK' | 'SEK' | 'DKK' | 'PLN' | 'CZK' | 'HUF' | 'RON' | 'BGN' | 'HRK' | 'SGD' | 'HKD' | 'NZD' | 'UYU' | 'INR' | 'CNY' | 'RUB' | 'TRY' | 'IDR' | 'MYR' | 'PHP' | 'THB' | 'VND' | 'KRW' | 'ILS' | 'TWD' | 'SAR' | 'AED' | 'ZAR' | 'NGN' | 'KES' | 'GHS' | 'EGP' | 'MAD';

export interface PaymentMethod {
  id: string;
  provider: PaymentProvider;
  type: 'card' | 'oxxo' | 'spei' | 'bank_transfer' | 'paypal' | 'crypto' | 'wire' | 'bank_account' | 'sepa' | 'ideal' | 'giropay';
  details: {
    brand?: string;
    last4?: string;
    exp_month?: number;
    exp_year?: number;
    bank_name?: string;
    wallet_address?: string;
    reference?: string;
  };
  is_default: boolean;
  metadata?: Record<string, any>;
}

export interface PaymentIntent {
  id: string;
  provider: PaymentProvider;
  provider_intent_id?: string;
  amount: number;
  currency: Currency;
  status: PaymentStatus;
  customer_id: string;
  organization_id: string;
  description?: string;
  metadata?: Record<string, any>;
  payment_method?: PaymentMethod;
  error?: {
    code: string;
    message: string;
    provider_error?: any;
  };
  created_at: Date;
  updated_at: Date;
}

export interface Customer {
  id: string;
  email: string;
  name: string;
  phone?: string;
  address?: Address;
  tax_info?: TaxInfo;
  provider_customers: {
    conekta?: { id: string; created_at: Date };
    fungies?: { id: string; created_at: Date };
    stripe?: { id: string; created_at: Date };
  };
  default_payment_method?: PaymentMethod;
  provider?: PaymentProvider;
  metadata?: Record<string, any>;
  created_at: Date;
  updated_at: Date;
}

export interface Address {
  line1: string;
  line2?: string;
  city: string;
  state?: string;
  postal_code: string;
  country: string; // ISO 3166-1 alpha-2
}

export interface TaxInfo {
  type: 'rfc' | 'vat' | 'gst' | 'ein' | 'abn';
  id: string;
  name?: string;
  address?: Address;
  verified?: boolean;
}

export interface CheckoutSession {
  id: string;
  provider: PaymentProvider;
  provider_session_id?: string;
  amount: number;
  currency: Currency;
  customer_id: string;
  success_url: string;
  cancel_url: string;
  line_items: LineItem[];
  payment_intent_id?: string;
  status: 'open' | 'complete' | 'expired';
  expires_at: Date;
  url?: string;
  metadata?: Record<string, any>;
  created_at: Date;
}

export interface LineItem {
  name: string;
  description?: string;
  amount: number;
  currency: Currency;
  quantity: number;
  images?: string[];
  tax_rate?: number;
}

export interface RefundRequest {
  payment_intent_id: string;
  amount?: number; // Partial refund if specified
  reason?: 'duplicate' | 'fraudulent' | 'requested_by_customer' | 'other';
  metadata?: Record<string, any>;
}

export interface ComplianceCheck {
  country: string;
  payment_type: string;
  amount: number;
  currency: Currency;
  is_recurring: boolean;
  customer_type: 'individual' | 'business';
}

// Provider Interfaces
export interface PaymentProviderInterface {
  name: PaymentProvider;
  
  // Customer Management
  createCustomer(customer: Partial<Customer>): Promise<string>;
  updateCustomer(customerId: string, updates: Partial<Customer>): Promise<void>;
  deleteCustomer(customerId: string): Promise<void>;
  
  // Payment Methods
  attachPaymentMethod(customerId: string, paymentMethodId: string): Promise<void>;
  detachPaymentMethod(paymentMethodId: string): Promise<void>;
  listPaymentMethods(customerId: string): Promise<PaymentMethod[]>;
  
  // Payments
  createPaymentIntent(params: {
    amount: number;
    currency: Currency;
    customer_id: string;
    payment_method_id?: string;
    description?: string;
    metadata?: Record<string, any>;
  }): Promise<PaymentIntent>;
  
  confirmPayment(intentId: string): Promise<PaymentIntent>;
  cancelPayment(intentId: string): Promise<PaymentIntent>;
  
  // Checkout
  createCheckoutSession(params: {
    customer_id: string;
    line_items: LineItem[];
    success_url: string;
    cancel_url: string;
    metadata?: Record<string, any>;
  }): Promise<CheckoutSession>;
  
  // Refunds
  createRefund(request: RefundRequest): Promise<{ id: string; status: string }>;
  
  // Webhooks
  validateWebhookSignature(payload: string, signature: string): boolean;
  processWebhookEvent(event: any): Promise<void>;
  
  // Utilities
  isAvailable(country: string, currency: Currency): boolean;
  getSupportedPaymentMethods(country: string): string[];
  getComplianceRequirements(check: ComplianceCheck): string[];
}

export class PaymentGatewayService extends EventEmitter {
  private redis: RedisService;
  private providers: Map<PaymentProvider, PaymentProviderInterface> = new Map();
  private customerCache: Map<string, Customer> = new Map();
  private routingRules: Map<string, PaymentProvider> = new Map();
  
  constructor() {
    super();
    this.redis = getRedis();
    this.initializeProviders();
    this.setupRoutingRules();
  }
  
  // Provider Selection & Routing
  async selectProvider(params: {
    country: string;
    currency: Currency;
    amount: number;
    payment_type?: string;
    customer_id?: string;
    preferred_provider?: PaymentProvider;
  }): Promise<PaymentProvider> {
    // 1. Check if preferred provider is specified and available
    if (params.preferred_provider) {
      const provider = this.providers.get(params.preferred_provider);
      if (provider && provider.isAvailable(params.country, params.currency)) {
        return params.preferred_provider;
      }
    }
    
    // 2. Apply intelligent routing rules
    
    // Mexico: Always use Conekta for MXN
    if (params.country === 'MX' || params.currency === 'MXN') {
      const conekta = this.providers.get('conekta');
      if (conekta && conekta.isAvailable(params.country, params.currency)) {
        return 'conekta';
      }
    }
    
    // International: Use Fungies.io as MoR for tax compliance
    const requiresMoR = this.requiresMerchantOfRecord(params.country, params.amount);
    if (requiresMoR) {
      const fungies = this.providers.get('fungies');
      if (fungies && fungies.isAvailable(params.country, params.currency)) {
        return 'fungies';
      }
    }
    
    // Latin America specific routing
    const latamCountries = ['AR', 'BR', 'CL', 'CO', 'PE', 'UY', 'BO', 'EC', 'PY', 'VE'];
    if (latamCountries.includes(params.country)) {
      // Try Conekta first for better local payment methods
      const conekta = this.providers.get('conekta');
      if (conekta && conekta.isAvailable(params.country, params.currency)) {
        return 'conekta';
      }
      
      // Then Fungies for MoR benefits
      const fungies = this.providers.get('fungies');
      if (fungies && fungies.isAvailable(params.country, params.currency)) {
        return 'fungies';
      }
    }
    
    // Europe: Prefer Fungies for VAT handling
    const euCountries = ['AT', 'BE', 'BG', 'HR', 'CY', 'CZ', 'DK', 'EE', 'FI', 'FR', 'DE', 
                         'GR', 'HU', 'IE', 'IT', 'LV', 'LT', 'LU', 'MT', 'NL', 'PL', 'PT', 
                         'RO', 'SK', 'SI', 'ES', 'SE'];
    if (euCountries.includes(params.country)) {
      const fungies = this.providers.get('fungies');
      if (fungies && fungies.isAvailable(params.country, params.currency)) {
        return 'fungies';
      }
    }
    
    // 3. Fallback to Stripe for everything else
    const stripe = this.providers.get('stripe');
    if (stripe && stripe.isAvailable(params.country, params.currency)) {
      return 'stripe';
    }
    
    // 4. If all else fails, try providers in order
    for (const [name, provider] of this.providers) {
      if (provider.isAvailable(params.country, params.currency)) {
        return name;
      }
    }
    
    throw new Error(`No payment provider available for ${params.country} with ${params.currency}`);
  }
  
  // Customer Management
  async createOrUpdateCustomer(data: {
    email: string;
    name: string;
    phone?: string;
    address?: Address;
    tax_info?: TaxInfo;
    organization_id: string;
  }): Promise<Customer> {
    // Check if customer exists
    let customer = await this.getCustomerByEmail(data.email);
    
    if (customer) {
      // Update existing customer
      Object.assign(customer, data);
      customer.updated_at = new Date();
    } else {
      // Create new customer
      customer = {
        id: this.generateCustomerId(),
        email: data.email,
        name: data.name,
        phone: data.phone,
        address: data.address,
        tax_info: data.tax_info,
        provider_customers: {},
        created_at: new Date(),
        updated_at: new Date()
      };
    }
    
    // Determine which providers need this customer
    const country = data.address?.country || 'US';
    const providers = this.determineRequiredProviders(country);
    
    // Create customer in each provider
    for (const providerName of providers) {
      if (!customer!.provider_customers[providerName]) {
        const provider = this.providers.get(providerName);
        if (provider) {
          try {
            const providerId = await provider.createCustomer(customer!);
            customer!.provider_customers[providerName] = {
              id: providerId,
              created_at: new Date()
            };
          } catch (error) {
            console.error(`Failed to create customer in ${providerName}:`, error);
            // Continue with other providers
          }
        }
      }
    }
    
    // Store customer
    await this.storeCustomer(customer!);
    
    // Emit event
    this.emit('customer_created_or_updated', {
      customer_id: customer!.id,
      email: customer!.email,
      providers: Object.keys(customer!.provider_customers),
      timestamp: new Date()
    });

    return customer!;
  }
  
  // Unified Payment Creation
  async createPayment(params: {
    amount: number;
    currency: Currency;
    customer_id: string;
    organization_id: string;
    description?: string;
    payment_method_id?: string;
    metadata?: Record<string, any>;
    preferred_provider?: PaymentProvider;
  }): Promise<PaymentIntent> {
    // Get customer
    const customer = await this.getCustomer(params.customer_id);
    if (!customer) {
      throw new Error('Customer not found');
    }
    
    // Select optimal provider
    const country = customer.address?.country || 'US';
    const provider = await this.selectProvider({
      country,
      currency: params.currency,
      amount: params.amount,
      customer_id: params.customer_id,
      preferred_provider: params.preferred_provider
    });
    
    // Check for provider-specific customer
    const providerCustomerId = customer.provider_customers[provider]?.id;
    if (!providerCustomerId) {
      throw new Error(`Customer not registered with ${provider}`);
    }
    
    // Create payment intent
    const providerInterface = this.providers.get(provider)!;
    const intent = await providerInterface.createPaymentIntent({
      amount: params.amount,
      currency: params.currency,
      customer_id: providerCustomerId,
      payment_method_id: params.payment_method_id,
      description: params.description,
      metadata: {
        ...params.metadata,
        organization_id: params.organization_id,
        plinto_customer_id: params.customer_id
      }
    });
    
    // Store payment intent
    await this.storePaymentIntent(intent);
    
    // Emit event
    this.emit('payment_created', {
      payment_id: intent.id,
      provider,
      amount: params.amount,
      currency: params.currency,
      customer_id: params.customer_id,
      timestamp: new Date()
    });
    
    return intent;
  }
  
  // Unified Checkout Experience
  async createCheckout(params: {
    customer_id: string;
    line_items: LineItem[];
    success_url: string;
    cancel_url: string;
    metadata?: Record<string, any>;
    preferred_provider?: PaymentProvider;
    locale?: string;
  }): Promise<{
    url: string;
    session_id: string;
    provider: PaymentProvider;
    expires_at: Date;
  }> {
    // Get customer
    const customer = await this.getCustomer(params.customer_id);
    if (!customer) {
      throw new Error('Customer not found');
    }
    
    // Calculate total amount and determine currency
    const totalAmount = params.line_items.reduce((sum, item) => sum + (item.amount * item.quantity), 0);
    const currency = params.line_items[0].currency;
    const country = customer.address?.country || 'US';
    
    // Select provider
    const provider = await this.selectProvider({
      country,
      currency,
      amount: totalAmount,
      customer_id: params.customer_id,
      preferred_provider: params.preferred_provider
    });
    
    // Get provider-specific customer ID
    const providerCustomerId = customer.provider_customers[provider]?.id;
    if (!providerCustomerId) {
      // Create customer in provider if needed
      const providerInterface = this.providers.get(provider)!;
      const providerId = await providerInterface.createCustomer(customer);
      customer.provider_customers[provider] = {
        id: providerId,
        created_at: new Date()
      };
      await this.storeCustomer(customer);
    }
    
    // Create checkout session
    const providerInterface = this.providers.get(provider)!;
    const session = await providerInterface.createCheckoutSession({
      customer_id: customer.provider_customers[provider]!.id,
      line_items: params.line_items,
      success_url: params.success_url,
      cancel_url: params.cancel_url,
      metadata: {
        ...params.metadata,
        plinto_customer_id: params.customer_id,
        locale: params.locale || this.getDefaultLocale(country)
      }
    });
    
    // Store session
    await this.storeCheckoutSession(session);
    
    // Generate checkout URL based on provider
    let checkoutUrl: string;
    switch (provider) {
      case 'conekta':
        checkoutUrl = `https://pay.conekta.com/${session.provider_session_id}`;
        break;
      case 'fungies':
        checkoutUrl = `https://checkout.fungies.io/${session.provider_session_id}`;
        break;
      case 'stripe':
        checkoutUrl = `https://checkout.stripe.com/pay/${session.provider_session_id}`;
        break;
      default:
        checkoutUrl = `${process.env.FRONTEND_URL}/checkout/${session.id}`;
    }
    
    // Emit event
    this.emit('checkout_created', {
      session_id: session.id,
      provider,
      amount: totalAmount,
      currency,
      customer_id: params.customer_id,
      timestamp: new Date()
    });
    
    return {
      url: checkoutUrl,
      session_id: session.id,
      provider,
      expires_at: session.expires_at
    };
  }
  
  // Payment Method Management
  async addPaymentMethod(params: {
    customer_id: string;
    payment_method: PaymentMethod;
    set_default?: boolean;
  }): Promise<PaymentMethod> {
    const customer = await this.getCustomer(params.customer_id);
    if (!customer) {
      throw new Error('Customer not found');
    }
    
    // Attach to provider
    const provider = this.providers.get(params.payment_method.provider);
    if (!provider) {
      throw new Error(`Provider ${params.payment_method.provider} not available`);
    }
    
    const providerCustomerId = customer.provider_customers[params.payment_method.provider]?.id;
    if (!providerCustomerId) {
      throw new Error(`Customer not registered with ${params.payment_method.provider}`);
    }
    
    await provider.attachPaymentMethod(providerCustomerId, params.payment_method.id);
    
    // Store payment method
    await this.redis.hset(
      `payment_methods:${params.customer_id}`,
      params.payment_method.id,
      params.payment_method
    );
    
    // Set as default if requested or if it's the first method
    if (params.set_default || !customer.default_payment_method) {
      customer.default_payment_method = params.payment_method;
      await this.storeCustomer(customer);
    }
    
    return params.payment_method;
  }
  
  // Refund Management
  async createRefund(request: RefundRequest): Promise<{
    id: string;
    status: string;
    amount: number;
    currency: Currency;
  }> {
    const intent = await this.getPaymentIntent(request.payment_intent_id);
    if (!intent) {
      throw new Error('Payment intent not found');
    }
    
    if (intent.status !== 'succeeded') {
      throw new Error('Can only refund successful payments');
    }
    
    const provider = this.providers.get(intent.provider);
    if (!provider) {
      throw new Error(`Provider ${intent.provider} not available`);
    }
    
    const refund = await provider.createRefund(request);
    
    // Update payment intent status
    intent.status = request.amount && request.amount < intent.amount ? 'succeeded' : 'refunded';
    await this.storePaymentIntent(intent);
    
    // Emit event
    this.emit('refund_created', {
      refund_id: refund.id,
      payment_intent_id: request.payment_intent_id,
      amount: request.amount || intent.amount,
      provider: intent.provider,
      timestamp: new Date()
    });
    
    return {
      id: refund.id,
      status: refund.status,
      amount: request.amount || intent.amount,
      currency: intent.currency
    };
  }
  
  // Webhook Processing
  async handleWebhook(
    provider: PaymentProvider,
    payload: string,
    signature: string
  ): Promise<void> {
    const providerInterface = this.providers.get(provider);
    if (!providerInterface) {
      throw new Error(`Provider ${provider} not configured`);
    }
    
    // Validate signature
    if (!providerInterface.validateWebhookSignature(payload, signature)) {
      throw new Error('Invalid webhook signature');
    }
    
    // Parse and process event
    const event = JSON.parse(payload);
    await providerInterface.processWebhookEvent(event);
    
    // Handle common events
    await this.processCommonWebhookEvents(provider, event);
  }
  
  private async processCommonWebhookEvents(
    provider: PaymentProvider,
    event: any
  ): Promise<void> {
    switch (event.type) {
      case 'payment_intent.succeeded':
      case 'charge.succeeded':
      case 'order.paid':
        await this.handlePaymentSuccess(provider, event.data);
        break;
        
      case 'payment_intent.payment_failed':
      case 'charge.failed':
      case 'order.payment_failed':
        await this.handlePaymentFailure(provider, event.data);
        break;
        
      case 'checkout.session.completed':
        await this.handleCheckoutComplete(provider, event.data);
        break;
        
      case 'customer.subscription.created':
      case 'subscription.created':
        await this.handleSubscriptionCreated(provider, event.data);
        break;
        
      case 'customer.subscription.deleted':
      case 'subscription.canceled':
        await this.handleSubscriptionCanceled(provider, event.data);
        break;
    }
  }
  
  // Compliance & Tax Handling
  private requiresMerchantOfRecord(country: string, amount: number): boolean {
    // EU VAT requirements
    const euCountries = ['AT', 'BE', 'BG', 'HR', 'CY', 'CZ', 'DK', 'EE', 'FI', 'FR', 'DE',
                         'GR', 'HU', 'IE', 'IT', 'LV', 'LT', 'LU', 'MT', 'NL', 'PL', 'PT',
                         'RO', 'SK', 'SI', 'ES', 'SE'];
    if (euCountries.includes(country)) {
      return true; // Always use MoR for EU VAT compliance
    }
    
    // High-risk countries requiring MoR
    const highRiskCountries = ['IN', 'CN', 'RU', 'TR', 'SA', 'AE', 'EG', 'NG', 'ZA'];
    if (highRiskCountries.includes(country)) {
      return true;
    }
    
    // Use MoR for high-value transactions
    if (amount > 10000) { // $10,000 USD equivalent
      return true;
    }
    
    return false;
  }
  
  private determineRequiredProviders(country: string): PaymentProvider[] {
    const providers: PaymentProvider[] = [];
    
    // Mexico and Latin America
    if (country === 'MX' || ['AR', 'BR', 'CL', 'CO', 'PE'].includes(country)) {
      providers.push('conekta');
    }
    
    // International requiring MoR
    if (this.requiresMerchantOfRecord(country, 0)) {
      providers.push('fungies');
    }
    
    // Always include Stripe as fallback
    providers.push('stripe');
    
    return providers;
  }
  
  private getDefaultLocale(country: string): string {
    const locales: Record<string, string> = {
      'MX': 'es_MX',
      'ES': 'es_ES',
      'AR': 'es_AR',
      'BR': 'pt_BR',
      'FR': 'fr_FR',
      'DE': 'de_DE',
      'IT': 'it_IT',
      'JP': 'ja_JP',
      'KR': 'ko_KR',
      'CN': 'zh_CN',
      'IN': 'hi_IN',
      'US': 'en_US',
      'GB': 'en_GB',
      'CA': 'en_CA',
      'AU': 'en_AU'
    };
    
    return locales[country] || 'en_US';
  }
  
  // Storage Methods
  private async storeCustomer(customer: Customer): Promise<void> {
    await this.redis.hset('payment_customers', customer.id, customer);
    await this.redis.hset('payment_customers_by_email', customer.email, customer.id);
    this.customerCache.set(customer.id, customer);
  }
  
  private async getCustomer(customerId: string): Promise<Customer | null> {
    if (this.customerCache.has(customerId)) {
      return this.customerCache.get(customerId)!;
    }
    
    const customer = await this.redis.hget<Customer>('payment_customers', customerId);
    if (customer) {
      this.customerCache.set(customerId, customer);
    }
    
    return customer;
  }
  
  private async getCustomerByEmail(email: string): Promise<Customer | null> {
    const customerId = await this.redis.hget<string>('payment_customers_by_email', email);
    if (!customerId) return null;
    
    return this.getCustomer(customerId);
  }
  
  private async storePaymentIntent(intent: PaymentIntent): Promise<void> {
    await this.redis.hset('payment_intents', intent.id, intent);
  }
  
  private async getPaymentIntent(intentId: string): Promise<PaymentIntent | null> {
    return await this.redis.hget<PaymentIntent>('payment_intents', intentId);
  }
  
  private async storeCheckoutSession(session: CheckoutSession): Promise<void> {
    await this.redis.hset('checkout_sessions', session.id, session);
    await this.redis.expire(`checkout_sessions:${session.id}`, 86400); // 24 hours
  }
  
  // Provider Initialization
  private async initializeProviders(): Promise<void> {
    // Initialize Conekta
    if (process.env.CONEKTA_PRIVATE_KEY) {
      const conekta = new ConektaProvider({
        privateKey: process.env.CONEKTA_PRIVATE_KEY,
        publicKey: process.env.CONEKTA_PUBLIC_KEY,
        webhookSecret: process.env.CONEKTA_WEBHOOK_SECRET
      });
      this.providers.set('conekta', conekta);
    }
    
    // Initialize Fungies.io
    if (process.env.FUNGIES_API_KEY) {
      const fungies = new FungiesProvider({
        apiKey: process.env.FUNGIES_API_KEY,
        merchantId: process.env.FUNGIES_MERCHANT_ID,
        webhookSecret: process.env.FUNGIES_WEBHOOK_SECRET
      });
      this.providers.set('fungies', fungies);
    }
    
    // Initialize Stripe as fallback
    if (process.env.STRIPE_SECRET_KEY) {
      const stripe = new StripeProvider({
        secretKey: process.env.STRIPE_SECRET_KEY,
        publishableKey: process.env.STRIPE_PUBLISHABLE_KEY,
        webhookSecret: process.env.STRIPE_WEBHOOK_SECRET
      });
      this.providers.set('stripe', stripe);
    }
  }
  
  private setupRoutingRules(): void {
    // Mexico routing
    this.routingRules.set('MX:MXN', 'conekta');
    this.routingRules.set('MX:USD', 'conekta');
    
    // Latin America routing
    ['AR', 'BR', 'CL', 'CO', 'PE'].forEach(country => {
      this.routingRules.set(`${country}:local`, 'conekta');
      this.routingRules.set(`${country}:USD`, 'fungies');
    });
    
    // EU routing (MoR required)
    const euCountries = ['AT', 'BE', 'BG', 'HR', 'CY', 'CZ', 'DK', 'EE', 'FI', 'FR', 'DE',
                         'GR', 'HU', 'IE', 'IT', 'LV', 'LT', 'LU', 'MT', 'NL', 'PL', 'PT',
                         'RO', 'SK', 'SI', 'ES', 'SE'];
    euCountries.forEach(country => {
      this.routingRules.set(`${country}:EUR`, 'fungies');
      this.routingRules.set(`${country}:USD`, 'fungies');
    });
    
    // Default routing
    this.routingRules.set('default', 'stripe');
  }
  
  // Event Handlers
  private async handlePaymentSuccess(provider: PaymentProvider, data: any): Promise<void> {
    this.emit('payment_succeeded', {
      provider,
      payment_id: data.id,
      amount: data.amount,
      currency: data.currency,
      timestamp: new Date()
    });
  }
  
  private async handlePaymentFailure(provider: PaymentProvider, data: any): Promise<void> {
    this.emit('payment_failed', {
      provider,
      payment_id: data.id,
      error: data.failure_message || data.error,
      timestamp: new Date()
    });
  }
  
  private async handleCheckoutComplete(provider: PaymentProvider, data: any): Promise<void> {
    this.emit('checkout_completed', {
      provider,
      session_id: data.id,
      payment_status: data.payment_status,
      timestamp: new Date()
    });
  }
  
  private async handleSubscriptionCreated(provider: PaymentProvider, data: any): Promise<void> {
    this.emit('subscription_created', {
      provider,
      subscription_id: data.id,
      customer_id: data.customer,
      timestamp: new Date()
    });
  }
  
  private async handleSubscriptionCanceled(provider: PaymentProvider, data: any): Promise<void> {
    this.emit('subscription_canceled', {
      provider,
      subscription_id: data.id,
      customer_id: data.customer,
      timestamp: new Date()
    });
  }
  
  // ID Generation
  private generateCustomerId(): string {
    return `cus_${Date.now()}_${Math.random().toString(36).substring(2, 9)}`;
  }
}

// Placeholder provider implementations (would be in separate files)
class ConektaProvider implements PaymentProviderInterface {
  name: PaymentProvider = 'conekta';
  private config: any;
  
  constructor(config: any) {
    this.config = config;
  }
  
  // Implementation would go here...
  async createCustomer(customer: Partial<Customer>): Promise<string> {
    // Conekta API integration
    return `conekta_cus_${Math.random().toString(36).substring(2)}`;
  }
  
  async updateCustomer(customerId: string, updates: Partial<Customer>): Promise<void> {}
  async deleteCustomer(customerId: string): Promise<void> {}
  async attachPaymentMethod(customerId: string, paymentMethodId: string): Promise<void> {}
  async detachPaymentMethod(paymentMethodId: string): Promise<void> {}
  async listPaymentMethods(customerId: string): Promise<PaymentMethod[]> { return []; }
  
  async createPaymentIntent(params: any): Promise<PaymentIntent> {
    return {
      id: `pi_${Math.random().toString(36).substring(2)}`,
      provider: 'conekta',
      amount: params.amount,
      currency: params.currency,
      status: 'pending',
      customer_id: params.customer_id,
      organization_id: params.metadata?.organization_id,
      created_at: new Date(),
      updated_at: new Date()
    };
  }
  
  async confirmPayment(intentId: string): Promise<PaymentIntent> {
    throw new Error('Not implemented');
  }
  
  async cancelPayment(intentId: string): Promise<PaymentIntent> {
    throw new Error('Not implemented');
  }
  
  async createCheckoutSession(params: any): Promise<CheckoutSession> {
    return {
      id: `cs_${Math.random().toString(36).substring(2)}`,
      provider: 'conekta',
      amount: params.line_items.reduce((sum: number, item: any) => sum + item.amount * item.quantity, 0),
      currency: params.line_items[0].currency,
      customer_id: params.customer_id,
      success_url: params.success_url,
      cancel_url: params.cancel_url,
      line_items: params.line_items,
      status: 'open',
      expires_at: new Date(Date.now() + 24 * 60 * 60 * 1000),
      created_at: new Date()
    };
  }
  
  async createRefund(request: RefundRequest): Promise<{ id: string; status: string }> {
    return { id: `ref_${Math.random().toString(36).substring(2)}`, status: 'pending' };
  }
  
  validateWebhookSignature(payload: string, signature: string): boolean {
    return true; // Implement actual validation
  }
  
  async processWebhookEvent(event: any): Promise<void> {}
  
  isAvailable(country: string, currency: Currency): boolean {
    // Conekta supports Mexico and Latin America
    const supportedCountries = ['MX', 'AR', 'BR', 'CL', 'CO', 'PE', 'CR', 'GT', 'PA'];
    const supportedCurrencies: Currency[] = ['MXN', 'USD', 'BRL', 'ARS', 'COP', 'CLP', 'PEN'];
    
    return supportedCountries.includes(country) && supportedCurrencies.includes(currency);
  }
  
  getSupportedPaymentMethods(country: string): string[] {
    const methods = ['card'];
    
    if (country === 'MX') {
      methods.push('oxxo', 'spei', 'bank_transfer');
    } else if (country === 'BR') {
      methods.push('boleto', 'pix');
    } else if (country === 'AR') {
      methods.push('rapipago', 'pagofacil');
    }
    
    return methods;
  }
  
  getComplianceRequirements(check: ComplianceCheck): string[] {
    const requirements: string[] = [];
    
    if (check.country === 'MX' && check.customer_type === 'business') {
      requirements.push('rfc');
    }
    
    if (check.amount > 10000) {
      requirements.push('identity_verification');
    }
    
    return requirements;
  }
}

class FungiesProvider implements PaymentProviderInterface {
  name: PaymentProvider = 'fungies';
  private config: any;
  
  constructor(config: any) {
    this.config = config;
  }
  
  // Similar implementation structure...
  async createCustomer(customer: Partial<Customer>): Promise<string> {
    return `fungies_cus_${Math.random().toString(36).substring(2)}`;
  }
  
  // ... other methods implemented similarly
  
  isAvailable(country: string, currency: Currency): boolean {
    // Fungies.io operates globally as MoR
    const unsupportedCountries = ['IR', 'KP', 'SY', 'CU', 'SD']; // Sanctioned countries
    return !unsupportedCountries.includes(country);
  }
  
  getSupportedPaymentMethods(country: string): string[] {
    return ['card', 'paypal', 'crypto', 'wire'];
  }
  
  getComplianceRequirements(check: ComplianceCheck): string[] {
    const requirements: string[] = [];
    
    // VAT requirements for EU
    if (['AT', 'BE', 'BG', 'HR', 'CY', 'CZ', 'DK', 'EE', 'FI', 'FR', 'DE'].includes(check.country)) {
      requirements.push('vat_number');
    }
    
    // KYC for high amounts
    if (check.amount > 5000) {
      requirements.push('kyc_verification');
    }
    
    return requirements;
  }
  
  async updateCustomer(customerId: string, updates: Partial<Customer>): Promise<void> {}
  async deleteCustomer(customerId: string): Promise<void> {}
  async attachPaymentMethod(customerId: string, paymentMethodId: string): Promise<void> {}
  async detachPaymentMethod(paymentMethodId: string): Promise<void> {}
  async listPaymentMethods(customerId: string): Promise<PaymentMethod[]> { return []; }
  async createPaymentIntent(params: any): Promise<PaymentIntent> {
    throw new Error('Not implemented');
  }
  async confirmPayment(intentId: string): Promise<PaymentIntent> {
    throw new Error('Not implemented');
  }
  async cancelPayment(intentId: string): Promise<PaymentIntent> {
    throw new Error('Not implemented');
  }
  async createCheckoutSession(params: any): Promise<CheckoutSession> {
    throw new Error('Not implemented');
  }
  async createRefund(request: RefundRequest): Promise<{ id: string; status: string }> {
    throw new Error('Not implemented');
  }
  validateWebhookSignature(payload: string, signature: string): boolean {
    return true;
  }
  async processWebhookEvent(event: any): Promise<void> {}
}

class StripeProvider implements PaymentProviderInterface {
  name: PaymentProvider = 'stripe';
  private config: any;
  
  constructor(config: any) {
    this.config = config;
  }
  
  // Similar implementation structure...
  async createCustomer(customer: Partial<Customer>): Promise<string> {
    return `stripe_cus_${Math.random().toString(36).substring(2)}`;
  }
  
  // ... other methods
  
  isAvailable(country: string, currency: Currency): boolean {
    // Stripe is available almost globally
    const unsupportedCountries = ['IR', 'KP', 'SY', 'CU'];
    return !unsupportedCountries.includes(country);
  }
  
  getSupportedPaymentMethods(country: string): string[] {
    const methods = ['card'];
    
    // Add region-specific methods
    if (['US', 'CA'].includes(country)) {
      methods.push('ach_debit');
    }
    if (['GB', 'EU'].includes(country)) {
      methods.push('sepa_debit');
    }
    if (country === 'JP') {
      methods.push('konbini');
    }
    
    return methods;
  }
  
  getComplianceRequirements(check: ComplianceCheck): string[] {
    return []; // Stripe handles compliance internally
  }
  
  async updateCustomer(customerId: string, updates: Partial<Customer>): Promise<void> {}
  async deleteCustomer(customerId: string): Promise<void> {}
  async attachPaymentMethod(customerId: string, paymentMethodId: string): Promise<void> {}
  async detachPaymentMethod(paymentMethodId: string): Promise<void> {}
  async listPaymentMethods(customerId: string): Promise<PaymentMethod[]> { return []; }
  async createPaymentIntent(params: any): Promise<PaymentIntent> {
    throw new Error('Not implemented');
  }
  async confirmPayment(intentId: string): Promise<PaymentIntent> {
    throw new Error('Not implemented');
  }
  async cancelPayment(intentId: string): Promise<PaymentIntent> {
    throw new Error('Not implemented');
  }
  async createCheckoutSession(params: any): Promise<CheckoutSession> {
    throw new Error('Not implemented');
  }
  async createRefund(request: RefundRequest): Promise<{ id: string; status: string }> {
    throw new Error('Not implemented');
  }
  validateWebhookSignature(payload: string, signature: string): boolean {
    return true;
  }
  async processWebhookEvent(event: any): Promise<void> {}
}

// Export singleton
let paymentGatewayService: PaymentGatewayService | null = null;

export function getPaymentGatewayService(): PaymentGatewayService {
  if (!paymentGatewayService) {
    paymentGatewayService = new PaymentGatewayService();
  }
  return paymentGatewayService;
}