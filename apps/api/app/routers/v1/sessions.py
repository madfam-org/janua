"""
Session management endpoints
"""

import uuid
from datetime import datetime
from typing import Any, List, Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.routers.v1.auth import get_current_user
from app.services.auth_service import AuthService

from ...models import Session as UserSession
from ...models import User

router = APIRouter(prefix="/sessions", tags=["sessions"])

logger = structlog.get_logger()


def _live_session_filters() -> tuple[Any, ...]:
    """SQL twin of `token_revocation.session_is_live` (minus expiry).

    A row is revoked when ANY revocation flag says so: bulk admin and
    account-deletion updates set only `revoked`, device revocation sets only
    `is_active = False` and `revoked_at`.
    """
    return (
        UserSession.revoked_at.is_(None),
        UserSession.revoked.isnot(True),
        UserSession.is_active.isnot(False),
    )


class SessionResponse(BaseModel):
    """Session response model"""

    id: str
    user_id: str
    ip_address: Optional[str]
    user_agent: Optional[str]
    device_name: Optional[str]
    device_type: Optional[str]
    browser: Optional[str]
    os: Optional[str]
    is_current: bool
    created_at: datetime
    last_activity_at: datetime
    expires_at: datetime
    revoked: bool


class SessionsListResponse(BaseModel):
    """Sessions list response"""

    sessions: List[SessionResponse]
    total: int


def parse_user_agent(user_agent: str) -> dict:
    """Parse user agent string to extract device info"""
    device_info = {
        "device_type": "unknown",
        "browser": "unknown",
        "os": "unknown",
        "device_name": None,
    }

    if not user_agent:
        return device_info

    # Simple parsing (in production, use a library like user-agents)
    user_agent_lower = user_agent.lower()

    # Detect device type
    if "mobile" in user_agent_lower or "android" in user_agent_lower:
        device_info["device_type"] = "mobile"
    elif "tablet" in user_agent_lower or "ipad" in user_agent_lower:
        device_info["device_type"] = "tablet"
    else:
        device_info["device_type"] = "desktop"

    # Detect browser
    if "chrome" in user_agent_lower:
        device_info["browser"] = "Chrome"
    elif "firefox" in user_agent_lower:
        device_info["browser"] = "Firefox"
    elif "safari" in user_agent_lower:
        device_info["browser"] = "Safari"
    elif "edge" in user_agent_lower:
        device_info["browser"] = "Edge"

    # Detect OS
    if "windows" in user_agent_lower:
        device_info["os"] = "Windows"
    elif "mac" in user_agent_lower:
        device_info["os"] = "macOS"
    elif "linux" in user_agent_lower:
        device_info["os"] = "Linux"
    elif "android" in user_agent_lower:
        device_info["os"] = "Android"
    elif "ios" in user_agent_lower or "iphone" in user_agent_lower:
        device_info["os"] = "iOS"

    return device_info


@router.get("/", response_model=SessionsListResponse)
async def list_sessions(
    request: Request, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    """List all active sessions for current user"""
    # Get current session JTI from token
    current_jti = None
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ")[1]
        payload = await AuthService.identify_token(token, token_type="access")
        if payload:
            current_jti = payload.get("jti")

    # Get all active sessions
    result = await db.execute(
        select(UserSession)
        .where(
            UserSession.user_id == current_user.id,
            *_live_session_filters(),
            UserSession.expires_at > datetime.utcnow(),
        )
        .order_by(UserSession.last_activity.desc())
    )
    sessions = result.scalars().all()

    # Convert to response
    sessions_response = []
    for session in sessions:
        device_info = parse_user_agent(session.user_agent)

        sessions_response.append(
            SessionResponse(
                id=str(session.id),
                user_id=str(session.user_id),
                ip_address=session.ip_address,
                user_agent=session.user_agent,
                device_name=device_info["device_name"],
                device_type=device_info["device_type"],
                browser=device_info["browser"],
                os=device_info["os"],
                is_current=session.access_token_jti == current_jti,
                created_at=session.created_at,
                last_activity_at=session.last_activity,
                expires_at=session.expires_at,
                revoked=session.revoked,
            )
        )

    return SessionsListResponse(sessions=sessions_response, total=len(sessions_response))


@router.get("/{session_id}", response_model=SessionResponse)
async def get_session(
    session_id: str,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get specific session details"""
    # Parse UUID
    try:
        session_uuid = uuid.UUID(session_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid session ID")

    # Get session
    result = await db.execute(
        select(UserSession).where(
            UserSession.id == session_uuid, UserSession.user_id == current_user.id
        )
    )
    session = result.scalar_one_or_none()

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Get current session JTI
    current_jti = None
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ")[1]
        payload = await AuthService.identify_token(token, token_type="access")
        if payload:
            current_jti = payload.get("jti")

    device_info = parse_user_agent(session.user_agent)

    return SessionResponse(
        id=str(session.id),
        user_id=str(session.user_id),
        ip_address=session.ip_address,
        user_agent=session.user_agent,
        device_name=device_info["device_name"],
        device_type=device_info["device_type"],
        browser=device_info["browser"],
        os=device_info["os"],
        is_current=session.access_token_jti == current_jti,
        created_at=session.created_at,
        last_activity_at=session.last_activity,
        expires_at=session.expires_at,
        revoked=session.revoked,
    )


@router.delete("/{session_id}")
async def revoke_session(
    session_id: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    """Revoke a specific session.

    Only the session's owner, or a platform admin (`is_admin`, the same gate as
    the admin API's session revocation), may revoke it. Anyone else gets 404,
    the same answer as for a session that does not exist. Revoking marks the
    row revoked, revokes its refresh-token family (so `/auth/refresh` refuses
    it) and blacklists its current access token; the account chooser and
    account switching stop offering it because they only accept live rows.
    """
    # Parse UUID
    try:
        session_uuid = uuid.UUID(session_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid session ID")

    query = select(UserSession).where(UserSession.id == session_uuid)
    is_admin = bool(getattr(current_user, "is_admin", False))
    if not is_admin:
        query = query.where(UserSession.user_id == current_user.id)
    result = await db.execute(query)
    session = result.scalar_one_or_none()

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    if session.revoked or session.is_active is False or session.revoked_at is not None:
        raise HTTPException(status_code=400, detail="Session already revoked")

    by_admin = session.user_id != current_user.id
    await AuthService.revoke_sessions(
        [session], reason="admin_revoked" if by_admin else "user_revoked"
    )
    await db.commit()
    logger.info(
        "Session revoked via sessions API",
        session_id=str(session.id),
        by_admin=by_admin,
    )

    return {"message": "Session revoked successfully"}


@router.delete("/")
async def revoke_all_sessions(
    request: Request, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    """Revoke all of the caller's sessions except the current one.

    Each revoked session's refresh-token family stops refreshing. The current
    session is the one whose access token made this request; when it cannot be
    identified, every session is revoked.
    """
    # Get current session JTI
    current_jti = None
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ")[1]
        payload = await AuthService.identify_token(token, token_type="access")
        if payload:
            current_jti = payload.get("jti")

    query = select(UserSession).where(
        UserSession.user_id == current_user.id,
        *_live_session_filters(),
    )
    if current_jti:
        # `!=` alone would also drop rows whose access_token_jti is NULL.
        query = query.where(
            (UserSession.access_token_jti != current_jti) | UserSession.access_token_jti.is_(None)
        )
    result = await db.execute(query)
    sessions = result.scalars().all()

    revoked_count = await AuthService.revoke_sessions(sessions, reason="user_revoked_all")
    await db.commit()

    return {"message": f"Revoked {revoked_count} sessions", "revoked_count": revoked_count}


@router.post("/{session_id}/refresh")
async def refresh_session(
    session_id: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    """Refresh a session's expiration"""
    # Parse UUID
    try:
        session_uuid = uuid.UUID(session_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid session ID")

    # Get session
    result = await db.execute(
        select(UserSession).where(
            UserSession.id == session_uuid,
            UserSession.user_id == current_user.id,
            UserSession.revoked_at.is_(None),
        )
    )
    session = result.scalar_one_or_none()

    if not session:
        raise HTTPException(status_code=404, detail="Session not found or revoked")

    # Update last activity
    session.last_activity = datetime.utcnow()
    await db.commit()

    return {"message": "Session refreshed successfully"}


@router.get("/activity/recent")
async def get_recent_activity(
    limit: int = Query(10, ge=1, le=50),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get recent session activity"""
    # Get recent sessions with activity
    result = await db.execute(
        select(UserSession)
        .where(UserSession.user_id == current_user.id)
        .order_by(UserSession.last_activity.desc())
        .limit(limit)
    )
    sessions = result.scalars().all()

    activities = []
    for session in sessions:
        device_info = parse_user_agent(session.user_agent)

        activities.append(
            {
                "session_id": str(session.id),
                "activity_type": "session_created"
                if session.created_at == session.last_activity
                else "session_active",
                "timestamp": session.last_activity,
                "ip_address": session.ip_address,
                "device": f"{device_info['browser']} on {device_info['os']}",
                "device_type": device_info["device_type"],
                "revoked": session.revoked,
            }
        )

    return {"activities": activities, "total": len(activities)}


@router.get("/security/alerts")
async def get_security_alerts(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    """Get security alerts for sessions"""
    alerts = []

    # Check for sessions from new locations
    result = await db.execute(
        select(UserSession).where(
            UserSession.user_id == current_user.id, UserSession.revoked_at.is_(None)
        )
    )
    sessions = result.scalars().all()

    # Get unique IPs
    ip_addresses = set()
    for session in sessions:
        if session.ip_address:
            ip_addresses.add(session.ip_address)

    # Alert if multiple IPs
    if len(ip_addresses) > 1:
        alerts.append(
            {
                "type": "multiple_locations",
                "severity": "info",
                "message": f"Sessions active from {len(ip_addresses)} different locations",
                "locations": list(ip_addresses),
            }
        )

    # Check for old sessions
    old_sessions = []
    for session in sessions:
        days_old = (datetime.utcnow() - session.created_at).days
        if days_old > 30:
            old_sessions.append(str(session.id))

    if old_sessions:
        alerts.append(
            {
                "type": "old_sessions",
                "severity": "warning",
                "message": f"{len(old_sessions)} sessions older than 30 days",
                "session_ids": old_sessions,
            }
        )

    # Check for suspicious user agents
    suspicious_agents = []
    for session in sessions:
        if session.user_agent and (
            "bot" in session.user_agent.lower() or "curl" in session.user_agent.lower()
        ):
            suspicious_agents.append(str(session.id))

    if suspicious_agents:
        alerts.append(
            {
                "type": "suspicious_user_agent",
                "severity": "warning",
                "message": "Suspicious user agents detected",
                "session_ids": suspicious_agents,
            }
        )

    return {"alerts": alerts, "total": len(alerts)}
