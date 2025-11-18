# Logging Migration Guide - Structured Logging Best Practices

**Version**: 1.0  
**Date**: November 18, 2025  
**Status**: Active

---

## Overview

This guide demonstrates how to migrate from `structlog.get_logger()` to the enhanced `app.core.logger` infrastructure for consistent, context-aware logging across the Plinto API.

---

## Key Differences

### Current Approach (structlog)
```python
import structlog
logger = structlog.get_logger()

logger.info("User authenticated", user_id=user.id)
```

### Enhanced Approach (app.core.logger)
```python
from app.core.logger import get_context_logger

logger = get_context_logger(__name__, user_id=user.id, request_id=request.id)
logger.info("User authenticated")  # Context automatically included
```

---

## Benefits of Migration

1. **Automatic Context Propagation**: User ID, org ID, request ID added to all logs
2. **Consistent JSON Structure**: Standardized timestamp, level, module, function fields
3. **Production/Development Modes**: JSON for production, readable for development
4. **Integration Ready**: Works with Datadog, CloudWatch, Loki out-of-the-box

---

## Migration Examples

### Example 1: Auth Service (Already Using structlog ✅)

**Current Code** (`apps/api/app/services/auth_service.py`):
```python
import structlog

logger = structlog.get_logger()

class AuthService:
    async def authenticate_user(self, email: str, password: str):
        logger.info("Authentication attempt", email=email)
        # ... authentication logic
```

**Enhanced Version** (Optional, for consistency):
```python
from app.core.logger import get_logger

logger = get_logger(__name__)  # Module-level logger

class AuthService:
    async def authenticate_user(self, email: str, password: str):
        logger.info("Authentication attempt", extra={"email": email})
        # ... authentication logic
```

**With Request Context** (Recommended):
```python
from app.core.logger import get_context_logger

class AuthService:
    async def authenticate_user(
        self, 
        email: str, 
        password: str,
        request_id: Optional[str] = None
    ):
        # Create context logger with request ID
        logger = get_context_logger(
            __name__, 
            request_id=request_id
        )
        
        logger.info("Authentication attempt started", extra={"email": email})
        
        try:
            user = await self._find_user(email)
            if not user:
                logger.warn("Authentication failed - user not found", 
                           extra={"email": email})
                return None
            
            if not self.verify_password(password, user.hashed_password):
                logger.warn("Authentication failed - invalid password",
                           extra={"user_id": str(user.id), "email": email})
                return None
            
            # Success - add user context
            logger = get_context_logger(
                __name__,
                user_id=str(user.id),
                organization_id=str(user.organization_id) if user.organization_id else None,
                request_id=request_id
            )
            logger.info("Authentication successful")
            
            return user
            
        except Exception as e:
            logger.error("Authentication error", 
                        extra={"email": email, "error": str(e)},
                        exc_info=True)
            raise
```

---

### Example 2: API Router Integration

**FastAPI Dependency for Request Logging**:
```python
# apps/api/app/core/dependencies.py
from fastapi import Request
from app.core.logger import get_context_logger
import uuid

async def get_request_logger(request: Request):
    """
    FastAPI dependency that creates a context logger with request ID
    """
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    
    # Add to request state for access in endpoints
    request.state.request_id = request_id
    
    return get_context_logger(
        __name__,
        request_id=request_id,
        path=request.url.path,
        method=request.method
    )
```

**Using in Router**:
```python
# apps/api/app/routers/v1/auth.py
from fastapi import APIRouter, Depends
from app.core.dependencies import get_request_logger
from app.core.logger import LoggerAdapter

router = APIRouter()

@router.post("/auth/signin")
async def signin(
    credentials: SignInRequest,
    logger: LoggerAdapter = Depends(get_request_logger)
):
    logger.info("Sign-in request received", extra={"email": credentials.email})
    
    try:
        user = await auth_service.authenticate_user(
            credentials.email,
            credentials.password,
            request_id=logger.extra.get('request_id')
        )
        
        if not user:
            logger.warn("Sign-in failed - invalid credentials")
            raise HTTPException(status_code=401, detail="Invalid credentials")
        
        logger.info("Sign-in successful", extra={"user_id": str(user.id)})
        return {"access_token": token, "user": user}
        
    except Exception as e:
        logger.error("Sign-in error", exc_info=True)
        raise
```

---

### Example 3: Background Task Logging

```python
from fastapi import BackgroundTasks
from app.core.logger import get_context_logger

async def send_welcome_email_task(user_id: str, email: str, request_id: str):
    """Background task with logging context"""
    logger = get_context_logger(
        __name__,
        user_id=user_id,
        request_id=request_id,
        task="welcome_email"
    )
    
    logger.info("Starting welcome email task", extra={"email": email})
    
    try:
        # Send email logic
        await email_service.send_welcome(email)
        logger.info("Welcome email sent successfully")
        
    except Exception as e:
        logger.error("Failed to send welcome email", 
                    extra={"error": str(e)},
                    exc_info=True)

@router.post("/auth/signup")
async def signup(
    data: SignUpRequest,
    background_tasks: BackgroundTasks,
    logger: LoggerAdapter = Depends(get_request_logger)
):
    user = await auth_service.create_user(data)
    
    # Queue background task with request context
    background_tasks.add_task(
        send_welcome_email_task,
        user_id=str(user.id),
        email=user.email,
        request_id=logger.extra.get('request_id')
    )
    
    logger.info("User created, welcome email queued", 
               extra={"user_id": str(user.id)})
    
    return {"user": user}
```

---

## Application Startup Configuration

**`apps/api/app/main.py`**:
```python
from fastapi import FastAPI
from app.core.logger import setup_logging
import os

# Configure logging on startup
setup_logging(
    level=os.getenv("LOG_LEVEL", "INFO"),
    json_output=os.getenv("ENVIRONMENT", "development") == "production"
)

app = FastAPI(title="Plinto API")

@app.on_event("startup")
async def startup_event():
    logger = get_logger(__name__)
    logger.info("Application starting", extra={
        "environment": os.getenv("ENVIRONMENT"),
        "log_level": os.getenv("LOG_LEVEL", "INFO")
    })
```

---

## Output Examples

### Development Mode (Human-Readable)
```
2025-11-18 10:30:45 - app.services.auth_service - INFO - Authentication attempt started
2025-11-18 10:30:45 - app.services.auth_service - INFO - Authentication successful
```

### Production Mode (JSON)
```json
{
  "timestamp": "2025-11-18T10:30:45.123Z",
  "level": "INFO",
  "module": "auth_service",
  "function": "authenticate_user",
  "message": "Authentication successful",
  "user_id": "user_abc123",
  "organization_id": "org_xyz789",
  "request_id": "req_123456",
  "email": "user@example.com"
}
```

---

## Migration Checklist

### Phase 1: Infrastructure Setup ✅
- [x] Create `app/core/logger.py`
- [x] Add `python-json-logger` dependency
- [x] Configure in `main.py` startup

### Phase 2: Core Services (Week 3)
- [ ] Migrate auth services
- [ ] Migrate session management
- [ ] Migrate user management
- [ ] Add request ID middleware

### Phase 3: API Routes (Week 3-4)
- [ ] Add request logger dependency
- [ ] Migrate auth routes
- [ ] Migrate user routes
- [ ] Migrate organization routes

### Phase 4: Background Tasks (Week 4)
- [ ] Migrate email tasks
- [ ] Migrate webhook tasks
- [ ] Migrate scheduled jobs

---

## Best Practices

### DO ✅
- Use `get_context_logger()` for request-scoped operations
- Include user_id, org_id, request_id in context
- Log at appropriate levels (DEBUG, INFO, WARN, ERROR)
- Include extra context in `extra` parameter
- Use `exc_info=True` for exceptions

### DON'T ❌
- Don't log sensitive data (passwords, tokens, PII)
- Don't use `print()` statements
- Don't use `console.log` equivalent
- Don't log in tight loops (use sampling)
- Don't duplicate context in message and extra

### Sensitive Data Handling
```python
# ❌ DON'T
logger.info("User login", extra={"password": password})

# ✅ DO
logger.info("User login", extra={"email": email, "method": "password"})
```

---

## Integration with Log Aggregators

### Datadog
```python
# Environment variables
DATADOG_API_KEY=your_key
DATADOG_APP_KEY=your_app_key
LOG_LEVEL=INFO
ENVIRONMENT=production

# Logs automatically ingested via JSON stdout
```

### CloudWatch
```python
# AWS CloudWatch agent configuration
{
  "logs": {
    "logs_collected": {
      "files": {
        "collect_list": [
          {
            "file_path": "/var/log/plinto/*.log",
            "log_group_name": "/aws/plinto/api",
            "log_stream_name": "{instance_id}",
            "timestamp_format": "%Y-%m-%dT%H:%M:%S"
          }
        ]
      }
    }
  }
}
```

---

## Testing Logging

```python
# tests/test_logging.py
import logging
from app.core.logger import get_context_logger

def test_context_logger(caplog):
    """Test context logger includes context in all logs"""
    with caplog.at_level(logging.INFO):
        logger = get_context_logger(
            "test_module",
            user_id="user_123",
            request_id="req_456"
        )
        
        logger.info("Test message")
        
        # Verify log record has context
        assert len(caplog.records) == 1
        record = caplog.records[0]
        assert record.user_id == "user_123"
        assert record.request_id == "req_456"
        assert "Test message" in record.message
```

---

## Performance Considerations

**Logging Overhead**: ~0.1-0.5ms per log statement

**Best Practices**:
- Use appropriate log levels (DEBUG in dev, INFO+ in prod)
- Sample high-frequency logs (e.g., 1% of requests)
- Avoid logging in hot paths (inner loops)
- Use lazy evaluation for expensive context

```python
# ❌ Expensive - always evaluated
logger.debug(f"Complex data: {expensive_computation()}")

# ✅ Efficient - only evaluated if DEBUG enabled
logger.debug("Complex data: %s", expensive_computation)
```

---

## Migration Timeline

**Week 3** (Current):
- ✅ Infrastructure ready
- 🔄 Migrate auth services
- 🔄 Migrate critical API routes
- Target: 80% coverage

**Week 4**:
- Migrate remaining services
- Add sampling for high-frequency logs
- Performance optimization
- Target: 95% coverage

---

**Status**: Ready for production use ✅  
**Next Action**: Begin migrating auth services with request context
