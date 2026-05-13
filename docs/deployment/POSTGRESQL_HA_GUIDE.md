# PostgreSQL High Availability Guide

> [!IMPORTANT]
> MADFAM-ENCLII-FIRST-LEGACY-RAW v1: This document contains legacy raw infrastructure command examples.
> Routine production operations must use Enclii web, API, or CLI. Treat raw
> `kubectl`, `helm`, SSH, provider CLI/API, `docker exec`, and direct container
> access as platform bootstrap or documented break-glass only, and record any
> missing Enclii adapter gap.


This guide covers setting up PostgreSQL high availability for Janua production deployments.

## Overview

For production deployments requiring high availability, we recommend:

1. **Streaming Replication** - Primary/replica setup with automatic failover
2. **Connection Pooling** - PgBouncer for connection management
3. **Automated Backups** - Point-in-time recovery capability

## Architecture Options

### Option 1: Docker Compose with Replication (Simpler)

Best for: Single-server deployments, smaller teams

```yaml
# docker-compose.ha.yml
services:
  postgres-primary:
    image: postgres:15-alpine
    environment:
      POSTGRES_DB: janua
      POSTGRES_USER: janua
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
      POSTGRES_REPLICATION_USER: replicator
      POSTGRES_REPLICATION_PASSWORD: ${REPLICATION_PASSWORD}
    volumes:
      - postgres_primary:/var/lib/postgresql/data
      - ./init-replication.sh:/docker-entrypoint-initdb.d/init-replication.sh
    command: >
      postgres
      -c wal_level=replica
      -c max_wal_senders=3
      -c max_replication_slots=3
      -c hot_standby=on
      -c ssl=on
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U janua -d janua"]
      interval: 10s
      timeout: 5s
      retries: 5

  postgres-replica:
    image: postgres:15-alpine
    environment:
      PGUSER: replicator
      PGPASSWORD: ${REPLICATION_PASSWORD}
    volumes:
      - postgres_replica:/var/lib/postgresql/data
    command: >
      bash -c "
        rm -rf /var/lib/postgresql/data/*
        pg_basebackup -h postgres-primary -D /var/lib/postgresql/data -U replicator -vP -W
        touch /var/lib/postgresql/data/standby.signal
        exec postgres -c hot_standby=on
      "
    depends_on:
      postgres-primary:
        condition: service_healthy

  pgbouncer:
    image: edoburu/pgbouncer
    environment:
      DATABASE_URL: postgres://janua:${POSTGRES_PASSWORD}@postgres-primary:5432/janua
      POOL_MODE: transaction
      MAX_CLIENT_CONN: 1000
      DEFAULT_POOL_SIZE: 50
    ports:
      - "6432:5432"
    depends_on:
      - postgres-primary
```

### Option 2: Kubernetes with CloudNativePG (Recommended)

Best for: K8s deployments, auto-scaling, multi-node clusters

```yaml
# Install CloudNativePG operator first:
# kubectl apply -f https://raw.githubusercontent.com/cloudnative-pg/cloudnative-pg/release-1.21/releases/cnpg-1.21.0.yaml

apiVersion: postgresql.cnpg.io/v1
kind: Cluster
metadata:
  name: janua-postgres
  namespace: janua
spec:
  instances: 3  # 1 primary + 2 replicas

  # PostgreSQL configuration
  postgresql:
    parameters:
      max_connections: "200"
      shared_buffers: "256MB"
      effective_cache_size: "768MB"
      maintenance_work_mem: "64MB"
      checkpoint_completion_target: "0.9"
      wal_buffers: "16MB"
      default_statistics_target: "100"
      random_page_cost: "1.1"
      effective_io_concurrency: "200"
      min_wal_size: "1GB"
      max_wal_size: "4GB"
      max_worker_processes: "4"
      max_parallel_workers_per_gather: "2"
      max_parallel_workers: "4"
      max_parallel_maintenance_workers: "2"

  # Storage configuration
  storage:
    size: 100Gi
    storageClass: standard  # Adjust for your cluster

  # Backup configuration
  backup:
    barmanObjectStore:
      destinationPath: s3://janua-backups/postgres/
      s3Credentials:
        accessKeyId:
          name: s3-creds
          key: ACCESS_KEY_ID
        secretAccessKey:
          name: s3-creds
          key: SECRET_ACCESS_KEY
      wal:
        compression: gzip
        maxParallel: 4
    retentionPolicy: "30d"

  # Monitoring
  monitoring:
    enablePodMonitor: true

  # Enable SSL
  enableSuperuserAccess: true

  # Bootstrap from backup (for disaster recovery)
  # bootstrap:
  #   recovery:
  #     source: janua-postgres
```

### Option 3: Managed PostgreSQL (Simplest)

For teams that prefer managed services:

| Provider | Service | Features |
|----------|---------|----------|
| AWS | RDS PostgreSQL | Multi-AZ, Read Replicas, Automated Backups |
| GCP | Cloud SQL | HA, Cross-region replicas, Point-in-time recovery |
| Azure | Azure PostgreSQL Flexible | Zone redundant HA, Read replicas |
| DigitalOcean | Managed PostgreSQL | Standby nodes, Daily backups |

Connection string format:
```
DATABASE_URL=postgresql://janua:password@hostname:5432/janua?sslmode=require
```

## Connection Pooling with PgBouncer

### Why PgBouncer?

- Reduces connection overhead
- Handles connection storms
- Enables connection reuse across API instances

### Docker Compose Configuration

```yaml
pgbouncer:
  image: edoburu/pgbouncer:latest
  environment:
    DATABASE_URL: postgres://janua:${POSTGRES_PASSWORD}@postgres:5432/janua
    POOL_MODE: transaction
    MAX_CLIENT_CONN: 1000
    DEFAULT_POOL_SIZE: 50
    MIN_POOL_SIZE: 10
    RESERVE_POOL_SIZE: 5
    RESERVE_POOL_TIMEOUT: 3
    SERVER_RESET_QUERY: "DISCARD ALL"
    SERVER_IDLE_TIMEOUT: 600
    SERVER_LIFETIME: 3600
    AUTH_TYPE: scram-sha-256
  ports:
    - "6432:5432"
  healthcheck:
    test: ["CMD", "pg_isready", "-h", "localhost", "-p", "5432"]
    interval: 10s
    timeout: 5s
    retries: 5
```

### API Configuration for PgBouncer

Update `DATABASE_URL` to point to PgBouncer:

```bash
# Instead of direct PostgreSQL connection:
# DATABASE_URL=postgresql://janua:password@postgres:5432/janua

# Use PgBouncer:
DATABASE_URL=postgresql://janua:password@pgbouncer:6432/janua

# With SSL:
DATABASE_URL=postgresql://janua:password@pgbouncer:6432/janua?sslmode=require
```

## Failover Configuration

### Automatic Failover with Patroni

For Docker/VM deployments without K8s:

```yaml
# patroni.yml
scope: janua-cluster
namespace: /janua/
name: postgres-node-1

restapi:
  listen: 0.0.0.0:8008
  connect_address: postgres-node-1:8008

etcd3:
  hosts: etcd1:2379,etcd2:2379,etcd3:2379

bootstrap:
  dcs:
    ttl: 30
    loop_wait: 10
    retry_timeout: 10
    maximum_lag_on_failover: 1048576
    postgresql:
      use_pg_rewind: true
      parameters:
        wal_level: replica
        hot_standby: "on"
        max_wal_senders: 5
        max_replication_slots: 5
        wal_log_hints: "on"

postgresql:
  listen: 0.0.0.0:5432
  connect_address: postgres-node-1:5432
  data_dir: /var/lib/postgresql/data
  authentication:
    replication:
      username: replicator
      password: ${REPLICATION_PASSWORD}
    superuser:
      username: postgres
      password: ${POSTGRES_PASSWORD}
```

## Monitoring

### Key Metrics to Monitor

```yaml
# Prometheus alerts for PostgreSQL HA
groups:
  - name: postgresql-ha
    rules:
      - alert: PostgreSQLDown
        expr: pg_up == 0
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "PostgreSQL instance down"

      - alert: PostgreSQLReplicationLag
        expr: pg_replication_lag > 300
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "PostgreSQL replication lag > 5 minutes"

      - alert: PostgreSQLTooManyConnections
        expr: sum(pg_stat_activity_count) > 150
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "PostgreSQL connections exceeding threshold"

      - alert: PostgreSQLDeadlocks
        expr: increase(pg_stat_database_deadlocks[1m]) > 0
        labels:
          severity: warning
        annotations:
          summary: "PostgreSQL deadlock detected"
```

## Backup and Recovery

### Point-in-Time Recovery (PITR)

With WAL archiving enabled, you can recover to any point in time:

```bash
# Restore to specific timestamp
pg_restore --target-time="2024-01-11 14:30:00" \
  --target-action=promote \
  -d janua /backups/janua_latest.dump

# Or using recovery.conf (PostgreSQL < 12)
# Or recovery.signal + postgresql.conf (PostgreSQL >= 12)
restore_command = 'cp /archive/%f %p'
recovery_target_time = '2024-01-11 14:30:00'
recovery_target_action = 'promote'
```

### Backup Verification

```bash
# Verify backup integrity
pg_restore --list /backups/janua_latest.dump

# Test restore to temporary database
createdb janua_test
pg_restore -d janua_test /backups/janua_latest.dump
psql janua_test -c "SELECT COUNT(*) FROM users;"
dropdb janua_test
```

## Migration from Single Instance

### Step 1: Enable WAL Archiving

```sql
ALTER SYSTEM SET wal_level = 'replica';
ALTER SYSTEM SET max_wal_senders = 3;
ALTER SYSTEM SET max_replication_slots = 3;
-- Requires restart
```

### Step 2: Create Replication User

```sql
CREATE USER replicator WITH REPLICATION ENCRYPTED PASSWORD 'secure_password';
```

### Step 3: Configure pg_hba.conf

```
# Allow replication connections
host replication replicator 0.0.0.0/0 scram-sha-256
```

### Step 4: Set Up Replica

```bash
# On replica server
pg_basebackup -h primary-host -D /var/lib/postgresql/data -U replicator -vP -W -R
```

### Step 5: Verify Replication

```sql
-- On primary
SELECT * FROM pg_stat_replication;

-- On replica
SELECT * FROM pg_stat_wal_receiver;
```

## Recommended Configuration

For Janua production with ~1000 daily active users:

| Setting | Value | Reason |
|---------|-------|--------|
| `max_connections` | 200 | With PgBouncer, API needs fewer direct connections |
| `shared_buffers` | 25% of RAM | Standard recommendation |
| `effective_cache_size` | 75% of RAM | Helps query planner |
| `work_mem` | 64MB | Good for complex queries |
| `maintenance_work_mem` | 256MB | Speeds up VACUUM, CREATE INDEX |
| `wal_level` | replica | Required for HA |
| `synchronous_commit` | on | Data safety (can be 'off' for performance) |

## Troubleshooting

### Replica Not Syncing

```sql
-- Check replication status
SELECT * FROM pg_stat_replication;

-- Check for conflicts
SELECT * FROM pg_stat_database_conflicts;
```

### Connection Pool Exhaustion

```bash
# Check PgBouncer stats
psql -h pgbouncer -p 6432 -U janua pgbouncer -c "SHOW POOLS;"

# Increase pool size if needed
DEFAULT_POOL_SIZE=100
```

### Split Brain Prevention

- Always use odd number of nodes (1, 3, 5)
- Configure quorum-based failover
- Use fencing mechanisms in production

## Resources

- [PostgreSQL Replication Documentation](https://www.postgresql.org/docs/current/high-availability.html)
- [CloudNativePG Documentation](https://cloudnative-pg.io/documentation/)
- [Patroni Documentation](https://patroni.readthedocs.io/)
- [PgBouncer Documentation](https://www.pgbouncer.org/)
