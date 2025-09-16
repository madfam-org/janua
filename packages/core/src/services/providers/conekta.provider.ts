import axios, { AxiosInstance } from 'axios';
import crypto from 'crypto';
import {
  PaymentProvider,
  PaymentStatus,
  Currency,
  PaymentMethod,
  PaymentIntent,
  Customer,
  CheckoutSession,
  LineItem,
  RefundRequest,
  ComplianceCheck,
  PaymentProviderInterface
} from '../payment-gateway.service';

interface ConektaConfig {
  privateKey: string;
  publicKey?: string;
  webhookSecret?: string;
  locale?: string;
  sandbox?: boolean;
}

interface ConektaCustomer {
  id: string;
  name: string;
  email: string;
  phone?: string;
  corporate?: boolean;
  payment_sources?: ConektaPaymentSource[];
  shipping_contacts?: ConektaShippingContact[];
  fiscal_entities?: ConektaFiscalEntity[];
  metadata?: Record<string, any>;
  created_at: number;
}

interface ConektaPaymentSource {
  id: string;
  type: string;
  created_at: number;
  last4?: string;
  brand?: string;
  exp_month?: string;
  exp_year?: string;
  name?: string;
}

interface ConektaShippingContact {
  id: string;
  phone?: string;
  receiver?: string;
  between_streets?: string;
  address: {
    street1: string;
    street2?: string;
    city: string;
    state?: string;
    postal_code: string;
    country: string;
  };
}

interface ConektaFiscalEntity {
  id: string;
  tax_id: string;
  name?: string;
  email?: string;
  phone?: string;
  address: {
    street1: string;
    street2?: string;
    city: string;
    state?: string;
    postal_code: string;
    country: string;
  };
}

interface ConektaOrder {
  id: string;
  amount: number;
  currency: string;
  payment_status: string;
  customer_info: {
    customer_id?: string;
    name: string;
    email: string;
    phone?: string;
  };
  line_items: ConektaLineItem[];
  charges?: ConektaCharge[];
  checkout?: {
    id: string;
    url: string;
    expires_at: number;
  };
  metadata?: Record<string, any>;
  created_at: number;
  updated_at: number;
}

interface ConektaLineItem {
  name: string;
  unit_price: number;
  quantity: number;
  description?: string;
  sku?: string;
  category?: string;
  brand?: string;
  metadata?: Record<string, any>;
}

interface ConektaCharge {
  id: string;
  status: string;
  amount: number;
  currency: string;
  payment_method: {
    type: string;
    reference?: string;
    barcode_url?: string;
    service_name?: string;
    store_name?: string;
  };
  created_at: number;
}

interface ConektaCheckout {
  id: string;
  name: string;
  slug: string;
  expires_at: number;
  type: 'Integration' | 'HostedPayment' | 'PaymentLink';
  allowed_payment_methods?: string[];
  monthly_installments_enabled?: boolean;
  monthly_installments_options?: number[];
  on_demand_enabled?: boolean;
  success_url?: string;
  failure_url?: string;
  cancel_url?: string;
  metadata?: Record<string, any>;
}

export class ConektaProvider implements PaymentProviderInterface {
  name: PaymentProvider = 'conekta';
  private client: AxiosInstance;
  private config: ConektaConfig;
  
  constructor(config: ConektaConfig) {
    this.config = config;
    
    // Initialize Conekta API client
    this.client = axios.create({
      baseURL: config.sandbox ? 'https://api.conekta.io' : 'https://api.conekta.io',
      headers: {
        'Accept': 'application/vnd.conekta-v2.1.0+json',
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${config.privateKey}`,
        'Accept-Language': config.locale || 'es'
      }
    });
  }
  
  // Customer Management
  async createCustomer(customer: Partial<Customer>): Promise<string> {
    try {
      const conektaCustomer: any = {
        name: customer.name,
        email: customer.email,
        phone: customer.phone,
        metadata: customer.metadata
      };
      
      // Add shipping contact if address provided
      if (customer.address) {
        conektaCustomer.shipping_contacts = [{
          receiver: customer.name,
          phone: customer.phone,
          address: {
            street1: customer.address.line1,
            street2: customer.address.line2,
            city: customer.address.city,
            state: customer.address.state,
            postal_code: customer.address.postal_code,
            country: customer.address.country
          }
        }];
      }
      
      // Add fiscal entity for Mexican businesses
      if (customer.tax_info && customer.tax_info.type === 'rfc') {
        conektaCustomer.fiscal_entities = [{
          tax_id: customer.tax_info.id,
          name: customer.tax_info.name,
          address: customer.tax_info.address ? {
            street1: customer.tax_info.address.line1,
            street2: customer.tax_info.address.line2,
            city: customer.tax_info.address.city,
            state: customer.tax_info.address.state,
            postal_code: customer.tax_info.address.postal_code,
            country: customer.tax_info.address.country
          } : undefined
        }];
        conektaCustomer.corporate = true;
      }
      
      const response = await this.client.post('/customers', conektaCustomer);
      return response.data.id;
    } catch (error: any) {
      throw this.handleConektaError(error);
    }
  }
  
  async updateCustomer(customerId: string, updates: Partial<Customer>): Promise<void> {
    try {
      const conektaUpdates: any = {};
      
      if (updates.name) conektaUpdates.name = updates.name;
      if (updates.email) conektaUpdates.email = updates.email;
      if (updates.phone) conektaUpdates.phone = updates.phone;
      if (updates.metadata) conektaUpdates.metadata = updates.metadata;
      
      await this.client.put(`/customers/${customerId}`, conektaUpdates);
    } catch (error: any) {
      throw this.handleConektaError(error);
    }
  }
  
  async deleteCustomer(customerId: string): Promise<void> {
    try {
      await this.client.delete(`/customers/${customerId}`);
    } catch (error: any) {
      throw this.handleConektaError(error);
    }
  }
  
  // Payment Methods
  async attachPaymentMethod(customerId: string, paymentMethodData: any): Promise<void> {
    try {
      const paymentSource = {
        type: 'card',
        token_id: paymentMethodData.token_id
      };
      
      await this.client.post(`/customers/${customerId}/payment_sources`, paymentSource);
    } catch (error: any) {
      throw this.handleConektaError(error);
    }
  }
  
  async detachPaymentMethod(paymentMethodId: string): Promise<void> {
    try {
      // In Conekta, we need the customer ID to delete a payment source
      // This would need to be tracked separately or passed as parameter
      throw new Error('Detaching payment method requires customer ID in Conekta');
    } catch (error: any) {
      throw this.handleConektaError(error);
    }
  }
  
  async listPaymentMethods(customerId: string): Promise<PaymentMethod[]> {
    try {
      const response = await this.client.get(`/customers/${customerId}`);
      const customer: ConektaCustomer = response.data;
      
      return (customer.payment_sources || []).map(source => ({
        id: source.id,
        provider: 'conekta' as PaymentProvider,
        type: source.type === 'card' ? 'card' : 'bank_transfer',
        details: {
          brand: source.brand,
          last4: source.last4,
          exp_month: source.exp_month ? parseInt(source.exp_month) : undefined,
          exp_year: source.exp_year ? parseInt(source.exp_year) : undefined
        },
        is_default: false,
        metadata: {}
      }));
    } catch (error: any) {
      throw this.handleConektaError(error);
    }
  }
  
  // Payments
  async createPaymentIntent(params: {
    amount: number;
    currency: Currency;
    customer_id: string;
    payment_method_id?: string;
    description?: string;
    metadata?: Record<string, any>;
  }): Promise<PaymentIntent> {
    try {
      // Conekta uses Orders instead of Payment Intents
      const order: any = {
        currency: params.currency.toLowerCase(),
        customer_info: {
          customer_id: params.customer_id
        },
        line_items: [{
          name: params.description || 'Payment',
          unit_price: params.amount,
          quantity: 1
        }],
        metadata: params.metadata
      };
      
      // Add payment method if provided
      if (params.payment_method_id) {
        order.charges = [{
          payment_method: {
            type: 'default'
          }
        }];
      }
      
      const response = await this.client.post('/orders', order);
      const conektaOrder: ConektaOrder = response.data;
      
      return {
        id: conektaOrder.id,
        provider: 'conekta',
        provider_intent_id: conektaOrder.id,
        amount: conektaOrder.amount,
        currency: conektaOrder.currency.toUpperCase() as Currency,
        status: this.mapConektaStatus(conektaOrder.payment_status),
        customer_id: params.customer_id,
        organization_id: params.metadata?.organization_id || '',
        description: params.description,
        metadata: params.metadata,
        created_at: new Date(conektaOrder.created_at * 1000),
        updated_at: new Date(conektaOrder.updated_at * 1000)
      };
    } catch (error: any) {
      throw this.handleConektaError(error);
    }
  }
  
  async confirmPayment(intentId: string): Promise<PaymentIntent> {
    try {
      // In Conekta, payments are confirmed through charges
      const response = await this.client.get(`/orders/${intentId}`);
      const order: ConektaOrder = response.data;
      
      return {
        id: order.id,
        provider: 'conekta',
        provider_intent_id: order.id,
        amount: order.amount,
        currency: order.currency.toUpperCase() as Currency,
        status: this.mapConektaStatus(order.payment_status),
        customer_id: order.customer_info.customer_id || '',
        organization_id: order.metadata?.organization_id || '',
        metadata: order.metadata,
        created_at: new Date(order.created_at * 1000),
        updated_at: new Date(order.updated_at * 1000)
      };
    } catch (error: any) {
      throw this.handleConektaError(error);
    }
  }
  
  async cancelPayment(intentId: string): Promise<PaymentIntent> {
    try {
      const response = await this.client.put(`/orders/${intentId}/cancel`);
      const order: ConektaOrder = response.data;
      
      return {
        id: order.id,
        provider: 'conekta',
        provider_intent_id: order.id,
        amount: order.amount,
        currency: order.currency.toUpperCase() as Currency,
        status: 'canceled',
        customer_id: order.customer_info.customer_id || '',
        organization_id: order.metadata?.organization_id || '',
        metadata: order.metadata,
        created_at: new Date(order.created_at * 1000),
        updated_at: new Date(order.updated_at * 1000)
      };
    } catch (error: any) {
      throw this.handleConektaError(error);
    }
  }
  
  // Checkout
  async createCheckoutSession(params: {
    customer_id: string;
    line_items: LineItem[];
    success_url: string;
    cancel_url: string;
    metadata?: Record<string, any>;
  }): Promise<CheckoutSession> {
    try {
      // Create an order with checkout
      const order: any = {
        currency: params.line_items[0].currency.toLowerCase(),
        customer_info: {
          customer_id: params.customer_id
        },
        line_items: params.line_items.map(item => ({
          name: item.name,
          unit_price: item.amount,
          quantity: item.quantity,
          description: item.description
        })),
        checkout: {
          type: 'HostedPayment',
          allowed_payment_methods: this.getAllowedPaymentMethods(params.line_items[0].currency),
          success_url: params.success_url,
          failure_url: params.cancel_url,
          monthly_installments_enabled: true,
          monthly_installments_options: [3, 6, 9, 12],
          expires_at: Math.floor((Date.now() + 24 * 60 * 60 * 1000) / 1000)
        },
        metadata: params.metadata
      };
      
      const response = await this.client.post('/orders', order);
      const conektaOrder: ConektaOrder = response.data;
      
      return {
        id: conektaOrder.checkout?.id || conektaOrder.id,
        provider: 'conekta',
        provider_session_id: conektaOrder.checkout?.id,
        amount: conektaOrder.amount,
        currency: conektaOrder.currency.toUpperCase() as Currency,
        customer_id: params.customer_id,
        success_url: params.success_url,
        cancel_url: params.cancel_url,
        line_items: params.line_items,
        status: 'open',
        expires_at: new Date((conektaOrder.checkout?.expires_at || 0) * 1000),
        metadata: params.metadata,
        created_at: new Date(conektaOrder.created_at * 1000)
      };
    } catch (error: any) {
      throw this.handleConektaError(error);
    }
  }
  
  // Refunds
  async createRefund(request: RefundRequest): Promise<{ id: string; status: string }> {
    try {
      const response = await this.client.post(`/orders/${request.payment_intent_id}/refunds`, {
        amount: request.amount,
        reason: request.reason || 'requested_by_customer',
        metadata: request.metadata
      });
      
      return {
        id: response.data.id,
        status: response.data.status
      };
    } catch (error: any) {
      throw this.handleConektaError(error);
    }
  }
  
  // Webhooks
  validateWebhookSignature(payload: string, signature: string): boolean {
    if (!this.config.webhookSecret) {
      console.warn('Conekta webhook secret not configured');
      return false;
    }
    
    const computedSignature = crypto
      .createHmac('sha256', this.config.webhookSecret)
      .update(payload)
      .digest('hex');
    
    return computedSignature === signature;
  }
  
  async processWebhookEvent(event: any): Promise<void> {
    // Process Conekta-specific webhook events
    switch (event.type) {
      case 'order.paid':
        // Handle successful payment
        break;
        
      case 'order.payment_failed':
        // Handle failed payment
        break;
        
      case 'charge.paid':
        // Handle charge payment
        break;
        
      case 'subscription.created':
        // Handle subscription creation
        break;
        
      case 'subscription.canceled':
        // Handle subscription cancellation
        break;
        
      case 'customer.created':
        // Handle customer creation
        break;
    }
  }
  
  // Utilities
  isAvailable(country: string, currency: Currency): boolean {
    // Conekta primarily supports Mexico and Latin America
    const supportedCountries = [
      'MX', // Mexico
      'AR', // Argentina
      'BR', // Brazil
      'CL', // Chile
      'CO', // Colombia
      'PE', // Peru
      'CR', // Costa Rica
      'GT', // Guatemala
      'PA', // Panama
      'EC', // Ecuador
      'UY', // Uruguay
      'PY', // Paraguay
      'BO', // Bolivia
      'HN', // Honduras
      'SV', // El Salvador
      'NI', // Nicaragua
      'DO'  // Dominican Republic
    ];
    
    const supportedCurrencies: Currency[] = [
      'MXN', // Mexican Peso
      'USD', // US Dollar
      'BRL', // Brazilian Real
      'ARS', // Argentine Peso
      'COP', // Colombian Peso
      'CLP', // Chilean Peso
      'PEN'  // Peruvian Sol
    ];
    
    return supportedCountries.includes(country) && supportedCurrencies.includes(currency);
  }
  
  getSupportedPaymentMethods(country: string): string[] {
    const methods = ['card']; // Credit/Debit cards available everywhere
    
    if (country === 'MX') {
      methods.push(
        'oxxo',         // OXXO Pay cash payments
        'spei',         // SPEI bank transfers
        'bank_transfer', // Bank transfers
        'paynet'        // PayNet cash payments
      );
    } else if (country === 'BR') {
      methods.push(
        'boleto',       // Boleto Bancário
        'pix'           // PIX instant payments
      );
    } else if (country === 'AR') {
      methods.push(
        'rapipago',     // Rapipago cash payments
        'pagofacil',    // PagoFácil cash payments
        'mercadopago'   // MercadoPago
      );
    } else if (country === 'CL') {
      methods.push(
        'servipag',     // Servipag
        'webpay'        // Webpay
      );
    } else if (country === 'CO') {
      methods.push(
        'efecty',       // Efecty cash payments
        'baloto',       // Baloto
        'pse'           // PSE bank transfers
      );
    } else if (country === 'PE') {
      methods.push(
        'pagoefectivo'  // PagoEfectivo
      );
    }
    
    return methods;
  }
  
  getComplianceRequirements(check: ComplianceCheck): string[] {
    const requirements: string[] = [];
    
    // RFC requirement for Mexican businesses
    if (check.country === 'MX' && check.customer_type === 'business') {
      requirements.push('rfc'); // Registro Federal de Contribuyentes
    }
    
    // CFDI for Mexican invoicing
    if (check.country === 'MX' && check.amount > 2000) {
      requirements.push('cfdi'); // Comprobante Fiscal Digital por Internet
    }
    
    // Identity verification for high amounts
    if (check.amount > 50000) { // ~$2,500 USD
      requirements.push('identity_verification');
      requirements.push('proof_of_address');
    }
    
    // Anti-money laundering checks
    if (check.amount > 100000) { // ~$5,000 USD
      requirements.push('aml_check');
      requirements.push('source_of_funds');
    }
    
    // Recurring payment authorization
    if (check.is_recurring) {
      requirements.push('recurring_authorization');
    }
    
    return requirements;
  }
  
  // Helper Methods
  private mapConektaStatus(status: string): PaymentStatus {
    const statusMap: Record<string, PaymentStatus> = {
      'pending_payment': 'pending',
      'paid': 'succeeded',
      'canceled': 'canceled',
      'expired': 'canceled',
      'refunded': 'refunded',
      'partially_refunded': 'succeeded',
      'charged_back': 'failed',
      'pre_authorized': 'processing',
      'declined': 'failed'
    };
    
    return statusMap[status] || 'pending';
  }
  
  private getAllowedPaymentMethods(currency: Currency): string[] {
    if (currency === 'MXN') {
      return ['card', 'oxxo_cash', 'spei', 'bank_transfer'];
    } else if (currency === 'BRL') {
      return ['card', 'boleto', 'pix'];
    } else {
      return ['card'];
    }
  }
  
  private handleConektaError(error: any): Error {
    if (error.response?.data) {
      const conektaError = error.response.data;
      return new Error(
        `Conekta Error: ${conektaError.details?.[0]?.message || conektaError.message || 'Unknown error'}`
      );
    }
    return error;
  }
  
  // Special Methods for Mexico
  async generateOXXOReference(orderId: string): Promise<{
    reference: string;
    barcode_url: string;
    expires_at: Date;
  }> {
    try {
      const response = await this.client.post(`/orders/${orderId}/charges`, {
        payment_method: {
          type: 'oxxo_cash'
        }
      });
      
      const charge = response.data;
      
      return {
        reference: charge.payment_method.reference,
        barcode_url: charge.payment_method.barcode_url,
        expires_at: new Date(charge.payment_method.expires_at * 1000)
      };
    } catch (error: any) {
      throw this.handleConektaError(error);
    }
  }
  
  async generateSPEIInstructions(orderId: string): Promise<{
    clabe: string;
    bank: string;
    reference: string;
    amount: number;
    expires_at: Date;
  }> {
    try {
      const response = await this.client.post(`/orders/${orderId}/charges`, {
        payment_method: {
          type: 'spei'
        }
      });
      
      const charge = response.data;
      
      return {
        clabe: charge.payment_method.clabe,
        bank: charge.payment_method.bank,
        reference: charge.payment_method.reference,
        amount: charge.amount,
        expires_at: new Date(charge.payment_method.expires_at * 1000)
      };
    } catch (error: any) {
      throw this.handleConektaError(error);
    }
  }
  
  // Monthly Installments (Meses Sin Intereses)
  async createInstallmentPayment(params: {
    order_id: string;
    payment_source_id: string;
    installments: 3 | 6 | 9 | 12 | 18;
  }): Promise<any> {
    try {
      const response = await this.client.post(`/orders/${params.order_id}/charges`, {
        payment_method: {
          type: 'card',
          payment_source_id: params.payment_source_id
        },
        monthly_installments: params.installments
      });
      
      return response.data;
    } catch (error: any) {
      throw this.handleConektaError(error);
    }
  }
}