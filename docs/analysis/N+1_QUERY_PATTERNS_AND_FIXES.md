# N+1 Query Patterns and Fixes

**Date**: November 19, 2025
**Impact**: HIGH - Performance optimization
**Estimated Improvement**: 10-100x faster for queries with relationships

---

## What is the N+1 Query Problem?

The N+1 query problem occurs when:
1. You query for N records (1 query)
2. For each record, you access a relationship, triggering N additional queries
3. Total: **1 + N queries** instead of **1 or 2 queries**

**Example**:
```python
# ❌ N+1 PROBLEM (1000 organizations = 1001 queries!)
orgs = await db.execute(select(Organization))  # 1 query

for org in orgs:
    members = org.members  # N queries (one per organization!)
    print(f"{org.name}: {len(members)} members")
```

**Impact**: With 1000 organizations, this creates **1001 database queries**!

---

## How to Detect N+1 Queries

### Method 1: Enable SQLAlchemy Query Logging

```python
# In app/database.py or app/main.py
import logging

# Enable SQLAlchemy query logging
logging.basicConfig()
logging.getLogger('sqlalchemy.engine').setLevel(logging.INFO)
```

Look for patterns like:
```
INFO:sqlalchemy.engine:SELECT * FROM organizations
INFO:sqlalchemy.engine:SELECT * FROM members WHERE org_id = 1
INFO:sqlalchemy.engine:SELECT * FROM members WHERE org_id = 2
INFO:sqlalchemy.engine:SELECT * FROM members WHERE org_id = 3
...  # Hundreds more queries
```

### Method 2: Count Queries in Tests

```python
from sqlalchemy import event
from sqlalchemy.engine import Engine

query_count = 0

@event.listens_for(Engine, "before_cursor_execute")
def receive_before_cursor_execute(conn, cursor, statement, params, context, executemany):
    global query_count
    query_count += 1

# In test
query_count = 0
orgs = await get_organizations_with_members()
print(f"Executed {query_count} queries")  # Should be 1-2, not 100+
```

### Method 3: Use Database Query Analysis Tools

- **PostgreSQL**: `EXPLAIN ANALYZE`
- **MySQL**: `EXPLAIN`
- **Application Performance Monitoring**: New Relic, DataDog APM

---

## Common N+1 Patterns in the Codebase

### Pattern 1: Accessing Relationships in Loops

**Location**: `apps/api/app/routers/v1/organizations.py:get_organizations()`

**❌ PROBLEM**:
```python
@router.get("/organizations")
async def get_organizations(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Organization))
    orgs = result.scalars().all()

    # N+1: One query per org for members!
    return [
        {
            "id": org.id,
            "name": org.name,
            "member_count": len(org.members)  # Triggers N queries!
        }
        for org in orgs
    ]
```

**✅ FIX**: Use `selectinload()` or `joinedload()`
```python
from sqlalchemy.orm import selectinload

@router.get("/organizations")
async def get_organizations(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Organization)
        .options(selectinload(Organization.members))  # Eager load members
    )
    orgs = result.scalars().all()

    # Now only 2 queries total:
    # 1. SELECT * FROM organizations
    # 2. SELECT * FROM members WHERE org_id IN (...)
    return [
        {
            "id": org.id,
            "name": org.name,
            "member_count": len(org.members)  # Already loaded!
        }
        for org in orgs
    ]
```

---

### Pattern 2: Nested Relationships

**Location**: `apps/api/app/routers/v1/users.py:get_user_details()`

**❌ PROBLEM**:
```python
@router.get("/users/{user_id}")
async def get_user_details(user_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(User).where(User.id == user_id)
    )
    user = result.scalar_one()

    return {
        "user": user.to_dict(),
        "organizations": [
            {
                "id": org.id,
                "name": org.name,
                "roles": [role.name for role in org.roles]  # N+1 for roles!
            }
            for org in user.organizations  # N+1 for orgs!
        ]
    }
```

**Queries Executed**:
1. Get user
2. Get user's organizations (N queries)
3. For each org, get roles (N × M queries)
**Total**: 1 + N + (N × M) queries!

**✅ FIX**: Use nested `selectinload()`
```python
from sqlalchemy.orm import selectinload

@router.get("/users/{user_id}")
async def get_user_details(user_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(User)
        .options(
            selectinload(User.organizations)
            .selectinload(Organization.roles)  # Nested eager loading
        )
        .where(User.id == user_id)
    )
    user = result.scalar_one()

    # Now only 3 queries:
    # 1. SELECT * FROM users WHERE id = ?
    # 2. SELECT * FROM user_organizations WHERE user_id = ?
    # 3. SELECT * FROM organization_roles WHERE org_id IN (...)

    return {
        "user": user.to_dict(),
        "organizations": [
            {
                "id": org.id,
                "name": org.name,
                "roles": [role.name for role in org.roles]  # Already loaded!
            }
            for org in user.organizations  # Already loaded!
        ]
    }
```

---

### Pattern 3: Permissions/RBAC Checks in Loops

**Location**: `apps/api/app/services/rbac_service.py:check_bulk_permissions()`

**❌ PROBLEM**:
```python
async def check_permissions_for_resources(user_id: str, resources: list[str]):
    permissions = {}

    for resource in resources:
        # N+1: One query per resource!
        result = await db.execute(
            select(Permission)
            .join(Role)
            .join(UserRole)
            .where(
                UserRole.user_id == user_id,
                Permission.resource == resource
            )
        )
        permissions[resource] = result.scalar_one_or_none() is not None

    return permissions
```

**✅ FIX**: Single query with `IN` clause
```python
async def check_permissions_for_resources(user_id: str, resources: list[str]):
    # Single query for all resources
    result = await db.execute(
        select(Permission)
        .join(Role)
        .join(UserRole)
        .where(
            UserRole.user_id == user_id,
            Permission.resource.in_(resources)  # IN clause!
        )
    )
    allowed_resources = {perm.resource for perm in result.scalars().all()}

    # Check which resources are allowed
    permissions = {
        resource: resource in allowed_resources
        for resource in resources
    }

    return permissions
```

---

### Pattern 4: Audit Logs with User/Organization Details

**Location**: `apps/api/app/routers/v1/audit_logs.py:get_audit_logs()`

**❌ PROBLEM**:
```python
@router.get("/audit-logs")
async def get_audit_logs(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(AuditLog).limit(100))
    logs = result.scalars().all()

    return [
        {
            "id": log.id,
            "action": log.action,
            "user": log.user.email,  # N+1 for users!
            "organization": log.organization.name  # N+1 for orgs!
        }
        for log in logs
    ]
```

**✅ FIX**: Use `joinedload()` for single relationships
```python
from sqlalchemy.orm import joinedload

@router.get("/audit-logs")
async def get_audit_logs(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(AuditLog)
        .options(
            joinedload(AuditLog.user),  # JOIN instead of separate query
            joinedload(AuditLog.organization)
        )
        .limit(100)
    )
    logs = result.scalars().unique().all()  # unique() important with joinedload!

    # Now only 1 query with JOINs:
    # SELECT * FROM audit_logs
    # JOIN users ON ...
    # JOIN organizations ON ...
    # LIMIT 100

    return [
        {
            "id": log.id,
            "action": log.action,
            "user": log.user.email,  # Already loaded!
            "organization": log.organization.name  # Already loaded!
        }
        for log in logs
    ]
```

---

## SQLAlchemy Eager Loading Strategies

### 1. `selectinload()` - Best for Collections (1-to-Many)

**Use When**: Loading collections (e.g., organization.members, user.roles)
**Queries**: 1 + number of relationship types
**Performance**: Good for most cases

```python
# Load organizations with all members
select(Organization).options(selectinload(Organization.members))

# Executes:
# 1. SELECT * FROM organizations
# 2. SELECT * FROM members WHERE org_id IN (1, 2, 3, ...)
```

**Pros**:
- Simple to use
- Works well with large result sets
- Consistent query count

**Cons**:
- Requires 2+ queries (not always 1 JOIN)
- Not efficient for small result sets with single relationships

---

### 2. `joinedload()` - Best for Single Objects (1-to-1, Many-to-1)

**Use When**: Loading single relationships (e.g., audit_log.user, member.organization)
**Queries**: 1 (with JOIN)
**Performance**: Best for small-medium result sets

```python
# Load audit logs with user and organization
select(AuditLog).options(
    joinedload(AuditLog.user),
    joinedload(AuditLog.organization)
)

# Executes:
# SELECT * FROM audit_logs
# JOIN users ON audit_logs.user_id = users.id
# JOIN organizations ON audit_logs.org_id = organizations.id
```

**Important**: Use `.unique()` when fetching results:
```python
result = await db.execute(query)
items = result.scalars().unique().all()  # ← Important!
```

**Pros**:
- Only 1 query
- Best performance for small result sets

**Cons**:
- Can create very large result sets with many JOINs
- Cartesian product issues with multiple collections

---

### 3. `subqueryload()` - Alternative for Collections

**Use When**: `selectinload()` not working or subquery is more efficient
**Queries**: 2
**Performance**: Similar to `selectinload()`

```python
from sqlalchemy.orm import subqueryload

select(Organization).options(subqueryload(Organization.members))
```

---

### 4. Mixed Strategy for Complex Cases

```python
# Load organizations with members and their permissions
select(Organization).options(
    selectinload(Organization.members)  # Collection
    .joinedload(Member.user),  # Single object
    joinedload(Organization.owner)  # Single object
)

# Executes 3 queries:
# 1. SELECT orgs JOIN owners
# 2. SELECT members WHERE org_id IN (...) JOIN users
# 3. (If Member.user has relationships, additional queries)
```

---

## Quick Reference: When to Use Each Strategy

| Scenario | Strategy | Queries | Example |
|----------|----------|---------|---------|
| **Collection** (1-to-Many) | `selectinload()` | 2 | org.members, user.sessions |
| **Single** (Many-to-1) | `joinedload()` | 1 | log.user, member.organization |
| **Nested** (Collection → Single) | Mixed | 2-3 | org.members.user |
| **Nested** (Collection → Collection) | `selectinload()` × 2 | 3+ | org.members.permissions |
| **Multiple Singles** | `joinedload()` × N | 1 | log.user + log.org |
| **Bulk Permission Checks** | `IN` clause | 1 | WHERE user_id IN (...) |

---

## Testing for N+1 Queries

### Test Pattern 1: Query Counter

```python
# tests/test_queries.py
import pytest
from sqlalchemy import event
from sqlalchemy.engine import Engine

@pytest.fixture
def query_counter(db_engine):
    """Fixture to count database queries"""
    query_count = {"count": 0}

    def receive_before_cursor_execute(conn, cursor, statement, params, context, executemany):
        query_count["count"] += 1

    event.listen(db_engine, "before_cursor_execute", receive_before_cursor_execute)

    yield query_count

    event.remove(db_engine, "before_cursor_execute", receive_before_cursor_execute)


@pytest.mark.asyncio
async def test_get_organizations_no_n_plus_1(client, query_counter):
    """Test that getting organizations doesn't create N+1 queries"""
    # Create 100 organizations with members
    for i in range(100):
        await create_organization_with_members(f"org{i}", member_count=10)

    # Reset counter
    query_counter["count"] = 0

    # Fetch organizations
    response = await client.get("/api/v1/organizations")

    # Should be 2 queries max (orgs + members), not 101+
    assert query_counter["count"] <= 3, f"N+1 detected: {query_counter['count']} queries"
    assert response.status_code == 200
```

### Test Pattern 2: Performance Benchmark

```python
import time

@pytest.mark.asyncio
async def test_organization_query_performance():
    """Ensure organization queries are performant"""
    # Create test data
    for i in range(1000):
        await create_organization_with_members(f"org{i}", member_count=50)

    start = time.time()

    # Query all organizations with members
    orgs = await get_all_organizations_with_members()

    duration = time.time() - start

    # Should complete in under 1 second for 1000 orgs
    assert duration < 1.0, f"Query too slow: {duration}s (N+1 likely)"
    assert len(orgs) == 1000
```

---

## Checklist: Files to Review for N+1 Patterns

Based on the audit, these files likely have N+1 issues:

### High Priority (User-Facing Endpoints)
- [ ] `app/routers/v1/organizations.py` - Organization list with members
- [ ] `app/routers/v1/users.py` - User details with organizations/roles
- [ ] `app/routers/v1/audit_logs.py` - Audit logs with user/org details
- [ ] `app/routers/v1/rbac.py` - Permission checks

### Medium Priority (Background/Admin)
- [ ] `app/routers/v1/admin.py` - Admin dashboards
- [ ] `app/routers/v1/organization_members.py` - Member management
- [ ] `app/services/rbac_service.py` - Permission checking
- [ ] `app/services/monitoring.py` - Monitoring queries

### Service Layer
- [ ] `app/services/auth_service.py` - Session/user queries
- [ ] `app/services/sso_service.py` - SSO configuration queries
- [ ] `app/services/audit_service.py` - Audit log creation

---

## Implementation Checklist

### Phase 1: Detect (Week 1)
- [ ] Enable SQLAlchemy query logging in development
- [ ] Add query counters to key endpoint tests
- [ ] Run load tests to identify slow endpoints
- [ ] Document N+1 patterns found

### Phase 2: Fix High-Traffic Endpoints (Week 2)
- [ ] Fix organization list endpoints
- [ ] Fix user detail endpoints
- [ ] Fix audit log endpoints
- [ ] Add eager loading to hot paths

### Phase 3: Fix Remaining Endpoints (Week 3)
- [ ] Fix admin endpoints
- [ ] Fix RBAC permission checks
- [ ] Fix service layer queries
- [ ] Add regression tests

### Phase 4: Monitor (Ongoing)
- [ ] Set up query performance monitoring
- [ ] Add alerts for slow queries (>100ms)
- [ ] Review new code for N+1 patterns in PR reviews
- [ ] Document eager loading patterns in team docs

---

## Performance Improvements Expected

Based on typical N+1 fixes:

| Endpoint | Before | After | Improvement |
|----------|--------|-------|-------------|
| List 100 organizations with members | 101 queries, ~500ms | 2 queries, ~50ms | **10x faster** |
| User details with 10 orgs + roles | 21 queries, ~200ms | 3 queries, ~30ms | **7x faster** |
| Audit logs (100 entries) | 201 queries, ~1000ms | 1 query, ~80ms | **12x faster** |
| Bulk permission check (50 resources) | 50 queries, ~400ms | 1 query, ~20ms | **20x faster** |

**Overall API Response Time**: Expected **30-50% improvement** on endpoints with relationships.

---

## Common Mistakes to Avoid

### Mistake 1: Forgetting `.unique()` with `joinedload()`

```python
# ❌ WRONG: Returns duplicates
result = await db.execute(query.options(joinedload(Model.relation)))
items = result.scalars().all()  # May have duplicates!

# ✅ CORRECT: Use unique()
items = result.scalars().unique().all()
```

### Mistake 2: Using `joinedload()` for Collections

```python
# ❌ BAD: Creates cartesian product
select(Organization).options(joinedload(Organization.members))

# ✅ GOOD: Use selectinload() for collections
select(Organization).options(selectinload(Organization.members))
```

### Mistake 3: Not Testing with Realistic Data

```python
# ❌ Test with 1 organization - won't catch N+1
await create_organization(1 member)
# Looks fast!

# ✅ Test with many organizations
for i in range(100):
    await create_organization(50 members each)
# Now you see the problem!
```

---

## Resources

- **SQLAlchemy Docs**: https://docs.sqlalchemy.org/en/20/orm/loading_relationships.html
- **N+1 Detection Tools**:
  - `nplusone` Python package
  - Django Debug Toolbar (for Django)
  - SQLAlchemy-Utils `QueryRecorder`

---

**Next Steps**: Review the files listed in the checklist and apply the patterns documented here. Start with high-traffic endpoints for maximum impact.
