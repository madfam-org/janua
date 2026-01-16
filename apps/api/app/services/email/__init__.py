"""
Email Services Module
Handles email sending via Resend and notification management
"""

# Import EmailService from email_service.py for backward compatibility
# auth.py uses: from app.services.email import EmailService
from app.services.email_service import EmailService

# Lazy imports for optional dependencies
def get_resend_service():
    """Get ResendService (requires 'resend' package)"""
    from app.services.email.resend_service import ResendService
    return ResendService

def get_notification_service():
    """Get NotificationService"""
    from app.services.email.notifications import NotificationService
    return NotificationService

__all__ = ["EmailService", "get_resend_service", "get_notification_service"]
