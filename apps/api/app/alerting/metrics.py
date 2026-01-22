"""
Metrics Collection and Context Generation
Handles retrieval of metric values and context generation for alerts
"""

import structlog
from typing import Dict, Any, Optional

logger = structlog.get_logger()


class MetricsCollector:
    """Collects metric values from various sources"""

    def __init__(self, apm_collector=None, log_analyzer=None):
        """Initialize with monitoring dependencies"""
        self.apm_collector = apm_collector
        self.log_analyzer = log_analyzer

    async def get_metric_value(self, metric_name: str, window_seconds: int) -> Optional[float]:
        """Get current metric value"""
        try:
            if metric_name == "avg_response_time":
                # Get from APM data
                if self.apm_collector:
                    perf_summary = await self.apm_collector.get_performance_summary("all", hours=1)
                    return perf_summary.get("performance", {}).get("avg_duration_ms", 0)
                return 0.0

            elif metric_name == "error_rate":
                if self.apm_collector:
                    perf_summary = await self.apm_collector.get_performance_summary("all", hours=1)
                    return perf_summary.get("errors", {}).get("error_rate", 0)
                return 0.0

            elif metric_name == "memory_usage_percent":
                # Would integrate with system monitoring
                return 75.0  # Placeholder

            elif metric_name == "disk_usage_percent":
                # Would integrate with system monitoring
                return 70.0  # Placeholder

            elif metric_name == "database_connection_errors":
                # Would check database connection health
                return 0  # Placeholder

            elif metric_name == "security_events_count":
                # Get from log analyzer
                if self.log_analyzer:
                    log_stats = await self.log_analyzer.get_log_statistics(hours=1)
                    return log_stats.get("security", {}).get("security_events", 0)
                return 0

            else:
                logger.warning("Unknown metric name", metric_name=metric_name)
                return None

        except Exception as e:
            logger.error("Failed to get metric value", metric_name=metric_name, error=str(e))
            return None

    async def get_alert_context(self, rule, current_value: float) -> Dict[str, Any]:
        """Get additional context for alert"""
        context = {
            "metric_name": rule.metric_name,
            "evaluation_window": rule.evaluation_window,
            "comparison": f"{current_value} {rule.comparison_operator} {rule.threshold_value}",
        }

        try:
            # Add rule-specific context
            if rule.metric_name == "avg_response_time":
                # Add slowest endpoints
                if self.apm_collector:
                    perf_summary = await self.apm_collector.get_performance_summary("all", hours=1)
                    context["slowest_endpoints"] = perf_summary.get("performance", {}).get(
                        "slowest_endpoints", []
                    )[:5]

            elif rule.metric_name == "error_rate":
                # Add error distribution
                if self.log_analyzer:
                    log_stats = await self.log_analyzer.get_log_statistics(hours=1)
                    context["error_types"] = log_stats.get("errors", {}).get("error_types", {})

            elif rule.metric_name == "security_events_count":
                # Add security event details
                if self.log_analyzer:
                    log_stats = await self.log_analyzer.get_log_statistics(hours=1)
                    context["recent_security_events"] = log_stats.get("security", {}).get(
                        "recent_events", []
                    )[:5]

            # Add rule metadata if available
            if hasattr(rule, "metadata") and rule.metadata:
                context.update(rule.metadata)

        except Exception as e:
            logger.error("Failed to get alert context", rule_id=rule.rule_id, error=str(e))

        return context

    def register_apm_collector(self, apm_collector):
        """Register APM collector"""
        self.apm_collector = apm_collector

    def register_log_analyzer(self, log_analyzer):
        """Register log analyzer"""
        self.log_analyzer = log_analyzer


# Global instance for easy import
metrics_collector = MetricsCollector()
