#!/usr/bin/env python3
"""
Database Query Monitoring for Phase 3 Validation

Monitors database queries to validate N+1 fixes:
- Tracks query count per endpoint
- Identifies N+1 patterns
- Compares before/after optimizations
- Generates query analysis reports
"""

import asyncio
import logging
from typing import List, Dict, Any
from datetime import datetime
from dataclasses import dataclass, field
from contextlib import asynccontextmanager
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import event
from sqlalchemy.engine import Engine

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


@dataclass
class QueryLog:
    """Single query execution log"""

    timestamp: datetime
    query: str
    parameters: Any
    duration_ms: float
    endpoint: str = ""
    stack_trace: str = ""


@dataclass
class EndpointQueryStats:
    """Query statistics for an endpoint"""

    endpoint: str
    total_queries: int = 0
    unique_queries: int = 0
    total_duration_ms: float = 0
    queries: List[QueryLog] = field(default_factory=list)
    n_plus_one_detected: bool = False
    similar_queries: List[str] = field(default_factory=list)


class DatabaseQueryMonitor:
    """
    Monitors database queries to validate N+1 optimizations
    """

    def __init__(self):
        self.query_logs: List[QueryLog] = []
        self.endpoint_stats: Dict[str, EndpointQueryStats] = {}
        self.monitoring_enabled = False
        self.current_endpoint: str = ""

    def start_monitoring(self):
        """Start monitoring database queries"""
        logger.info("🔍 Starting database query monitoring...")
        self.monitoring_enabled = True

        # Hook into SQLAlchemy query execution
        @event.listens_for(Engine, "before_cursor_execute")
        def receive_before_cursor_execute(
            conn, cursor, statement, parameters, context, executemany
        ):
            if self.monitoring_enabled:
                conn.info.setdefault("query_start_time", []).append(datetime.now())

        @event.listens_for(Engine, "after_cursor_execute")
        def receive_after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
            if self.monitoring_enabled:
                query_start_times = conn.info.get("query_start_time", [])
                if query_start_times:
                    start_time = query_start_times.pop()
                    duration_ms = (datetime.now() - start_time).total_seconds() * 1000

                    query_log = QueryLog(
                        timestamp=datetime.now(),
                        query=statement,
                        parameters=parameters,
                        duration_ms=duration_ms,
                        endpoint=self.current_endpoint,
                    )

                    self.query_logs.append(query_log)

                    # Update endpoint stats
                    if self.current_endpoint:
                        if self.current_endpoint not in self.endpoint_stats:
                            self.endpoint_stats[self.current_endpoint] = EndpointQueryStats(
                                endpoint=self.current_endpoint
                            )

                        stats = self.endpoint_stats[self.current_endpoint]
                        stats.total_queries += 1
                        stats.total_duration_ms += duration_ms
                        stats.queries.append(query_log)

        logger.info("✅ Database query monitoring started")

    def stop_monitoring(self):
        """Stop monitoring database queries"""
        logger.info("🛑 Stopping database query monitoring...")
        self.monitoring_enabled = False

    @asynccontextmanager
    async def track_endpoint(self, endpoint: str):
        """Context manager to track queries for a specific endpoint"""
        self.current_endpoint = endpoint
        try:
            yield
        finally:
            self.current_endpoint = ""

    def analyze_n_plus_one(self):
        """Analyze query logs for N+1 patterns"""
        logger.info("🔍 Analyzing for N+1 query patterns...")

        for endpoint, stats in self.endpoint_stats.items():
            # Group queries by similarity (ignoring parameters)
            query_patterns = {}

            for query_log in stats.queries:
                # Normalize query (remove parameter values)
                normalized = self._normalize_query(query_log.query)

                if normalized not in query_patterns:
                    query_patterns[normalized] = []
                query_patterns[normalized].append(query_log)

            # Detect N+1 pattern: same query executed many times
            for pattern, queries in query_patterns.items():
                if len(queries) > 10:  # Threshold for N+1 detection
                    stats.n_plus_one_detected = True
                    stats.similar_queries.append(f"{len(queries)}x: {pattern[:100]}...")
                    logger.warning(f"⚠️ N+1 detected in {endpoint}: {len(queries)} similar queries")

            stats.unique_queries = len(query_patterns)

        logger.info("✅ N+1 analysis complete")

    def _normalize_query(self, query: str) -> str:
        """Normalize query by removing parameter values"""
        import re

        # Remove specific values from IN clauses
        query = re.sub(r"IN \([^)]+\)", "IN (...)", query)

        # Remove specific WHERE values
        query = re.sub(r"= \'[^\']+\'", "= ?", query)
        query = re.sub(r"= \d+", "= ?", query)

        # Remove extra whitespace
        query = " ".join(query.split())

        return query

    def generate_report(self) -> str:
        """Generate query monitoring report"""
        logger.info("📊 Generating query monitoring report...")

        total_queries = len(self.query_logs)
        total_duration = sum(q.duration_ms for q in self.query_logs)
        avg_duration = total_duration / total_queries if total_queries > 0 else 0

        report = f"""
# Database Query Monitoring Report

**Generated**: {datetime.now().isoformat()}
**Total Queries Logged**: {total_queries:,}
**Total Duration**: {total_duration:.2f}ms
**Average Query Duration**: {avg_duration:.2f}ms

## 📊 Query Statistics by Endpoint

"""

        # Sort endpoints by query count
        sorted_endpoints = sorted(
            self.endpoint_stats.items(), key=lambda x: x[1].total_queries, reverse=True
        )

        for endpoint, stats in sorted_endpoints:
            n_plus_one_icon = "❌ N+1 DETECTED" if stats.n_plus_one_detected else "✅ Optimized"
            avg_endpoint_duration = (
                stats.total_duration_ms / stats.total_queries if stats.total_queries > 0 else 0
            )

            report += f"""
### {endpoint}

- **Status**: {n_plus_one_icon}
- **Total Queries**: {stats.total_queries}
- **Unique Queries**: {stats.unique_queries}
- **Total Duration**: {stats.total_duration_ms:.2f}ms
- **Avg Duration per Query**: {avg_endpoint_duration:.2f}ms
"""

            if stats.n_plus_one_detected:
                report += "\n**N+1 Patterns Detected**:\n"
                for pattern in stats.similar_queries:
                    report += f"- {pattern}\n"

        report += f"""
## 🎯 Phase 3 Validation Results

### Expected Improvements

| Endpoint | Before | After | Status |
|----------|--------|-------|--------|
"""

        # Audit logs list
        audit_list_stats = self.endpoint_stats.get(
            "GET /api/v1/organizations/.*/audit", None
        ) or self.endpoint_stats.get("GET /api/v1/audit", None)

        if audit_list_stats:
            status = "✅ PASS" if audit_list_stats.total_queries <= 5 else "❌ FAIL"
            report += f"| Audit Logs List | 101 queries | {audit_list_stats.total_queries} queries | {status} |\n"

        # Audit logs stats
        audit_stats_stats = self.endpoint_stats.get(
            "GET /api/v1/organizations/.*/audit/stats", None
        ) or self.endpoint_stats.get("GET /api/v1/audit/stats", None)

        if audit_stats_stats:
            status = "✅ PASS" if audit_stats_stats.total_queries <= 5 else "❌ FAIL"
            report += f"| Audit Logs Stats | 11 queries | {audit_stats_stats.total_queries} queries | {status} |\n"

        # Audit logs export
        audit_export_stats = self.endpoint_stats.get(
            "GET /api/v1/organizations/.*/audit/export", None
        ) or self.endpoint_stats.get("GET /api/v1/audit/export", None)

        if audit_export_stats:
            status = "✅ PASS" if audit_export_stats.total_queries <= 5 else "❌ FAIL"
            report += f"| Audit Logs Export | 1001 queries | {audit_export_stats.total_queries} queries | {status} |\n"

        # Organization list
        org_list_stats = self.endpoint_stats.get("GET /api/v1/organizations", None)

        if org_list_stats:
            status = "✅ PASS" if org_list_stats.total_queries <= 3 else "❌ FAIL"
            report += f"| Organization List | N+1 pattern | {org_list_stats.total_queries} queries | {status} |\n"

        report += """
## 📋 Recommendations

"""

        n_plus_one_endpoints = [
            ep for ep, stats in self.endpoint_stats.items() if stats.n_plus_one_detected
        ]

        if n_plus_one_endpoints:
            report += "### ⚠️ N+1 Patterns Detected\n\n"
            report += "The following endpoints still have N+1 query patterns:\n\n"
            for endpoint in n_plus_one_endpoints:
                report += f"- `{endpoint}`\n"
            report += "\n**Action**: Implement bulk fetching or caching for these endpoints.\n\n"
        else:
            report += "### ✅ No N+1 Patterns Detected\n\n"
            report += "All monitored endpoints are optimized with proper bulk fetching!\n\n"

        report += """
---

**Query Monitoring Status**: Complete
"""

        return report

    def get_endpoint_query_count(self, endpoint: str) -> int:
        """Get query count for a specific endpoint"""
        stats = self.endpoint_stats.get(endpoint)
        return stats.total_queries if stats else 0


async def validate_phase3_n_plus_one_fixes():
    """
    Validate all Phase 3 N+1 fixes by monitoring queries
    """
    logger.info("=" * 80)
    logger.info("🔍 Starting Database Query Monitoring for Phase 3 Validation")
    logger.info("=" * 80)

    monitor = DatabaseQueryMonitor()
    monitor.start_monitoring()

    try:
        # Import after monitoring is started
        from fastapi.testclient import TestClient
        from app.main import app

        client = TestClient(app)

        # Create test user and authenticate
        test_email = f"query_monitor_{int(datetime.now().timestamp())}@test.com"
        test_password = "QueryMonitor123!@#"

        # Signup
        client.post(
            "/beta/signup",
            json={"email": test_email, "password": test_password, "name": "Query Monitor"},
        )

        # Signin
        signin_response = client.post(
            "/beta/signin", json={"email": test_email, "password": test_password}
        )

        token = signin_response.json().get("access_token")
        headers = {"Authorization": f"Bearer {token}"}

        # Test 1: Audit Logs List
        logger.info("\n📊 Testing: Audit Logs List endpoint")
        async with monitor.track_endpoint("GET /api/v1/audit"):
            response = client.get("/api/v1/audit?limit=100", headers=headers)
            logger.info(f"   Response status: {response.status_code}")

        queries_count = monitor.get_endpoint_query_count("GET /api/v1/audit")
        logger.info(f"   Queries executed: {queries_count}")
        logger.info(f"   Target: ≤ 5 queries")
        logger.info(f"   Status: {'✅ PASS' if queries_count <= 5 else '❌ FAIL'}")

        # Test 2: Organization List
        logger.info("\n📊 Testing: Organization List endpoint")
        async with monitor.track_endpoint("GET /api/v1/organizations"):
            response = client.get("/api/v1/organizations", headers=headers)
            logger.info(f"   Response status: {response.status_code}")

        queries_count = monitor.get_endpoint_query_count("GET /api/v1/organizations")
        logger.info(f"   Queries executed: {queries_count}")
        logger.info(f"   Target: ≤ 3 queries")
        logger.info(f"   Status: {'✅ PASS' if queries_count <= 3 else '❌ FAIL'}")

        # Analyze all queries
        monitor.analyze_n_plus_one()

        # Generate report
        report = monitor.generate_report()

        # Save report
        report_path = Path("database_query_monitoring_report.md")
        report_path.write_text(report)

        logger.info(f"\n📋 Query monitoring report saved: {report_path}")
        logger.info("\n" + report)

        return report

    finally:
        monitor.stop_monitoring()


if __name__ == "__main__":
    asyncio.run(validate_phase3_n_plus_one_fixes())
