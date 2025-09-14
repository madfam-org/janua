#!/usr/bin/env python3
"""
Database Optimization Script for Plinto Platform
Phase 2: Performance Optimization

This script applies database indexes and optimizations for sub-100ms API performance.
Implements concurrent index creation to minimize downtime impact.
"""

import asyncio
import asyncpg
import logging
import os
import sys
from datetime import datetime
from typing import List, Dict, Any
import time

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('database_optimization.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

class DatabaseOptimizer:
    """Database optimization manager with safe concurrent index creation"""
    
    def __init__(self, database_url: str):
        self.database_url = database_url
        self.connection = None
        
    async def connect(self):
        """Establish database connection"""
        try:
            self.connection = await asyncpg.connect(self.database_url)
            logger.info("✅ Database connection established")
            
            # Check PostgreSQL version
            version_result = await self.connection.fetchrow("SELECT version()")
            logger.info(f"📊 PostgreSQL Version: {version_result['version']}")
            
        except Exception as e:
            logger.error(f"❌ Failed to connect to database: {e}")
            raise
    
    async def disconnect(self):
        """Close database connection"""
        if self.connection:
            await self.connection.close()
            logger.info("🔌 Database connection closed")
    
    async def check_existing_indexes(self) -> Dict[str, bool]:
        """Check which optimization indexes already exist"""
        logger.info("🔍 Checking existing indexes...")
        
        query = """
        SELECT indexname, tablename 
        FROM pg_indexes 
        WHERE schemaname = 'public' 
        AND (
            indexname LIKE 'idx_users_%' OR 
            indexname LIKE 'idx_sessions_%' OR 
            indexname LIKE 'idx_org_%' OR 
            indexname LIKE 'idx_activity_%' OR
            indexname LIKE 'idx_magic_%' OR
            indexname LIKE 'idx_password_%' OR
            indexname LIKE 'idx_email_%' OR
            indexname LIKE 'idx_oauth_%' OR
            indexname LIKE 'idx_webhook_%' OR
            indexname LIKE 'idx_audit_%' OR
            indexname LIKE 'idx_scim_%'
        )
        ORDER BY tablename, indexname
        """
        
        result = await self.connection.fetch(query)
        existing = {f"{row['tablename']}.{row['indexname']}": True for row in result}
        
        logger.info(f"📋 Found {len(existing)} existing optimization indexes")
        return existing
    
    async def get_table_sizes(self) -> List[Dict[str, Any]]:
        """Get current table sizes for monitoring"""
        query = """
        SELECT 
            schemaname,
            tablename,
            pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size,
            pg_total_relation_size(schemaname||'.'||tablename) as size_bytes,
            COALESCE(pg_stat_get_live_tuples(c.oid), 0) as live_tuples
        FROM pg_tables pt
        LEFT JOIN pg_class c ON pt.tablename = c.relname
        LEFT JOIN pg_namespace n ON c.relnamespace = n.oid AND n.nspname = pt.schemaname
        WHERE schemaname = 'public'
        ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC NULLS LAST
        """
        
        result = await self.connection.fetch(query)
        return [dict(row) for row in result]
    
    async def execute_index_creation(self, index_sql: str, index_name: str) -> bool:
        """Execute index creation with error handling and timing"""
        start_time = time.time()
        
        try:
            logger.info(f"🔨 Creating index: {index_name}")
            await self.connection.execute(index_sql)
            
            duration = time.time() - start_time
            logger.info(f"✅ Index {index_name} created successfully in {duration:.2f}s")
            return True
            
        except asyncpg.exceptions.DuplicateTableError:
            logger.info(f"ℹ️  Index {index_name} already exists, skipping")
            return True
            
        except Exception as e:
            duration = time.time() - start_time
            logger.error(f"❌ Failed to create index {index_name} after {duration:.2f}s: {e}")
            return False
    
    async def apply_critical_indexes(self) -> Dict[str, bool]:
        """Apply the most critical indexes for authentication and sessions"""
        logger.info("🚀 Applying critical performance indexes...")
        
        critical_indexes = [
            # Authentication (Most Critical)
            ("CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_users_email_status ON users(email, status) WHERE status = 'active'", 
             "idx_users_email_status"),
            
            ("CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_users_id_status ON users(id, status) WHERE status = 'active'", 
             "idx_users_id_status"),
            
            # Session validation (Every authenticated request)
            ("CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_sessions_access_token_jti ON sessions(access_token_jti) WHERE status = 'active' AND revoked = false", 
             "idx_sessions_access_token_jti"),
            
            ("CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_sessions_refresh_token_jti ON sessions(refresh_token_jti) WHERE status = 'active' AND revoked = false", 
             "idx_sessions_refresh_token_jti"),
            
            # Organization access (Multi-tenant)
            ("CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_org_members_user_org ON organization_members(user_id, organization_id)", 
             "idx_org_members_user_org"),
            
            ("CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_organizations_slug_active ON organizations(slug) WHERE slug IS NOT NULL", 
             "idx_organizations_slug_active"),
        ]
        
        results = {}
        for sql, name in critical_indexes:
            results[name] = await self.execute_index_creation(sql, name)
            
        return results
    
    async def apply_security_indexes(self) -> Dict[str, bool]:
        """Apply indexes for security-critical operations"""
        logger.info("🔐 Applying security and token validation indexes...")
        
        security_indexes = [
            # Token validation
            ("CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_magic_links_token_active ON magic_links(token) WHERE used = false", 
             "idx_magic_links_token_active"),
            
            ("CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_password_resets_token_active ON password_resets(token) WHERE used = false", 
             "idx_password_resets_token_active"),
            
            ("CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_email_verifications_token_active ON email_verifications(token) WHERE verified = false", 
             "idx_email_verifications_token_active"),
            
            # OAuth
            ("CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_oauth_accounts_provider_user_id ON oauth_accounts(provider, provider_user_id)", 
             "idx_oauth_accounts_provider_user_id"),
            
            # Session management
            ("CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_sessions_expires_at ON sessions(expires_at) WHERE status = 'active'", 
             "idx_sessions_expires_at"),
            
            ("CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_sessions_user_status ON sessions(user_id, status, expires_at)", 
             "idx_sessions_user_status"),
        ]
        
        results = {}
        for sql, name in security_indexes:
            results[name] = await self.execute_index_creation(sql, name)
            
        return results
    
    async def apply_enterprise_indexes(self) -> Dict[str, bool]:
        """Apply indexes for enterprise features"""
        logger.info("🏢 Applying enterprise feature indexes...")
        
        enterprise_indexes = [
            # Activity logging
            ("CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_activity_logs_user_created ON activity_logs(user_id, created_at DESC)", 
             "idx_activity_logs_user_created"),
            
            ("CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_activity_logs_action_created ON activity_logs(action, created_at DESC)", 
             "idx_activity_logs_action_created"),
            
            # Organization roles
            ("CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_org_members_org_role ON organization_members(organization_id, role)", 
             "idx_org_members_org_role"),
            
            # JSONB metadata
            ("CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_users_metadata_gin ON users USING GIN (user_metadata) WHERE user_metadata IS NOT NULL", 
             "idx_users_metadata_gin"),
            
            ("CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_organizations_settings_gin ON organizations USING GIN (settings) WHERE settings IS NOT NULL", 
             "idx_organizations_settings_gin"),
        ]
        
        results = {}
        for sql, name in enterprise_indexes:
            results[name] = await self.execute_index_creation(sql, name)
            
        return results
    
    async def apply_foreign_key_indexes(self) -> Dict[str, bool]:
        """Apply indexes for foreign key columns to optimize joins"""
        logger.info("🔗 Applying foreign key optimization indexes...")
        
        fk_indexes = [
            ("CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_sessions_user_id ON sessions(user_id)", "idx_sessions_user_id"),
            ("CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_oauth_accounts_user_id ON oauth_accounts(user_id)", "idx_oauth_accounts_user_id"),
            ("CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_passkeys_user_id ON passkeys(user_id)", "idx_passkeys_user_id"),
            ("CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_magic_links_user_id ON magic_links(user_id)", "idx_magic_links_user_id"),
            ("CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_password_resets_user_id ON password_resets(user_id)", "idx_password_resets_user_id"),
            ("CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_email_verifications_user_id ON email_verifications(user_id)", "idx_email_verifications_user_id"),
            ("CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_organizations_owner_id ON organizations(owner_id)", "idx_organizations_owner_id"),
        ]
        
        results = {}
        for sql, name in fk_indexes:
            results[name] = await self.execute_index_creation(sql, name)
            
        return results
    
    async def analyze_query_performance(self) -> Dict[str, Any]:
        """Analyze current query performance metrics"""
        logger.info("📊 Analyzing query performance...")
        
        # Check if pg_stat_statements is available
        try:
            check_query = "SELECT COUNT(*) as count FROM pg_stat_statements LIMIT 1"
            await self.connection.fetchrow(check_query)
            has_pg_stat_statements = True
        except:
            has_pg_stat_statements = False
            logger.warning("⚠️  pg_stat_statements extension not available")
        
        analysis = {
            'has_pg_stat_statements': has_pg_stat_statements,
            'table_sizes': await self.get_table_sizes(),
        }
        
        if has_pg_stat_statements:
            # Get slow queries
            slow_queries = await self.connection.fetch("""
                SELECT 
                    substring(query, 1, 100) as query_start,
                    calls, 
                    total_time, 
                    mean_time, 
                    rows
                FROM pg_stat_statements 
                WHERE mean_time > 50
                ORDER BY mean_time DESC 
                LIMIT 10
            """)
            analysis['slow_queries'] = [dict(row) for row in slow_queries]
        
        # Get index usage stats
        index_stats = await self.connection.fetch("""
            SELECT 
                schemaname, 
                tablename, 
                indexname, 
                idx_scan, 
                idx_tup_read, 
                idx_tup_fetch
            FROM pg_stat_user_indexes 
            WHERE schemaname = 'public'
            ORDER BY idx_scan DESC 
            LIMIT 20
        """)
        analysis['index_usage'] = [dict(row) for row in index_stats]
        
        return analysis
    
    async def generate_optimization_report(self, results: Dict[str, Dict[str, bool]]) -> str:
        """Generate comprehensive optimization report"""
        logger.info("📋 Generating optimization report...")
        
        # Count successes and failures
        total_indexes = sum(len(category_results) for category_results in results.values())
        successful_indexes = sum(
            sum(1 for success in category_results.values() if success)
            for category_results in results.values()
        )
        
        # Get performance analysis
        performance_analysis = await self.analyze_query_performance()
        
        report = f"""
# Database Optimization Report
**Generated**: {datetime.now().isoformat()}
**Phase**: 2 - Performance Optimization

## Index Creation Results
- **Total indexes processed**: {total_indexes}
- **Successfully created/verified**: {successful_indexes}
- **Success rate**: {(successful_indexes/total_indexes*100):.1f}%

## Index Categories
"""
        
        for category, category_results in results.items():
            successful = sum(1 for success in category_results.values() if success)
            total = len(category_results)
            report += f"\n### {category.replace('_', ' ').title()}\n"
            report += f"- **Status**: {successful}/{total} successful\n"
            
            for index_name, success in category_results.items():
                status = "✅" if success else "❌"
                report += f"  - {status} {index_name}\n"
        
        # Add table size analysis
        report += "\n## Database Size Analysis\n"
        for table_info in performance_analysis['table_sizes'][:10]:
            report += f"- **{table_info['tablename']}**: {table_info['size']} ({table_info['live_tuples']:,} rows)\n"
        
        # Add performance insights
        if performance_analysis['has_pg_stat_statements'] and 'slow_queries' in performance_analysis:
            report += "\n## Query Performance Analysis\n"
            report += f"- **Slow queries found**: {len(performance_analysis['slow_queries'])}\n"
            
            for query in performance_analysis['slow_queries'][:5]:
                report += f"  - **Query**: {query['query_start']}...\n"
                report += f"    - **Mean time**: {query['mean_time']:.2f}ms\n"
                report += f"    - **Calls**: {query['calls']}\n"
        
        return report

async def main():
    """Main optimization execution"""
    logger.info("🚀 Starting Plinto Database Optimization - Phase 2")
    
    # Get database URL from environment
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        logger.error("❌ DATABASE_URL environment variable not set")
        sys.exit(1)
    
    optimizer = DatabaseOptimizer(database_url)
    
    try:
        # Connect to database
        await optimizer.connect()
        
        # Check existing state
        existing_indexes = await optimizer.check_existing_indexes()
        logger.info(f"📊 Current optimization indexes: {len(existing_indexes)}")
        
        # Apply optimizations in phases
        results = {}
        
        # Phase 1: Critical performance indexes (authentication, sessions)
        results['critical_indexes'] = await optimizer.apply_critical_indexes()
        
        # Phase 2: Security and token validation
        results['security_indexes'] = await optimizer.apply_security_indexes()
        
        # Phase 3: Enterprise features
        results['enterprise_indexes'] = await optimizer.apply_enterprise_indexes()
        
        # Phase 4: Foreign key optimization
        results['foreign_key_indexes'] = await optimizer.apply_foreign_key_indexes()
        
        # Generate and save report
        report = await optimizer.generate_optimization_report(results)
        
        # Save report to file
        with open('database_optimization_report.md', 'w') as f:
            f.write(report)
        
        logger.info("📋 Optimization report saved to database_optimization_report.md")
        logger.info(report)
        
        # Final summary
        total_indexes = sum(len(category_results) for category_results in results.values())
        successful_indexes = sum(
            sum(1 for success in category_results.values() if success)
            for category_results in results.values()
        )
        
        logger.info(f"🎉 Database optimization completed!")
        logger.info(f"📊 Final Results: {successful_indexes}/{total_indexes} indexes successfully applied")
        
        if successful_indexes == total_indexes:
            logger.info("✅ All optimizations applied successfully")
            return 0
        else:
            logger.warning(f"⚠️  {total_indexes - successful_indexes} optimizations failed")
            return 1
            
    except Exception as e:
        logger.error(f"❌ Database optimization failed: {e}")
        return 1
        
    finally:
        await optimizer.disconnect()

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)