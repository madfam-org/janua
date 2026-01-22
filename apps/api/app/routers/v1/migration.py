"""
Migration API endpoints for data portability and user migration
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field
import logging
import asyncio
import json

from app.core.database_manager import get_db
from app.dependencies import require_admin
from app.models import User
from app.models.migration import (
    MigrationJob,
    MigrationProvider,
    MigrationStatus,
    MigratedUser,
    MigrationLog,
    MigrationTemplate,
)
from app.services.migration_service import MigrationService

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/migration",
    tags=["Migration"],
    responses={404: {"description": "Not found"}},
)


# Pydantic models
class MigrationJobCreate(BaseModel):
    """Create migration job request"""

    name: str = Field(..., max_length=200)
    provider: MigrationProvider
    source_config: Dict[str, Any]
    mapping_config: Optional[Dict[str, Any]] = None
    options: Optional[Dict[str, Any]] = None


class MigrationJobResponse(BaseModel):
    """Migration job response"""

    id: str
    name: str
    provider: MigrationProvider
    status: MigrationStatus
    total_users: int
    migrated_users: int
    failed_users: int
    skipped_users: int
    started_at: Optional[str]
    completed_at: Optional[str]
    estimated_completion: Optional[str]
    last_error: Optional[str]
    created_at: str
    updated_at: str


class MigrationProgressResponse(BaseModel):
    """Migration progress update"""

    type: str  # progress, completed, error
    total: Optional[int] = None
    migrated: Optional[int] = None
    failed: Optional[int] = None
    skipped: Optional[int] = None
    current_user: Optional[str] = None
    error: Optional[str] = None


class DataExportRequest(BaseModel):
    """Data export request"""

    export_type: str  # user_data, organization_data, audit_logs
    format: str = "json"  # json, csv, xml
    include_options: Optional[Dict[str, Any]] = None
    exclude_options: Optional[Dict[str, Any]] = None


# Initialize migration service
migration_service = MigrationService()


@router.post("/jobs", response_model=Dict[str, str])
async def create_migration_job(
    job_request: MigrationJobCreate,
    organization_id: Optional[str] = None,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Create a new migration job

    Requires admin privileges.
    """
    try:
        result = await migration_service.create_migration_job(
            db=db,
            organization_id=organization_id,
            provider=job_request.provider,
            name=job_request.name,
            source_config=job_request.source_config,
            mapping_config=job_request.mapping_config,
            options=job_request.options,
        )
        return result

    except Exception as e:
        logger.exception("Failed to create migration job")
        raise HTTPException(
            status_code=500, detail="Failed to create migration job. Please contact support."
        )


@router.get("/jobs", response_model=List[MigrationJobResponse])
async def list_migration_jobs(
    organization_id: Optional[str] = None,
    status: Optional[MigrationStatus] = None,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    List migration jobs

    Requires admin privileges.
    """
    try:
        stmt = select(MigrationJob)

        if organization_id:
            stmt = stmt.where(MigrationJob.organization_id == organization_id)

        if status:
            stmt = stmt.where(MigrationJob.status == status)

        result = await db.execute(stmt)
        jobs = result.scalars().all()

        return [
            MigrationJobResponse(
                id=str(job.id),
                name=job.name,
                provider=job.provider,
                status=job.status,
                total_users=job.total_users,
                migrated_users=job.migrated_users,
                failed_users=job.failed_users,
                skipped_users=job.skipped_users,
                started_at=job.started_at.isoformat() if job.started_at else None,
                completed_at=job.completed_at.isoformat() if job.completed_at else None,
                estimated_completion=job.estimated_completion.isoformat()
                if job.estimated_completion
                else None,
                last_error=job.last_error,
                created_at=job.created_at.isoformat(),
                updated_at=job.updated_at.isoformat(),
            )
            for job in jobs
        ]

    except Exception as e:
        logger.exception("Failed to list migration jobs")
        raise HTTPException(
            status_code=500, detail="Failed to list migration jobs. Please contact support."
        )


@router.get("/jobs/{job_id}", response_model=MigrationJobResponse)
async def get_migration_job(
    job_id: str, current_user: User = Depends(require_admin), db: AsyncSession = Depends(get_db)
):
    """
    Get migration job details

    Requires admin privileges.
    """
    try:
        job = await db.get(MigrationJob, job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Migration job not found")

        return MigrationJobResponse(
            id=str(job.id),
            name=job.name,
            provider=job.provider,
            status=job.status,
            total_users=job.total_users,
            migrated_users=job.migrated_users,
            failed_users=job.failed_users,
            skipped_users=job.skipped_users,
            started_at=job.started_at.isoformat() if job.started_at else None,
            completed_at=job.completed_at.isoformat() if job.completed_at else None,
            estimated_completion=job.estimated_completion.isoformat()
            if job.estimated_completion
            else None,
            last_error=job.last_error,
            created_at=job.created_at.isoformat(),
            updated_at=job.updated_at.isoformat(),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to get migration job")
        raise HTTPException(
            status_code=500, detail="Failed to get migration job. Please contact support."
        )


@router.post("/jobs/{job_id}/start")
async def start_migration_job(
    job_id: str,
    batch_size: int = 100,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Start migration job with real-time progress streaming

    Returns Server-Sent Events (SSE) stream with progress updates.
    """

    async def generate_progress():
        try:
            async for progress in migration_service.start_migration(
                db=db, job_id=job_id, batch_size=batch_size
            ):
                yield f"data: {json.dumps(progress)}\n\n"

        except Exception as e:
            logger.exception("Migration job failed")
            error_response = {"type": "error", "error": "Migration failed. Please contact support."}
            yield f"data: {json.dumps(error_response)}\n\n"

    return StreamingResponse(
        generate_progress(),
        media_type="text/plain",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Content-Type": "text/event-stream",
        },
    )


@router.delete("/jobs/{job_id}")
async def delete_migration_job(
    job_id: str, current_user: User = Depends(require_admin), db: AsyncSession = Depends(get_db)
):
    """
    Delete migration job

    Requires admin privileges.
    """
    try:
        job = await db.get(MigrationJob, job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Migration job not found")

        if job.status == MigrationStatus.IN_PROGRESS:
            raise HTTPException(
                status_code=400, detail="Cannot delete job while migration is in progress"
            )

        await db.delete(job)
        await db.commit()

        return {"message": "Migration job deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to delete migration job")
        raise HTTPException(
            status_code=500, detail="Failed to delete migration job. Please contact support."
        )


@router.get("/jobs/{job_id}/logs")
async def get_migration_logs(
    job_id: str,
    level: Optional[str] = None,
    limit: int = 100,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Get migration job logs

    Requires admin privileges.
    """
    try:
        stmt = (
            select(MigrationLog)
            .where(MigrationLog.migration_job_id == job_id)
            .order_by(MigrationLog.created_at.desc())
        )

        if level:
            stmt = stmt.where(MigrationLog.level == level)

        result = await db.execute(stmt.limit(limit))
        logs = result.scalars().all()

        return [
            {
                "id": str(log.id),
                "level": log.level,
                "message": log.message,
                "details": log.details,
                "user_id": log.user_id,
                "created_at": log.created_at.isoformat(),
            }
            for log in logs
        ]

    except Exception as e:
        logger.exception("Failed to get migration logs")
        raise HTTPException(
            status_code=500, detail="Failed to get migration logs. Please contact support."
        )


@router.get("/jobs/{job_id}/users")
async def get_migrated_users(
    job_id: str,
    is_migrated: Optional[bool] = None,
    limit: int = 100,
    offset: int = 0,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Get migrated users for a job

    Requires admin privileges.
    """
    try:
        stmt = (
            select(MigratedUser)
            .where(MigratedUser.migration_job_id == job_id)
            .order_by(MigratedUser.created_at.desc())
        )

        if is_migrated is not None:
            stmt = stmt.where(MigratedUser.is_migrated == is_migrated)

        result = await db.execute(stmt.offset(offset).limit(limit))
        users = result.scalars().all()

        return [
            {
                "id": str(user.id),
                "source_user_id": user.source_user_id,
                "source_email": user.source_email,
                "source_username": user.source_username,
                "target_user_id": str(user.target_user_id) if user.target_user_id else None,
                "is_migrated": user.is_migrated,
                "migration_errors": user.migration_errors,
                "password_migrated": user.password_migrated,
                "requires_password_reset": user.requires_password_reset,
                "migrated_at": user.migrated_at.isoformat() if user.migrated_at else None,
                "created_at": user.created_at.isoformat(),
            }
            for user in users
        ]

    except Exception as e:
        logger.exception("Failed to get migrated users")
        raise HTTPException(
            status_code=500, detail="Failed to get migrated users. Please contact support."
        )


@router.get("/templates", response_model=List[Dict[str, Any]])
async def list_migration_templates(
    provider: Optional[MigrationProvider] = None,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    List migration templates

    Requires admin privileges.
    """
    try:
        stmt = select(MigrationTemplate)

        if provider:
            stmt = stmt.where(MigrationTemplate.provider == provider)

        result = await db.execute(stmt)
        templates = result.scalars().all()

        return [
            {
                "id": str(template.id),
                "name": template.name,
                "description": template.description,
                "provider": template.provider.value,
                "field_mappings": template.field_mappings,
                "transformations": template.transformations,
                "is_default": template.is_default,
                "times_used": template.times_used,
                "created_at": template.created_at.isoformat(),
            }
            for template in templates
        ]

    except Exception as e:
        logger.exception("Failed to list migration templates")
        raise HTTPException(
            status_code=500, detail="Failed to list migration templates. Please contact support."
        )


@router.post("/export")
async def export_data(
    export_request: DataExportRequest,
    background_tasks: BackgroundTasks,
    organization_id: Optional[str] = None,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Export organization or user data for portability

    Requires admin privileges.
    """
    try:
        # Create export job in background
        export_id = str(uuid.uuid4())

        background_tasks.add_task(
            _process_data_export,
            db,
            export_id,
            export_request,
            organization_id,
            str(current_user.id),
        )

        return {
            "export_id": export_id,
            "status": "processing",
            "message": "Data export started. You will be notified when complete.",
        }

    except Exception as e:
        logger.exception("Failed to start data export")
        raise HTTPException(
            status_code=500, detail="Failed to start data export. Please contact support."
        )


async def _process_data_export(
    db: AsyncSession,
    export_id: str,
    export_request: DataExportRequest,
    organization_id: Optional[str],
    user_id: str,
):
    """Background task to process data export"""
    try:
        # Implementation would collect and export data
        # This is a placeholder for the actual export logic
        logger.info(f"Processing data export {export_id}")

        # Simulate export processing
        await asyncio.sleep(5)

        # Update export status in database
        # In real implementation, would create DataExport record

        logger.info(f"Data export {export_id} completed")

    except Exception as e:
        logger.exception(f"Data export {export_id} failed")


@router.get("/providers")
async def list_supported_providers():
    """
    List supported migration providers
    """
    return {
        "providers": [
            {
                "id": provider.value,
                "name": provider.name,
                "description": f"Migration from {provider.value.upper()} identity provider",
            }
            for provider in MigrationProvider
        ]
    }
