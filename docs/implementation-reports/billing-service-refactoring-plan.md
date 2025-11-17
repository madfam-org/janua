# BillingService Refactoring Plan

**Status**: Planned - Not Yet Implemented  
**Priority**: High (Priority 1 candidate)  
**Estimated Effort**: 2-3 days  
**Risk Level**: Medium (revenue-critical functionality)

## Executive Summary

The `BillingService` (1,199 lines, 62 methods) severely violates the Single Responsibility Principle by handling subscriptions, invoices, payment methods, usage tracking, billing alerts, Stripe integration, and webhook processing in a single class.

This document outlines a systematic refactoring plan to split it into 4 focused services while maintaining backward compatibility and zero downtime.

---

## Current State Analysis

### File Statistics
- **Location**: `packages/core/src/services/billing.service.ts`
- **Lines of Code**: 1,199
- **Methods**: 62 (highest count in codebase)
- **Dependencies**: Redis, MultiTenancy, Stripe SDK, EventEmitter
- **External Coupling**: High (Stripe API, Redis storage, organization features)

### Method Categories (62 total)

#### Subscription Management (12 methods)
- `createSubscription()` - Create new subscription
- `updateSubscription()` - Modify existing subscription
- `cancelSubscription()` - Cancel subscription immediately or at period end
- `reactivateSubscription()` - Reactivate canceled subscription
- `getSubscription()` - Retrieve subscription by ID
- `getOrganizationSubscription()` - Get subscription for organization
- `createStripeSubscription()` - Stripe integration
- `updateStripeSubscription()` - Stripe integration
- `cancelStripeSubscription()` - Stripe integration
- `reactivateStripeSubscription()` - Stripe integration
- `handleSubscriptionUpdate()` - Webhook handler
- `handleSubscriptionDeleted()` - Webhook handler

#### Invoice Management (7 methods)
- `getInvoices()` - List all invoices for organization
- `getInvoice()` - Get specific invoice
- `downloadInvoice()` - Generate PDF download
- `getStripeInvoice()` - Stripe integration

#### Payment Method Management (5 methods)
- `addPaymentMethod()` - Attach payment method to customer
- `removePaymentMethod()` - Detach payment method
- `setDefaultPaymentMethod()` - Set default for billing
- `getPaymentMethods()` - List customer payment methods
- `attachStripePaymentMethod()` - Stripe integration
- `detachStripePaymentMethod()` - Stripe integration

#### Usage Tracking (5 methods)
- `recordUsage()` - Record usage metric
- `checkUsageLimits()` - Verify limits not exceeded
- `getUsageSummary()` - Aggregate usage data

#### Billing Alerts (4 methods)
- `createBillingAlert()` - Create new alert
- `acknowledgeAlert()` - Mark alert as seen
- `getAlerts()` - List alerts for organization
- `sendAlertNotification()` - Send notification

#### Plan Management (6 methods)
- `createPlan()` - Create billing plan
- `updatePlan()` - Modify plan
- `getPlan()` - Retrieve plan
- `getPlans()` - List all plans
- `initializePlans()` - Seed default plans
- `storePlan()` - Persist plan to Redis

#### Checkout (3 methods)
- `createCheckoutSession()` - Create Stripe checkout
- `createStripeCheckoutSession()` - Stripe integration
- `handleCheckoutComplete()` - Webhook handler

#### Webhook Processing (4 methods)
- `processWebhook()` - Main webhook router
- `handlePaymentSuccess()` - Payment webhook
- `handlePaymentFailure()` - Payment webhook
- `handleCheckoutComplete()` - Checkout webhook

#### Utility Methods (16 methods)
- `initializeStripe()` - Setup Stripe client
- `getOrCreateStripeCustomer()` - Customer management
- `updateStripeCustomer()` - Customer management
- `createStripeProduct()` - Product management
- `createStripePrice()` - Price management
- `calculatePeriodEnd()` - Date calculations
- `scheduleTrialEndReminder()` - Trial management
- `applyPlanFeatures()` - Feature provisioning
- `storeSubscription()` - Persistence
- `generateSubscriptionId()` - ID generation
- `generatePlanId()` - ID generation
- `generatePaymentMethodId()` - ID generation
- `generateUsageRecordId()` - ID generation
- `generateAlertId()` - ID generation
- `generateSessionId()` - ID generation

---

## Proposed Architecture

### Service Breakdown

#### 1. SubscriptionService (~400 lines, ~15 methods)
**Responsibility**: Subscription lifecycle management

**Methods**:
- `createSubscription(organizationId, planId, paymentMethodId?, trialDays?)`
- `updateSubscription(subscriptionId, updates)`
- `cancelSubscription(subscriptionId, immediately?, reason?)`
- `reactivateSubscription(subscriptionId)`
- `pauseSubscription(subscriptionId)`
- `resumeSubscription(subscriptionId)`
- `getSubscription(subscriptionId)`
- `getOrganizationSubscription(organizationId)`
- `listSubscriptions(filters?)`
- `calculatePeriodEnd(startDate, interval)`
- `scheduleTrialEndReminder(subscription)`
- `applyPlanFeatures(organizationId, plan)` - Move to PlanService

**Dependencies**:
- Redis (storage)
- PlanService (plan details)
- StripeIntegrationService (Stripe operations)
- MultiTenancyService (feature updates)
- EventEmitter (events)

**Events Emitted**:
- `subscription_created`
- `subscription_updated`
- `subscription_canceled`
- `subscription_reactivated`

#### 2. InvoiceService (~300 lines, ~10 methods)
**Responsibility**: Invoice generation and management

**Methods**:
- `getInvoices(organizationId, filters?)`
- `getInvoice(invoiceId)`
- `createInvoice(subscriptionId, lineItems)`
- `downloadInvoice(invoiceId)`
- `sendInvoice(invoiceId, email)`
- `voidInvoice(invoiceId)`
- `retryPayment(invoiceId)`
- `applyCredit(invoiceId, amount)`
- `generateInvoiceNumber()`
- `generateInvoicePDF(invoice)`

**Dependencies**:
- Redis (storage)
- StripeIntegrationService (Stripe invoices)
- EmailService (invoice delivery)
- PDFGeneratorService (PDF creation)

**Events Emitted**:
- `invoice_created`
- `invoice_paid`
- `invoice_failed`
- `invoice_voided`

#### 3. UsageTrackingService (~250 lines, ~8 methods)
**Responsibility**: Usage metering and limit enforcement

**Methods**:
- `recordUsage(organizationId, metric, quantity, metadata?)`
- `checkUsageLimits(organizationId, metric)`
- `getUsageSummary(organizationId, period?)`
- `getUsageReport(organizationId, startDate, endDate)`
- `resetUsage(organizationId, metric?)`
- `aggregateUsage(organizationId, metric, period)`
- `getUsageHistory(organizationId, metric)`
- `generateUsageRecordId()`

**Dependencies**:
- Redis (storage)
- SubscriptionService (plan limits)
- BillingAlertService (limit notifications)

**Events Emitted**:
- `usage_recorded`
- `usage_limit_approaching`
- `usage_limit_exceeded`

#### 4. BillingAlertService (~150 lines, ~6 methods)
**Responsibility**: Billing notifications and alerts

**Methods**:
- `createBillingAlert(organizationId, type, severity, message, details?)`
- `acknowledgeAlert(alertId, userId)`
- `getAlerts(organizationId, filters?)`
- `updateAlert(alertId, updates)`
- `sendAlertNotification(alert)`
- `generateAlertId()`

**Dependencies**:
- Redis (storage)
- EmailService (notifications)
- WebhookService (external notifications)

**Alert Types**:
- `usage_limit` - Usage approaching/exceeding limits
- `payment_failed` - Payment processing failure
- `subscription_ending` - Subscription cancellation scheduled
- `trial_ending` - Trial period expiring soon

**Events Emitted**:
- `alert_created`
- `alert_acknowledged`

#### 5. PaymentMethodService (~200 lines, ~8 methods)
**Responsibility**: Payment method management

**Methods**:
- `addPaymentMethod(customerId, paymentMethod)`
- `removePaymentMethod(paymentMethodId)`
- `setDefaultPaymentMethod(customerId, paymentMethodId)`
- `getPaymentMethods(customerId)`
- `updatePaymentMethod(paymentMethodId, updates)`
- `verifyPaymentMethod(paymentMethodId)`
- `generatePaymentMethodId()`

**Dependencies**:
- Redis (storage)
- StripeIntegrationService (Stripe payment methods)

**Events Emitted**:
- `payment_method_added`
- `payment_method_removed`
- `payment_method_updated`

#### 6. PlanService (~200 lines, ~10 methods)
**Responsibility**: Billing plan management

**Methods**:
- `createPlan(planData)`
- `updatePlan(planId, updates)`
- `getPlan(planId)`
- `getPlans(filters?)`
- `archivePlan(planId)`
- `initializePlans()` - Seed defaults
- `storePlan(plan)`
- `generatePlanId()`
- `validatePlanFeatures(features)`

**Dependencies**:
- Redis (storage)
- StripeIntegrationService (Stripe products/prices)

**Events Emitted**:
- `plan_created`
- `plan_updated`
- `plan_archived`

#### 7. StripeIntegrationService (~250 lines, ~15 methods)
**Responsibility**: Stripe API integration and webhook handling

**Methods**:
- `initializeStripe()`
- `getOrCreateCustomer(organizationId, email, name)`
- `updateCustomer(customerId, updates)`
- `createProduct(name, description, metadata?)`
- `createPrice(productId, amount, currency, interval)`
- `createSubscription(customerId, priceId, paymentMethodId?, trialDays?)`
- `updateSubscription(subscriptionId, updates)`
- `cancelSubscription(subscriptionId, immediately)`
- `reactivateSubscription(subscriptionId)`
- `attachPaymentMethod(customerId, paymentMethodId)`
- `detachPaymentMethod(paymentMethodId)`
- `getInvoice(invoiceId)`
- `createCheckoutSession(params)`
- `processWebhook(payload, signature)`
- `validateWebhookSignature(payload, signature)`

**Webhook Handlers**:
- `handlePaymentSuccess(event)`
- `handlePaymentFailure(event)`
- `handleSubscriptionUpdate(event)`
- `handleSubscriptionDeleted(event)`
- `handleCheckoutComplete(event)`

**Dependencies**:
- Stripe SDK
- SubscriptionService (sync subscriptions)
- InvoiceService (sync invoices)
- PaymentMethodService (sync methods)

**Events Emitted**:
- `stripe_webhook_received`
- `stripe_webhook_processed`
- `stripe_webhook_failed`

#### 8. BillingService (Orchestrator) (~150 lines, ~8 methods)
**Responsibility**: Coordinate billing operations, provide unified API

**Methods**:
- `constructor()` - Initialize all services
- `createSubscriptionWithCheckout(organizationId, planId)` - Orchestration
- `processWebhook(provider, payload, signature)` - Route to appropriate service
- `getBillingOverview(organizationId)` - Aggregate data
- `handleOrganizationDeleted(organizationId)` - Cleanup
- `validateBillingSetup(organizationId)` - Health check

**Dependencies**:
- All billing services (injected)
- EventEmitter (orchestration events)

---

## Dependency Graph

```
BillingService (Orchestrator)
├─→ SubscriptionService
│   ├─→ PlanService
│   ├─→ StripeIntegrationService
│   └─→ MultiTenancyService
├─→ InvoiceService
│   ├─→ StripeIntegrationService
│   └─→ EmailService
├─→ UsageTrackingService
│   ├─→ SubscriptionService (plan limits)
│   └─→ BillingAlertService
├─→ BillingAlertService
│   └─→ EmailService
├─→ PaymentMethodService
│   └─→ StripeIntegrationService
├─→ PlanService
│   └─→ StripeIntegrationService
└─→ StripeIntegrationService
    ├─→ SubscriptionService
    ├─→ InvoiceService
    └─→ PaymentMethodService
```

---

## Implementation Plan

### Phase 1: Foundation (Day 1)
**Goal**: Create infrastructure and least-coupled service

#### Tasks:
1. **Create shared types file**: `types/billing.types.ts`
   - Move all interfaces (BillingPlan, Subscription, Invoice, etc.)
   - Export common types for all services

2. **Create StripeIntegrationService**: `services/stripe-integration.service.ts`
   - Extract all Stripe-specific methods
   - Implement webhook routing
   - Test Stripe connectivity

3. **Create PlanService**: `services/plan.service.ts`
   - Extract plan management methods
   - Migrate plan storage
   - Test plan operations

4. **Testing**:
   - Unit tests for StripeIntegrationService
   - Unit tests for PlanService
   - Verify existing functionality unaffected

### Phase 2: Core Services (Day 2)
**Goal**: Extract primary business logic services

#### Tasks:
1. **Create InvoiceService**: `services/invoice.service.ts`
   - Extract invoice methods
   - Integrate with StripeIntegrationService
   - Test invoice operations

2. **Create PaymentMethodService**: `services/payment-method.service.ts`
   - Extract payment method methods
   - Integrate with StripeIntegrationService
   - Test payment method operations

3. **Create BillingAlertService**: `services/billing-alert.service.ts`
   - Extract alert methods
   - Test alert notifications

4. **Testing**:
   - Integration tests for invoice workflows
   - Integration tests for payment method workflows
   - Integration tests for alert workflows

### Phase 3: Complex Services (Day 3)
**Goal**: Extract remaining services and create orchestrator

#### Tasks:
1. **Create UsageTrackingService**: `services/usage-tracking.service.ts`
   - Extract usage methods
   - Integrate with SubscriptionService
   - Test usage limits

2. **Create SubscriptionService**: `services/subscription.service.ts`
   - Extract subscription methods (most complex)
   - Integrate with all other services
   - Test subscription lifecycle

3. **Refactor BillingService to Orchestrator**:
   - Keep only coordination methods
   - Inject all services
   - Maintain backward-compatible API

4. **Migration**:
   - Update all imports to use new services
   - Update tests to use new service architecture
   - Update documentation

5. **Testing**:
   - End-to-end tests for complete workflows
   - Integration tests across all services
   - Regression tests for existing functionality
   - Load testing for performance validation

---

## Migration Strategy

### Backward Compatibility Approach

**Option 1: Facade Pattern** (Recommended)
```typescript
// Old code continues to work:
import { BillingService } from './billing.service';
const billing = new BillingService();
await billing.createSubscription(orgId, planId);

// New code uses specific services:
import { SubscriptionService } from './subscription.service';
const subscriptions = new SubscriptionService();
await subscriptions.createSubscription(orgId, planId);
```

BillingService becomes a facade that delegates to appropriate services.

**Option 2: Immediate Migration**
- Update all imports simultaneously
- Higher risk but cleaner outcome
- Requires comprehensive test coverage

**Recommendation**: Use Option 1 for safe, incremental migration.

### Data Migration
- No data migration required (Redis keys remain unchanged)
- Storage format remains compatible
- Only code structure changes

### Testing Strategy
1. **Before Refactoring**: Run full test suite, record baseline
2. **During Refactoring**: Test each service independently
3. **After Refactoring**: 
   - Run full test suite again
   - Compare results to baseline
   - Add integration tests for new service boundaries
   - Perform manual testing of critical paths

---

## Risks and Mitigation

### Risk 1: Breaking Changes
**Severity**: High  
**Impact**: Existing code stops working  
**Mitigation**:
- Maintain facade pattern for backward compatibility
- Comprehensive test coverage before refactoring
- Feature flag for gradual rollout
- Automated regression testing

### Risk 2: Stripe Integration Issues
**Severity**: High (revenue-critical)  
**Impact**: Payment processing failures  
**Mitigation**:
- Test against Stripe test environment
- Validate webhook processing thoroughly
- Monitor Stripe events during rollout
- Have rollback plan ready

### Risk 3: Service Communication Overhead
**Severity**: Medium  
**Impact**: Performance degradation  
**Mitigation**:
- Profile performance before and after
- Optimize service boundaries to minimize cross-service calls
- Use caching where appropriate
- Consider event-driven patterns for loose coupling

### Risk 4: Circular Dependencies
**Severity**: Medium  
**Impact**: Dependency injection complexity  
**Mitigation**:
- Clear dependency graph (see above)
- Use dependency injection container
- Apply dependency inversion principle
- Careful design of service boundaries

---

## Success Metrics

### Code Quality
- ✅ No file >400 lines
- ✅ No service >20 methods
- ✅ Each service has single, clear responsibility
- ✅ Reduced cyclomatic complexity

### Testing
- ✅ 100% test coverage maintained or improved
- ✅ All existing tests pass
- ✅ New integration tests added for service boundaries

### Performance
- ✅ No degradation in response times
- ✅ No increase in database/Redis queries
- ✅ Memory usage stable or improved

### Maintainability
- ✅ New developers can find code faster
- ✅ Bug fixes isolated to single service
- ✅ Feature additions require fewer file changes
- ✅ Reduced cognitive load for developers

---

## Implementation Checklist

### Pre-Implementation
- [ ] Review refactoring plan with team
- [ ] Get approval for 3-day development window
- [ ] Ensure comprehensive test coverage exists
- [ ] Create feature flag for gradual rollout
- [ ] Set up monitoring for key metrics

### Phase 1 (Day 1)
- [ ] Create `types/billing.types.ts`
- [ ] Create `StripeIntegrationService`
- [ ] Create `PlanService`
- [ ] Unit tests for both services
- [ ] Code review
- [ ] Merge to development branch

### Phase 2 (Day 2)
- [ ] Create `InvoiceService`
- [ ] Create `PaymentMethodService`
- [ ] Create `BillingAlertService`
- [ ] Integration tests
- [ ] Code review
- [ ] Merge to development branch

### Phase 3 (Day 3)
- [ ] Create `UsageTrackingService`
- [ ] Create `SubscriptionService`
- [ ] Refactor `BillingService` to orchestrator
- [ ] Update all imports
- [ ] End-to-end tests
- [ ] Performance testing
- [ ] Code review
- [ ] Merge to development branch

### Post-Implementation
- [ ] Deploy to staging
- [ ] Run full test suite in staging
- [ ] Monitor performance metrics
- [ ] Gradual rollout to production (feature flag)
- [ ] Monitor error rates and performance
- [ ] Full production rollout
- [ ] Update documentation
- [ ] Team knowledge sharing session

---

## Alternative Approaches Considered

### Approach 1: Monolithic Refactoring
**Description**: Keep single service but organize into internal modules  
**Pros**: Lower risk, simpler migration  
**Cons**: Doesn't solve SRP violation, limited maintainability improvement  
**Verdict**: ❌ Rejected - doesn't address root cause

### Approach 2: Microservices Architecture
**Description**: Deploy each service as separate microservice  
**Pros**: Maximum separation, independent scaling  
**Cons**: Operational complexity, latency overhead, distributed transactions  
**Verdict**: ❌ Rejected - over-engineering for current scale

### Approach 3: Modular Monolith (Selected)
**Description**: Separate services within single codebase  
**Pros**: Clear boundaries, manageable complexity, no distributed system issues  
**Cons**: Services still share runtime  
**Verdict**: ✅ Selected - best balance of benefits and complexity

---

## Future Enhancements

### Short-term (Next 3 months)
1. **Async Event Processing**: Replace direct service calls with event bus
2. **Enhanced Monitoring**: Add metrics for each service
3. **Caching Layer**: Implement Redis caching for frequently accessed data

### Long-term (Next 6-12 months)
1. **Extract to Microservices**: If scale demands, services are ready to extract
2. **Advanced Analytics**: Usage prediction, churn analysis
3. **Multi-currency Support**: Enhanced internationalization
4. **Tax Automation**: Integration with tax calculation services

---

## References

### Codebase Analysis
- **Original File**: `packages/core/src/services/billing.service.ts` (1,199 lines, 62 methods)
- **Refactoring Analysis**: `/sc:explain which are our top candidates for refactoring?`
- **Git Commit**: [To be added after implementation]

### Design Patterns
- **Facade Pattern**: BillingService as orchestrator
- **Repository Pattern**: Data access through Redis
- **Event-Driven**: Service communication via events
- **Dependency Injection**: Service composition

### Related Documentation
- Stripe Integration Guide
- Redis Data Model
- Multi-Tenancy Service Architecture
- Testing Strategy

---

**Last Updated**: 2025-11-16  
**Status**: Ready for Implementation  
**Assigned To**: [To be assigned]  
**Estimated Completion**: 3 days after start
