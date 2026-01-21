"""
Redis Cluster Management
High availability Redis with automatic failover and load balancing
"""

import asyncio
import json
import time
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
import redis.asyncio as redis
from redis.sentinel import Sentinel
import structlog

logger = structlog.get_logger()


class RedisNodeRole(Enum):
    """Redis node roles"""
    MASTER = "master"
    SLAVE = "slave"
    SENTINEL = "sentinel"


class RedisConnectionType(Enum):
    """Redis connection types"""
    READ = "read"
    WRITE = "write"
    PUBSUB = "pubsub"


@dataclass
class RedisNode:
    """Redis node configuration"""
    host: str
    port: int
    role: RedisNodeRole
    name: str = ""
    is_healthy: bool = True
    last_health_check: Optional[datetime] = None
    response_time_ms: float = 0.0
    memory_usage_mb: float = 0.0
    connections: int = 0
    ops_per_sec: float = 0.0


@dataclass
class RedisClusterStatus:
    """Redis cluster status information"""
    master_node: Optional[str]
    slave_nodes: List[str]
    sentinel_nodes: List[str]
    healthy_nodes: int
    unhealthy_nodes: int
    total_memory_mb: float
    total_ops_per_sec: float
    failover_in_progress: bool
    last_failover: Optional[datetime]
    last_updated: datetime


class RedisClusterManager:
    """Manages Redis cluster with sentinel-based failover"""

    def __init__(self, sentinel_hosts: List[Tuple[str, int]], master_name: str = "mymaster"):
        self.sentinel_hosts = sentinel_hosts
        self.master_name = master_name
        self.sentinel = None
        self.redis_pools: Dict[str, redis.ConnectionPool] = {}
        self.nodes: Dict[str, RedisNode] = {}
        self.health_check_interval = 30
        self.failover_timeout = 60
        self.max_retries = 3

        # Initialize sentinel
        self._initialize_sentinel()

    def _initialize_sentinel(self):
        """Initialize Redis Sentinel"""
        try:
            self.sentinel = Sentinel(
                self.sentinel_hosts,
                socket_timeout=0.5,
                socket_connect_timeout=0.5,
                socket_keepalive=True,
                socket_keepalive_options={},
                retry_on_timeout=True,
                health_check_interval=30
            )
            logger.info("Redis Sentinel initialized", hosts=self.sentinel_hosts)
        except Exception as e:
            logger.error("Failed to initialize Redis Sentinel", error=str(e))
            raise

    async def initialize_cluster(self):
        """Initialize Redis cluster connections"""
        try:
            # Get master and slave info from sentinel
            await self._discover_nodes()

            # Create connection pools
            await self._create_connection_pools()

            # Start health monitoring
            asyncio.create_task(self._health_check_loop())

            logger.info("Redis cluster initialized successfully")

        except Exception as e:
            logger.error("Failed to initialize Redis cluster", error=str(e))
            raise

    async def _discover_nodes(self):
        """Discover Redis nodes through Sentinel"""
        try:
            # Get master info
            master_info = self.sentinel.discover_master(self.master_name)
            if master_info:
                master_node = RedisNode(
                    host=master_info[0],
                    port=master_info[1],
                    role=RedisNodeRole.MASTER,
                    name=f"master_{master_info[0]}_{master_info[1]}"
                )
                self.nodes[master_node.name] = master_node

            # Get slave info
            slaves_info = self.sentinel.discover_slaves(self.master_name)
            for i, slave_info in enumerate(slaves_info):
                slave_node = RedisNode(
                    host=slave_info[0],
                    port=slave_info[1],
                    role=RedisNodeRole.SLAVE,
                    name=f"slave_{i}_{slave_info[0]}_{slave_info[1]}"
                )
                self.nodes[slave_node.name] = slave_node

            # Add sentinel nodes
            for i, (host, port) in enumerate(self.sentinel_hosts):
                sentinel_node = RedisNode(
                    host=host,
                    port=port,
                    role=RedisNodeRole.SENTINEL,
                    name=f"sentinel_{i}_{host}_{port}"
                )
                self.nodes[sentinel_node.name] = sentinel_node

            logger.info("Discovered Redis nodes", total_nodes=len(self.nodes))

        except Exception as e:
            logger.error("Failed to discover Redis nodes", error=str(e))
            raise

    async def _create_connection_pools(self):
        """Create connection pools for Redis nodes"""
        for node_name, node in self.nodes.items():
            if node.role == RedisNodeRole.SENTINEL:
                continue  # Skip sentinel nodes for regular connections

            try:
                pool = redis.ConnectionPool(
                    host=node.host,
                    port=node.port,
                    max_connections=50,
                    retry_on_timeout=True,
                    health_check_interval=30,
                    socket_keepalive=True,
                    socket_keepalive_options={},
                    decode_responses=True
                )
                self.redis_pools[node_name] = pool
                logger.debug("Created connection pool", node=node_name)

            except Exception as e:
                logger.error("Failed to create connection pool", node=node_name, error=str(e))
                node.is_healthy = False

    async def get_connection(self, connection_type: RedisConnectionType = RedisConnectionType.READ) -> redis.Redis:
        """Get Redis connection based on type"""
        if connection_type == RedisConnectionType.WRITE:
            return await self._get_master_connection()
        elif connection_type == RedisConnectionType.READ:
            return await self._get_read_connection()
        elif connection_type == RedisConnectionType.PUBSUB:
            return await self._get_pubsub_connection()
        else:
            raise ValueError(f"Unknown connection type: {connection_type}")

    async def _get_master_connection(self) -> redis.Redis:
        """Get connection to Redis master for writes"""
        try:
            master_redis = self.sentinel.master_for(
                self.master_name,
                socket_timeout=0.5,
                socket_connect_timeout=0.5,
                decode_responses=True
            )
            return master_redis
        except Exception as e:
            logger.error("Failed to get master connection", error=str(e))
            raise

    async def _get_read_connection(self) -> redis.Redis:
        """Get connection for reads (load balanced across slaves)"""
        try:
            # Try to get slave connection first
            slave_redis = self.sentinel.slave_for(
                self.master_name,
                socket_timeout=0.5,
                socket_connect_timeout=0.5,
                decode_responses=True
            )
            return slave_redis
        except Exception:
            # Fallback to master if no slaves available
            logger.warning("No slaves available, falling back to master for reads")
            return await self._get_master_connection()

    async def _get_pubsub_connection(self) -> redis.Redis:
        """Get connection for pub/sub operations"""
        # Use master for pub/sub to ensure message delivery
        return await self._get_master_connection()

    async def execute_command(self, command: str, *args, connection_type: RedisConnectionType = RedisConnectionType.READ, **kwargs) -> Any:
        """Execute Redis command with automatic retry and failover"""
        retries = 0
        last_error = None

        while retries < self.max_retries:
            try:
                redis_client = await self.get_connection(connection_type)
                result = await getattr(redis_client, command)(*args, **kwargs)
                return result

            except (redis.ConnectionError, redis.TimeoutError) as e:
                last_error = e
                retries += 1
                if retries < self.max_retries:
                    wait_time = 0.1 * (2 ** retries)  # Exponential backoff
                    logger.warning(
                        "Redis command failed, retrying",
                        command=command,
                        retry=retries,
                        wait_time=wait_time,
                        error=str(e)
                    )
                    await asyncio.sleep(wait_time)
                else:
                    logger.error("Redis command failed after all retries", command=command, error=str(e))

            except Exception as e:
                logger.error("Unexpected error executing Redis command", command=command, error=str(e))
                raise

        raise last_error

    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """Set a key-value pair"""
        try:
            if isinstance(value, (dict, list)):
                value = json.dumps(value)

            if ttl:
                return await self.execute_command("setex", key, ttl, value, connection_type=RedisConnectionType.WRITE)
            else:
                return await self.execute_command("set", key, value, connection_type=RedisConnectionType.WRITE)
        except Exception as e:
            logger.error("Failed to set key", key=key, error=str(e))
            return False

    async def get(self, key: str, decode_json: bool = False) -> Optional[Any]:
        """Get a value by key"""
        try:
            value = await self.execute_command("get", key, connection_type=RedisConnectionType.READ)
            if value and decode_json:
                try:
                    return json.loads(value)
                except json.JSONDecodeError:
                    return value
            return value
        except Exception as e:
            logger.error("Failed to get key", key=key, error=str(e))
            return None

    async def delete(self, *keys: str) -> int:
        """Delete one or more keys"""
        try:
            return await self.execute_command("delete", *keys, connection_type=RedisConnectionType.WRITE)
        except Exception as e:
            logger.error("Failed to delete keys", keys=keys, error=str(e))
            return 0

    async def exists(self, *keys: str) -> int:
        """Check if keys exist"""
        try:
            return await self.execute_command("exists", *keys, connection_type=RedisConnectionType.READ)
        except Exception as e:
            logger.error("Failed to check key existence", keys=keys, error=str(e))
            return 0

    async def expire(self, key: str, seconds: int) -> bool:
        """Set expiration time for a key"""
        try:
            return await self.execute_command("expire", key, seconds, connection_type=RedisConnectionType.WRITE)
        except Exception as e:
            logger.error("Failed to set expiration", key=key, error=str(e))
            return False

    async def incr(self, key: str, amount: int = 1) -> int:
        """Increment a key's value"""
        try:
            if amount == 1:
                return await self.execute_command("incr", key, connection_type=RedisConnectionType.WRITE)
            else:
                return await self.execute_command("incrby", key, amount, connection_type=RedisConnectionType.WRITE)
        except Exception as e:
            logger.error("Failed to increment key", key=key, error=str(e))
            return 0

    async def hset(self, name: str, mapping: Dict[str, Any]) -> int:
        """Set hash fields"""
        try:
            # Convert complex values to JSON
            serialized_mapping = {}
            for field, value in mapping.items():
                if isinstance(value, (dict, list)):
                    serialized_mapping[field] = json.dumps(value)
                else:
                    serialized_mapping[field] = value

            return await self.execute_command("hset", name, mapping=serialized_mapping, connection_type=RedisConnectionType.WRITE)
        except Exception as e:
            logger.error("Failed to set hash", name=name, error=str(e))
            return 0

    async def hget(self, name: str, key: str, decode_json: bool = False) -> Optional[Any]:
        """Get hash field value"""
        try:
            value = await self.execute_command("hget", name, key, connection_type=RedisConnectionType.READ)
            if value and decode_json:
                try:
                    return json.loads(value)
                except json.JSONDecodeError:
                    return value
            return value
        except Exception as e:
            logger.error("Failed to get hash field", name=name, key=key, error=str(e))
            return None

    async def hgetall(self, name: str, decode_json: bool = False) -> Dict[str, Any]:
        """Get all hash fields"""
        try:
            result = await self.execute_command("hgetall", name, connection_type=RedisConnectionType.READ)
            if not result:
                return {}

            if decode_json:
                decoded_result = {}
                for field, value in result.items():
                    try:
                        decoded_result[field] = json.loads(value)
                    except json.JSONDecodeError:
                        decoded_result[field] = value
                return decoded_result

            return result
        except Exception as e:
            logger.error("Failed to get all hash fields", name=name, error=str(e))
            return {}

    async def publish(self, channel: str, message: Any) -> int:
        """Publish message to a channel"""
        try:
            if isinstance(message, (dict, list)):
                message = json.dumps(message)

            return await self.execute_command("publish", channel, message, connection_type=RedisConnectionType.PUBSUB)
        except Exception as e:
            logger.error("Failed to publish message", channel=channel, error=str(e))
            return 0

    async def _health_check_loop(self):
        """Continuous health checking of Redis nodes"""
        while True:
            try:
                await self._perform_health_checks()
                await asyncio.sleep(self.health_check_interval)
            except Exception as e:
                logger.error("Health check loop error", error=str(e))
                await asyncio.sleep(5)

    async def _perform_health_checks(self):
        """Perform health checks on all Redis nodes"""
        for node_name, node in self.nodes.items():
            if node.role == RedisNodeRole.SENTINEL:
                continue  # Skip sentinel health checks for now

            await self._check_node_health(node_name, node)

    async def _check_node_health(self, node_name: str, node: RedisNode):
        """Check health of individual Redis node"""
        start_time = time.time()

        try:
            pool = self.redis_pools.get(node_name)
            if not pool:
                node.is_healthy = False
                return

            # Create temporary connection for health check
            redis_client = redis.Redis(connection_pool=pool)

            # Basic connectivity test
            await redis_client.ping()

            # Get node info
            info = await redis_client.info()

            # Update node statistics
            node.response_time_ms = (time.time() - start_time) * 1000
            node.memory_usage_mb = float(info.get('used_memory', 0)) / (1024 * 1024)
            node.connections = int(info.get('connected_clients', 0))
            node.ops_per_sec = float(info.get('instantaneous_ops_per_sec', 0))
            node.is_healthy = True
            node.last_health_check = datetime.now()

            logger.debug(
                "Health check passed",
                node=node_name,
                response_time_ms=node.response_time_ms,
                memory_mb=node.memory_usage_mb
            )

        except Exception as e:
            node.is_healthy = False
            logger.warning("Health check failed", node=node_name, error=str(e))

    async def get_cluster_status(self) -> RedisClusterStatus:
        """Get current cluster status"""
        master_nodes = [name for name, node in self.nodes.items()
                       if node.role == RedisNodeRole.MASTER]
        slave_nodes = [name for name, node in self.nodes.items()
                      if node.role == RedisNodeRole.SLAVE]
        sentinel_nodes = [name for name, node in self.nodes.items()
                         if node.role == RedisNodeRole.SENTINEL]

        healthy_nodes = sum(1 for node in self.nodes.values() if node.is_healthy)
        unhealthy_nodes = len(self.nodes) - healthy_nodes

        total_memory_mb = sum(node.memory_usage_mb for node in self.nodes.values()
                             if node.role != RedisNodeRole.SENTINEL)
        total_ops_per_sec = sum(node.ops_per_sec for node in self.nodes.values()
                               if node.role != RedisNodeRole.SENTINEL)

        # Check if failover is in progress (simplified check)
        failover_in_progress = False
        try:
            sentinel_info = self.sentinel.sentinel_masters()
            master_info = sentinel_info.get(self.master_name, {})
            failover_in_progress = master_info.get('flags', '').find('failover') != -1
        except Exception:
            pass

        return RedisClusterStatus(
            master_node=master_nodes[0] if master_nodes else None,
            slave_nodes=slave_nodes,
            sentinel_nodes=sentinel_nodes,
            healthy_nodes=healthy_nodes,
            unhealthy_nodes=unhealthy_nodes,
            total_memory_mb=total_memory_mb,
            total_ops_per_sec=total_ops_per_sec,
            failover_in_progress=failover_in_progress,
            last_failover=None,  # Would need to track this
            last_updated=datetime.now()
        )

    async def get_detailed_status(self) -> Dict[str, Any]:
        """Get detailed cluster status for monitoring"""
        cluster_status = await self.get_cluster_status()

        return {
            "cluster": {
                "master": cluster_status.master_node,
                "slaves": cluster_status.slave_nodes,
                "sentinels": cluster_status.sentinel_nodes,
                "healthy_nodes": cluster_status.healthy_nodes,
                "unhealthy_nodes": cluster_status.unhealthy_nodes,
                "total_memory_mb": cluster_status.total_memory_mb,
                "total_ops_per_sec": cluster_status.total_ops_per_sec,
                "failover_in_progress": cluster_status.failover_in_progress
            },
            "nodes": {
                name: {
                    "host": node.host,
                    "port": node.port,
                    "role": node.role.value,
                    "healthy": node.is_healthy,
                    "response_time_ms": node.response_time_ms,
                    "memory_usage_mb": node.memory_usage_mb,
                    "connections": node.connections,
                    "ops_per_sec": node.ops_per_sec,
                    "last_health_check": node.last_health_check.isoformat() if node.last_health_check else None
                }
                for name, node in self.nodes.items()
            }
        }

    async def close_all_connections(self):
        """Close all Redis connections"""
        for node_name, pool in self.redis_pools.items():
            try:
                await pool.disconnect()
                logger.info("Closed Redis connection pool", node=node_name)
            except Exception as e:
                logger.error("Error closing Redis connection pool", node=node_name, error=str(e))

        self.redis_pools.clear()


# Global Redis cluster manager instance
redis_cluster_manager: Optional[RedisClusterManager] = None


def initialize_redis_cluster(sentinel_hosts: List[Tuple[str, int]], master_name: str = "mymaster"):
    """Initialize global Redis cluster manager"""
    global redis_cluster_manager
    redis_cluster_manager = RedisClusterManager(sentinel_hosts, master_name)
    return redis_cluster_manager


async def get_redis_cluster() -> RedisClusterManager:
    """Get Redis cluster manager instance"""
    if not redis_cluster_manager:
        raise RuntimeError("Redis cluster not initialized")
    return redis_cluster_manager


# Health check endpoint helper
async def get_redis_cluster_health() -> Dict[str, Any]:
    """Get Redis cluster health for monitoring"""
    cluster = await get_redis_cluster()
    return await cluster.get_detailed_status()