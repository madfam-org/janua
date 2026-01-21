"""
REST API controller for SSO operations
"""

from typing import Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from ...application.services.sso_orchestrator import SSOOrchestrator
from ...domain.services.user_provisioning import UserProvisioningService
from ...infrastructure.configuration.config_repository import SSOConfigurationRepository
from ...infrastructure.session.session_repository import SSOSessionRepository
from ...exceptions import ValidationError, AuthenticationError
from ....database import get_db
from ....dependencies import get_current_user


class SSOInitiateRequest(BaseModel):
    """Request model for SSO initiation"""
    organization_id: str
    protocol: str
    return_url: Optional[str] = None


class SSOConfigurationRequest(BaseModel):
    """Request model for SSO configuration"""
    organization_id: str
    protocol: str
    provider_name: str
    config: Dict[str, Any]
    attribute_mapping: Optional[Dict[str, str]] = None
    jit_provisioning: bool = True
    default_role: str = "member"


class SSOController:
    """REST controller for SSO operations"""
    
    def __init__(self):
        self.router = APIRouter(prefix="/sso", tags=["SSO"])
        self._setup_routes()
    
    def _setup_routes(self):
        """Setup API routes"""
        
        self.router.post("/initiate")(self.initiate_sso)
        self.router.post("/saml/callback")(self.handle_saml_callback)
        self.router.post("/oidc/callback")(self.handle_oidc_callback)
        self.router.get("/saml/callback")(self.handle_saml_callback)
        self.router.get("/oidc/callback")(self.handle_oidc_callback)
        self.router.post("/logout")(self.initiate_logout)
        self.router.post("/configure")(self.configure_sso)
        self.router.get("/configuration/{organization_id}")(self.get_sso_configuration)
        self.router.get("/protocols")(self.get_supported_protocols)
    
    async def initiate_sso(
        self,
        request: SSOInitiateRequest,
        db: AsyncSession = Depends(get_db)
    ):
        """Initiate SSO authentication flow"""
        
        try:
            orchestrator = await self._get_orchestrator(db)
            
            result = await orchestrator.initiate_authentication(
                organization_id=request.organization_id,
                protocol=request.protocol,
                return_url=request.return_url
            )
            
            return {
                "success": True,
                "auth_url": result["auth_url"],
                "protocol": result["protocol"],
                "params": result.get("params", {})
            }
            
        except (ValidationError, AuthenticationError) as e:
            raise HTTPException(status_code=400, detail=str(e))
        except Exception:
            raise HTTPException(status_code=500, detail="Internal server error")
    
    async def handle_saml_callback(
        self,
        request: Request,
        db: AsyncSession = Depends(get_db)
    ):
        """Handle SAML authentication callback"""
        
        try:
            # Get form data for POST or query params for GET
            if request.method == "POST":
                form_data = await request.form()
                callback_data = dict(form_data)
            else:
                callback_data = dict(request.query_params)
            
            orchestrator = await self._get_orchestrator(db)
            
            result = await orchestrator.handle_authentication_callback(
                protocol="saml2",
                callback_data=callback_data
            )
            
            # Set JWT token in cookie
            response_data = {
                "success": True,
                "user": {
                    "id": result["user"].id,
                    "email": result["user"].email,
                    "name": result["user"].display_name
                },
                "tokens": result["tokens"]
            }
            
            # Redirect to return URL if provided
            if result.get("return_url"):
                response = RedirectResponse(url=result["return_url"])
                response.set_cookie(
                    key="access_token",
                    value=result["tokens"]["access_token"],
                    httponly=True,
                    secure=True,
                    samesite="lax"
                )
                return response
            
            return response_data
            
        except (ValidationError, AuthenticationError) as e:
            raise HTTPException(status_code=400, detail=str(e))
        except Exception:
            raise HTTPException(status_code=500, detail="Internal server error")
    
    async def handle_oidc_callback(
        self,
        request: Request,
        db: AsyncSession = Depends(get_db)
    ):
        """Handle OIDC authentication callback"""
        
        try:
            # OIDC typically uses query parameters
            callback_data = dict(request.query_params)
            
            orchestrator = await self._get_orchestrator(db)
            
            result = await orchestrator.handle_authentication_callback(
                protocol="oidc",
                callback_data=callback_data
            )
            
            # Set JWT token in cookie
            response_data = {
                "success": True,
                "user": {
                    "id": result["user"].id,
                    "email": result["user"].email,
                    "name": result["user"].display_name
                },
                "tokens": result["tokens"]
            }
            
            # Redirect to return URL if provided
            if result.get("return_url"):
                response = RedirectResponse(url=result["return_url"])
                response.set_cookie(
                    key="access_token",
                    value=result["tokens"]["access_token"],
                    httponly=True,
                    secure=True,
                    samesite="lax"
                )
                return response
            
            return response_data
            
        except (ValidationError, AuthenticationError) as e:
            raise HTTPException(status_code=400, detail=str(e))
        except Exception:
            raise HTTPException(status_code=500, detail="Internal server error")
    
    async def initiate_logout(
        self,
        request: Request,
        current_user = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
    ):
        """Initiate SSO logout (Single Logout)"""
        
        try:
            # Get SSO session ID from request
            session_id = request.headers.get("X-SSO-Session-ID")
            if not session_id:
                # Try to get from user's current session
                session_id = getattr(current_user, "sso_session_id", None)
            
            if not session_id:
                raise ValidationError("SSO session ID not found")
            
            orchestrator = await self._get_orchestrator(db)
            
            logout_data = await orchestrator.initiate_logout(
                user_id=current_user.id,
                session_id=session_id,
                return_url=request.query_params.get("return_url")
            )
            
            if logout_data:
                # Provider supports SLO
                return {
                    "success": True,
                    "logout_url": logout_data["logout_url"],
                    "requires_redirect": True
                }
            else:
                # Local logout only
                return {
                    "success": True,
                    "message": "Logged out successfully",
                    "requires_redirect": False
                }
            
        except (ValidationError, AuthenticationError) as e:
            raise HTTPException(status_code=400, detail=str(e))
        except Exception:
            raise HTTPException(status_code=500, detail="Internal server error")
    
    async def configure_sso(
        self,
        request: SSOConfigurationRequest,
        current_user = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
    ):
        """Configure SSO for an organization"""
        
        try:
            # Check if user has admin permissions for the organization
            if not self._has_admin_access(current_user, request.organization_id):
                raise HTTPException(status_code=403, detail="Insufficient permissions")
            
            orchestrator = await self._get_orchestrator(db)
            
            # Validate configuration
            is_valid = await orchestrator.validate_protocol_configuration(
                protocol=request.protocol,
                config=request.config
            )
            
            if not is_valid:
                raise ValidationError("Invalid SSO configuration")
            
            # Store configuration
            config_repo = SSOConfigurationRepository(db)
            
            from ...domain.protocols.base import SSOConfiguration
            sso_config = SSOConfiguration(
                organization_id=request.organization_id,
                protocol=request.protocol,
                provider_name=request.provider_name,
                config=request.config,
                attribute_mapping=request.attribute_mapping,
                jit_provisioning=request.jit_provisioning,
                default_role=request.default_role
            )
            
            result = await config_repo.create(sso_config)
            
            return {
                "success": True,
                "message": "SSO configuration saved successfully",
                "configuration_id": result.organization_id  # This should be a proper ID
            }
            
        except ValidationError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except Exception:
            raise HTTPException(status_code=500, detail="Internal server error")
    
    async def get_sso_configuration(
        self,
        organization_id: str,
        current_user = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
    ):
        """Get SSO configuration for an organization"""
        
        try:
            # Check if user has access to the organization
            if not self._has_access(current_user, organization_id):
                raise HTTPException(status_code=403, detail="Insufficient permissions")
            
            config_repo = SSOConfigurationRepository(db)
            configs = await config_repo.list_by_organization(organization_id)
            
            return {
                "success": True,
                "configurations": [
                    {
                        "protocol": config.protocol,
                        "provider_name": config.provider_name,
                        "jit_provisioning": config.jit_provisioning,
                        "default_role": config.default_role,
                        "created_at": config.created_at.isoformat()
                    }
                    for config in configs
                ]
            }
            
        except Exception:
            raise HTTPException(status_code=500, detail="Internal server error")
    
    async def get_supported_protocols(self):
        """Get list of supported SSO protocols"""
        
        # This could be made dynamic by querying the orchestrator
        return {
            "success": True,
            "protocols": [
                {
                    "name": "saml2",
                    "display_name": "SAML 2.0",
                    "description": "Security Assertion Markup Language 2.0"
                },
                {
                    "name": "oidc",
                    "display_name": "OpenID Connect",
                    "description": "OpenID Connect authentication protocol"
                }
            ]
        }
    
    async def _get_orchestrator(self, db: AsyncSession) -> SSOOrchestrator:
        """Get SSO orchestrator with dependencies"""

        # This would typically be injected via DI container
        from ....core.redis import get_redis
        from ....services.cache import CacheService
        from ....services.jwt_service import JWTService
        from ....services.audit_logger import AuditLogger

        config_repo = SSOConfigurationRepository(db)
        session_repo = SSOSessionRepository(db)
        user_provisioning = UserProvisioningService(db)
        cache_service = CacheService()  # Singleton, no arguments needed
        redis_client = await get_redis()
        jwt_service = JWTService(db, redis_client)  # Requires db and redis
        audit_logger = AuditLogger(db)  # Requires db

        return SSOOrchestrator(
            config_repository=config_repo,
            session_repository=session_repo,
            user_provisioning=user_provisioning,
            cache_service=cache_service,
            jwt_service=jwt_service,
            audit_logger=audit_logger
        )
    
    def _has_admin_access(self, user, organization_id: str) -> bool:
        """Check if user has admin access to organization"""
        return (
            user.organization_id == organization_id and
            user.role in ["admin", "owner"]
        )
    
    def _has_access(self, user, organization_id: str) -> bool:
        """Check if user has access to organization"""
        return user.organization_id == organization_id


# Create router instance
sso_router = SSOController().router