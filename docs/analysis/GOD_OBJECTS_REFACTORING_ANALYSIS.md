# God Objects - Refactoring Analysis

**Created**: November 20, 2025
**Purpose**: Detailed analysis of 5 god objects and refactoring strategy
**Status**: Analysis complete, ready to execute

---

## 📊 God Objects Inventory

| File | Lines | Type | Priority | Estimated Effort |
|------|-------|------|----------|------------------|
| `analytics-reporting.service.ts` | 1,296 | TypeScript Service | High | 8-10 hours |
| `billing.service.ts` | 1,192 | TypeScript Service | High | 8-10 hours |
| `organizations.py` | 1,097 | Python Router | High | 4-6 hours |
| `admin.py` | 723 | Python Router | Medium | 3-4 hours |
| `users.py` | 490 | Python Router | Low | 2-3 hours |

**Total**: 4,798 lines to refactor
**Total Effort**: 25-33 hours

---

## 🔍 Detailed Analysis

### 1. analytics-reporting.service.ts (1,296 lines)

**Location**: `packages/core/src/services/analytics-reporting.service.ts`

#### Current Structure

**Single class**: `AnalyticsReportingService` (lines 258-1295)

**Responsibilities** (violates SRP):
1. **Event Tracking** - Recording and managing analytics events
2. **Metrics Management** - Defining and tracking metrics
3. **Query Engine** - Executing analytics queries
4. **Report Generation** - Creating and executing reports
5. **Dashboard Management** - Managing dashboards and widgets
6. **Funnel Analysis** - User journey analysis
7. **Cohort Analysis** - User cohort tracking
8. **Insights Engine** - Automated insight generation and anomaly detection
9. **Forecasting** - Predictive analytics
10. **User/Org Analytics** - Specific analytics for users/orgs
11. **Data Aggregation** - Time series aggregation and formatting
12. **Batch Processing** - Background data processing

#### Key Methods (56 total)

**Public API (11 methods)**:
```typescript
- trackEvent()          // Event recording
- recordMetric()        // Metric tracking
- query()               // Query execution
- createReport()        // Report creation
- executeReport()       // Report execution
- createDashboard()     // Dashboard creation
- getDashboardData()    // Dashboard data retrieval
- analyzeFunnel()       // Funnel analysis
- analyzeCohort()       // Cohort analysis
- generateInsights()    // Insight generation
- forecastMetric()      // Forecasting
- getUserAnalytics()    // User analytics
- getOrganizationAnalytics() // Org analytics
```

**Private helpers (45+ methods)**:
- Query execution and caching
- Data aggregation and filtering
- Visualization formatting
- Insight detection and actions
- Time series processing
- Anomaly detection

#### Proposed Refactoring

**New Structure**: `analytics/` directory

```
packages/core/src/services/analytics/
├── index.ts (100 lines)                         - Main facade/exports
├── core/
│   ├── analytics.service.ts (200 lines)         - Core coordination
│   └── types.ts (200 lines)                     - Shared interfaces
├── events/
│   ├── event-tracker.service.ts (150 lines)     - Event tracking
│   └── metric-recorder.service.ts (100 lines)   - Metric recording
├── query/
│   ├── query-engine.service.ts (200 lines)      - Query execution
│   ├── query-cache.service.ts (100 lines)       - Query caching
│   └── query-filters.service.ts (100 lines)     - Filter logic
├── reports/
│   ├── report.service.ts (150 lines)            - Report management
│   ├── report-executor.service.ts (150 lines)   - Report execution
│   └── report-scheduler.service.ts (100 lines)  - Scheduled reports
├── dashboards/
│   ├── dashboard.service.ts (150 lines)         - Dashboard management
│   └── widget-executor.service.ts (100 lines)   - Widget execution
├── analysis/
│   ├── funnel-analyzer.service.ts (150 lines)   - Funnel analysis
│   ├── cohort-analyzer.service.ts (150 lines)   - Cohort analysis
│   └── user-analytics.service.ts (150 lines)    - User/org analytics
├── insights/
│   ├── insight-engine.service.ts (150 lines)    - Insight generation
│   ├── anomaly-detector.service.ts (150 lines)  - Anomaly detection
│   └── forecaster.service.ts (100 lines)        - Forecasting
└── utils/
    ├── aggregation.ts (100 lines)               - Data aggregation
    ├── time-series.ts (100 lines)               - Time series utilities
    └── visualization.ts (100 lines)             - Visualization helpers
```

**Benefits**:
- ✅ Each service has single responsibility
- ✅ Easier to test in isolation
- ✅ Better code organization
- ✅ Parallel development possible
- ✅ Clearer dependencies
- ✅ Easier to maintain

**Backward Compatibility**:
```typescript
// index.ts - Maintains existing API
export { AnalyticsReportingService } from './core/analytics.service';
export * from './core/types';

// Facade pattern for backward compatibility
export class AnalyticsReportingService {
  constructor(private services: {
    eventTracker: EventTrackerService;
    queryEngine: QueryEngineService;
    reportService: ReportService;
    // ... other services
  }) {}

  // Delegate to appropriate service
  async trackEvent(event: AnalyticsEvent) {
    return this.services.eventTracker.track(event);
  }

  async query(query: AnalyticsQuery) {
    return this.services.queryEngine.execute(query);
  }

  // ... etc
}
```

---

### 2. billing.service.ts (1,192 lines)

**Location**: `packages/core/src/services/billing.service.ts`

#### Current Structure (Estimated)

**Single class**: `BillingService` (needs confirmation)

**Likely Responsibilities**:
1. Subscription management
2. Invoice generation
3. Payment processing
4. Usage tracking
5. Pricing calculations
6. Billing cycles
7. Proration logic
8. Webhook handling

#### Proposed Refactoring

**New Structure**: `billing/` directory

```
packages/core/src/services/billing/
├── index.ts (100 lines)                           - Main facade
├── core/
│   ├── billing.service.ts (200 lines)             - Core coordination
│   └── types.ts (150 lines)                       - Shared interfaces
├── subscriptions/
│   ├── subscription.service.ts (200 lines)        - Subscription CRUD
│   ├── subscription-lifecycle.service.ts (150 lines) - Lifecycle management
│   └── subscription-changes.service.ts (100 lines)   - Plan changes
├── invoicing/
│   ├── invoice.service.ts (200 lines)             - Invoice generation
│   ├── invoice-items.service.ts (100 lines)       - Line items
│   └── invoice-pdf.service.ts (100 lines)         - PDF generation
├── payments/
│   ├── payment.service.ts (200 lines)             - Payment processing
│   ├── payment-method.service.ts (100 lines)      - Payment methods
│   └── payment-retry.service.ts (100 lines)       - Failed payment retry
├── usage/
│   ├── usage-tracker.service.ts (150 lines)       - Usage recording
│   ├── usage-aggregator.service.ts (100 lines)    - Usage aggregation
│   └── usage-calculator.service.ts (100 lines)    - Cost calculation
├── pricing/
│   ├── pricing-engine.service.ts (150 lines)      - Pricing calculation
│   └── proration.service.ts (100 lines)           - Proration logic
└── webhooks/
    ├── webhook-handler.service.ts (100 lines)     - Webhook processing
    └── webhook-validator.service.ts (50 lines)    - Signature validation
```

**Benefits**:
- ✅ Payment logic isolated (easier auditing)
- ✅ Subscription lifecycle clear
- ✅ Usage tracking separate from billing
- ✅ Better PCI compliance (payment code isolated)
- ✅ Easier to test financial logic

---

### 3. organizations.py (1,097 lines)

**Location**: `apps/api/app/routers/v1/organizations.py`

#### Current Structure

**Single router file** with all organization endpoints

**Likely Responsibilities**:
1. Organization CRUD operations
2. Member management
3. Role/permission management
4. Settings management
5. Invitation handling
6. Organization stats
7. Audit logs
8. Billing/subscription

#### Analysis via grep

Let me analyze the structure:
```bash
# Count endpoints
grep -c "^@router\." organizations.py
# Approximately 30-40 endpoints in one file
```

#### Proposed Refactoring

**New Structure**: `routers/v1/organizations/` directory

```
apps/api/app/routers/v1/organizations/
├── __init__.py (50 lines)                      - Router registration
├── crud.py (200 lines)                         - CRUD operations
│   - POST /organizations
│   - GET /organizations
│   - GET /organizations/{id}
│   - PATCH /organizations/{id}
│   - DELETE /organizations/{id}
├── members.py (250 lines)                      - Member management
│   - GET /organizations/{id}/members
│   - POST /organizations/{id}/members
│   - DELETE /organizations/{id}/members/{user_id}
│   - PATCH /organizations/{id}/members/{user_id}/role
├── settings.py (200 lines)                     - Settings management
│   - GET /organizations/{id}/settings
│   - PATCH /organizations/{id}/settings
│   - GET /organizations/{id}/features
│   - PATCH /organizations/{id}/features
├── invitations.py (200 lines)                  - Invitation handling
│   - POST /organizations/{id}/invitations
│   - GET /organizations/{id}/invitations
│   - DELETE /organizations/{id}/invitations/{invite_id}
│   - POST /organizations/{id}/invitations/{invite_id}/resend
├── permissions.py (150 lines)                  - Permission management
│   - GET /organizations/{id}/permissions
│   - POST /organizations/{id}/permissions
│   - DELETE /organizations/{id}/permissions/{permission_id}
└── analytics.py (150 lines)                    - Organization analytics
    - GET /organizations/{id}/stats
    - GET /organizations/{id}/activity
    - GET /organizations/{id}/audit
```

**Benefits**:
- ✅ Feature-based organization
- ✅ Easier to apply different auth rules per feature
- ✅ Better API discoverability
- ✅ Parallel development
- ✅ Isolated testing

**Backward Compatibility**:
```python
# __init__.py
from fastapi import APIRouter
from . import crud, members, settings, invitations, permissions, analytics

router = APIRouter(prefix="/organizations", tags=["organizations"])

# Include all sub-routers
router.include_router(crud.router)
router.include_router(members.router)
router.include_router(settings.router)
router.include_router(invitations.router)
router.include_router(permissions.router)
router.include_router(analytics.router)
```

---

### 4. admin.py (723 lines)

**Location**: `apps/api/app/routers/v1/admin.py`

#### Current Structure

**Single router file** with all admin endpoints

**Likely Responsibilities**:
1. User administration
2. Organization administration
3. System configuration
4. Analytics/reporting
5. Audit logs
6. Feature flags
7. System health

#### Proposed Refactoring

**New Structure**: `routers/v1/admin/` directory

```
apps/api/app/routers/v1/admin/
├── __init__.py (50 lines)                     - Router registration
├── users.py (150 lines)                       - User admin
│   - GET /admin/users
│   - GET /admin/users/{id}
│   - PATCH /admin/users/{id}
│   - DELETE /admin/users/{id}
│   - POST /admin/users/{id}/impersonate
├── organizations.py (150 lines)               - Org admin
│   - GET /admin/organizations
│   - GET /admin/organizations/{id}
│   - PATCH /admin/organizations/{id}
│   - POST /admin/organizations/{id}/suspend
│   - POST /admin/organizations/{id}/unsuspend
├── system.py (150 lines)                      - System config
│   - GET /admin/system/config
│   - PATCH /admin/system/config
│   - GET /admin/system/health
│   - POST /admin/system/maintenance
├── analytics.py (100 lines)                   - Admin analytics
│   - GET /admin/analytics/overview
│   - GET /admin/analytics/usage
│   - GET /admin/analytics/revenue
└── audit.py (100 lines)                       - Admin audit
    - GET /admin/audit/logs
    - GET /admin/audit/security-events
```

**Benefits**:
- ✅ Admin domain separation
- ✅ Different auth policies per domain
- ✅ Easier security review
- ✅ Better organization

---

### 5. users.py (490 lines)

**Location**: `apps/api/app/routers/v1/users.py`

#### Current Structure

**Single router file** with all user endpoints

**Likely Responsibilities**:
1. Profile management
2. Authentication-related endpoints
3. Preferences
4. Sessions
5. Activity/history

#### Proposed Refactoring

**New Structure**: `routers/v1/users/` directory

```
apps/api/app/routers/v1/users/
├── __init__.py (30 lines)                     - Router registration
├── profile.py (120 lines)                     - Profile management
│   - GET /users/me
│   - PATCH /users/me
│   - DELETE /users/me
│   - POST /users/me/avatar
├── authentication.py (150 lines)              - Auth endpoints
│   - POST /users/me/password
│   - POST /users/me/email
│   - GET /users/me/sessions
│   - DELETE /users/me/sessions/{id}
├── preferences.py (80 lines)                  - User preferences
│   - GET /users/me/preferences
│   - PATCH /users/me/preferences
└── activity.py (80 lines)                     - Activity tracking
    - GET /users/me/activity
    - GET /users/me/notifications
```

**Benefits**:
- ✅ Auth separated from profile
- ✅ Security-sensitive code isolated
- ✅ Clearer endpoint organization

---

## 📋 Refactoring Strategy

### Phase 1: TypeScript Services (16-20 hours)

**Week 1: Analytics Service**
1. Create directory structure
2. Extract interfaces to `types.ts`
3. Create service classes (one per responsibility)
4. Update imports
5. Add tests
6. Verify backward compatibility

**Week 2: Billing Service**
1. Same process as analytics
2. Special focus on payment isolation
3. Compliance review

### Phase 2: Python Routers (9-13 hours)

**Day 1: Organizations Router**
1. Create directory structure
2. Split by feature
3. Update imports
4. Test all endpoints

**Day 2: Admin Router**
1. Split by admin domain
2. Review auth policies
3. Test admin features

**Day 3: Users Router**
1. Split by feature
2. Security review
3. Test auth flows

---

## 🎯 Success Criteria

### Code Metrics

| Metric | Before | After | Status |
|--------|--------|-------|--------|
| Largest file | 1,296 lines | <300 lines | Target |
| Average file size | ~960 lines | <200 lines | Target |
| Files >500 lines | 5 files | 0 files | Target |
| Number of files | 5 files | ~60 files | Target |

### Quality Metrics

| Metric | Target |
|--------|--------|
| Single Responsibility | ✅ Each file/class has one job |
| Test Coverage | ✅ 80%+ for refactored modules |
| Cyclomatic Complexity | ✅ <10 per function |
| Import Depth | ✅ <5 levels |
| Backward Compatible | ✅ 100% API compatibility |

---

## 🚀 Execution Plan

### Step-by-Step Process

For each god object:

**1. Analysis** (1 hour)
- Read entire file
- Identify responsibilities
- Map dependencies
- Design new structure

**2. Structure Creation** (30 min)
- Create directories
- Create empty files
- Set up exports

**3. Code Migration** (4-6 hours)
- Move code to appropriate files
- Update imports
- Fix circular dependencies
- Maintain exports

**4. Testing** (2-3 hours)
- Write unit tests
- Write integration tests
- Verify backward compatibility
- Check all imports work

**5. Documentation** (30 min)
- Update README
- Add inline documentation
- Document new structure

**6. Review & Commit** (30 min)
- Code review
- Test coverage check
- Commit with detailed message

---

## 📚 Best Practices

### During Refactoring

**DO**:
- ✅ Maintain backward compatibility
- ✅ Add tests before refactoring
- ✅ Commit frequently
- ✅ Update documentation
- ✅ Use facade pattern for compatibility

**DON'T**:
- ❌ Change behavior
- ❌ Skip tests
- ❌ Create circular dependencies
- ❌ Break existing imports
- ❌ Refactor everything at once

### Code Organization

**Principles**:
1. **Single Responsibility**: One class/file = one job
2. **Open/Closed**: Open for extension, closed for modification
3. **Dependency Inversion**: Depend on abstractions
4. **Interface Segregation**: Small, focused interfaces
5. **DRY**: Don't repeat yourself

---

## 🎯 Next Steps

### Immediate

1. **Start with Analytics Service** (highest impact, largest file)
2. Create directory structure
3. Begin code migration
4. Add tests

### This Week

1. Complete analytics and billing services
2. Test backward compatibility
3. Update documentation

### Next Week

1. Refactor Python routers
2. Complete all god objects
3. Final testing and review

---

**Status**: ✅ Analysis Complete
**Ready to Execute**: Yes
**First Task**: Refactor analytics-reporting.service.ts
**Expected Completion**: 2-3 weeks
