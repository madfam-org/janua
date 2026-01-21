"""
Audit logs API endpoints for compliance and security monitoring.
Updated to match existing production database schema.
"""

from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query, status, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy import and_, desc, select, func, delete
from pydantic import BaseModel, Field

from app.database import get_db
from app.dependencies import get_current_user, require_admin
from app.models import AuditLog
from app.services.audit_logger import AuditLogger, AuditAction


router = APIRouter(prefix="/v1/audit-logs", tags=["audit-logs"])


class AuditLogResponse(BaseModel):
    """Response model for audit log entries."""
    id: str
    action: str
    user_id: Optional[str]
    user_email: Optional[str]
    resource_type: Optional[str]
    resource_id: Optional[str]
    details: Optional[Dict[str, Any]]
    ip_address: Optional[str]
    user_agent: Optional[str]
    timestamp: datetime  # Maps to created_at in DB

    class Config:
        from_attributes = True


class AuditLogListResponse(BaseModel):
    """Response model for paginated audit log list."""
    logs: List[AuditLogResponse]
    total: int
    cursor: Optional[str]
    has_more: bool


class AuditLogStatsResponse(BaseModel):
    """Response model for audit log statistics."""
    total_events: int
    events_by_action: Dict[str, int]
    events_by_user: List[Dict[str, Any]]
    events_by_resource_type: Dict[str, int]
    events_by_hour: List[Dict[str, Any]]
    unique_users: int
    unique_ips: int
    time_range: Dict[str, datetime]


class AuditLogExportRequest(BaseModel):
    """Request model for audit log export."""
    format: str = Field("json", pattern="^(json|csv)$")
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    actions: Optional[List[str]] = None
    user_ids: Optional[List[str]] = None
    resource_types: Optional[List[str]] = None


@router.get("/", response_model=AuditLogListResponse)
async def list_audit_logs(
    actor: Optional[str] = Query(None, description="Filter by user ID"),
    action: Optional[str] = Query(None, description="Filter by action type"),
    resource: Optional[str] = Query(None, description="Filter by resource ID"),
    resource_type: Optional[str] = Query(None, description="Filter by resource type"),
    start_date: Optional[datetime] = Query(None, description="Start of time range"),
    end_date: Optional[datetime] = Query(None, description="End of time range"),
    ip_address: Optional[str] = Query(None, description="Filter by IP address"),
    limit: int = Query(100, ge=1, le=1000),
    cursor: Optional[str] = Query(None, description="Pagination cursor"),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Query audit logs with filtering and pagination.
    Regular users can only see their own logs, admins can see all.
    """
    # Build base query
    stmt = select(AuditLog)

    # Non-admins can only see their own logs
    if not current_user.is_admin:
        stmt = stmt.where(AuditLog.user_id == str(current_user.id))

    # Apply filters
    if actor:
        stmt = stmt.where(AuditLog.user_id == actor)

    if action:
        stmt = stmt.where(AuditLog.action == action)

    if resource:
        stmt = stmt.where(AuditLog.resource_id == resource)

    if resource_type:
        stmt = stmt.where(AuditLog.resource_type == resource_type)

    if ip_address:
        stmt = stmt.where(AuditLog.ip_address == ip_address)

    # Time range filter - use created_at (actual DB column)
    if start_date:
        stmt = stmt.where(AuditLog.created_at >= start_date)

    if end_date:
        stmt = stmt.where(AuditLog.created_at <= end_date)

    # Handle cursor-based pagination
    if cursor:
        # Cursor is the timestamp of the last item from previous page
        cursor_time = datetime.fromisoformat(cursor)
        stmt = stmt.where(AuditLog.created_at < cursor_time)

    # Get total count (expensive, consider caching)
    count_stmt = select(func.count()).select_from(stmt.subquery())
    count_result = await db.execute(count_stmt)
    total = count_result.scalar()

    # Get paginated results - use created_at for ordering
    result = await db.execute(stmt.order_by(desc(AuditLog.created_at)).limit(limit + 1))
    logs = result.scalars().all()

    # Check if there are more results
    has_more = len(logs) > limit
    if has_more:
        logs = logs[:-1]  # Remove the extra item

    # Get next cursor
    next_cursor = None
    if has_more and logs:
        next_cursor = logs[-1].created_at.isoformat()

    # OPTIMIZED: Bulk fetch user emails to avoid N+1 queries
    # Collect unique user IDs
    user_ids = list(set(str(log.user_id) for log in logs if log.user_id))
    user_email_map = {}

    if user_ids:
        from app.models.user import User
        users_result = await db.execute(select(User).where(User.id.in_(user_ids)))
        users = users_result.scalars().all()
        user_email_map = {str(user.id): user.email for user in users}

    # Convert to response models
    log_responses = []
    for log in logs:
        user_id_str = str(log.user_id) if log.user_id else None
        log_responses.append(AuditLogResponse(
            id=str(log.id),
            action=log.action,
            user_id=user_id_str,
            user_email=user_email_map.get(user_id_str) if user_id_str else None,
            resource_type=log.resource_type,
            resource_id=str(log.resource_id) if log.resource_id else None,
            details=log.details,
            ip_address=str(log.ip_address) if log.ip_address else None,
            user_agent=log.user_agent,
            timestamp=log.created_at  # Map created_at to timestamp for frontend
        ))

    return AuditLogListResponse(
        logs=log_responses,
        total=total,
        cursor=next_cursor,
        has_more=has_more
    )


@router.get("/stats", response_model=AuditLogStatsResponse)
async def get_audit_stats(
    start_date: Optional[datetime] = Query(None, description="Start of time range"),
    end_date: Optional[datetime] = Query(None, description="End of time range"),
    current_user=Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Get audit log statistics (admin only).
    """
    # Default to last 30 days if no range specified
    if not end_date:
        end_date = datetime.utcnow()
    if not start_date:
        start_date = end_date - timedelta(days=30)

    # Build base query - use created_at for time filtering
    stmt = select(AuditLog).where(
        and_(
            AuditLog.created_at >= start_date,
            AuditLog.created_at <= end_date
        )
    )

    result = await db.execute(stmt)
    logs = result.scalars().all()

    # Calculate statistics
    total_events = len(logs)

    # Events by action
    events_by_action = {}
    for log in logs:
        events_by_action[log.action] = events_by_action.get(log.action, 0) + 1

    # Events by user (top 10)
    events_by_user_dict = {}
    for log in logs:
        if log.user_id:
            user_id_str = str(log.user_id)
            events_by_user_dict[user_id_str] = events_by_user_dict.get(user_id_str, 0) + 1

    # OPTIMIZED: Bulk fetch user emails for top 10 users
    top_10_users = sorted(events_by_user_dict.items(), key=lambda x: x[1], reverse=True)[:10]
    top_user_ids = [user_id for user_id, _ in top_10_users]

    user_email_map = {}
    if top_user_ids:
        from app.models.user import User
        users_result = await db.execute(select(User).where(User.id.in_(top_user_ids)))
        users = users_result.scalars().all()
        user_email_map = {str(user.id): user.email for user in users}

    events_by_user = []
    for user_id, count in top_10_users:
        events_by_user.append({
            "user_id": user_id,
            "email": user_email_map.get(user_id, "Unknown"),
            "count": count
        })

    # Events by resource type
    events_by_resource_type = {}
    for log in logs:
        if log.resource_type:
            events_by_resource_type[log.resource_type] = events_by_resource_type.get(log.resource_type, 0) + 1

    # Events by hour (last 24 hours) - use created_at
    events_by_hour = []
    hour_counts = {}
    for log in logs:
        if log.created_at >= datetime.utcnow() - timedelta(hours=24):
            hour = log.created_at.replace(minute=0, second=0, microsecond=0)
            hour_counts[hour] = hour_counts.get(hour, 0) + 1

    for hour in sorted(hour_counts.keys()):
        events_by_hour.append({
            "hour": hour.isoformat(),
            "count": hour_counts[hour]
        })

    # Unique users and IPs
    unique_users = len(set(str(log.user_id) for log in logs if log.user_id))
    unique_ips = len(set(str(log.ip_address) for log in logs if log.ip_address))

    return AuditLogStatsResponse(
        total_events=total_events,
        events_by_action=events_by_action,
        events_by_user=events_by_user,
        events_by_resource_type=events_by_resource_type,
        events_by_hour=events_by_hour,
        unique_users=unique_users,
        unique_ips=unique_ips,
        time_range={
            "start": start_date,
            "end": end_date
        }
    )


@router.get("/{log_id}", response_model=AuditLogResponse)
async def get_audit_log(
    log_id: str,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get a specific audit log entry by ID.
    """
    result = await db.execute(select(AuditLog).where(AuditLog.id == log_id))
    log = result.scalar_one_or_none()

    if not log:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Audit log entry not found"
        )

    # Non-admins can only see their own logs
    if not current_user.is_admin and log.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )

    # Get user email if available
    user_email = None
    if log.user_id:
        from app.models.user import User
        user_result = await db.execute(select(User).where(User.id == log.user_id))
        user = user_result.scalar_one_or_none()
        if user:
            user_email = user.email

    return AuditLogResponse(
        id=str(log.id),
        action=log.action,
        user_id=str(log.user_id) if log.user_id else None,
        user_email=user_email,
        resource_type=log.resource_type,
        resource_id=str(log.resource_id) if log.resource_id else None,
        details=log.details,
        ip_address=str(log.ip_address) if log.ip_address else None,
        user_agent=log.user_agent,
        timestamp=log.created_at
    )


@router.post("/export")
async def export_audit_logs(
    export_request: AuditLogExportRequest,
    background_tasks: BackgroundTasks,
    current_user=Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Export audit logs in JSON or CSV format (admin only).
    """
    import json

    # Build query
    stmt = select(AuditLog)

    # Apply filters - use created_at for time filtering
    if export_request.start_date:
        stmt = stmt.where(AuditLog.created_at >= export_request.start_date)

    if export_request.end_date:
        stmt = stmt.where(AuditLog.created_at <= export_request.end_date)

    if export_request.actions:
        stmt = stmt.where(AuditLog.action.in_(export_request.actions))

    if export_request.user_ids:
        stmt = stmt.where(AuditLog.user_id.in_(export_request.user_ids))

    if export_request.resource_types:
        stmt = stmt.where(AuditLog.resource_type.in_(export_request.resource_types))

    # Get logs
    result = await db.execute(stmt.order_by(desc(AuditLog.created_at)))
    logs = result.scalars().all()

    # OPTIMIZED: Bulk fetch user emails to avoid N+1 queries
    user_ids = list(set(str(log.user_id) for log in logs if log.user_id))
    user_email_map = {}

    if user_ids:
        from app.models.user import User
        users_result = await db.execute(select(User).where(User.id.in_(user_ids)))
        users = users_result.scalars().all()
        user_email_map = {str(user.id): user.email for user in users}

    # Generate export
    if export_request.format == "csv":
        import csv
        import io

        output = io.StringIO()
        writer = csv.writer(output)

        # Write header
        writer.writerow([
            "ID", "Timestamp", "Action", "User ID", "User Email",
            "Resource Type", "Resource ID", "IP Address", "User Agent",
            "Details"
        ])

        # Write data
        for log in logs:
            user_id_str = str(log.user_id) if log.user_id else ""
            writer.writerow([
                str(log.id),
                log.created_at.isoformat(),
                log.action,
                user_id_str,
                user_email_map.get(user_id_str, ""),
                log.resource_type or "",
                str(log.resource_id) if log.resource_id else "",
                str(log.ip_address) if log.ip_address else "",
                log.user_agent or "",
                json.dumps(log.details) if log.details else ""
            ])

        content = output.getvalue()
        content_type = "text/csv"
        filename = f"audit_logs_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.csv"

    else:  # JSON format
        export_data = []
        for log in logs:
            user_id_str = str(log.user_id) if log.user_id else None
            export_data.append({
                "id": str(log.id),
                "timestamp": log.created_at.isoformat(),
                "action": log.action,
                "user_id": user_id_str,
                "user_email": user_email_map.get(user_id_str) if user_id_str else None,
                "resource_type": log.resource_type,
                "resource_id": str(log.resource_id) if log.resource_id else None,
                "ip_address": str(log.ip_address) if log.ip_address else None,
                "user_agent": log.user_agent,
                "details": log.details
            })

        content = json.dumps(export_data, indent=2)
        content_type = "application/json"
        filename = f"audit_logs_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"

    # Log export action
    audit_logger = AuditLogger(db)
    await audit_logger.log(
        action=AuditAction.AUDIT_EXPORT,
        user_id=str(current_user.id),
        resource_type="audit_logs",
        details={
            "format": export_request.format,
            "count": len(logs),
            "filters": export_request.dict(exclude_unset=True)
        }
    )

    # Return export data
    from fastapi.responses import Response
    return Response(
        content=content,
        media_type=content_type,
        headers={
            "Content-Disposition": f"attachment; filename={filename}"
        }
    )


@router.delete("/cleanup")
async def cleanup_old_audit_logs(
    days: int = Query(90, ge=30, le=365, description="Delete logs older than this many days"),
    current_user=Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Delete old audit logs for compliance (admin only).
    """
    cutoff_date = datetime.utcnow() - timedelta(days=days)

    # Count logs to be deleted - use created_at
    count_result = await db.execute(
        select(func.count()).select_from(AuditLog).where(
            AuditLog.created_at < cutoff_date
        )
    )
    count = count_result.scalar()

    # Delete logs
    await db.execute(
        delete(AuditLog).where(AuditLog.created_at < cutoff_date)
    )

    await db.commit()

    # Log cleanup action
    audit_logger = AuditLogger(db)
    await audit_logger.log(
        action=AuditAction.AUDIT_CLEANUP,
        user_id=str(current_user.id),
        resource_type="audit_logs",
        details={
            "deleted_count": count,
            "cutoff_date": cutoff_date.isoformat(),
            "retention_days": days
        }
    )

    return {
        "message": f"Deleted {count} audit log entries older than {days} days",
        "deleted_count": count,
        "cutoff_date": cutoff_date.isoformat()
    }


@router.get("/actions/list")
async def list_available_actions(
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get list of all available audit actions.
    """
    # Get all action values from enum
    actions = [action.value for action in AuditAction]

    # Get usage counts for each action - simplified query without tenant_id
    action_counts = {}
    for action in actions:
        count_result = await db.execute(
            select(func.count()).select_from(AuditLog).where(
                AuditLog.action == action
            )
        )
        count = count_result.scalar()
        action_counts[action] = count

    return {
        "actions": actions,
        "counts": action_counts
    }
