"""
Optimized Authentication Service
Implements caching, connection pooling, and sub-100ms response patterns
"""

import asyncio
import time
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
import logging

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_
from sqlalchemy.orm import selectinload

from app.models import User, Session, UserStatus, SessionStatus
from app.core.performance import performance_cache, cache_manager, performance_context
from app.core.security import verify_password, create_access_token, decode_token

logger = logging.getLogger(__name__)

class OptimizedAuthService:
    """High-performance authentication service with caching and optimization"""
    
    @staticmethod
    @performance_cache(namespace="user_profile", ttl=300)  # 5 minute cache
    async def get_user_by_email(db: AsyncSession, email: str) -> Optional[Dict[str, Any]]:
        """Get user by email with performance optimization"""
        async with performance_context():
            # Optimized query with selective loading
            query = select(User).where(
                and_(
                    User.email == email,
                    User.status == UserStatus.ACTIVE
                )
            ).options(
                # Only load necessary fields for authentication
                selectinload(User.sessions).selectinload(Session.user)
            )
            
            result = await db.execute(query)
            user = result.scalar_one_or_none()
            
            if user:
                # Return serialized user data for caching
                return {
                    'id': str(user.id),
                    'email': user.email,
                    'password_hash': user.password_hash,
                    'email_verified': user.email_verified,
                    'mfa_enabled': user.mfa_enabled,
                    'status': user.status.value,
                    'last_sign_in_at': user.last_sign_in_at.isoformat() if user.last_sign_in_at else None,
                }
            return None
    
    @staticmethod
    @performance_cache(namespace="session_validation", ttl=60)  # 1 minute cache
    async def validate_session_fast(db: AsyncSession, access_token_jti: str) -> Optional[Dict[str, Any]]:
        """Fast session validation with aggressive caching"""
        async with performance_context():
            # Highly optimized session query
            query = select(Session).where(
                and_(
                    Session.access_token_jti == access_token_jti,
                    Session.status == SessionStatus.ACTIVE,
                    Session.revoked == False,
                    Session.expires_at > datetime.utcnow()
                )
            ).options(
                selectinload(Session.user)
            )
            
            result = await db.execute(query)
            session = result.scalar_one_or_none()
            
            if session:
                return {
                    'id': str(session.id),
                    'user_id': str(session.user_id),
                    'expires_at': session.expires_at.isoformat(),
                    'user': {
                        'id': str(session.user.id),
                        'email': session.user.email,
                        'status': session.user.status.value,
                        'email_verified': session.user.email_verified
                    }
                }
            return None
    
    @staticmethod
    async def authenticate_user_optimized(
        db: AsyncSession, 
        email: str, 
        password: str
    ) -> Optional[Dict[str, Any]]:
        """Optimized user authentication with performance monitoring"""
        start_time = time.perf_counter()
        
        try:
            # Get user from cache or database
            user_data = await OptimizedAuthService.get_user_by_email(db, email)
            
            if not user_data:
                logger.info(f"Authentication failed - user not found: {email}")
                return None
            
            # Verify password
            if not user_data.get('password_hash'):
                logger.info(f"Authentication failed - no password hash: {email}")
                return None
            
            if not verify_password(password, user_data['password_hash']):
                logger.info(f"Authentication failed - invalid password: {email}")
                return None
            
            # Check if email is verified (if required)
            if not user_data.get('email_verified', False):
                logger.info(f"Authentication failed - email not verified: {email}")
                return None
            
            duration = time.perf_counter() - start_time
            logger.info(f"User authenticated successfully in {duration * 1000:.2f}ms: {email}")
            
            return user_data
            
        except Exception as e:
            duration = time.perf_counter() - start_time
            logger.error(f"Authentication error after {duration * 1000:.2f}ms: {e}")
            return None
    
    @staticmethod
    async def create_session_optimized(
        db: AsyncSession,
        user_id: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        device_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create session with optimized token generation"""
        async with performance_context():
            # Generate tokens
            access_token_data = {
                'sub': user_id,
                'type': 'access'
            }
            
            refresh_token_data = {
                'sub': user_id,
                'type': 'refresh'
            }
            
            access_token, access_jti = create_access_token(access_token_data)
            refresh_token, refresh_jti = create_access_token(
                refresh_token_data, 
                expires_delta=timedelta(days=30)
            )
            
            # Create session record
            session = Session(
                user_id=user_id,
                access_token_jti=access_jti,
                refresh_token_jti=refresh_jti,
                ip_address=ip_address,
                user_agent=user_agent,
                device_name=device_name,
                expires_at=datetime.utcnow() + timedelta(hours=24)
            )
            
            db.add(session)
            await db.flush()  # Get the session ID without full commit
            
            # Cache the session for fast validation
            session_data = {
                'id': str(session.id),
                'user_id': str(session.user_id),
                'expires_at': session.expires_at.isoformat(),
                'access_token_jti': access_jti
            }
            
            await cache_manager.set(
                namespace="session_validation",
                key=access_jti,
                value=session_data,
                ttl=3600  # 1 hour
            )
            
            return {
                'session_id': str(session.id),
                'access_token': access_token,
                'refresh_token': refresh_token,
                'expires_at': session.expires_at.isoformat()
            }
    
    @staticmethod
    async def get_current_user_optimized(
        db: AsyncSession, 
        access_token: str
    ) -> Optional[Dict[str, Any]]:
        """Get current user with optimized token validation"""
        async with performance_context():
            try:
                # Decode token to get JTI
                payload = decode_token(access_token)
                if not payload:
                    return None
                
                access_jti = payload.get('jti')
                if not access_jti:
                    return None
                
                # Fast session validation from cache
                session_data = await OptimizedAuthService.validate_session_fast(db, access_jti)
                if not session_data:
                    return None
                
                # Update last activity (async, don't wait)
                asyncio.create_task(
                    OptimizedAuthService._update_session_activity(db, session_data['id'])
                )
                
                return session_data['user']
                
            except Exception as e:
                logger.error(f"Token validation error: {e}")
                return None
    
    @staticmethod
    async def _update_session_activity(db: AsyncSession, session_id: str):
        """Update session activity asynchronously"""
        try:
            # Update session last_active_at
            await db.execute(
                select(Session).where(Session.id == session_id)
            )
            # This would update the last_active_at field
            # Implementation depends on your update pattern preference
            await db.commit()
            
            # Invalidate related caches
            await cache_manager.clear_namespace("session_validation")
            
        except Exception as e:
            logger.warning(f"Failed to update session activity: {e}")
    
    @staticmethod
    async def revoke_session_optimized(
        db: AsyncSession, 
        session_id: str,
        access_token_jti: str
    ) -> bool:
        """Revoke session with cache invalidation"""
        async with performance_context():
            try:
                # Update session in database
                query = select(Session).where(Session.id == session_id)
                result = await db.execute(query)
                session = result.scalar_one_or_none()
                
                if session:
                    session.status = SessionStatus.REVOKED
                    session.revoked = True
                    session.revoked_at = datetime.utcnow()
                    
                    await db.commit()
                    
                    # Remove from cache
                    await cache_manager.delete(
                        namespace="session_validation",
                        key=access_token_jti
                    )
                    
                    return True
                
                return False
                
            except Exception as e:
                logger.error(f"Session revocation error: {e}")
                await db.rollback()
                return False
    
    @staticmethod
    async def cleanup_expired_sessions(db: AsyncSession) -> int:
        """Clean up expired sessions (background task)"""
        try:
            # This would typically be run as a background task
            # Delete expired sessions
            from sqlalchemy import delete
            
            result = await db.execute(
                delete(Session).where(
                    or_(
                        Session.expires_at < datetime.utcnow(),
                        and_(
                            Session.status == SessionStatus.EXPIRED,
                            Session.created_at < datetime.utcnow() - timedelta(days=30)
                        )
                    )
                )
            )
            
            await db.commit()
            
            # Clear related caches
            await cache_manager.clear_namespace("session_validation")
            
            deleted_count = result.rowcount
            logger.info(f"Cleaned up {deleted_count} expired sessions")
            
            return deleted_count
            
        except Exception as e:
            logger.error(f"Session cleanup error: {e}")
            await db.rollback()
            return 0

# Performance monitoring utilities
class AuthPerformanceMonitor:
    """Monitor authentication performance metrics"""
    
    @staticmethod
    async def get_auth_metrics() -> Dict[str, Any]:
        """Get authentication performance metrics"""
        return {
            'cache_stats': cache_manager.get_stats(),
            'timestamp': datetime.now().isoformat()
        }
    
    @staticmethod
    async def log_slow_auth_operation(operation: str, duration_ms: float, context: Dict[str, Any]):
        """Log slow authentication operations for optimization"""
        if duration_ms > 100:  # Log operations over 100ms
            logger.warning(
                f"Slow auth operation: {operation} took {duration_ms:.2f}ms",
                extra={'context': context}
            )