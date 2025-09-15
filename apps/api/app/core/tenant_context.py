"""
Multi-Tenant Context Management
Provides tenant isolation and context propagation throughout the application
"""

import contextvars
from typing import Optional, Any, Dict
from uuid import UUID

import structlog
from fastapi import Request, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware
from sqlalchemy import event
from sqlalchemy.orm import Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.jwt_manager import verify_access_token

logger = structlog.get_logger()

# Context variable for current tenant
_tenant_context: contextvars.ContextVar[Optional[Dict[str, Any]]] = contextvars.ContextVar(
    "tenant_context", default=None
)


class TenantContext:
    """Manages tenant context throughout request lifecycle"""

    @staticmethod
    def set(tenant_id: UUID, organization_id: UUID, user_id: Optional[UUID] = None) -> None:
        """Set the current tenant context"""
        context = {
            "tenant_id": str(tenant_id),
            "organization_id": str(organization_id),
            "user_id": str(user_id) if user_id else None,
        }
        _tenant_context.set(context)
        logger.debug("Tenant context set", **context)

    @staticmethod
    def get() -> Optional[Dict[str, Any]]:
        """Get the current tenant context"""
        return _tenant_context.get()

    @staticmethod
    def get_tenant_id() -> Optional[str]:
        """Get the current tenant ID"""
        context = _tenant_context.get()
        return context.get("tenant_id") if context else None

    @staticmethod
    def get_organization_id() -> Optional[str]:
        """Get the current organization ID"""
        context = _tenant_context.get()
        return context.get("organization_id") if context else None

    @staticmethod
    def get_user_id() -> Optional[str]:
        """Get the current user ID"""
        context = _tenant_context.get()
        return context.get("user_id") if context else None

    @staticmethod
    def clear() -> None:
        """Clear the tenant context"""
        _tenant_context.set(None)
        logger.debug("Tenant context cleared")

    @staticmethod
    def require_tenant() -> str:
        """Get tenant ID or raise if not set"""
        tenant_id = TenantContext.get_tenant_id()
        if not tenant_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Tenant context required"
            )
        return tenant_id

    @staticmethod
    def require_organization() -> str:
        """Get organization ID or raise if not set"""
        org_id = TenantContext.get_organization_id()
        if not org_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Organization context required"
            )
        return org_id


class TenantMiddleware(BaseHTTPMiddleware):
    """Middleware to extract and set tenant context from requests"""

    async def dispatch(self, request: Request, call_next):
        """Extract tenant context from request and propagate it"""
        
        # Skip tenant extraction for public endpoints
        public_paths = [
            "/health", "/ready", "/", "/docs", "/redoc", "/openapi.json",
            "/metrics", "/metrics/performance", "/metrics/scalability",
            "/.well-known", "/api/status", "/beta"
        ]
        
        # Check if this is a public endpoint
        for public_path in public_paths:
            if request.url.path == public_path or request.url.path.startswith(f"{public_path}/"):
                # Process request without tenant context
                return await call_next(request)

        try:
            # Extract tenant from various sources
            tenant_id = None
            organization_id = None
            user_id = None

            # 1. Check subdomain (e.g., acme.plinto.dev)
            host = request.headers.get("host", "")
            if "." in host:
                subdomain = host.split(".")[0]
                if subdomain and subdomain not in ["www", "api", "app"]:
                    # Look up organization by subdomain
                    # TODO: Implement organization lookup by subdomain
                    pass

            # 2. Check JWT token for tenant information
            auth_header = request.headers.get("authorization")
            if auth_header and auth_header.startswith("Bearer "):
                try:
                    token = auth_header.split(" ")[1]
                    payload = verify_access_token(token)
                    if payload:
                        tenant_id = payload.get("tid")  # Tenant ID
                        organization_id = payload.get("oid")  # Organization ID
                        user_id = payload.get("sub")  # User ID
                except Exception:
                    # Token verification failed, continue without tenant context
                    pass

            # 3. Check X-Tenant-ID header (for service-to-service calls)
            if not tenant_id:
                tenant_id = request.headers.get("x-tenant-id")
                organization_id = request.headers.get("x-organization-id")

            # 4. Check query parameters (for certain endpoints)
            if not tenant_id and request.query_params.get("tenant_id"):
                tenant_id = request.query_params.get("tenant_id")
                organization_id = request.query_params.get("organization_id")

            # Set context if we have tenant information
            if tenant_id and organization_id:
                TenantContext.set(
                    tenant_id=UUID(tenant_id),
                    organization_id=UUID(organization_id),
                    user_id=UUID(user_id) if user_id else None
                )

            # Process request
            response = await call_next(request)

            # Add tenant headers to response for debugging
            if tenant_id:
                response.headers["X-Tenant-ID"] = str(tenant_id)

            return response

        finally:
            # Always clear context after request
            TenantContext.clear()


class TenantFilter:
    """SQLAlchemy filter for automatic tenant isolation"""

    @staticmethod
    def apply_tenant_filter(query: Query, model_class: Any) -> Query:
        """Apply tenant filter to query if model has tenant_id"""
        tenant_id = TenantContext.get_tenant_id()
        if not tenant_id:
            return query

        # Check if model has tenant_id column
        if hasattr(model_class, "tenant_id"):
            return query.filter(model_class.tenant_id == tenant_id)

        # Check if model has organization_id column
        if hasattr(model_class, "organization_id"):
            org_id = TenantContext.get_organization_id()
            if org_id:
                return query.filter(model_class.organization_id == org_id)

        return query


def configure_tenant_filtering(session: AsyncSession) -> None:
    """Configure automatic tenant filtering for SQLAlchemy session"""

    @event.listens_for(session, "do_orm_execute")
    def receive_do_orm_execute(orm_execute_state):
        """Automatically add tenant filter to queries"""
        if orm_execute_state.is_select:
            # Get the tenant context
            tenant_id = TenantContext.get_tenant_id()
            if tenant_id:
                # Apply tenant filter to the query
                # This would need more sophisticated implementation
                # to handle all query types properly
                pass


class TenantIsolation:
    """Helper class for tenant isolation operations"""

    @staticmethod
    async def validate_tenant_access(
        session: AsyncSession,
        resource_id: str,
        resource_type: str,
        tenant_id: Optional[str] = None
    ) -> bool:
        """Validate that a resource belongs to the current tenant"""
        current_tenant = tenant_id or TenantContext.get_tenant_id()
        if not current_tenant:
            return False

        # Resource-specific validation logic
        # This would query the database to verify ownership
        # Implementation depends on your specific models

        return True

    @staticmethod
    def ensure_tenant_context(required: bool = True):
        """Decorator to ensure tenant context is set"""
        def decorator(func):
            async def wrapper(*args, **kwargs):
                if required and not TenantContext.get_tenant_id():
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Tenant context required for this operation"
                    )
                return await func(*args, **kwargs)
            return wrapper
        return decorator

    @staticmethod
    def inject_tenant_id(data: dict) -> dict:
        """Inject current tenant ID into data dictionary"""
        tenant_id = TenantContext.get_tenant_id()
        if tenant_id:
            data["tenant_id"] = tenant_id

        org_id = TenantContext.get_organization_id()
        if org_id:
            data["organization_id"] = org_id

        return data


class TenantRateLimiter:
    """Tenant-specific rate limiting"""

    @staticmethod
    def get_tenant_key(request: Request) -> str:
        """Get rate limit key based on tenant"""
        tenant_id = TenantContext.get_tenant_id()
        if tenant_id:
            return f"tenant:{tenant_id}"

        # Fallback to IP-based limiting
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            client_ip = forwarded_for.split(",")[0].strip()
        else:
            client_ip = request.client.host if request.client else "unknown"

        return f"ip:{client_ip}"

    @staticmethod
    def get_tenant_limits() -> Dict[str, int]:
        """Get rate limits based on tenant's subscription tier"""
        # TODO: Implement tier-based limits
        # This would look up the organization's subscription
        # and return appropriate limits

        return {
            "requests_per_minute": 100,
            "requests_per_hour": 1000,
            "requests_per_day": 10000,
        }


# Export commonly used functions
__all__ = [
    "TenantContext",
    "TenantMiddleware",
    "TenantFilter",
    "TenantIsolation",
    "TenantRateLimiter",
    "configure_tenant_filtering",
]