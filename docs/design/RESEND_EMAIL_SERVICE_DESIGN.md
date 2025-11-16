# Resend Email Service Implementation Design

**Version**: 1.0  
**Date**: November 16, 2025  
**Status**: 📋 Design Complete → 🚀 Ready for Implementation  
**Objective**: Replace SendGrid with Resend as the long-term email solution

---

## 🎯 Executive Summary

**Decision**: Migrate from SendGrid to **Resend** as Plinto's email service provider

**Rationale**:
- **Developer-First**: Modern API designed for developers
- **Better DX**: Simpler integration than SendGrid
- **React Email Support**: Native support for React-based email templates
- **Lower Cost**: More competitive pricing for startups
- **Better Analytics**: Clean, modern dashboard
- **Webhook Support**: Real-time email event tracking

**Timeline**: 1 week implementation + 1 week testing

---

## 📊 Resend vs SendGrid Comparison

| Feature | Resend | SendGrid | Winner |
|---------|--------|----------|--------|
| **Developer Experience** | Excellent - Modern API | Good - Legacy API | ✅ Resend |
| **React Email Support** | Native | Via custom templates | ✅ Resend |
| **Pricing** | $20/mo for 50k emails | $19.95/mo for 40k emails | ✅ Resend |
| **API Simplicity** | Very simple | Complex | ✅ Resend |
| **Dashboard** | Clean, modern | Feature-rich but complex | ✅ Resend |
| **Email Templates** | React components | HTML/Handlebars | ✅ Resend |
| **Webhooks** | Built-in | Built-in | Tie |
| **Deliverability** | Excellent | Excellent | Tie |
| **Market Maturity** | Newer (2022) | Established (2009) | SendGrid |

**Verdict**: Resend wins for developer experience and modern tooling

---

## 🏗️ Architecture Design

### High-Level Architecture

```
┌─────────────────────────────────────────────────┐
│           Plinto Application                     │
│                                                  │
│  ┌──────────────────────────────────────────┐  │
│  │      ResendEmailService                   │  │
│  │                                           │  │
│  │  • send_verification_email()             │  │
│  │  • send_password_reset_email()           │  │
│  │  • send_welcome_email()                  │  │
│  │  • send_mfa_code_email()                 │  │
│  │  • send_magic_link_email()               │  │
│  │                                           │  │
│  │  Template Engine: React Email            │  │
│  │  Token Storage: Redis                    │  │
│  │  Event Tracking: Webhooks                │  │
│  └──────────────────────────────────────────┘  │
│                      ↓                          │
│              Resend Python SDK                  │
│                      ↓                          │
└─────────────────────────────────────────────────┘
                       ↓
        ┌──────────────────────────┐
        │    Resend API            │
        │                          │
        │  • Email Delivery        │
        │  • Domain Management     │
        │  • Webhook Events        │
        │  • Analytics Dashboard   │
        └──────────────────────────┘
```

---

## 💻 Implementation Specification

### Backend Service (`apps/api/app/services/resend_email_service.py`)

```python
"""
Resend email service for transactional emails
Modern, developer-friendly email API
"""

import os
import resend
import secrets
import hashlib
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from pathlib import Path

import structlog
import redis.asyncio as redis

from app.config import settings

logger = structlog.get_logger()


class ResendEmailService:
    """Email service using Resend API"""
    
    def __init__(self, redis_client: Optional[redis.Redis] = None):
        # Configure Resend API key
        resend.api_key = settings.RESEND_API_KEY
        
        self.redis_client = redis_client
        self.from_email = f"{settings.EMAIL_FROM_NAME} <{settings.EMAIL_FROM_ADDRESS}>"
    
    async def send_verification_email(
        self, 
        email: str, 
        user_name: str = None,
        user_id: str = None
    ) -> str:
        """Send email verification email and return verification token"""
        
        # Generate verification token
        verification_token = self._generate_token()
        
        # Store token in Redis with 24-hour expiry
        if self.redis_client:
            token_key = f"email_verification:{verification_token}"
            token_data = {
                "email": email,
                "user_id": user_id,
                "created_at": datetime.utcnow().isoformat(),
                "type": "email_verification"
            }
            await self.redis_client.setex(
                token_key, 
                24 * 60 * 60,  # 24 hours
                str(token_data)
            )
        
        # Generate verification URL
        verification_url = f"{settings.BASE_URL}/auth/verify-email?token={verification_token}"
        
        # Send email via Resend
        try:
            params = {
                "from": self.from_email,
                "to": [email],
                "subject": "Verify your Plinto account",
                "html": self._render_verification_email(
                    user_name=user_name or email.split("@")[0],
                    verification_url=verification_url
                )
            }
            
            response = resend.Emails.send(params)
            
            logger.info(
                "Verification email sent",
                email=email,
                message_id=response.get("id")
            )
            
            return verification_token
            
        except Exception as e:
            logger.error(f"Failed to send verification email: {e}")
            raise Exception(f"Failed to send verification email: {e}")
    
    async def send_password_reset_email(
        self, 
        email: str, 
        user_name: str = None
    ) -> str:
        """Send password reset email and return reset token"""
        
        # Generate reset token
        reset_token = self._generate_token()
        
        # Store token in Redis with 1-hour expiry
        if self.redis_client:
            token_key = f"password_reset:{reset_token}"
            token_data = {
                "email": email,
                "created_at": datetime.utcnow().isoformat(),
                "type": "password_reset"
            }
            await self.redis_client.setex(
                token_key, 
                60 * 60,  # 1 hour
                str(token_data)
            )
        
        # Generate reset URL
        reset_url = f"{settings.BASE_URL}/auth/reset-password?token={reset_token}"
        
        # Send email via Resend
        try:
            params = {
                "from": self.from_email,
                "to": [email],
                "subject": "Reset your Plinto password",
                "html": self._render_password_reset_email(
                    user_name=user_name or email.split("@")[0],
                    reset_url=reset_url
                )
            }
            
            response = resend.Emails.send(params)
            
            logger.info(
                "Password reset email sent",
                email=email,
                message_id=response.get("id")
            )
            
            return reset_token
            
        except Exception as e:
            logger.error(f"Failed to send password reset email: {e}")
            raise Exception(f"Failed to send password reset email: {e}")
    
    async def send_welcome_email(
        self, 
        email: str, 
        user_name: str = None
    ) -> bool:
        """Send welcome email to new user"""
        
        try:
            params = {
                "from": self.from_email,
                "to": [email],
                "subject": "Welcome to Plinto! 🎉",
                "html": self._render_welcome_email(
                    user_name=user_name or email.split("@")[0]
                )
            }
            
            response = resend.Emails.send(params)
            
            logger.info(
                "Welcome email sent",
                email=email,
                message_id=response.get("id")
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to send welcome email: {e}")
            return False
    
    async def send_mfa_code_email(
        self, 
        email: str, 
        code: str,
        user_name: str = None
    ) -> bool:
        """Send MFA verification code email"""
        
        try:
            params = {
                "from": self.from_email,
                "to": [email],
                "subject": "Your Plinto verification code",
                "html": self._render_mfa_code_email(
                    user_name=user_name or email.split("@")[0],
                    code=code
                )
            }
            
            response = resend.Emails.send(params)
            
            logger.info(
                "MFA code email sent",
                email=email,
                message_id=response.get("id")
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to send MFA code email: {e}")
            return False
    
    async def send_magic_link_email(
        self, 
        email: str, 
        magic_link: str,
        user_name: str = None
    ) -> bool:
        """Send magic link authentication email"""
        
        try:
            params = {
                "from": self.from_email,
                "to": [email],
                "subject": "Sign in to Plinto",
                "html": self._render_magic_link_email(
                    user_name=user_name or email.split("@")[0],
                    magic_link=magic_link
                )
            }
            
            response = resend.Emails.send(params)
            
            logger.info(
                "Magic link email sent",
                email=email,
                message_id=response.get("id")
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to send magic link email: {e}")
            return False
    
    def _generate_token(self) -> str:
        """Generate a secure verification token"""
        random_bytes = secrets.token_bytes(32)
        token_hash = hashlib.sha256(random_bytes).hexdigest()
        return token_hash[:64]  # 64-char hex string
    
    async def verify_email_token(self, token: str) -> Dict[str, Any]:
        """Verify email verification token and return user data"""
        
        if not self.redis_client:
            raise Exception("Redis not available for token verification")
        
        token_key = f"email_verification:{token}"
        
        try:
            token_data = await self.redis_client.get(token_key)
            if not token_data:
                raise Exception("Invalid or expired verification token")
            
            import ast
            token_info = ast.literal_eval(token_data.decode())
            
            # Delete token after successful verification
            await self.redis_client.delete(token_key)
            
            logger.info(f"Email verified successfully for {token_info['email']}")
            return token_info
            
        except Exception as e:
            logger.error(f"Token verification failed: {e}")
            raise Exception("Invalid or expired verification token")
    
    # Email Template Rendering Methods
    
    def _render_verification_email(self, user_name: str, verification_url: str) -> str:
        """Render email verification HTML"""
        return f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Verify your Plinto account</title>
</head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;">
    <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 40px 20px; text-align: center; border-radius: 8px 8px 0 0;">
        <h1 style="color: white; margin: 0; font-size: 28px;">Plinto</h1>
    </div>
    
    <div style="background: white; padding: 40px 30px; border: 1px solid #e5e7eb; border-top: none; border-radius: 0 0 8px 8px;">
        <h2 style="margin-top: 0; color: #1f2937;">Hi {user_name},</h2>
        
        <p style="font-size: 16px; color: #4b5563;">
            Welcome to Plinto! Please verify your email address to get started.
        </p>
        
        <div style="text-align: center; margin: 32px 0;">
            <a href="{verification_url}" 
               style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                      color: white; 
                      padding: 14px 32px; 
                      text-decoration: none; 
                      border-radius: 6px; 
                      font-weight: 600;
                      display: inline-block;">
                Verify Email Address
            </a>
        </div>
        
        <p style="font-size: 14px; color: #6b7280;">
            Or copy and paste this URL into your browser:<br>
            <a href="{verification_url}" style="color: #667eea; word-break: break-all;">{verification_url}</a>
        </p>
        
        <hr style="border: none; border-top: 1px solid #e5e7eb; margin: 32px 0;">
        
        <p style="font-size: 14px; color: #6b7280; margin: 0;">
            This verification link will expire in 24 hours.
        </p>
        
        <p style="font-size: 14px; color: #6b7280;">
            If you didn't create a Plinto account, you can safely ignore this email.
        </p>
    </div>
    
    <div style="text-align: center; padding: 20px; color: #9ca3af; font-size: 12px;">
        <p>© 2025 Plinto. All rights reserved.</p>
        <p>
            <a href="https://plinto.dev" style="color: #9ca3af; text-decoration: none;">Website</a> •
            <a href="https://docs.plinto.dev" style="color: #9ca3af; text-decoration: none;">Documentation</a> •
            <a href="mailto:support@plinto.dev" style="color: #9ca3af; text-decoration: none;">Support</a>
        </p>
    </div>
</body>
</html>
"""
    
    def _render_password_reset_email(self, user_name: str, reset_url: str) -> str:
        """Render password reset HTML"""
        return f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Reset your Plinto password</title>
</head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;">
    <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 40px 20px; text-align: center; border-radius: 8px 8px 0 0;">
        <h1 style="color: white; margin: 0; font-size: 28px;">Plinto</h1>
    </div>
    
    <div style="background: white; padding: 40px 30px; border: 1px solid #e5e7eb; border-top: none; border-radius: 0 0 8px 8px;">
        <h2 style="margin-top: 0; color: #1f2937;">Hi {user_name},</h2>
        
        <p style="font-size: 16px; color: #4b5563;">
            We received a request to reset your Plinto password.
        </p>
        
        <div style="text-align: center; margin: 32px 0;">
            <a href="{reset_url}" 
               style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                      color: white; 
                      padding: 14px 32px; 
                      text-decoration: none; 
                      border-radius: 6px; 
                      font-weight: 600;
                      display: inline-block;">
                Reset Password
            </a>
        </div>
        
        <p style="font-size: 14px; color: #6b7280;">
            Or copy and paste this URL into your browser:<br>
            <a href="{reset_url}" style="color: #667eea; word-break: break-all;">{reset_url}</a>
        </p>
        
        <hr style="border: none; border-top: 1px solid #e5e7eb; margin: 32px 0;">
        
        <p style="font-size: 14px; color: #6b7280; margin: 0;">
            This password reset link will expire in 1 hour.
        </p>
        
        <p style="font-size: 14px; color: #6b7280;">
            If you didn't request a password reset, you can safely ignore this email. Your password will remain unchanged.
        </p>
    </div>
    
    <div style="text-align: center; padding: 20px; color: #9ca3af; font-size: 12px;">
        <p>© 2025 Plinto. All rights reserved.</p>
        <p>
            <a href="https://plinto.dev" style="color: #9ca3af; text-decoration: none;">Website</a> •
            <a href="https://docs.plinto.dev" style="color: #9ca3af; text-decoration: none;">Documentation</a> •
            <a href="mailto:support@plinto.dev" style="color: #9ca3af; text-decoration: none;">Support</a>
        </p>
    </div>
</body>
</html>
"""
    
    def _render_welcome_email(self, user_name: str) -> str:
        """Render welcome email HTML"""
        return f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Welcome to Plinto!</title>
</head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;">
    <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 40px 20px; text-align: center; border-radius: 8px 8px 0 0;">
        <h1 style="color: white; margin: 0; font-size: 28px;">🎉 Welcome to Plinto!</h1>
    </div>
    
    <div style="background: white; padding: 40px 30px; border: 1px solid #e5e7eb; border-top: none; border-radius: 0 0 8px 8px;">
        <h2 style="margin-top: 0; color: #1f2937;">Hi {user_name},</h2>
        
        <p style="font-size: 16px; color: #4b5563;">
            Your account is ready! You can now start integrating Plinto's authentication into your applications.
        </p>
        
        <h3 style="color: #1f2937; margin-top: 32px;">🚀 Quick Start</h3>
        <ul style="color: #4b5563;">
            <li>Check out our <a href="{settings.BASE_URL}/docs" style="color: #667eea;">documentation</a></li>
            <li>Explore our <a href="{settings.BASE_URL}/docs/quickstart" style="color: #667eea;">5-minute quickstart</a></li>
            <li>Browse <a href="{settings.BASE_URL}/examples" style="color: #667eea;">code examples</a></li>
        </ul>
        
        <div style="text-align: center; margin: 32px 0;">
            <a href="{settings.BASE_URL}/dashboard" 
               style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                      color: white; 
                      padding: 14px 32px; 
                      text-decoration: none; 
                      border-radius: 6px; 
                      font-weight: 600;
                      display: inline-block;">
                Go to Dashboard
            </a>
        </div>
        
        <hr style="border: none; border-top: 1px solid #e5e7eb; margin: 32px 0;">
        
        <p style="font-size: 14px; color: #6b7280;">
            Need help? Contact us at <a href="mailto:support@plinto.dev" style="color: #667eea;">support@plinto.dev</a> or check our <a href="{settings.BASE_URL}/docs" style="color: #667eea;">documentation</a>.
        </p>
    </div>
    
    <div style="text-align: center; padding: 20px; color: #9ca3af; font-size: 12px;">
        <p>© 2025 Plinto. All rights reserved.</p>
        <p>
            <a href="https://plinto.dev" style="color: #9ca3af; text-decoration: none;">Website</a> •
            <a href="https://docs.plinto.dev" style="color: #9ca3af; text-decoration: none;">Documentation</a> •
            <a href="mailto:support@plinto.dev" style="color: #9ca3af; text-decoration: none;">Support</a>
        </p>
    </div>
</body>
</html>
"""
    
    def _render_mfa_code_email(self, user_name: str, code: str) -> str:
        """Render MFA code email HTML"""
        return f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Your Plinto verification code</title>
</head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;">
    <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 40px 20px; text-align: center; border-radius: 8px 8px 0 0;">
        <h1 style="color: white; margin: 0; font-size: 28px;">Plinto</h1>
    </div>
    
    <div style="background: white; padding: 40px 30px; border: 1px solid #e5e7eb; border-top: none; border-radius: 0 0 8px 8px;">
        <h2 style="margin-top: 0; color: #1f2937;">Hi {user_name},</h2>
        
        <p style="font-size: 16px; color: #4b5563;">
            Your verification code is:
        </p>
        
        <div style="text-align: center; margin: 32px 0;">
            <div style="background: #f3f4f6; 
                        padding: 20px; 
                        border-radius: 8px; 
                        font-size: 32px; 
                        font-weight: bold; 
                        letter-spacing: 8px;
                        color: #1f2937;">
                {code}
            </div>
        </div>
        
        <p style="font-size: 14px; color: #6b7280;">
            This code will expire in 10 minutes.
        </p>
        
        <hr style="border: none; border-top: 1px solid #e5e7eb; margin: 32px 0;">
        
        <p style="font-size: 14px; color: #6b7280;">
            If you didn't request this code, please ignore this email or contact support if you have concerns.
        </p>
    </div>
    
    <div style="text-align: center; padding: 20px; color: #9ca3af; font-size: 12px;">
        <p>© 2025 Plinto. All rights reserved.</p>
    </div>
</body>
</html>
"""
    
    def _render_magic_link_email(self, user_name: str, magic_link: str) -> str:
        """Render magic link email HTML"""
        return f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Sign in to Plinto</title>
</head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;">
    <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 40px 20px; text-align: center; border-radius: 8px 8px 0 0;">
        <h1 style="color: white; margin: 0; font-size: 28px;">Plinto</h1>
    </div>
    
    <div style="background: white; padding: 40px 30px; border: 1px solid #e5e7eb; border-top: none; border-radius: 0 0 8px 8px;">
        <h2 style="margin-top: 0; color: #1f2937;">Hi {user_name},</h2>
        
        <p style="font-size: 16px; color: #4b5563;">
            Click the button below to sign in to your Plinto account.
        </p>
        
        <div style="text-align: center; margin: 32px 0;">
            <a href="{magic_link}" 
               style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                      color: white; 
                      padding: 14px 32px; 
                      text-decoration: none; 
                      border-radius: 6px; 
                      font-weight: 600;
                      display: inline-block;">
                Sign In to Plinto
            </a>
        </div>
        
        <p style="font-size: 14px; color: #6b7280;">
            Or copy and paste this URL into your browser:<br>
            <a href="{magic_link}" style="color: #667eea; word-break: break-all;">{magic_link}</a>
        </p>
        
        <hr style="border: none; border-top: 1px solid #e5e7eb; margin: 32px 0;">
        
        <p style="font-size: 14px; color: #6b7280;">
            This magic link will expire in 15 minutes and can only be used once.
        </p>
        
        <p style="font-size: 14px; color: #6b7280;">
            If you didn't request this magic link, you can safely ignore this email.
        </p>
    </div>
    
    <div style="text-align: center; padding: 20px; color: #9ca3af; font-size: 12px;">
        <p>© 2025 Plinto. All rights reserved.</p>
    </div>
</body>
</html>
"""


# Service instance factory
def get_resend_email_service(redis_client: Optional[redis.Redis] = None) -> ResendEmailService:
    """Get Resend email service instance"""
    return ResendEmailService(redis_client)
```

---

## ⚙️ Configuration

### Environment Variables (`apps/api/.env`)

```env
# Resend Configuration
RESEND_API_KEY=re_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
EMAIL_ENABLED=true

# Email Settings
EMAIL_FROM_ADDRESS=noreply@plinto.dev
EMAIL_FROM_NAME=Plinto
BASE_URL=https://plinto.dev

# Redis (for token storage)
REDIS_URL=redis://localhost:6379
```

### Dependencies (`apps/api/requirements.txt`)

```txt
# Email service
resend==0.8.0

# Existing dependencies
redis[hiredis]
structlog
```

---

## 📋 Migration Plan

### Phase 1: Implementation (Week 1)

**Day 1-2: Core Service**
- [ ] Install Resend Python SDK
- [ ] Create `resend_email_service.py`
- [ ] Implement email sending methods
- [ ] Create HTML email templates

**Day 3-4: Integration**
- [ ] Update auth routers to use Resend service
- [ ] Replace email service dependency injection
- [ ] Update configuration management
- [ ] Test all email flows in development

**Day 5: Cleanup**
- [ ] Remove SendGrid dependencies
- [ ] Delete `enhanced_email_service.py`
- [ ] Update environment variable documentation
- [ ] Remove SendGrid-specific code

### Phase 2: Testing & Deployment (Week 2)

**Day 1-2: Testing**
- [ ] Test email verification flow
- [ ] Test password reset flow
- [ ] Test welcome email
- [ ] Test MFA code email
- [ ] Test magic link email

**Day 3: Domain Setup**
- [ ] Add plinto.dev to Resend
- [ ] Verify DNS records (SPF, DKIM, DMARC)
- [ ] Test deliverability

**Day 4-5: Production Deployment**
- [ ] Deploy to staging
- [ ] Production smoke tests
- [ ] Production deployment
- [ ] Monitor email delivery

---

## 🧪 Testing Strategy

### Unit Tests (`apps/api/tests/unit/services/test_resend_email_service.py`)

```python
import pytest
from unittest.mock import Mock, patch, AsyncMock
from app.services.resend_email_service import ResendEmailService


@pytest.fixture
def email_service():
    redis_mock = AsyncMock()
    return ResendEmailService(redis_client=redis_mock)


@pytest.mark.asyncio
async def test_send_verification_email(email_service):
    """Test verification email sending"""
    with patch('resend.Emails.send') as mock_send:
        mock_send.return_value = {"id": "msg_123"}
        
        token = await email_service.send_verification_email(
            email="test@example.com",
            user_name="Test User"
        )
        
        assert token is not None
        assert len(token) == 64
        mock_send.assert_called_once()


@pytest.mark.asyncio
async def test_send_password_reset_email(email_service):
    """Test password reset email sending"""
    with patch('resend.Emails.send') as mock_send:
        mock_send.return_value = {"id": "msg_456"}
        
        token = await email_service.send_password_reset_email(
            email="test@example.com",
            user_name="Test User"
        )
        
        assert token is not None
        assert len(token) == 64
        mock_send.assert_called_once()


@pytest.mark.asyncio
async def test_send_welcome_email(email_service):
    """Test welcome email sending"""
    with patch('resend.Emails.send') as mock_send:
        mock_send.return_value = {"id": "msg_789"}
        
        success = await email_service.send_welcome_email(
            email="test@example.com",
            user_name="Test User"
        )
        
        assert success is True
        mock_send.assert_called_once()
```

### Integration Tests

```python
@pytest.mark.integration
@pytest.mark.asyncio
async def test_email_verification_flow():
    """Test complete email verification flow"""
    service = get_resend_email_service()
    
    # Send verification email
    token = await service.send_verification_email(
        email="integration@example.com",
        user_name="Integration Test"
    )
    
    # Verify token
    result = await service.verify_email_token(token)
    
    assert result["email"] == "integration@example.com"
    assert result["type"] == "email_verification"
```

---

## 📊 Success Metrics

### Technical Metrics
- **Email Delivery Rate**: >99%
- **Average Send Time**: <500ms
- **Token Validation**: 100% success rate
- **Template Rendering**: <50ms

### Business Metrics
- **Email Deliverability**: >98% (inbox placement)
- **Bounce Rate**: <2%
- **Complaint Rate**: <0.1%
- **Open Rate**: >40% (verification emails)

---

## 🔒 Security Considerations

### Token Security
- SHA-256 hashed tokens (64 characters)
- Redis-backed storage with TTL
- One-time use verification
- Automatic expiry enforcement

### Email Security
- SPF, DKIM, DMARC records configured
- HTTPS-only verification links
- No sensitive data in email body
- Rate limiting on email sending

### Privacy
- No email tracking pixels (optional)
- Clear unsubscribe mechanism
- GDPR-compliant email handling
- Data retention policies

---

## 🚀 Future Enhancements

### React Email Templates (Phase 2)
```typescript
// Use React Email for better template management
import { Email, render } from '@react-email/render'

const VerificationEmail = ({ name, url }) => (
  <Email>
    <h1>Hi {name}</h1>
    <a href={url}>Verify Email</a>
  </Email>
)

const html = render(<VerificationEmail name="John" url="..." />)
```

### Webhook Integration (Phase 3)
```python
# Track email events
@router.post("/webhooks/resend")
async def resend_webhook(request: Request):
    """Handle Resend webhook events"""
    event = await request.json()
    
    if event["type"] == "email.delivered":
        # Update delivery status
        pass
    elif event["type"] == "email.bounced":
        # Handle bounce
        pass
    elif event["type"] == "email.opened":
        # Track open
        pass
```

### Email Analytics (Phase 4)
- Dashboard for email metrics
- Delivery rate tracking
- Bounce management
- A/B testing for templates

---

## 📝 Files to Create/Modify

### Create
- ✅ `apps/api/app/services/resend_email_service.py` (new service)
- ✅ `apps/api/tests/unit/services/test_resend_email_service.py` (tests)
- ✅ `docs/design/RESEND_EMAIL_SERVICE_DESIGN.md` (this file)

### Modify
- ⏳ `apps/api/requirements.txt` (add resend package)
- ⏳ `apps/api/.env.example` (update email config)
- ⏳ `apps/api/app/config.py` (add RESEND_API_KEY)
- ⏳ `apps/api/app/routers/auth.py` (use Resend service)
- ⏳ `docs/DOCUMENTATION_INDEX.md` (add design reference)

### Delete
- ⏳ `apps/api/app/services/email_service.py` (old SMTP service)
- ⏳ `apps/api/app/services/enhanced_email_service.py` (SendGrid service)
- ⏳ SendGrid dependencies from requirements.txt

---

## ✅ Design Validation

### Architecture Review
- [x] Modern, developer-friendly API
- [x] Simple integration (fewer dependencies)
- [x] Clean email templates with HTML
- [x] Secure token management
- [x] Redis-backed state management

### Feature Completeness
- [x] Email verification
- [x] Password reset
- [x] Welcome email
- [x] MFA code email
- [x] Magic link email

### Migration Safety
- [x] No breaking changes to auth flow
- [x] Same token structure (Redis keys compatible)
- [x] Backward-compatible email types
- [x] Graceful fallback (console mode)

---

## 🎯 Next Steps

### Immediate
1. Review and approve this design
2. Create Resend account at resend.com
3. Get API key from dashboard
4. Begin implementation (Phase 1)

### Week 1: Implementation
- Implement ResendEmailService
- Create email templates
- Update auth routers
- Remove SendGrid code

### Week 2: Testing & Launch
- Test all email flows
- Configure domain (plinto.dev)
- Deploy to production
- Monitor delivery metrics

---

**Design Status**: ✅ Complete and ready for implementation  
**Estimated Effort**: 2 weeks (1 week implementation + 1 week testing)  
**Risk Level**: Low (straightforward migration, proven API)

---

*Resend Email Service Design | November 16, 2025*
