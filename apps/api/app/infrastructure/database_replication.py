"""
Database Replication Management
Handles read/write splitting, failover, and monitoring for PostgreSQL replication
"""

import asyncio
import random
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
import asyncpg
import structlog
from app.config import settings

logger = structlog.get_logger()


class DatabaseRole(Enum):
    """Database server roles"""
    PRIMARY = "primary"
    REPLICA = "replica"
    UNKNOWN = "unknown"


class ConnectionType(Enum):
    """Connection types for routing"""
    READ = "read"
    WRITE = "write"


@dataclass
class DatabaseServer:
    """Database server configuration"""
    host: str
    port: int
    database: str
    username: str
    password: str
    role: DatabaseRole = DatabaseRole.UNKNOWN
    weight: int = 100
    max_connections: int = 25
    is_healthy: bool = True
    last_health_check: Optional[datetime] = None
    lag_bytes: int = 0
    lag_seconds: float = 0.0


@dataclass
class ReplicationStatus:
    """Replication status information"""
    primary_server: str
    replica_servers: List[str]
    total_lag_bytes: int
    max_lag_seconds: float
    healthy_replicas: int
    unhealthy_replicas: int
    last_updated: datetime


class DatabaseReplicationManager:
    """Manages database replication, failover, and load balancing"""

    def __init__(self):
        self.servers: Dict[str, DatabaseServer] = {}
        self.connection_pools: Dict[str, asyncpg.Pool] = {}
        self.health_check_interval = 30  # seconds
        self.max_lag_threshold = 10 * 1024 * 1024  # 10MB
        self.max_lag_seconds_threshold = 30.0
        self.failover_in_progress = False

        # Initialize servers from configuration
        self._initialize_servers()

    def _initialize_servers(self):
        """Initialize database servers from configuration"""
        # Primary server
        primary = DatabaseServer(
            host=settings.DATABASE_HOST,
            port=settings.DATABASE_PORT,
            database=settings.DATABASE_NAME,
            username=settings.DATABASE_USER,
            password=settings.DATABASE_PASSWORD,
            role=DatabaseRole.PRIMARY,
            weight=0  # Primary doesn't participate in read load balancing
        )
        self.servers["primary"] = primary

        # Read replicas (configured via environment variables)
        replica_configs = self._get_replica_configs()
        for i, replica_config in enumerate(replica_configs):
            replica_name = f"replica_{i+1}"
            replica = DatabaseServer(
                host=replica_config["host"],
                port=replica_config["port"],
                database=replica_config["database"],
                username=replica_config["username"],
                password=replica_config["password"],
                role=DatabaseRole.REPLICA,
                weight=replica_config.get("weight", 100)
            )
            self.servers[replica_name] = replica

    def _get_replica_configs(self) -> List[Dict]:
        """Get replica configurations from environment"""
        replicas = []

        # Support multiple replicas via environment variables
        for i in range(1, 10):  # Support up to 9 replicas
            host_key = f"DATABASE_REPLICA_{i}_HOST"
            if hasattr(settings, host_key) and getattr(settings, host_key):
                replica_config = {
                    "host": getattr(settings, host_key),
                    "port": getattr(settings, f"DATABASE_REPLICA_{i}_PORT", 5432),
                    "database": getattr(settings, f"DATABASE_REPLICA_{i}_NAME", settings.DATABASE_NAME),
                    "username": getattr(settings, f"DATABASE_REPLICA_{i}_USER", settings.DATABASE_USER),
                    "password": getattr(settings, f"DATABASE_REPLICA_{i}_PASSWORD", settings.DATABASE_PASSWORD),
                    "weight": getattr(settings, f"DATABASE_REPLICA_{i}_WEIGHT", 100),
                }
                replicas.append(replica_config)

        return replicas

    async def initialize_connections(self):
        """Initialize connection pools for all servers"""
        for server_name, server in self.servers.items():
            try:
                dsn = f"postgresql://{server.username}:{server.password}@{server.host}:{server.port}/{server.database}"

                pool = await asyncpg.create_pool(
                    dsn,
                    min_size=5,
                    max_size=server.max_connections,
                    max_queries=50000,
                    max_inactive_connection_lifetime=300.0,
                    command_timeout=60.0,
                    server_settings={
                        'application_name': f'janua_{server_name}',
                        'tcp_keepalives_idle': '600',
                        'tcp_keepalives_interval': '30',
                        'tcp_keepalives_count': '3',
                    }
                )

                self.connection_pools[server_name] = pool
                logger.info("Database connection pool created", server=server_name, role=server.role.value)

            except Exception as e:
                logger.error("Failed to create connection pool", server=server_name, error=str(e))
                server.is_healthy = False

        # Start health check task
        asyncio.create_task(self._health_check_loop())

    async def get_connection(self, connection_type: ConnectionType = ConnectionType.READ) -> Tuple[asyncpg.Connection, str]:
        """Get database connection based on type"""
        if connection_type == ConnectionType.WRITE:
            return await self._get_write_connection()
        else:
            return await self._get_read_connection()

    async def _get_write_connection(self) -> Tuple[asyncpg.Connection, str]:
        """Get connection to primary database for writes"""
        primary_server = self.servers["primary"]

        if not primary_server.is_healthy:
            if not self.failover_in_progress:
                asyncio.create_task(self._handle_primary_failure())
            raise Exception("Primary database is unavailable")

        pool = self.connection_pools.get("primary")
        if not pool:
            raise Exception("Primary database connection pool not available")

        connection = await pool.acquire()
        return connection, "primary"

    async def _get_read_connection(self) -> Tuple[asyncpg.Connection, str]:
        """Get connection to read replica (or primary if no replicas available)"""
        # Get healthy replicas
        healthy_replicas = [
            (name, server) for name, server in self.servers.items()
            if server.role == DatabaseRole.REPLICA and server.is_healthy
        ]

        if not healthy_replicas:
            logger.warning("No healthy read replicas available, falling back to primary")
            return await self._get_write_connection()

        # Select replica based on weights
        selected_server = self._select_weighted_replica(healthy_replicas)
        pool = self.connection_pools.get(selected_server)

        if not pool:
            logger.warning("Selected replica pool not available", server=selected_server)
            return await self._get_write_connection()

        connection = await pool.acquire()
        return connection, selected_server

    def _select_weighted_replica(self, healthy_replicas: List[Tuple[str, DatabaseServer]]) -> str:
        """Select replica based on weights and lag"""
        if len(healthy_replicas) == 1:
            return healthy_replicas[0][0]

        # Calculate weights considering lag
        weighted_replicas = []
        for name, server in healthy_replicas:
            # Reduce weight based on lag
            lag_penalty = min(50, server.lag_seconds * 2)  # Max 50% penalty
            effective_weight = max(1, server.weight - lag_penalty)
            weighted_replicas.append((name, effective_weight))

        # Weighted random selection
        total_weight = sum(weight for _, weight in weighted_replicas)
        random_value = random.randint(1, total_weight)

        current_weight = 0
        for name, weight in weighted_replicas:
            current_weight += weight
            if current_weight >= random_value:
                return name

        # Fallback to first replica
        return healthy_replicas[0][0]

    async def release_connection(self, connection: asyncpg.Connection, server_name: str):
        """Release connection back to pool"""
        pool = self.connection_pools.get(server_name)
        if pool:
            await pool.release(connection)

    async def _health_check_loop(self):
        """Continuous health checking of database servers"""
        while True:
            try:
                await self._perform_health_checks()
                await asyncio.sleep(self.health_check_interval)
            except Exception as e:
                logger.error("Health check loop error", error=str(e))
                await asyncio.sleep(5)

    async def _perform_health_checks(self):
        """Perform health checks on all database servers"""
        tasks = []
        for server_name in self.servers.keys():
            task = asyncio.create_task(self._check_server_health(server_name))
            tasks.append(task)

        await asyncio.gather(*tasks, return_exceptions=True)

        # Update replication status
        await self._update_replication_status()

    async def _check_server_health(self, server_name: str):
        """Check health of individual server"""
        server = self.servers[server_name]
        pool = self.connection_pools.get(server_name)

        if not pool:
            server.is_healthy = False
            return

        try:
            async with pool.acquire() as connection:
                # Basic connectivity test
                await connection.execute("SELECT 1")

                # Check replication lag for replicas
                if server.role == DatabaseRole.REPLICA:
                    await self._check_replication_lag(connection, server)

                # Update health status
                server.is_healthy = True
                server.last_health_check = datetime.now()

                logger.debug("Health check passed", server=server_name)

        except Exception as e:
            server.is_healthy = False
            logger.warning("Health check failed", server=server_name, error=str(e))

    async def _check_replication_lag(self, connection: asyncpg.Connection, server: DatabaseServer):
        """Check replication lag for a replica server"""
        try:
            # Get current WAL position
            result = await connection.fetchrow(
                "SELECT pg_last_wal_receive_lsn(), pg_last_wal_replay_lsn(), "
                "EXTRACT(EPOCH FROM (now() - pg_last_xact_replay_timestamp())) AS lag_seconds"
            )

            if result:
                receive_lsn = result['pg_last_wal_receive_lsn']
                replay_lsn = result['pg_last_wal_replay_lsn']
                lag_seconds = result['lag_seconds'] or 0.0

                # Calculate byte lag (simplified)
                if receive_lsn and replay_lsn:
                    # This is a simplified calculation
                    server.lag_bytes = 0  # Would need more complex calculation
                else:
                    server.lag_bytes = 0

                server.lag_seconds = float(lag_seconds)

                # Check if lag is within acceptable limits
                if server.lag_seconds > self.max_lag_seconds_threshold:
                    logger.warning(
                        "High replication lag detected",
                        server=server.host,
                        lag_seconds=server.lag_seconds
                    )

        except Exception as e:
            logger.warning("Failed to check replication lag", server=server.host, error=str(e))

    async def _update_replication_status(self):
        """Update overall replication status"""
        primary_servers = [name for name, server in self.servers.items()
                          if server.role == DatabaseRole.PRIMARY]
        replica_servers = [name for name, server in self.servers.items()
                          if server.role == DatabaseRole.REPLICA]

        healthy_replicas = sum(1 for name in replica_servers
                              if self.servers[name].is_healthy)
        unhealthy_replicas = len(replica_servers) - healthy_replicas

        total_lag_bytes = sum(self.servers[name].lag_bytes
                             for name in replica_servers if self.servers[name].is_healthy)
        max_lag_seconds = max((self.servers[name].lag_seconds
                              for name in replica_servers if self.servers[name].is_healthy),
                             default=0.0)

        status = ReplicationStatus(
            primary_server=primary_servers[0] if primary_servers else "none",
            replica_servers=replica_servers,
            total_lag_bytes=total_lag_bytes,
            max_lag_seconds=max_lag_seconds,
            healthy_replicas=healthy_replicas,
            unhealthy_replicas=unhealthy_replicas,
            last_updated=datetime.now()
        )

        # Log status if there are issues
        if unhealthy_replicas > 0 or max_lag_seconds > self.max_lag_seconds_threshold:
            logger.warning(
                "Replication issues detected",
                healthy_replicas=healthy_replicas,
                unhealthy_replicas=unhealthy_replicas,
                max_lag_seconds=max_lag_seconds
            )

    async def _handle_primary_failure(self):
        """Handle primary database failure"""
        if self.failover_in_progress:
            return

        self.failover_in_progress = True
        logger.critical("Primary database failure detected, initiating failover procedures")

        try:
            # Find the best replica to promote
            best_replica = self._select_failover_candidate()

            if best_replica:
                logger.info("Promoting replica to primary", replica=best_replica)
                await self._promote_replica_to_primary(best_replica)
            else:
                logger.critical("No suitable replica found for failover")

        except Exception as e:
            logger.error("Failover procedure failed", error=str(e))

        finally:
            self.failover_in_progress = False

    def _select_failover_candidate(self) -> Optional[str]:
        """Select the best replica for failover"""
        healthy_replicas = [
            (name, server) for name, server in self.servers.items()
            if server.role == DatabaseRole.REPLICA and server.is_healthy
        ]

        if not healthy_replicas:
            return None

        # Select replica with lowest lag
        best_replica = min(healthy_replicas, key=lambda x: x[1].lag_seconds)
        return best_replica[0]

    async def _promote_replica_to_primary(self, replica_name: str):
        """Promote a replica to primary (requires manual intervention in most cases)"""
        replica_server = self.servers[replica_name]

        # This is a simplified promotion - in reality, this would involve:
        # 1. Stopping the replica
        # 2. Creating a trigger file or using pg_promote()
        # 3. Updating application configuration
        # 4. Redirecting write traffic

        logger.info(
            "Replica promotion initiated - manual intervention may be required",
            replica=replica_name,
            host=replica_server.host
        )

        # Update server role (this would normally be done after successful promotion)
        replica_server.role = DatabaseRole.PRIMARY

        # The old primary should be marked as unhealthy
        if "primary" in self.servers:
            self.servers["primary"].is_healthy = False

    async def get_replication_status(self) -> Dict[str, Any]:
        """Get current replication status"""
        primary_servers = [(name, server) for name, server in self.servers.items()
                          if server.role == DatabaseRole.PRIMARY]
        replica_servers = [(name, server) for name, server in self.servers.items()
                          if server.role == DatabaseRole.REPLICA]

        status = {
            "primary": {
                "server": primary_servers[0][0] if primary_servers else None,
                "healthy": primary_servers[0][1].is_healthy if primary_servers else False,
                "host": primary_servers[0][1].host if primary_servers else None,
            },
            "replicas": [
                {
                    "name": name,
                    "host": server.host,
                    "healthy": server.is_healthy,
                    "lag_seconds": server.lag_seconds,
                    "lag_bytes": server.lag_bytes,
                    "weight": server.weight,
                    "last_health_check": server.last_health_check.isoformat() if server.last_health_check else None
                }
                for name, server in replica_servers
            ],
            "summary": {
                "total_replicas": len(replica_servers),
                "healthy_replicas": sum(1 for _, server in replica_servers if server.is_healthy),
                "max_lag_seconds": max((server.lag_seconds for _, server in replica_servers), default=0.0),
                "failover_in_progress": self.failover_in_progress
            }
        }

        return status

    async def close_all_connections(self):
        """Close all database connection pools"""
        for server_name, pool in self.connection_pools.items():
            try:
                await pool.close()
                logger.info("Closed connection pool", server=server_name)
            except Exception as e:
                logger.error("Error closing connection pool", server=server_name, error=str(e))

        self.connection_pools.clear()


# Global instance
db_replication_manager = DatabaseReplicationManager()


# Context managers for database connections
class DatabaseConnection:
    """Context manager for database connections with automatic routing"""

    def __init__(self, connection_type: ConnectionType = ConnectionType.READ):
        self.connection_type = connection_type
        self.connection = None
        self.server_name = None

    async def __aenter__(self):
        self.connection, self.server_name = await db_replication_manager.get_connection(self.connection_type)
        return self.connection

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.connection and self.server_name:
            await db_replication_manager.release_connection(self.connection, self.server_name)


# Convenience functions
async def get_read_connection():
    """Get read connection context manager"""
    return DatabaseConnection(ConnectionType.READ)


async def get_write_connection():
    """Get write connection context manager"""
    return DatabaseConnection(ConnectionType.WRITE)


# Health check endpoint helper
async def get_database_replication_health() -> Dict[str, Any]:
    """Get database replication health for monitoring"""
    return await db_replication_manager.get_replication_status()