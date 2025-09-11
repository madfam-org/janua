from typing import Optional, Dict, Any, List, Literal
from datetime import datetime
from pydantic import BaseModel, Field, EmailStr


class User(BaseModel):
    id: str
    email: EmailStr
    email_verified: bool
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    username: Optional[str] = None
    profile_image_url: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    created_at: datetime
    updated_at: datetime
    last_sign_in_at: Optional[datetime] = None


class Session(BaseModel):
    id: str
    user_id: str
    expires_at: datetime
    last_active_at: datetime
    status: Literal["active", "expired", "revoked"]


class AuthTokens(BaseModel):
    access_token: str
    refresh_token: str
    id_token: Optional[str] = None
    expires_in: int


class SignUpRequest(BaseModel):
    email: EmailStr
    password: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    username: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class SignInRequest(BaseModel):
    email: Optional[EmailStr] = None
    username: Optional[str] = None
    password: str


class SignInResponse(BaseModel):
    user: User
    session: Session
    tokens: AuthTokens


class SignUpResponse(BaseModel):
    user: User
    session: Session
    tokens: AuthTokens


class UpdateUserRequest(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    username: Optional[str] = None
    profile_image_url: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class PasswordResetRequest(BaseModel):
    email: EmailStr


class PasswordResetConfirm(BaseModel):
    token: str
    new_password: str


class VerifyEmailRequest(BaseModel):
    token: str


class MagicLinkRequest(BaseModel):
    email: EmailStr
    redirect_url: Optional[str] = None


class OAuthProvider(BaseModel):
    provider: Literal[
        "google", "github", "microsoft", "apple", "discord", "twitter", "linkedin"
    ]
    redirect_url: Optional[str] = None
    scopes: Optional[List[str]] = None


class PasskeyRegistrationOptions(BaseModel):
    username: Optional[str] = None
    display_name: Optional[str] = None
    authenticator_attachment: Optional[Literal["platform", "cross-platform"]] = None


class OrganizationInfo(BaseModel):
    id: str
    name: str
    slug: str
    logo_url: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class OrganizationMembership(BaseModel):
    id: str
    organization_id: str
    user_id: str
    role: str
    permissions: List[str]
    created_at: datetime
    updated_at: datetime


class CreateOrganizationRequest(BaseModel):
    name: str
    slug: Optional[str] = None
    description: Optional[str] = None
    logo_url: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class UpdateOrganizationRequest(BaseModel):
    name: Optional[str] = None
    slug: Optional[str] = None
    description: Optional[str] = None
    logo_url: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class InviteMemberRequest(BaseModel):
    email: EmailStr
    role: str
    permissions: Optional[List[str]] = None
    send_email: bool = True


class UpdateMemberRequest(BaseModel):
    role: Optional[str] = None
    permissions: Optional[List[str]] = None


class PlintoError(BaseModel):
    code: str
    message: str
    status_code: Optional[int] = None
    details: Optional[Any] = None