"""
Audit logging service for compliance and security monitoring
"""

import logging
from datetime import datetime
from typing import Dict, Any, Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from ..models import AuditLog

logger = logging.getLogger(__name__)


class AuditService:
    """Service for comprehensive audit logging"""
    
    def __init__(self):
        self.high_risk_actions = {
            'user_delete', 'admin_login', 'password_reset', 'sso_config_change',
            'user_suspend', 'role_change', 'api_key_create', 'webhook_create'
        }
        
        self.compliance_relevant_actions = {
            'user_create', 'user_update', 'user_delete', 'consent_granted',
            'consent_revoked', 'data_export', 'data_delete', 'privacy_setting_change'
        }
    
    async def log_action(
        self,
        db: AsyncSession,
        action: str,
        resource_type: str,
        actor_id: Optional[str] = None,
        actor_type: str = "user",
        resource_id: Optional[str] = None,
        organization_id: Optional[str] = None,
        old_values: Optional[Dict[str, Any]] = None,
        new_values: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        actor_ip: Optional[str] = None,
        actor_user_agent: Optional[str] = None,
        success: bool = True,
        error_message: Optional[str] = None
    ) -> str:
        """
        Log an audit event
        
        Args:
            action: Action performed (e.g., 'user_create', 'login_attempt')
            resource_type: Type of resource (e.g., 'user', 'organization')
            actor_id: ID of the actor performing the action
            actor_type: Type of actor ('user', 'system', 'api')
            resource_id: ID of the affected resource
            organization_id: Organization context
            old_values: Previous state of the resource
            new_values: New state of the resource
            metadata: Additional context information
            actor_ip: IP address of the actor
            actor_user_agent: User agent string
            success: Whether the action succeeded
            error_message: Error message if action failed
            
        Returns:
            Audit log ID
        """
        try:
            # Determine risk level
            risk_level = self._calculate_risk_level(action, success, error_message)
            
            # Check if compliance relevant
            compliance_relevant = action in self.compliance_relevant_actions
            compliance_standards = []
            if compliance_relevant:
                compliance_standards = ["gdpr", "hipaa"]  # Example standards
            
            # Check for suspicious activity
            is_suspicious = self._is_suspicious_activity(
                action, actor_ip, actor_user_agent, metadata
            )
            
            # Create audit log entry
            audit_log = AuditLog(
                organization_id=organization_id,
                actor_id=actor_id,
                actor_type=actor_type,
                actor_ip=actor_ip,
                actor_user_agent=actor_user_agent,
                action=action,
                resource_type=resource_type,
                resource_id=resource_id,
                old_values=old_values,
                new_values=new_values,
                metadata=metadata or {},
                compliance_relevant=compliance_relevant,
                compliance_standards=compliance_standards,
                risk_level=risk_level,
                is_suspicious=is_suspicious,
                success=success,
                error_message=error_message
            )
            
            db.add(audit_log)
            await db.commit()
            
            # Log to application logger for high-risk events
            if risk_level in ["high", "critical"] or is_suspicious:
                logger.warning(
                    f"High-risk audit event: {action} by {actor_type}:{actor_id} "
                    f"on {resource_type}:{resource_id} - Risk: {risk_level}, "
                    f"Suspicious: {is_suspicious}"
                )
            
            return str(audit_log.id)
            
        except Exception as e:
            logger.error(f"Failed to create audit log: {e}")
            # Don't fail the main operation if audit logging fails
            return None
    
    async def log_authentication_event(
        self,
        db: AsyncSession,
        event_type: str,  # login_success, login_failure, logout, etc.
        user_id: Optional[str] = None,
        email: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        auth_method: Optional[str] = None,
        organization_id: Optional[str] = None,
        failure_reason: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """Log authentication-specific events"""
        
        action_metadata = {
            "auth_method": auth_method,
            "email": email,
            "failure_reason": failure_reason,
            **(metadata or {})
        }
        
        success = "failure" not in event_type
        
        return await self.log_action(
            db=db,
            action=event_type,
            resource_type="authentication",
            actor_id=user_id,
            actor_type="user",
            organization_id=organization_id,
            metadata=action_metadata,
            actor_ip=ip_address,
            actor_user_agent=user_agent,
            success=success,
            error_message=failure_reason
        )
    
    async def log_data_access(
        self,
        db: AsyncSession,
        access_type: str,  # read, create, update, delete, export
        data_type: str,  # user_data, organization_data, etc.
        actor_id: str,
        resource_id: Optional[str] = None,
        organization_id: Optional[str] = None,
        data_fields: Optional[List[str]] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        lawful_basis: Optional[str] = None,
        purpose: Optional[str] = None
    ) -> str:
        """Log data access events for GDPR compliance"""
        
        metadata = {
            "data_fields": data_fields,
            "lawful_basis": lawful_basis,
            "purpose": purpose
        }
        
        return await self.log_action(
            db=db,
            action=f"data_{access_type}",
            resource_type=data_type,
            actor_id=actor_id,
            resource_id=resource_id,
            organization_id=organization_id,
            metadata=metadata,
            actor_ip=ip_address,
            actor_user_agent=user_agent
        )
    
    async def search_audit_logs(
        self,
        db: AsyncSession,
        organization_id: Optional[str] = None,
        actor_id: Optional[str] = None,
        action: Optional[str] = None,
        resource_type: Optional[str] = None,
        risk_level: Optional[str] = None,
        compliance_relevant: Optional[bool] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """Search audit logs with filters"""
        
        try:
            query = select(AuditLog).order_by(AuditLog.occurred_at.desc())
            
            # Apply filters
            conditions = []
            
            if organization_id:
                conditions.append(AuditLog.organization_id == organization_id)
            
            if actor_id:
                conditions.append(AuditLog.actor_id == actor_id)
            
            if action:
                conditions.append(AuditLog.action == action)
            
            if resource_type:
                conditions.append(AuditLog.resource_type == resource_type)
            
            if risk_level:
                conditions.append(AuditLog.risk_level == risk_level)
            
            if compliance_relevant is not None:
                conditions.append(AuditLog.compliance_relevant == compliance_relevant)
            
            if start_date:
                conditions.append(AuditLog.occurred_at >= start_date)
            
            if end_date:
                conditions.append(AuditLog.occurred_at <= end_date)
            
            if conditions:
                query = query.where(and_(*conditions))
            
            query = query.offset(offset).limit(limit)
            
            result = await db.execute(query)
            logs = result.scalars().all()
            
            return [
                {
                    "id": str(log.id),
                    "organization_id": str(log.organization_id) if log.organization_id else None,
                    "actor_id": str(log.actor_id) if log.actor_id else None,
                    "actor_type": log.actor_type,
                    "actor_ip": log.actor_ip,
                    "action": log.action,
                    "resource_type": log.resource_type,
                    "resource_id": log.resource_id,
                    "old_values": log.old_values,
                    "new_values": log.new_values,
                    "metadata": log.metadata,
                    "compliance_relevant": log.compliance_relevant,
                    "compliance_standards": log.compliance_standards,
                    "risk_level": log.risk_level,
                    "is_suspicious": log.is_suspicious,
                    "success": log.success,
                    "error_message": log.error_message,
                    "occurred_at": log.occurred_at.isoformat()
                }
                for log in logs
            ]
            
        except Exception as e:
            logger.error(f"Failed to search audit logs: {e}")
            raise
    
    async def generate_compliance_report(
        self,
        db: AsyncSession,
        organization_id: str,
        start_date: datetime,
        end_date: datetime,
        standards: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Generate compliance report for audit purposes"""
        
        try:
            # Get compliance-relevant logs
            logs = await self.search_audit_logs(
                db=db,
                organization_id=organization_id,
                compliance_relevant=True,
                start_date=start_date,
                end_date=end_date,
                limit=10000  # Large limit for comprehensive report
            )
            
            # Categorize logs by action type
            categories = {}
            for log in logs:
                action = log["action"]
                if action not in categories:
                    categories[action] = []
                categories[action].append(log)
            
            # Calculate statistics
            total_events = len(logs)
            failed_events = sum(1 for log in logs if not log["success"])
            high_risk_events = sum(1 for log in logs if log["risk_level"] in ["high", "critical"])
            suspicious_events = sum(1 for log in logs if log["is_suspicious"])
            
            # Data access summary
            data_access_events = [log for log in logs if log["action"].startswith("data_")]
            
            return {
                "report_period": {
                    "start_date": start_date.isoformat(),
                    "end_date": end_date.isoformat()
                },
                "organization_id": organization_id,
                "standards": standards or ["gdpr", "hipaa"],
                "summary": {
                    "total_events": total_events,
                    "failed_events": failed_events,
                    "high_risk_events": high_risk_events,
                    "suspicious_events": suspicious_events,
                    "data_access_events": len(data_access_events)
                },
                "categories": {
                    category: len(events) for category, events in categories.items()
                },
                "data_access_summary": self._summarize_data_access(data_access_events),
                "compliance_status": self._assess_compliance_status(logs),
                "generated_at": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to generate compliance report: {e}")
            raise
    
    def _calculate_risk_level(
        self,
        action: str,
        success: bool,
        error_message: Optional[str]
    ) -> str:
        """Calculate risk level for an action"""
        
        if not success:
            if action in self.high_risk_actions:
                return "critical"
            return "high"
        
        if action in self.high_risk_actions:
            return "high"
        
        if action.startswith("admin_") or "delete" in action:
            return "medium"
        
        return "low"
    
    def _is_suspicious_activity(
        self,
        action: str,
        actor_ip: Optional[str],
        actor_user_agent: Optional[str],
        metadata: Optional[Dict[str, Any]]
    ) -> bool:
        """Determine if activity is suspicious"""
        
        # Simple heuristics - in production, this would be more sophisticated
        suspicious_indicators = []
        
        # Check for rapid repeated actions
        if metadata and metadata.get("rapid_requests"):
            suspicious_indicators.append("rapid_requests")
        
        # Check for unusual IP patterns
        if actor_ip and self._is_suspicious_ip(actor_ip):
            suspicious_indicators.append("suspicious_ip")
        
        # Check for bot-like user agents
        if actor_user_agent and self._is_bot_user_agent(actor_user_agent):
            suspicious_indicators.append("bot_user_agent")
        
        return len(suspicious_indicators) > 0
    
    def _is_suspicious_ip(self, ip: str) -> bool:
        """Check if IP address is suspicious"""
        # Placeholder - in production, check against threat intelligence
        suspicious_ranges = ["10.0.0.0", "192.168.1.0"]  # Example
        return any(ip.startswith(range_ip) for range_ip in suspicious_ranges)
    
    def _is_bot_user_agent(self, user_agent: str) -> bool:
        """Check if user agent appears to be a bot"""
        bot_indicators = ["bot", "crawler", "spider", "scraper"]
        return any(indicator in user_agent.lower() for indicator in bot_indicators)
    
    def _summarize_data_access(self, data_access_events: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Summarize data access events for compliance reporting"""
        
        access_types = {}
        data_types = {}
        
        for event in data_access_events:
            action = event["action"]
            resource_type = event["resource_type"]
            
            if action not in access_types:
                access_types[action] = 0
            access_types[action] += 1
            
            if resource_type not in data_types:
                data_types[resource_type] = 0
            data_types[resource_type] += 1
        
        return {
            "access_types": access_types,
            "data_types": data_types,
            "total_access_events": len(data_access_events)
        }
    
    def _assess_compliance_status(self, logs: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Assess compliance status based on audit logs"""
        
        issues = []
        
        # Check for failed high-risk operations
        failed_high_risk = [
            log for log in logs
            if not log["success"] and log["risk_level"] in ["high", "critical"]
        ]
        if failed_high_risk:
            issues.append(f"{len(failed_high_risk)} failed high-risk operations")
        
        # Check for suspicious activities
        suspicious_activities = [log for log in logs if log["is_suspicious"]]
        if suspicious_activities:
            issues.append(f"{len(suspicious_activities)} suspicious activities detected")
        
        # Overall assessment
        if len(issues) == 0:
            status = "compliant"
        elif len(issues) <= 2:
            status = "review_required"
        else:
            status = "non_compliant"
        
        return {
            "status": status,
            "issues": issues,
            "total_violations": len(issues)
        }