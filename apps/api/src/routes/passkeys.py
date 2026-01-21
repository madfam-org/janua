"""
Passkeys/WebAuthn API endpoints for passwordless authentication.
"""
from fastapi import APIRouter, Depends, HTTPException, status, Request, Response
from typing import Optional, Dict, Any, List
from datetime import datetime
from pydantic import BaseModel, Field

from app.auth import get_current_user
from app.models import User
from app.services.webauthn import WebAuthnService
from app.services.audit import AuditService
from app.services.session_manager import SessionManager
from app.database import get_db

router = APIRouter(prefix="/api/v1/passkeys", tags=["passkeys"])

# Initialize services
webauthn_service = WebAuthnService()
audit_service = AuditService()
session_manager = SessionManager()


# Request/Response Models
class RegistrationOptionsRequest(BaseModel):
    """Request for passkey registration options."""
    authenticator_selection: Optional[Dict[str, Any]] = Field(
        default=None,
        description="WebAuthn authenticator selection criteria"
    )
    attestation: Optional[str] = Field(
        default="none",
        description="Attestation conveyance preference"
    )


class RegistrationOptionsResponse(BaseModel):
    """Response with passkey registration options."""
    challenge: str
    rp: Dict[str, str]
    user: Dict[str, Any]
    pubKeyCredParams: List[Dict[str, Any]]
    timeout: int
    attestation: str
    authenticatorSelection: Optional[Dict[str, Any]]
    excludeCredentials: List[Dict[str, Any]]


class RegistrationVerificationRequest(BaseModel):
    """Request to verify passkey registration."""
    credential: Dict[str, Any] = Field(..., description="WebAuthn credential response")
    challenge: str = Field(..., description="Registration challenge")
    name: Optional[str] = Field(None, description="Optional passkey name")


class AuthenticationOptionsRequest(BaseModel):
    """Request for passkey authentication options."""
    user_id: Optional[str] = Field(None, description="Optional user ID for passkey selection")


class AuthenticationOptionsResponse(BaseModel):
    """Response with passkey authentication options."""
    challenge: str
    timeout: int
    rpId: str
    allowCredentials: List[Dict[str, Any]]
    userVerification: str


class AuthenticationVerificationRequest(BaseModel):
    """Request to verify passkey authentication."""
    credential: Dict[str, Any] = Field(..., description="WebAuthn assertion response")
    challenge: str = Field(..., description="Authentication challenge")


class PasskeyResponse(BaseModel):
    """Passkey information response."""
    id: str
    name: str
    created_at: datetime
    last_used_at: Optional[datetime]
    device_type: str
    backed_up: bool
    transports: List[str]


class UpdatePasskeyRequest(BaseModel):
    """Request to update passkey."""
    name: str = Field(..., min_length=1, max_length=100, description="New passkey name")


class DeletePasskeyRequest(BaseModel):
    """Request to delete passkey."""
    password: str = Field(..., description="User password for verification")


# Endpoints
@router.get("/availability")
async def check_availability(request: Request) -> Dict[str, bool]:
    """
    Check if passkeys are available for the current environment.
    
    Returns:
        Dictionary with availability status
    """
    # Check browser support based on user agent
    user_agent = request.headers.get("user-agent", "").lower()
    
    # Basic browser support detection
    supported_browsers = ["chrome", "edge", "safari", "firefox"]
    browser_supported = any(browser in user_agent for browser in supported_browsers)
    
    # Check if HTTPS (required for WebAuthn)
    is_secure = request.url.scheme == "https" or request.headers.get("x-forwarded-proto") == "https"
    
    return {
        "available": browser_supported and is_secure,
        "browser_supported": browser_supported,
        "secure_context": is_secure,
        "platform_authenticator": True,  # Most modern devices have platform authenticators
    }


@router.post("/register/options", response_model=RegistrationOptionsResponse)
async def get_registration_options(
    options: Optional[RegistrationOptionsRequest] = None,
    current_user: User = Depends(get_current_user),
    db=Depends(get_db)
) -> RegistrationOptionsResponse:
    """
    Generate registration options for a new passkey.
    
    Args:
        options: Optional registration preferences
        current_user: Authenticated user
        
    Returns:
        WebAuthn registration options
    """
    try:
        # Generate registration options
        reg_options = await webauthn_service.generate_registration_options(
            user_id=current_user.id,
            user_name=current_user.email,
            user_display_name=current_user.name or current_user.email,
            authenticator_selection=options.authenticator_selection if options else None,
            attestation=options.attestation if options else "none"
        )
        
        # Log the registration attempt
        await audit_service.log(
            event_type="passkey.registration.started",
            user_id=current_user.id,
            metadata={
                "attestation": options.attestation if options else "none",
                "authenticator_selection": options.authenticator_selection if options else None
            }
        )
        
        return RegistrationOptionsResponse(**reg_options)
        
    except Exception as e:
        await audit_service.log(
            event_type="passkey.registration.error",
            user_id=current_user.id,
            metadata={"error": str(e)},
            severity="error"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate registration options"
        )


@router.post("/register/verify")
async def verify_registration(
    data: RegistrationVerificationRequest,
    current_user: User = Depends(get_current_user),
    db=Depends(get_db)
) -> Dict[str, Any]:
    """
    Verify and complete passkey registration.
    
    Args:
        data: Registration verification data
        current_user: Authenticated user
        
    Returns:
        Registration result with passkey details
    """
    try:
        # Verify the registration
        result = await webauthn_service.verify_registration(
            credential=data.credential,
            challenge=data.challenge,
            user_id=current_user.id,
            expected_origin=data.credential.get("response", {}).get("clientDataJSON", {}).get("origin")
        )
        
        if not result["verified"]:
            await audit_service.log(
                event_type="passkey.registration.failed",
                user_id=current_user.id,
                metadata={"reason": "verification_failed"},
                severity="warning"
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Registration verification failed"
            )
        
        # Update passkey name if provided
        if data.name and result.get("passkey"):
            await webauthn_service.update_passkey_name(
                passkey_id=result["passkey"]["id"],
                name=data.name
            )
            result["passkey"]["name"] = data.name
        
        # Log successful registration
        await audit_service.log(
            event_type="passkey.registration.completed",
            user_id=current_user.id,
            metadata={
                "passkey_id": result["passkey"]["id"],
                "device_type": result["passkey"]["device_type"],
                "backed_up": result["passkey"]["backed_up"]
            }
        )
        
        return {
            "verified": True,
            "passkey": PasskeyResponse(
                id=result["passkey"]["id"],
                name=result["passkey"].get("name", "Unnamed Passkey"),
                created_at=result["passkey"]["created_at"],
                last_used_at=result["passkey"].get("last_used_at"),
                device_type=result["passkey"]["device_type"],
                backed_up=result["passkey"]["backed_up"],
                transports=result["passkey"]["transports"]
            )
        }
        
    except HTTPException:
        raise
    except Exception as e:
        await audit_service.log(
            event_type="passkey.registration.error",
            user_id=current_user.id,
            metadata={"error": str(e)},
            severity="error"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Registration verification failed"
        )


@router.post("/authenticate/options", response_model=AuthenticationOptionsResponse)
async def get_authentication_options(
    data: Optional[AuthenticationOptionsRequest] = None,
    db=Depends(get_db)
) -> AuthenticationOptionsResponse:
    """
    Generate authentication options for passkey login.
    
    Args:
        data: Optional authentication preferences
        
    Returns:
        WebAuthn authentication options
    """
    try:
        # Generate authentication options
        auth_options = await webauthn_service.generate_authentication_options(
            user_id=data.user_id if data else None
        )
        
        # Log the authentication attempt
        if data and data.user_id:
            await audit_service.log(
                event_type="passkey.authentication.started",
                user_id=data.user_id,
                metadata={}
            )
        
        return AuthenticationOptionsResponse(**auth_options)
        
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate authentication options"
        )


@router.post("/authenticate/verify")
async def verify_authentication(
    data: AuthenticationVerificationRequest,
    response: Response,
    db=Depends(get_db)
) -> Dict[str, Any]:
    """
    Verify passkey authentication and create session.
    
    Args:
        data: Authentication verification data
        response: FastAPI response for setting cookies
        
    Returns:
        Authentication result with session tokens
    """
    try:
        # Verify the authentication
        result = await webauthn_service.verify_authentication(
            credential=data.credential,
            challenge=data.challenge,
            expected_origin=data.credential.get("response", {}).get("clientDataJSON", {}).get("origin")
        )
        
        if not result["verified"]:
            await audit_service.log(
                event_type="passkey.authentication.failed",
                metadata={"reason": "verification_failed"},
                severity="warning"
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication verification failed"
            )
        
        # Get user from passkey
        user_id = result["user_id"]
        user = await db.get_user(user_id)
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        # Create session
        session = await session_manager.create_session(
            user_id=user_id,
            metadata={
                "auth_method": "passkey",
                "passkey_id": result["passkey"]["id"],
                "device_type": result["passkey"]["device_type"]
            }
        )
        
        # Set session cookie
        response.set_cookie(
            key="session_token",
            value=session["access_token"],
            httponly=True,
            secure=True,
            samesite="lax",
            max_age=3600 * 24 * 7  # 7 days
        )
        
        # Log successful authentication
        await audit_service.log(
            event_type="passkey.authentication.completed",
            user_id=user_id,
            metadata={
                "passkey_id": result["passkey"]["id"],
                "session_id": session["session_id"]
            }
        )
        
        return {
            "verified": True,
            "user": {
                "id": user.id,
                "email": user.email,
                "name": user.name
            },
            "session": session
        }
        
    except HTTPException:
        raise
    except Exception as e:
        await audit_service.log(
            event_type="passkey.authentication.error",
            metadata={"error": str(e)},
            severity="error"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Authentication verification failed"
        )


@router.get("/", response_model=List[PasskeyResponse])
async def list_passkeys(
    current_user: User = Depends(get_current_user),
    db=Depends(get_db)
) -> List[PasskeyResponse]:
    """
    List all passkeys for the current user.
    
    Returns:
        List of user's passkeys
    """
    try:
        passkeys = await webauthn_service.get_user_passkeys(current_user.id)
        
        return [
            PasskeyResponse(
                id=pk["id"],
                name=pk.get("name", "Unnamed Passkey"),
                created_at=pk["created_at"],
                last_used_at=pk.get("last_used_at"),
                device_type=pk["device_type"],
                backed_up=pk["backed_up"],
                transports=pk["transports"]
            )
            for pk in passkeys
        ]
        
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve passkeys"
        )


@router.patch("/{passkey_id}")
async def update_passkey(
    passkey_id: str,
    data: UpdatePasskeyRequest,
    current_user: User = Depends(get_current_user),
    db=Depends(get_db)
) -> PasskeyResponse:
    """
    Update a passkey's name.
    
    Args:
        passkey_id: Passkey identifier
        data: Update data
        current_user: Authenticated user
        
    Returns:
        Updated passkey information
    """
    try:
        # Verify passkey belongs to user
        passkey = await webauthn_service.get_passkey(passkey_id)
        if not passkey or passkey["user_id"] != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Passkey not found"
            )
        
        # Update the name
        success = await webauthn_service.update_passkey_name(passkey_id, data.name)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update passkey"
            )
        
        # Get updated passkey
        passkey = await webauthn_service.get_passkey(passkey_id)
        
        # Log the update
        await audit_service.log(
            event_type="passkey.updated",
            user_id=current_user.id,
            metadata={
                "passkey_id": passkey_id,
                "new_name": data.name
            }
        )
        
        return PasskeyResponse(
            id=passkey["id"],
            name=passkey["name"],
            created_at=passkey["created_at"],
            last_used_at=passkey.get("last_used_at"),
            device_type=passkey["device_type"],
            backed_up=passkey["backed_up"],
            transports=passkey["transports"]
        )
        
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update passkey"
        )


@router.delete("/{passkey_id}")
async def delete_passkey(
    passkey_id: str,
    data: DeletePasskeyRequest,
    current_user: User = Depends(get_current_user),
    db=Depends(get_db)
) -> Dict[str, str]:
    """
    Delete a passkey.
    
    Args:
        passkey_id: Passkey identifier
        data: Deletion request with password verification
        current_user: Authenticated user
        
    Returns:
        Deletion confirmation
    """
    try:
        # Verify password
        if not await db.verify_password(current_user.id, data.password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid password"
            )
        
        # Verify passkey belongs to user
        passkey = await webauthn_service.get_passkey(passkey_id)
        if not passkey or passkey["user_id"] != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Passkey not found"
            )
        
        # Delete the passkey
        success = await webauthn_service.delete_passkey(passkey_id)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to delete passkey"
            )
        
        # Log the deletion
        await audit_service.log(
            event_type="passkey.deleted",
            user_id=current_user.id,
            metadata={
                "passkey_id": passkey_id,
                "passkey_name": passkey.get("name", "Unnamed")
            }
        )
        
        return {"message": "Passkey deleted successfully"}
        
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete passkey"
        )