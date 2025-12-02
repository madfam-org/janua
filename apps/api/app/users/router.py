"""
User profile management endpoints for beta users
"""

from datetime import datetime
from typing import Optional, List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
import structlog

from app.config import settings
from app.core.database import get_db
from app.core.redis import get_redis
from app.models.user import User, Session
from app.services.auth_service import AuthService

logger = structlog.get_logger()
router = APIRouter()
security = HTTPBearer()


# Request/Response models
class UpdateProfileRequest(BaseModel):
    name: Optional[str] = None
    avatar_url: Optional[str] = None


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


class UserProfileResponse(BaseModel):
    id: str
    email: str
    name: Optional[str]
    avatar_url: Optional[str]
    email_verified: bool
    created_at: str
    updated_at: str
    last_login_at: Optional[str]
    is_active: bool


class UserSessionResponse(BaseModel):
    id: str
    device_name: Optional[str]
    ip_address: Optional[str]
    user_agent: Optional[str]
    created_at: str
    last_activity_at: str
    is_current: bool


# Dependency to get current user
async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db)
) -> User:
    """Get current authenticated user"""
    # Validate access token
    payload = await AuthService.verify_token(credentials.credentials, token_type="access")
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token"
        )
    
    # Fetch user from database
    user = await db.get(User, UUID(payload.get("sub")))
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive"
        )
    
    return user


@router.get("/profile", response_model=UserProfileResponse)
async def get_user_profile(
    current_user: User = Depends(get_current_user)
):
    """Get current user's profile information"""
    return UserProfileResponse(
        id=str(current_user.id),
        email=current_user.email,
        name=current_user.name,
        avatar_url=current_user.avatar_url,
        email_verified=current_user.email_verified,
        created_at=current_user.created_at.isoformat(),
        updated_at=current_user.updated_at.isoformat(),
        last_login_at=current_user.last_login_at.isoformat() if current_user.last_login_at else None,
        is_active=current_user.is_active
    )


@router.put("/profile", response_model=UserProfileResponse)
async def update_user_profile(
    request: UpdateProfileRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Update current user's profile information"""
    try:
        # Update fields if provided
        if request.name is not None:
            current_user.name = request.name
        
        if request.avatar_url is not None:
            current_user.avatar_url = request.avatar_url
        
        current_user.updated_at = datetime.utcnow()
        
        # Save changes
        await db.commit()
        await db.refresh(current_user)
        
        # Create audit log
        await AuthService.create_audit_log(
            db=db,
            user_id=current_user.id,
            tenant_id=current_user.tenant_id,
            event_type="profile_updated",
            event_data={
                "name_updated": request.name is not None,
                "avatar_updated": request.avatar_url is not None
            }
        )
        
        logger.info("Profile updated", user_id=str(current_user.id))
        
        return UserProfileResponse(
            id=str(current_user.id),
            email=current_user.email,
            name=current_user.name,
            avatar_url=current_user.avatar_url,
            email_verified=current_user.email_verified,
            created_at=current_user.created_at.isoformat(),
            updated_at=current_user.updated_at.isoformat(),
            last_login_at=current_user.last_login_at.isoformat() if current_user.last_login_at else None,
            is_active=current_user.is_active
        )
        
    except Exception as e:
        logger.error("Failed to update profile", error=str(e), user_id=str(current_user.id))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update profile"
        )


@router.post("/change-password")
async def change_password(
    request: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Change user's password"""
    try:
        # Verify current password
        if not AuthService.verify_password(request.current_password, current_user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Current password is incorrect"
            )
        
        # Validate new password strength
        is_valid, error_msg = AuthService.validate_password_strength(request.new_password)
        if not is_valid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=error_msg
            )
        
        # Update password
        current_user.password_hash = AuthService.hash_password(request.new_password)
        current_user.updated_at = datetime.utcnow()
        
        await db.commit()
        
        # Create audit log
        await AuthService.create_audit_log(
            db=db,
            user_id=current_user.id,
            tenant_id=current_user.tenant_id,
            event_type="password_changed",
            event_data={}
        )
        
        # Revoke all existing sessions for security (force re-login on all devices)
        # Keep only the current session if revoke_other_sessions query param is False
        try:
            from sqlalchemy import update as sql_update
            
            # Get current session token from request context if available
            # For maximum security, revoke ALL sessions including current
            await db.execute(
                sql_update(Session)
                .where(Session.user_id == current_user.id)
                .where(Session.is_active == True)
                .values(
                    is_active=False,
                    revoked_at=datetime.utcnow(),
                    revoked_reason="password_changed"
                )
            )
            await db.commit()
            
            logger.info(
                "All sessions revoked after password change",
                user_id=str(current_user.id)
            )
        except Exception as session_err:
            # Log but don't fail the password change
            logger.warning(
                "Failed to revoke sessions after password change",
                error=str(session_err),
                user_id=str(current_user.id)
            )
        
        logger.info("Password changed", user_id=str(current_user.id))
        
        return {"message": "Password changed successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to change password", error=str(e), user_id=str(current_user.id))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to change password"
        )


@router.get("/sessions", response_model=List[UserSessionResponse])
async def get_user_sessions(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get user's active sessions"""
    try:
        # Get user's active sessions
        result = await db.execute(
            select(Session)
            .where(Session.user_id == current_user.id)
            .where(Session.is_active == True)
            .order_by(Session.last_activity_at.desc())
        )
        sessions = result.scalars().all()
        
        # Get current session (from token)
        # For now, we'll mark the first session as current
        current_session_id = sessions[0].id if sessions else None
        
        session_list = []
        for session in sessions:
            session_list.append(UserSessionResponse(
                id=str(session.id),
                device_name=session.device_name,
                ip_address=session.ip_address,
                user_agent=session.user_agent,
                created_at=session.created_at.isoformat(),
                last_activity_at=session.last_activity_at.isoformat(),
                is_current=session.id == current_session_id
            ))
        
        return session_list
        
    except Exception as e:
        logger.error("Failed to get sessions", error=str(e), user_id=str(current_user.id))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve sessions"
        )


@router.delete("/sessions/{session_id}")
async def revoke_session(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Revoke a specific session"""
    try:
        session_uuid = UUID(session_id)
        
        # Check if session belongs to current user
        session = await db.get(Session, session_uuid)
        if not session or session.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Session not found"
            )
        
        # Revoke session using AuthService
        success = await AuthService.logout(db, session_uuid, current_user.id)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to revoke session"
            )
        
        logger.info("Session revoked", session_id=session_id, user_id=str(current_user.id))
        
        return {"message": "Session revoked successfully"}
        
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid session ID format"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to revoke session", error=str(e), user_id=str(current_user.id))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to revoke session"
        )


@router.delete("/sessions")
async def revoke_all_sessions(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Revoke all user sessions (logout from all devices)"""
    try:
        # Get all active sessions
        result = await db.execute(
            select(Session)
            .where(Session.user_id == current_user.id)
            .where(Session.is_active == True)
        )
        sessions = result.scalars().all()
        
        # Revoke all sessions
        revoked_count = 0
        for session in sessions:
            success = await AuthService.logout(db, session.id, current_user.id)
            if success:
                revoked_count += 1
        
        # Create audit log
        await AuthService.create_audit_log(
            db=db,
            user_id=current_user.id,
            tenant_id=current_user.tenant_id,
            event_type="all_sessions_revoked",
            event_data={"sessions_count": revoked_count}
        )
        
        logger.info("All sessions revoked", user_id=str(current_user.id), count=revoked_count)
        
        return {
            "message": f"Successfully revoked {revoked_count} sessions",
            "revoked_count": revoked_count
        }
        
    except Exception as e:
        logger.error("Failed to revoke all sessions", error=str(e), user_id=str(current_user.id))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to revoke sessions"
        )


@router.delete("/account")
async def delete_account(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Delete user account (soft delete)"""
    try:
        # Soft delete user account
        current_user.is_active = False
        current_user.updated_at = datetime.utcnow()
        
        # Revoke all sessions
        await db.execute(
            update(Session)
            .where(Session.user_id == current_user.id)
            .where(Session.is_active == True)
            .values(
                is_active=False,
                revoked_at=datetime.utcnow(),
                revoked_reason="account_deleted"
            )
        )
        
        # Create audit log
        await AuthService.create_audit_log(
            db=db,
            user_id=current_user.id,
            tenant_id=current_user.tenant_id,
            event_type="account_deleted",
            event_data={}
        )
        
        await db.commit()
        
        logger.info("Account deleted", user_id=str(current_user.id))
        
        return {"message": "Account deleted successfully"}
        
    except Exception as e:
        logger.error("Failed to delete account", error=str(e), user_id=str(current_user.id))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete account"
        )