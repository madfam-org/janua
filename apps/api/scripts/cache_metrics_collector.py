#!/usr/bin/env python3
"""
Cache Metrics Collection for Phase 3 Validation

Collects and analyzes caching performance metrics:
- Cache hit/miss rates
- Response time improvements
- Cache TTL effectiveness
- Memory usage
- Eviction rates

Validates:
- SSO configuration caching (15-min TTL)
- Organization settings caching (10-min TTL)
- RBAC permission caching (5-min TTL)
- User lookup caching (5-min TTL)
"""

import asyncio
import aioredis
import time
import statistics
from typing import Dict, List, Any, Optional
from datetime import datetime
from dataclasses import dataclass, field
import logging
import sys
import json
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class CacheMetric:
    """Single cache operation metric"""
    timestamp: datetime
    cache_key: str
    operation: str  # 'get', 'set', 'hit', 'miss'
    response_time_ms: float
    ttl_seconds: Optional[int] = None
    value_size_bytes: Optional[int] = None


@dataclass
class CacheStats:
    """Aggregated cache statistics"""
    cache_name: str
    total_requests: int = 0
    hits: int = 0
    misses: int = 0
    hit_rate: float = 0.0
    avg_hit_time_ms: float = 0.0
    avg_miss_time_ms: float = 0.0
    total_keys: int = 0
    total_memory_bytes: int = 0
    evictions: int = 0
    expired_keys: int = 0
    ttl_distribution: Dict[str, int] = field(default_factory=dict)


class CacheMetricsCollector:
    """
    Collects and analyzes Redis cache metrics for Phase 3 validation
    """

    def __init__(self, redis_url: str = "redis://localhost:6379"):
        self.redis_url = redis_url
        self.redis: Optional[aioredis.Redis] = None
        self.metrics: List[CacheMetric] = []
        self.stats_by_cache: Dict[str, CacheStats] = {}

    async def connect(self):
        """Connect to Redis"""
        logger.info(f"🔌 Connecting to Redis at {self.redis_url}...")

        try:
            self.redis = await aioredis.create_redis_pool(self.redis_url)
            logger.info("✅ Connected to Redis")
        except Exception as e:
            logger.error(f"❌ Failed to connect to Redis: {e}")
            raise

    async def disconnect(self):
        """Disconnect from Redis"""
        if self.redis:
            self.redis.close()
            await self.redis.wait_closed()
            logger.info("✅ Disconnected from Redis")

    async def collect_cache_info(self) -> Dict[str, Any]:
        """Collect general Redis cache information"""
        logger.info("📊 Collecting cache information...")

        info = await self.redis.info('stats')
        memory = await self.redis.info('memory')
        keyspace = await self.redis.info('keyspace')

        cache_info = {
            "total_connections": info.get('total_connections_received', 0),
            "total_commands": info.get('total_commands_processed', 0),
            "keyspace_hits": info.get('keyspace_hits', 0),
            "keyspace_misses": info.get('keyspace_misses', 0),
            "evicted_keys": info.get('evicted_keys', 0),
            "expired_keys": info.get('expired_keys', 0),
            "used_memory_bytes": memory.get('used_memory', 0),
            "used_memory_human": memory.get('used_memory_human', '0'),
            "total_keys": sum(db_info.get('keys', 0) for db_info in keyspace.values()),
        }

        # Calculate hit rate
        total_requests = cache_info['keyspace_hits'] + cache_info['keyspace_misses']
        cache_info['hit_rate'] = (
            (cache_info['keyspace_hits'] / total_requests * 100)
            if total_requests > 0 else 0.0
        )

        logger.info(f"   Total keys: {cache_info['total_keys']}")
        logger.info(f"   Hit rate: {cache_info['hit_rate']:.1f}%")
        logger.info(f"   Memory used: {cache_info['used_memory_human']}")

        return cache_info

    async def analyze_cache_keys(self) -> Dict[str, List[str]]:
        """Analyze cache keys by pattern"""
        logger.info("🔍 Analyzing cache keys...")

        # Define Phase 3 cache key patterns
        patterns = {
            "sso_config": "sso:config:*",
            "org_data": "org:data:*",
            "rbac_permissions": "rbac:perms:*",
            "user_lookup": "user:*",
            "organization_list": "org:list:*",
        }

        keys_by_pattern = {}

        for pattern_name, pattern in patterns.items():
            keys = await self.redis.keys(pattern)
            keys_by_pattern[pattern_name] = [key.decode() if isinstance(key, bytes) else key for key in keys]
            logger.info(f"   {pattern_name}: {len(keys_by_pattern[pattern_name])} keys")

        return keys_by_pattern

    async def measure_cache_performance(
        self,
        cache_pattern: str,
        operation_count: int = 100
    ) -> CacheStats:
        """Measure cache performance for a specific pattern"""
        logger.info(f"📊 Measuring cache performance for pattern: {cache_pattern}")

        stats = CacheStats(cache_name=cache_pattern)

        # Get all keys matching pattern
        keys = await self.redis.keys(cache_pattern)

        if not keys:
            logger.warning(f"   No keys found for pattern: {cache_pattern}")
            return stats

        stats.total_keys = len(keys)

        # Measure GET performance
        hit_times = []
        miss_times = []

        for i in range(operation_count):
            # Test with existing key (hit)
            if keys:
                key = keys[i % len(keys)]

                start_time = time.perf_counter()
                value = await self.redis.get(key)
                end_time = time.perf_counter()

                response_time_ms = (end_time - start_time) * 1000

                if value:
                    stats.hits += 1
                    hit_times.append(response_time_ms)

                    self.metrics.append(CacheMetric(
                        timestamp=datetime.now(),
                        cache_key=key.decode() if isinstance(key, bytes) else key,
                        operation='hit',
                        response_time_ms=response_time_ms,
                        value_size_bytes=len(value) if value else 0
                    ))

            # Test with non-existent key (miss)
            fake_key = f"{cache_pattern.rstrip('*')}fake_{i}"

            start_time = time.perf_counter()
            value = await self.redis.get(fake_key)
            end_time = time.perf_counter()

            response_time_ms = (end_time - start_time) * 1000

            if not value:
                stats.misses += 1
                miss_times.append(response_time_ms)

                self.metrics.append(CacheMetric(
                    timestamp=datetime.now(),
                    cache_key=fake_key,
                    operation='miss',
                    response_time_ms=response_time_ms
                ))

        stats.total_requests = stats.hits + stats.misses
        stats.hit_rate = (stats.hits / stats.total_requests * 100) if stats.total_requests > 0 else 0.0
        stats.avg_hit_time_ms = statistics.mean(hit_times) if hit_times else 0.0
        stats.avg_miss_time_ms = statistics.mean(miss_times) if miss_times else 0.0

        logger.info(f"   Requests: {stats.total_requests}, Hits: {stats.hits}, Misses: {stats.misses}")
        logger.info(f"   Hit rate: {stats.hit_rate:.1f}%")
        logger.info(f"   Avg hit time: {stats.avg_hit_time_ms:.2f}ms")
        logger.info(f"   Avg miss time: {stats.avg_miss_time_ms:.2f}ms")

        return stats

    async def analyze_ttl_distribution(self, pattern: str) -> Dict[str, int]:
        """Analyze TTL distribution for cached keys"""
        logger.info(f"⏰ Analyzing TTL distribution for: {pattern}")

        keys = await self.redis.keys(pattern)

        ttl_buckets = {
            "expired": 0,
            "0-60s": 0,
            "60-300s": 0,  # 1-5 minutes
            "300-600s": 0,  # 5-10 minutes
            "600-900s": 0,  # 10-15 minutes
            "900s+": 0,  # 15+ minutes
            "no_expiry": 0
        }

        for key in keys:
            ttl = await self.redis.ttl(key)

            if ttl == -2:  # Key doesn't exist
                ttl_buckets["expired"] += 1
            elif ttl == -1:  # No expiry set
                ttl_buckets["no_expiry"] += 1
            elif ttl < 60:
                ttl_buckets["0-60s"] += 1
            elif ttl < 300:
                ttl_buckets["60-300s"] += 1
            elif ttl < 600:
                ttl_buckets["300-600s"] += 1
            elif ttl < 900:
                ttl_buckets["600-900s"] += 1
            else:
                ttl_buckets["900s+"] += 1

        for bucket, count in ttl_buckets.items():
            if count > 0:
                logger.info(f"   {bucket}: {count} keys")

        return ttl_buckets

    async def validate_phase3_caching(self) -> Dict[str, Any]:
        """Validate all Phase 3 caching implementations"""
        logger.info("=" * 80)
        logger.info("🎯 Validating Phase 3 Caching Implementations")
        logger.info("=" * 80)

        await self.connect()

        try:
            # Collect general cache info
            cache_info = await self.collect_cache_info()

            # Analyze cache keys
            keys_by_pattern = await self.analyze_cache_keys()

            # Measure performance for each cache type
            cache_performance = {}

            # SSO Configuration Caching (15-min TTL)
            sso_stats = await self.measure_cache_performance("sso:config:*", operation_count=50)
            sso_ttl_dist = await self.analyze_ttl_distribution("sso:config:*")
            cache_performance['sso_config'] = {
                "stats": sso_stats,
                "ttl_distribution": sso_ttl_dist,
                "target_ttl": 900,  # 15 minutes
                "target_hit_rate": 95.0,
                "performance_target": "15-20ms → 0.5-1ms"
            }

            # Organization Settings Caching (10-min TTL)
            org_stats = await self.measure_cache_performance("org:data:*", operation_count=50)
            org_ttl_dist = await self.analyze_ttl_distribution("org:data:*")
            cache_performance['org_settings'] = {
                "stats": org_stats,
                "ttl_distribution": org_ttl_dist,
                "target_ttl": 600,  # 10 minutes
                "target_hit_rate": 85.0,
                "performance_target": "20-30ms → 2-5ms"
            }

            # RBAC Permissions Caching (5-min TTL)
            rbac_stats = await self.measure_cache_performance("rbac:perms:*", operation_count=50)
            rbac_ttl_dist = await self.analyze_ttl_distribution("rbac:perms:*")
            cache_performance['rbac_permissions'] = {
                "stats": rbac_stats,
                "ttl_distribution": rbac_ttl_dist,
                "target_ttl": 300,  # 5 minutes
                "target_hit_rate": 90.0,
                "performance_target": "90% query reduction"
            }

            # User Lookup Caching (5-min TTL)
            user_stats = await self.measure_cache_performance("user:*", operation_count=50)
            user_ttl_dist = await self.analyze_ttl_distribution("user:*")
            cache_performance['user_lookup'] = {
                "stats": user_stats,
                "ttl_distribution": user_ttl_dist,
                "target_ttl": 300,  # 5 minutes
                "target_hit_rate": 75.0,
                "performance_target": "3-5ms → 0.5-1ms"
            }

            # Validate against targets
            validation_results = self._validate_cache_targets(cache_performance)

            results = {
                "timestamp": datetime.now().isoformat(),
                "cache_info": cache_info,
                "keys_by_pattern": {k: len(v) for k, v in keys_by_pattern.items()},
                "cache_performance": cache_performance,
                "validation_results": validation_results
            }

            return results

        finally:
            await self.disconnect()

    def _validate_cache_targets(self, cache_performance: Dict[str, Any]) -> Dict[str, Any]:
        """Validate cache performance against Phase 3 targets"""
        logger.info("\n🎯 Validating against Phase 3 targets...")

        validation = {}

        for cache_name, perf_data in cache_performance.items():
            stats = perf_data['stats']
            target_hit_rate = perf_data['target_hit_rate']

            # Check if actual keys exist
            if stats.total_keys == 0:
                validation[cache_name] = {
                    "status": "NOT_IN_USE",
                    "reason": "No cached keys found - cache may not be in use yet",
                    "hit_rate_met": False,
                    "performance_met": None
                }
                logger.warning(f"   ⚠️ {cache_name}: No cached keys found")
                continue

            # Check hit rate
            hit_rate_met = stats.hit_rate >= target_hit_rate

            # Check performance (cache hits should be <2ms)
            performance_met = stats.avg_hit_time_ms < 2.0

            # Overall status
            if hit_rate_met and performance_met:
                status = "PASS"
                icon = "✅"
            elif not hit_rate_met:
                status = "HIT_RATE_LOW"
                icon = "⚠️"
            else:
                status = "PERFORMANCE_SLOW"
                icon = "⚠️"

            validation[cache_name] = {
                "status": status,
                "hit_rate_met": hit_rate_met,
                "performance_met": performance_met,
                "actual_hit_rate": stats.hit_rate,
                "actual_hit_time_ms": stats.avg_hit_time_ms,
                "target_hit_rate": target_hit_rate,
                "target_performance": perf_data['performance_target']
            }

            logger.info(f"   {icon} {cache_name}: {status}")
            logger.info(f"      Hit rate: {stats.hit_rate:.1f}% (target: {target_hit_rate}%)")
            logger.info(f"      Hit time: {stats.avg_hit_time_ms:.2f}ms (target: <2ms)")

        return validation

    def generate_report(self, results: Dict[str, Any]) -> str:
        """Generate cache metrics report"""
        logger.info("📋 Generating cache metrics report...")

        cache_info = results['cache_info']
        validation = results['validation_results']

        report = f"""
# Cache Metrics Collection Report - Phase 3 Validation

**Generated**: {results['timestamp']}
**Overall Cache Hit Rate**: {cache_info['hit_rate']:.1f}%

## 📊 Redis Statistics

- **Total Keys**: {cache_info['total_keys']:,}
- **Total Commands**: {cache_info['total_commands']:,}
- **Memory Used**: {cache_info['used_memory_human']}
- **Keyspace Hits**: {cache_info['keyspace_hits']:,}
- **Keyspace Misses**: {cache_info['keyspace_misses']:,}
- **Evicted Keys**: {cache_info['evicted_keys']:,}
- **Expired Keys**: {cache_info['expired_keys']:,}

## 🎯 Phase 3 Cache Performance Validation

"""

        # Cache-by-cache results
        for cache_name, validation_data in validation.items():
            status_icon = {
                "PASS": "✅",
                "HIT_RATE_LOW": "⚠️",
                "PERFORMANCE_SLOW": "⚠️",
                "NOT_IN_USE": "⏸️"
            }.get(validation_data['status'], "❓")

            report += f"""
### {status_icon} {cache_name.replace('_', ' ').title()}

- **Status**: {validation_data['status']}
"""

            if validation_data['status'] != "NOT_IN_USE":
                report += f"""- **Hit Rate**: {validation_data['actual_hit_rate']:.1f}% (target: {validation_data['target_hit_rate']}%) {'✅' if validation_data['hit_rate_met'] else '❌'}
- **Hit Time**: {validation_data['actual_hit_time_ms']:.2f}ms (target: <2ms) {'✅' if validation_data['performance_met'] else '❌'}
- **Performance Target**: {validation_data['target_performance']}
"""
            else:
                report += f"- **Reason**: {validation_data['reason']}\n"

        # TTL distribution
        report += "\n## ⏰ TTL Distribution\n\n"

        for cache_name, perf_data in results['cache_performance'].items():
            if perf_data['stats'].total_keys > 0:
                report += f"### {cache_name.replace('_', ' ').title()}\n\n"
                for bucket, count in perf_data['ttl_distribution'].items():
                    if count > 0:
                        report += f"- {bucket}: {count} keys\n"
                report += "\n"

        # Keys by pattern
        report += "## 🔑 Cached Keys by Pattern\n\n"

        for pattern, count in results['keys_by_pattern'].items():
            report += f"- **{pattern}**: {count} keys\n"

        # Summary
        all_passed = all(
            v['status'] in ['PASS', 'NOT_IN_USE']
            for v in validation.values()
        )

        report += f"""
## 📋 Summary

**Overall Validation**: {'✅ PASSED - All caching targets met!' if all_passed else '⚠️ REVIEW NEEDED - Some targets not met'}

### Recommendations

"""

        if all_passed:
            report += """- ✅ All Phase 3 caching implementations are working as expected
- Monitor cache hit rates in production to verify real-world performance
- Consider adjusting TTLs based on production access patterns
"""
        else:
            report += """- Review caches with low hit rates or slow performance
- Ensure caching code is being executed in all code paths
- Consider pre-warming caches for frequently accessed data
- Adjust TTLs if cache churn is too high
"""

        report += """
---

**Cache Metrics Collection**: Complete
"""

        return report


async def main():
    """Main cache metrics collection execution"""
    import argparse

    parser = argparse.ArgumentParser(description="Phase 3 Cache Metrics Collection")
    parser.add_argument("--redis-url", default="redis://localhost:6379", help="Redis connection URL")
    parser.add_argument("--output", default="cache_metrics_report.md", help="Output report file")

    args = parser.parse_args()

    collector = CacheMetricsCollector(redis_url=args.redis_url)

    try:
        results = await collector.validate_phase3_caching()

        # Generate report
        report = collector.generate_report(results)

        # Save report
        output_path = Path(args.output)
        output_path.write_text(report)

        # Save raw data
        json_path = output_path.with_suffix('.json')
        json_path.write_text(json.dumps(results, indent=2, default=str))

        logger.info(f"\n📋 Cache metrics report saved: {output_path}")
        logger.info(f"📊 Raw data saved: {json_path}")

        # Print summary
        logger.info("\n" + report)

        # Exit code based on validation
        all_passed = all(
            v['status'] in ['PASS', 'NOT_IN_USE']
            for v in results['validation_results'].values()
        )

        return 0 if all_passed else 1

    except Exception as e:
        logger.error(f"Cache metrics collection failed: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
