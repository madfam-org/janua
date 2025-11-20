# Redis Circuit Breaker Testing Guide

This guide provides comprehensive testing procedures for the Redis circuit breaker implementation.

---

## Prerequisites

- API server running: `cd apps/api && python -m uvicorn app.main:app --reload`
- Redis running: `docker-compose up -d redis` or `docker run -p 6379:6379 redis:7-alpine`
- Access to Docker to stop/start Redis
- `curl` or similar HTTP client

---

## Test Scenarios

### Test 1: Verify Circuit Breaker is Initialized (Normal Operation)

**Objective**: Confirm circuit breaker starts in CLOSED state with Redis available.

**Steps**:
```bash
# 1. Start API and Redis
docker-compose up -d redis
cd apps/api && python -m uvicorn app.main:app --reload &

# 2. Wait for startup (5 seconds)
sleep 5

# 3. Check circuit breaker status
curl -s http://localhost:8000/api/v1/health/circuit-breaker | jq
```

**Expected Response**:
```json
{
  "state": "closed",
  "failure_count": 0,
  "total_calls": 0,
  "successful_calls": 0,
  "failed_calls": 0,
  "fallback_calls": 0,
  "cache_hits": 0,
  "cache_misses": 0,
  "cache_size": 0,
  "last_failure_time": null
}
```

**Success Criteria**:
- ✅ `state` is `"closed"`
- ✅ `failure_count` is `0`
- ✅ `redis_available` is `true` (if checking `/health/redis`)

---

### Test 2: Normal Redis Operations

**Objective**: Verify circuit breaker allows normal operations when Redis is healthy.

**Steps**:
```bash
# 1. Make several requests that use Redis (sessions, rate limiting, etc.)
for i in {1..10}; do
  curl -s http://localhost:8000/api/v1/health/redis > /dev/null
  echo "Request $i completed"
done

# 2. Check circuit breaker metrics
curl -s http://localhost:8000/api/v1/health/circuit-breaker | jq
```

**Expected Response**:
```json
{
  "state": "closed",
  "failure_count": 0,
  "total_calls": 10,
  "successful_calls": 10,
  "failed_calls": 0,
  "fallback_calls": 0,
  "cache_hits": 0,
  "cache_misses": 0,
  "cache_size": 10,
  "last_failure_time": null
}
```

**Success Criteria**:
- ✅ `state` remains `"closed"`
- ✅ `successful_calls` increases
- ✅ `failed_calls` is `0`
- ✅ No errors in API logs

---

### Test 3: Circuit Opens on Redis Failure

**Objective**: Verify circuit opens after configured failure threshold.

**Steps**:
```bash
# 1. Check initial state
curl -s http://localhost:8000/api/v1/health/circuit-breaker | jq '.state'

# 2. Stop Redis to simulate failure
docker stop redis
# OR if using docker-compose:
docker-compose stop redis

# 3. Make requests to trigger failures (default threshold is 5)
for i in {1..6}; do
  echo "Request $i:"
  curl -s http://localhost:8000/api/v1/health/redis | jq '.degraded_mode'
  sleep 0.5
done

# 4. Check circuit status
curl -s http://localhost:8000/api/v1/health/circuit-breaker | jq
```

**Expected Response** (after 5+ failed requests):
```json
{
  "state": "open",
  "failure_count": 5,
  "total_calls": 6,
  "successful_calls": 0,
  "failed_calls": 5,
  "fallback_calls": 1,
  "cache_hits": 0,
  "cache_misses": 1,
  "cache_size": 0,
  "last_failure_time": "2025-11-19T22:45:30.123456"
}
```

**Success Criteria**:
- ✅ `state` changes to `"open"` after 5 failures
- ✅ `failure_count` is `5`
- ✅ `failed_calls` is `5`
- ✅ `last_failure_time` is set
- ✅ API continues to respond (degraded mode)
- ✅ `/health/redis` shows `"degraded_mode": true`

---

### Test 4: Open Circuit Uses Fallback

**Objective**: Verify that when circuit is OPEN, requests use fallback without calling Redis.

**Steps**:
```bash
# 1. Ensure circuit is OPEN (from Test 3)
curl -s http://localhost:8000/api/v1/health/circuit-breaker | jq '.state'
# Should show "open"

# 2. Make multiple requests
before_calls=$(curl -s http://localhost:8000/api/v1/health/circuit-breaker | jq '.fallback_calls')
echo "Fallback calls before: $before_calls"

for i in {1..5}; do
  curl -s http://localhost:8000/api/v1/health/redis > /dev/null
done

after_calls=$(curl -s http://localhost:8000/api/v1/health/circuit-breaker | jq '.fallback_calls')
echo "Fallback calls after: $after_calls"

# 3. Verify fallback calls increased
curl -s http://localhost:8000/api/v1/health/circuit-breaker | jq
```

**Expected Behavior**:
- ✅ `fallback_calls` increases by 5
- ✅ `failed_calls` does NOT increase (Redis not being called)
- ✅ API responds quickly (no Redis timeout delay)
- ✅ `/health/redis` returns `"degraded_mode": true`

---

### Test 5: Circuit Recovery (HALF_OPEN)

**Objective**: Verify circuit attempts recovery after timeout.

**Steps**:
```bash
# 1. Ensure circuit is OPEN
curl -s http://localhost:8000/api/v1/health/circuit-breaker | jq '.state'

# 2. Restart Redis
docker start redis
# OR:
docker-compose start redis

# 3. Wait for recovery timeout (default 60 seconds)
echo "Waiting 60 seconds for recovery timeout..."
sleep 60

# 4. Make a request to trigger HALF_OPEN transition
echo "Making request to trigger recovery attempt..."
curl -s http://localhost:8000/api/v1/health/redis | jq

# 5. Check circuit state
curl -s http://localhost:8000/api/v1/health/circuit-breaker | jq '.state'
```

**Expected Response**:
```json
{
  "state": "half_open",
  "failure_count": 0,
  "total_calls": 17,
  "successful_calls": 1,
  "failed_calls": 5,
  "fallback_calls": 6,
  ...
}
```

**Success Criteria**:
- ✅ State transitions to `"half_open"`
- ✅ `failure_count` resets to `0`
- ✅ API successfully connects to Redis
- ✅ `/health/redis` shows `"redis_available": true`

---

### Test 6: Circuit Closes After Successful Recovery

**Objective**: Verify circuit fully closes after successful operations in HALF_OPEN state.

**Steps**:
```bash
# 1. Ensure circuit is HALF_OPEN (from Test 5)
curl -s http://localhost:8000/api/v1/health/circuit-breaker | jq '.state'

# 2. Make several successful requests (default: 3 needed to close)
for i in {1..3}; do
  echo "Recovery request $i:"
  curl -s http://localhost:8000/api/v1/health/redis | jq '.redis_available'
  sleep 1
done

# 3. Check circuit status
curl -s http://localhost:8000/api/v1/health/circuit-breaker | jq
```

**Expected Response**:
```json
{
  "state": "closed",
  "failure_count": 0,
  "total_calls": 20,
  "successful_calls": 4,
  "failed_calls": 5,
  "fallback_calls": 6,
  "cache_hits": 2,
  "cache_misses": 3,
  ...
}
```

**Success Criteria**:
- ✅ State transitions to `"closed"`
- ✅ `successful_calls` increases
- ✅ `failure_count` is `0`
- ✅ Normal operations resume

---

### Test 7: Fallback Cache Hit/Miss

**Objective**: Verify fallback cache stores and retrieves values.

**Steps**:
```bash
# 1. With Redis available, make requests to cache data
curl -s "http://localhost:8000/api/v1/some-endpoint" # Replace with actual endpoint
curl -s "http://localhost:8000/api/v1/another-endpoint"

# 2. Stop Redis
docker stop redis

# 3. Wait for circuit to open
for i in {1..6}; do
  curl -s http://localhost:8000/api/v1/health/redis > /dev/null
done

# 4. Make same requests - should hit cache
curl -s "http://localhost:8000/api/v1/some-endpoint"

# 5. Check cache metrics
curl -s http://localhost:8000/api/v1/health/circuit-breaker | jq '{cache_hits, cache_misses, cache_size}'
```

**Expected Response**:
```json
{
  "cache_hits": 1,
  "cache_misses": 0,
  "cache_size": 2
}
```

**Success Criteria**:
- ✅ `cache_hits` increases when requesting cached data
- ✅ `cache_misses` increases for new requests
- ✅ Cached data is returned correctly

---

### Test 8: Failed Recovery (HALF_OPEN → OPEN)

**Objective**: Verify circuit reopens if recovery attempt fails.

**Steps**:
```bash
# 1. Open circuit (stop Redis, trigger failures)
docker stop redis
for i in {1..6}; do curl -s http://localhost:8000/api/v1/health/redis > /dev/null; done

# 2. Wait for recovery timeout WITHOUT restarting Redis
sleep 60

# 3. Make a request (will transition to HALF_OPEN then fail)
curl -s http://localhost:8000/api/v1/health/redis | jq

# 4. Check circuit status
curl -s http://localhost:8000/api/v1/health/circuit-breaker | jq '.state'
```

**Expected Response**:
```json
{
  "state": "open",
  ...
}
```

**Success Criteria**:
- ✅ Circuit transitions to `"half_open"` briefly
- ✅ Circuit reopens to `"open"` after failed recovery
- ✅ System continues in degraded mode

---

## Integration Tests

### Test 9: Session Management with Circuit Breaker

**Objective**: Verify sessions work with circuit breaker.

**Steps**:
```bash
# 1. Create a session (Redis available)
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "test@example.com", "password": "password123"}' \
  -c cookies.txt

# 2. Use session
curl http://localhost:8000/api/v1/users/me -b cookies.txt

# 3. Stop Redis
docker stop redis

# 4. Try to use session (should fall back to JWT-only)
curl http://localhost:8000/api/v1/users/me -b cookies.txt

# 5. Restart Redis
docker start redis
sleep 5

# 6. Session should work normally again
curl http://localhost:8000/api/v1/users/me -b cookies.txt
```

**Success Criteria**:
- ✅ Sessions work with Redis available
- ✅ JWT-only authentication works when Redis is down
- ✅ Sessions resume when Redis recovers

---

### Test 10: Load Testing Circuit Breaker

**Objective**: Verify circuit breaker under load.

**Steps**:
```bash
# 1. Install apache bench or use similar tool
# sudo apt-get install apache2-utils

# 2. Run load test (100 requests, 10 concurrent)
ab -n 100 -c 10 http://localhost:8000/api/v1/health/redis

# 3. Check metrics
curl -s http://localhost:8000/api/v1/health/circuit-breaker | jq
```

**Success Criteria**:
- ✅ All requests complete successfully
- ✅ `successful_calls` matches request count
- ✅ Circuit remains `"closed"`
- ✅ No errors or timeouts

---

## Monitoring & Alerting

### Prometheus Metrics (Future Enhancement)

Example metrics to expose:
```
# Circuit breaker state (0=closed, 1=half_open, 2=open)
redis_circuit_breaker_state{service="plinto"} 0

# Total calls
redis_circuit_breaker_total_calls{service="plinto"} 1523

# Success rate
redis_circuit_breaker_success_rate{service="plinto"} 0.99

# Cache hit ratio
redis_circuit_breaker_cache_hit_ratio{service="plinto"} 0.85
```

### Alert Rules

**Critical Alert** - Circuit Opened:
```yaml
- alert: RedisCircuitBreakerOpen
  expr: redis_circuit_breaker_state == 2
  for: 5m
  labels:
    severity: critical
  annotations:
    summary: "Redis circuit breaker is OPEN"
    description: "Circuit breaker has been open for 5 minutes. Service is in degraded mode."
```

**Warning Alert** - High Failure Rate:
```yaml
- alert: RedisHighFailureRate
  expr: rate(redis_circuit_breaker_failed_calls[5m]) > 0.1
  for: 2m
  labels:
    severity: warning
  annotations:
    summary: "High Redis failure rate detected"
    description: "Redis is experiencing failures. Circuit may open soon."
```

---

## Troubleshooting

### Circuit Stuck OPEN

**Symptoms**: Circuit remains OPEN even after Redis is available.

**Diagnosis**:
```bash
# Check last failure time
curl -s http://localhost:8000/api/v1/health/circuit-breaker | jq '.last_failure_time'

# Calculate time since last failure
# If > 60 seconds, circuit should attempt recovery
```

**Solution**:
- Wait for recovery timeout (default 60s)
- Make a request to trigger HALF_OPEN transition
- Verify Redis is actually accessible: `redis-cli ping`

### High Cache Miss Rate

**Symptoms**: `cache_misses` is much higher than `cache_hits`.

**Diagnosis**:
```bash
curl -s http://localhost:8000/api/v1/health/circuit-breaker | \
  jq '{hits: .cache_hits, misses: .cache_misses, ratio: (.cache_hits / (.cache_hits + .cache_misses))}'
```

**Causes**:
- Cache size limit reached (1000 entries)
- Frequent unique key requests
- Cache eviction (LRU)

**Solution**:
- Consider increasing cache size in `redis_circuit_breaker.py`
- Review request patterns

### Failed Recovery Attempts

**Symptoms**: Circuit keeps reopening during recovery.

**Diagnosis**:
```bash
# Monitor circuit state transitions
watch -n 1 'curl -s http://localhost:8000/api/v1/health/circuit-breaker | jq .state'
```

**Causes**:
- Redis not fully recovered
- Network instability
- Redis under heavy load

**Solution**:
- Increase `recovery_timeout` (default 60s)
- Increase `half_open_max_calls` (default 3)
- Check Redis logs: `docker logs redis`

---

## Automated Test Script

Save this as `test_circuit_breaker.sh`:

```bash
#!/bin/bash
set -e

API_URL="http://localhost:8000"
HEALTH_URL="$API_URL/api/v1/health"

echo "🧪 Redis Circuit Breaker Test Suite"
echo "===================================="

# Test 1: Initial State
echo -e "\n📋 Test 1: Checking initial state..."
state=$(curl -s $HEALTH_URL/circuit-breaker | jq -r '.state')
if [ "$state" = "closed" ]; then
    echo "✅ Circuit is CLOSED (normal operation)"
else
    echo "❌ Circuit is not CLOSED (expected: closed, got: $state)"
    exit 1
fi

# Test 2: Stop Redis
echo -e "\n📋 Test 2: Simulating Redis failure..."
docker stop redis || docker-compose stop redis
sleep 2

# Test 3: Trigger circuit opening
echo -e "\n📋 Test 3: Triggering circuit breaker..."
for i in {1..6}; do
    curl -s $HEALTH_URL/redis > /dev/null
    echo "  Request $i completed"
done

state=$(curl -s $HEALTH_URL/circuit-breaker | jq -r '.state')
if [ "$state" = "open" ]; then
    echo "✅ Circuit opened after failures"
else
    echo "⚠️  Circuit state: $state (expected: open)"
fi

# Test 4: Verify degraded mode
echo -e "\n📋 Test 4: Verifying degraded mode..."
degraded=$(curl -s $HEALTH_URL/redis | jq -r '.degraded_mode')
if [ "$degraded" = "true" ]; then
    echo "✅ System running in degraded mode"
else
    echo "❌ Expected degraded_mode: true, got: $degraded"
fi

# Test 5: Start Redis
echo -e "\n📋 Test 5: Restarting Redis..."
docker start redis || docker-compose start redis
sleep 5

# Test 6: Wait for recovery
echo -e "\n📋 Test 6: Waiting for recovery timeout (60s)..."
sleep 60

# Test 7: Verify recovery
echo -e "\n📋 Test 7: Verifying circuit recovery..."
curl -s $HEALTH_URL/redis > /dev/null
sleep 1
curl -s $HEALTH_URL/redis > /dev/null
sleep 1
curl -s $HEALTH_URL/redis > /dev/null

state=$(curl -s $HEALTH_URL/circuit-breaker | jq -r '.state')
if [ "$state" = "closed" ] || [ "$state" = "half_open" ]; then
    echo "✅ Circuit recovering (state: $state)"
else
    echo "⚠️  Circuit state: $state"
fi

echo -e "\n📊 Final Metrics:"
curl -s $HEALTH_URL/circuit-breaker | jq '{
  state,
  total_calls,
  successful_calls,
  failed_calls,
  fallback_calls,
  cache_hits,
  cache_misses
}'

echo -e "\n✅ Circuit breaker test suite completed!"
```

Make executable and run:
```bash
chmod +x test_circuit_breaker.sh
./test_circuit_breaker.sh
```

---

## Configuration

Circuit breaker can be configured in `redis_circuit_breaker.py`:

```python
RedisCircuitBreaker(
    failure_threshold=5,      # Open circuit after 5 failures
    recovery_timeout=60,      # Attempt recovery after 60 seconds
    half_open_max_calls=3     # Allow 3 test calls in HALF_OPEN
)
```

---

## Success Metrics

After testing, verify:

- ✅ Circuit opens after failure threshold
- ✅ Circuit closes after successful recovery
- ✅ Fallback cache works correctly
- ✅ System remains available during Redis outages
- ✅ Automatic recovery within 60 seconds
- ✅ Metrics accurately track all operations
- ✅ Health endpoints return correct status

---

**Last Updated**: November 19, 2025
**Version**: 1.0.0
