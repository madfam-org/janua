"""
APM Dashboard API Routes
Endpoints for accessing performance monitoring data and metrics
"""

from typing import Dict, Any, Optional
from datetime import datetime
from fastapi import APIRouter, HTTPException, Query, Depends
from fastapi.responses import PlainTextResponse
import structlog

from app.monitoring.apm import apm_collector, get_apm_health
from app.core.auth import get_current_admin_user
from app.core.models import User

logger = structlog.get_logger()

router = APIRouter(prefix="/apm", tags=["APM"])


@router.get("/health")
async def apm_health_check():
    """Get APM system health status"""
    try:
        health = await get_apm_health()
        return health
    except Exception as e:
        logger.error("APM health check failed", error=str(e))
        raise HTTPException(status_code=500, detail="APM health check failed")


@router.get("/metrics", response_class=PlainTextResponse)
async def get_prometheus_metrics():
    """Get Prometheus metrics for scraping"""
    try:
        metrics = apm_collector.get_metrics()
        return metrics
    except Exception as e:
        logger.error("Failed to get metrics", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to retrieve metrics")


@router.get("/performance/summary")
async def get_performance_summary(
    operation: Optional[str] = Query(None, description="Filter by operation name"),
    hours: int = Query(24, ge=1, le=168, description="Hours to look back (1-168)"),
    current_user: User = Depends(get_current_admin_user)
) -> Dict[str, Any]:
    """Get performance summary for the specified time period"""
    try:
        summary = await apm_collector.get_performance_summary(operation, hours)
        return summary
    except Exception as e:
        logger.error("Failed to get performance summary", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to retrieve performance summary")


@router.get("/traces")
async def get_recent_traces(
    limit: int = Query(50, ge=1, le=1000, description="Number of traces to return"),
    operation: Optional[str] = Query(None, description="Filter by operation name"),
    status: Optional[str] = Query(None, description="Filter by trace status"),
    current_user: User = Depends(get_current_admin_user)
) -> Dict[str, Any]:
    """Get recent traces with optional filtering"""
    try:
        if not apm_collector.redis_client:
            raise HTTPException(status_code=503, detail="APM Redis not available")

        # Get recent traces from Redis
        trace_ids = await apm_collector.redis_client.zrevrange("apm:traces", 0, limit - 1)

        traces = []
        for trace_id in trace_ids:
            # Get all spans for this trace
            span_ids = await apm_collector.redis_client.zrange(f"apm:trace_index:{trace_id}", 0, -1)

            trace_spans = []
            for span_id in span_ids:
                span_data = await apm_collector.redis_client.hgetall(f"apm:trace:{trace_id}:{span_id}")
                if span_data:
                    # Filter by operation if specified
                    if operation and operation not in span_data.get('operation_name', ''):
                        continue

                    # Filter by status if specified
                    if status and span_data.get('status') != status:
                        continue

                    trace_spans.append({
                        "span_id": span_data.get('span_id'),
                        "operation_name": span_data.get('operation_name'),
                        "start_time": span_data.get('start_time'),
                        "end_time": span_data.get('end_time'),
                        "duration_ms": float(span_data.get('duration_ms', 0)),
                        "status": span_data.get('status'),
                        "error": span_data.get('error'),
                        "tags": eval(span_data.get('tags', '{}')) if span_data.get('tags') else {}
                    })

            if trace_spans:  # Only include traces that have matching spans
                traces.append({
                    "trace_id": trace_id,
                    "spans": trace_spans,
                    "total_spans": len(trace_spans),
                    "total_duration_ms": sum(span['duration_ms'] for span in trace_spans),
                    "has_errors": any(span['status'] == 'error' for span in trace_spans)
                })

        return {
            "traces": traces,
            "total_count": len(traces),
            "filters": {
                "operation": operation,
                "status": status,
                "limit": limit
            }
        }

    except Exception as e:
        logger.error("Failed to get traces", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to retrieve traces")


@router.get("/traces/{trace_id}")
async def get_trace_details(
    trace_id: str,
    current_user: User = Depends(get_current_admin_user)
) -> Dict[str, Any]:
    """Get detailed information for a specific trace"""
    try:
        if not apm_collector.redis_client:
            raise HTTPException(status_code=503, detail="APM Redis not available")

        # Get all spans for this trace
        span_ids = await apm_collector.redis_client.zrange(f"apm:trace_index:{trace_id}", 0, -1)

        if not span_ids:
            raise HTTPException(status_code=404, detail="Trace not found")

        spans = []
        for span_id in span_ids:
            span_data = await apm_collector.redis_client.hgetall(f"apm:trace:{trace_id}:{span_id}")
            if span_data:
                spans.append({
                    "span_id": span_data.get('span_id'),
                    "parent_span_id": span_data.get('parent_span_id'),
                    "operation_name": span_data.get('operation_name'),
                    "start_time": span_data.get('start_time'),
                    "end_time": span_data.get('end_time'),
                    "duration_ms": float(span_data.get('duration_ms', 0)),
                    "status": span_data.get('status'),
                    "error": span_data.get('error'),
                    "tags": eval(span_data.get('tags', '{}')) if span_data.get('tags') else {},
                    "logs": eval(span_data.get('logs', '[]')) if span_data.get('logs') else []
                })

        # Sort spans by start time
        spans.sort(key=lambda x: x['start_time'])

        return {
            "trace_id": trace_id,
            "spans": spans,
            "total_spans": len(spans),
            "total_duration_ms": sum(span['duration_ms'] for span in spans),
            "has_errors": any(span['status'] == 'error' for span in spans),
            "start_time": spans[0]['start_time'] if spans else None,
            "end_time": max(span['end_time'] for span in spans if span['end_time']) if spans else None
        }

    except Exception as e:
        logger.error("Failed to get trace details", error=str(e), trace_id=trace_id)
        raise HTTPException(status_code=500, detail="Failed to retrieve trace details")


@router.get("/performance/profiles")
async def get_performance_profiles(
    limit: int = Query(50, ge=1, le=500, description="Number of profiles to return"),
    operation: Optional[str] = Query(None, description="Filter by operation name"),
    min_duration: Optional[float] = Query(None, description="Minimum duration in ms"),
    current_user: User = Depends(get_current_admin_user)
) -> Dict[str, Any]:
    """Get recent performance profiles with optional filtering"""
    try:
        if not apm_collector.redis_client:
            raise HTTPException(status_code=503, detail="APM Redis not available")

        if operation:
            # Get profiles for specific operation
            profile_data = await apm_collector.redis_client.zrevrange(
                f"apm:performance:{operation}",
                0, limit - 1,
                withscores=True
            )
            profile_ids = [item[0] for item in profile_data]
        else:
            # Get all recent profiles
            profile_ids = await apm_collector.redis_client.zrevrange("apm:profiles", 0, limit - 1)

        profiles = []
        for profile_id in profile_ids:
            profile_data = await apm_collector.redis_client.hgetall(f"apm:profile:{profile_id}")
            if profile_data:
                duration_ms = float(profile_data.get('duration_ms', 0))

                # Filter by minimum duration if specified
                if min_duration and duration_ms < min_duration:
                    continue

                profiles.append({
                    "request_id": profile_data.get('request_id'),
                    "operation": profile_data.get('operation'),
                    "start_time": profile_data.get('start_time'),
                    "end_time": profile_data.get('end_time'),
                    "duration_ms": duration_ms,
                    "cpu_usage": float(profile_data.get('cpu_usage', 0)) if profile_data.get('cpu_usage') else None,
                    "memory_usage": int(profile_data.get('memory_usage', 0)) if profile_data.get('memory_usage') else None,
                    "database_calls": int(profile_data.get('database_calls', 0)),
                    "redis_calls": int(profile_data.get('redis_calls', 0)),
                    "external_api_calls": int(profile_data.get('external_api_calls', 0)),
                    "error_count": int(profile_data.get('error_count', 0)),
                    "custom_metrics": eval(profile_data.get('custom_metrics', '{}')) if profile_data.get('custom_metrics') else {}
                })

        return {
            "profiles": profiles,
            "total_count": len(profiles),
            "filters": {
                "operation": operation,
                "min_duration": min_duration,
                "limit": limit
            }
        }

    except Exception as e:
        logger.error("Failed to get performance profiles", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to retrieve performance profiles")


@router.get("/system/metrics")
async def get_system_metrics(
    hours: int = Query(1, ge=1, le=24, description="Hours of data to return"),
    current_user: User = Depends(get_current_admin_user)
) -> Dict[str, Any]:
    """Get system metrics for the specified time period"""
    try:
        if not apm_collector.redis_client:
            raise HTTPException(status_code=503, detail="APM Redis not available")

        # Calculate time range
        end_time = int(datetime.now().timestamp())
        start_time = end_time - (hours * 3600)

        # Get system metrics from Redis
        metrics_data = await apm_collector.redis_client.zrangebyscore(
            "apm:system_metrics",
            start_time, end_time,
            withscores=True
        )

        # Parse and organize metrics
        cpu_metrics = []
        memory_metrics = []
        app_memory_metrics = []

        for metric_key, timestamp in metrics_data:
            metric_type, ts = metric_key.split(':')

            if metric_type == "cpu":
                cpu_metrics.append({
                    "timestamp": datetime.fromtimestamp(float(ts)).isoformat(),
                    "value": timestamp  # The score is actually the value
                })
            elif metric_type == "memory":
                memory_metrics.append({
                    "timestamp": datetime.fromtimestamp(float(ts)).isoformat(),
                    "value": timestamp
                })
            elif metric_type == "app_memory":
                app_memory_metrics.append({
                    "timestamp": datetime.fromtimestamp(float(ts)).isoformat(),
                    "value": timestamp
                })

        return {
            "time_range": {
                "start_time": datetime.fromtimestamp(start_time).isoformat(),
                "end_time": datetime.fromtimestamp(end_time).isoformat(),
                "hours": hours
            },
            "metrics": {
                "cpu_usage": cpu_metrics,
                "memory_usage": memory_metrics,
                "application_memory": app_memory_metrics
            },
            "data_points": len(metrics_data)
        }

    except Exception as e:
        logger.error("Failed to get system metrics", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to retrieve system metrics")


@router.get("/analytics/top-endpoints")
async def get_top_endpoints(
    hours: int = Query(24, ge=1, le=168, description="Hours to analyze"),
    limit: int = Query(10, ge=1, le=50, description="Number of endpoints to return"),
    current_user: User = Depends(get_current_admin_user)
) -> Dict[str, Any]:
    """Get analytics for top endpoints by request count and performance"""
    try:
        if not apm_collector.redis_client:
            raise HTTPException(status_code=503, detail="APM Redis not available")

        cutoff_time = datetime.now().timestamp() - (hours * 3600)

        # Get recent profiles
        profile_ids = await apm_collector.redis_client.zrangebyscore(
            "apm:profiles",
            cutoff_time, "+inf"
        )

        # Aggregate data by endpoint
        endpoint_data = {}
        for profile_id in profile_ids:
            profile = await apm_collector.redis_client.hgetall(f"apm:profile:{profile_id}")
            if profile:
                operation = profile.get('operation', 'unknown')
                duration = float(profile.get('duration_ms', 0))
                error_count = int(profile.get('error_count', 0))

                if operation not in endpoint_data:
                    endpoint_data[operation] = {
                        "operation": operation,
                        "request_count": 0,
                        "total_duration": 0,
                        "error_count": 0,
                        "durations": []
                    }

                endpoint_data[operation]["request_count"] += 1
                endpoint_data[operation]["total_duration"] += duration
                endpoint_data[operation]["error_count"] += error_count
                endpoint_data[operation]["durations"].append(duration)

        # Calculate statistics for each endpoint
        analytics = []
        for operation, data in endpoint_data.items():
            durations = data["durations"]
            durations.sort()

            analytics.append({
                "operation": operation,
                "request_count": data["request_count"],
                "avg_duration_ms": data["total_duration"] / data["request_count"],
                "min_duration_ms": min(durations),
                "max_duration_ms": max(durations),
                "p95_duration_ms": durations[int(len(durations) * 0.95)] if durations else 0,
                "p99_duration_ms": durations[int(len(durations) * 0.99)] if durations else 0,
                "error_count": data["error_count"],
                "error_rate": data["error_count"] / data["request_count"] if data["request_count"] > 0 else 0
            })

        # Sort by request count and limit
        analytics.sort(key=lambda x: x["request_count"], reverse=True)
        analytics = analytics[:limit]

        return {
            "time_range_hours": hours,
            "total_endpoints": len(endpoint_data),
            "top_endpoints": analytics
        }

    except Exception as e:
        logger.error("Failed to get endpoint analytics", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to retrieve endpoint analytics")


@router.delete("/data/cleanup")
async def cleanup_old_data(
    days: int = Query(7, ge=1, le=30, description="Keep data newer than N days"),
    current_user: User = Depends(get_current_admin_user)
) -> Dict[str, Any]:
    """Clean up old APM data"""
    try:
        if not apm_collector.redis_client:
            raise HTTPException(status_code=503, detail="APM Redis not available")

        cutoff_time = datetime.now().timestamp() - (days * 24 * 3600)

        # Clean up old traces
        old_traces = await apm_collector.redis_client.zrangebyscore(
            "apm:traces", 0, cutoff_time
        )

        traces_deleted = 0
        for trace_id in old_traces:
            # Delete trace spans
            span_ids = await apm_collector.redis_client.zrange(f"apm:trace_index:{trace_id}", 0, -1)
            for span_id in span_ids:
                await apm_collector.redis_client.delete(f"apm:trace:{trace_id}:{span_id}")

            # Delete trace index
            await apm_collector.redis_client.delete(f"apm:trace_index:{trace_id}")
            traces_deleted += 1

        # Remove from main trace list
        await apm_collector.redis_client.zremrangebyscore("apm:traces", 0, cutoff_time)

        # Clean up old profiles
        old_profiles = await apm_collector.redis_client.zrangebyscore(
            "apm:profiles", 0, cutoff_time
        )

        profiles_deleted = 0
        for profile_id in old_profiles:
            await apm_collector.redis_client.delete(f"apm:profile:{profile_id}")
            profiles_deleted += 1

        # Remove from main profile list
        await apm_collector.redis_client.zremrangebyscore("apm:profiles", 0, cutoff_time)

        # Clean up system metrics
        await apm_collector.redis_client.zremrangebyscore("apm:system_metrics", 0, cutoff_time)

        logger.info("APM data cleanup completed",
                   traces_deleted=traces_deleted,
                   profiles_deleted=profiles_deleted,
                   cutoff_days=days)

        return {
            "status": "success",
            "traces_deleted": traces_deleted,
            "profiles_deleted": profiles_deleted,
            "cutoff_days": days
        }

    except Exception as e:
        logger.error("Failed to cleanup APM data", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to cleanup APM data")