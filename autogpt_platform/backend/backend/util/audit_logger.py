"""
Enterprise Audit Logging System

Provides comprehensive audit logging for security-critical operations.
Supports compliance requirements (SOC 2, GDPR, HIPAA, etc.)
"""

import json
import logging
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional

from pydantic import BaseModel

logger = logging.getLogger(__name__)


class AuditEventType(str, Enum):
    """Types of auditable events."""

    # Authentication & Authorization
    USER_LOGIN = "user.login"
    USER_LOGOUT = "user.logout"
    USER_LOGIN_FAILED = "user.login_failed"
    ADMIN_IMPERSONATION_START = "admin.impersonation.start"
    ADMIN_IMPERSONATION_END = "admin.impersonation.end"

    # User Management
    USER_CREATED = "user.created"
    USER_UPDATED = "user.updated"
    USER_DELETED = "user.deleted"
    USER_PASSWORD_CHANGED = "user.password_changed"
    USER_EMAIL_CHANGED = "user.email_changed"

    # Credentials & Secrets
    CREDENTIAL_CREATED = "credential.created"
    CREDENTIAL_UPDATED = "credential.updated"
    CREDENTIAL_DELETED = "credential.deleted"
    CREDENTIAL_ACCESSED = "credential.accessed"
    API_KEY_CREATED = "api_key.created"
    API_KEY_REVOKED = "api_key.revoked"
    API_KEY_USED = "api_key.used"

    # Agent & Graph Operations
    AGENT_CREATED = "agent.created"
    AGENT_UPDATED = "agent.updated"
    AGENT_DELETED = "agent.deleted"
    AGENT_PUBLISHED = "agent.published"
    AGENT_UNPUBLISHED = "agent.unpublished"
    GRAPH_EXECUTED = "graph.executed"
    GRAPH_EXECUTION_FAILED = "graph.execution_failed"
    GRAPH_EXECUTION_CANCELLED = "graph.execution_cancelled"

    # Data Access
    USER_DATA_ACCESSED = "user_data.accessed"
    USER_DATA_EXPORTED = "user_data.exported"
    USER_DATA_DELETED = "user_data.deleted"
    BULK_OPERATION_EXECUTED = "bulk_operation.executed"

    # Store & Marketplace
    STORE_LISTING_CREATED = "store.listing_created"
    STORE_LISTING_APPROVED = "store.listing_approved"
    STORE_LISTING_REJECTED = "store.listing_rejected"
    STORE_PURCHASE = "store.purchase"

    # Credits & Billing
    CREDITS_ADDED = "credits.added"
    CREDITS_DEDUCTED = "credits.deducted"
    CREDITS_REFUNDED = "credits.refunded"
    PAYMENT_PROCESSED = "payment.processed"
    PAYMENT_FAILED = "payment.failed"

    # System & Configuration
    CONFIGURATION_CHANGED = "config.changed"
    FEATURE_FLAG_CHANGED = "feature_flag.changed"
    SECURITY_SETTING_CHANGED = "security.setting_changed"

    # Compliance & Security
    DATA_BREACH_DETECTED = "security.data_breach_detected"
    SUSPICIOUS_ACTIVITY = "security.suspicious_activity"
    RATE_LIMIT_EXCEEDED = "security.rate_limit_exceeded"
    CSRF_VIOLATION = "security.csrf_violation"


class AuditSeverity(str, Enum):
    """Severity levels for audit events."""

    LOW = "low"  # Routine operations
    MEDIUM = "medium"  # Important but expected operations
    HIGH = "high"  # Sensitive operations requiring attention
    CRITICAL = "critical"  # Security incidents, breaches


class AuditEvent(BaseModel):
    """Structured audit event."""

    # Required fields
    event_type: AuditEventType
    timestamp: datetime
    user_id: Optional[str]
    severity: AuditSeverity = AuditSeverity.MEDIUM

    # Optional context
    actor_id: Optional[str] = None  # For admin impersonation
    actor_email: Optional[str] = None
    target_user_id: Optional[str] = None
    target_resource_type: Optional[str] = None
    target_resource_id: Optional[str] = None

    # Request context
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    request_method: Optional[str] = None
    request_url: Optional[str] = None

    # Event details
    action: str
    result: str = "success"  # success, failure, partial
    error_message: Optional[str] = None

    # Additional metadata
    metadata: Dict[str, Any] = {}

    # Compliance tags
    compliance_tags: list[str] = []  # e.g., ["GDPR", "SOC2", "HIPAA"]

    def to_log_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for logging."""
        return {
            "audit_event": True,  # Flag for log filtering
            "event_type": self.event_type.value,
            "timestamp": self.timestamp.isoformat(),
            "user_id": self.user_id,
            "severity": self.severity.value,
            "actor_id": self.actor_id,
            "actor_email": self.actor_email,
            "target_user_id": self.target_user_id,
            "target_resource_type": self.target_resource_type,
            "target_resource_id": self.target_resource_id,
            "ip_address": self.ip_address,
            "user_agent": self.user_agent,
            "request_method": self.request_method,
            "request_url": self.request_url,
            "action": self.action,
            "result": self.result,
            "error_message": self.error_message,
            "metadata": self.metadata,
            "compliance_tags": self.compliance_tags,
        }


class AuditLogger:
    """
    Enterprise audit logger.

    Features:
    - Structured logging with consistent format
    - Severity-based filtering
    - Compliance tagging
    - Async-safe logging
    - Contextual information capture
    """

    def __init__(self):
        self.logger = logging.getLogger("audit")
        # Ensure audit logs go to a separate file if configured
        self.logger.setLevel(logging.INFO)

    def log_event(self, event: AuditEvent) -> None:
        """
        Log an audit event.

        Args:
            event: The audit event to log
        """
        log_dict = event.to_log_dict()

        # Log at appropriate level based on severity
        if event.severity == AuditSeverity.CRITICAL:
            self.logger.critical(json.dumps(log_dict))
        elif event.severity == AuditSeverity.HIGH:
            self.logger.warning(json.dumps(log_dict))
        else:
            self.logger.info(json.dumps(log_dict))

    # Convenience methods for common events

    def log_authentication(
        self,
        event_type: AuditEventType,
        user_id: Optional[str],
        email: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        success: bool = True,
        error_message: Optional[str] = None,
    ) -> None:
        """Log authentication event."""
        event = AuditEvent(
            event_type=event_type,
            timestamp=datetime.utcnow(),
            user_id=user_id,
            severity=AuditSeverity.HIGH if not success else AuditSeverity.MEDIUM,
            actor_email=email,
            ip_address=ip_address,
            user_agent=user_agent,
            action=f"User {'failed to authenticate' if not success else 'authenticated'}",
            result="failure" if not success else "success",
            error_message=error_message,
            compliance_tags=["AUTHENTICATION"],
        )
        self.log_event(event)

    def log_data_access(
        self,
        user_id: str,
        target_user_id: Optional[str],
        resource_type: str,
        resource_id: str,
        action: str,
        ip_address: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Log data access event (GDPR compliance)."""
        event = AuditEvent(
            event_type=AuditEventType.USER_DATA_ACCESSED,
            timestamp=datetime.utcnow(),
            user_id=user_id,
            severity=AuditSeverity.HIGH,
            target_user_id=target_user_id,
            target_resource_type=resource_type,
            target_resource_id=resource_id,
            ip_address=ip_address,
            action=action,
            metadata=metadata or {},
            compliance_tags=["GDPR", "SOC2", "DATA_ACCESS"],
        )
        self.log_event(event)

    def log_credential_operation(
        self,
        event_type: AuditEventType,
        user_id: str,
        credential_id: str,
        provider: str,
        action: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Log credential operation (security-sensitive)."""
        event = AuditEvent(
            event_type=event_type,
            timestamp=datetime.utcnow(),
            user_id=user_id,
            severity=AuditSeverity.HIGH,
            target_resource_type="credential",
            target_resource_id=credential_id,
            action=action,
            metadata={**(metadata or {}), "provider": provider},
            compliance_tags=["SECURITY", "CREDENTIALS"],
        )
        self.log_event(event)

    def log_admin_action(
        self,
        event_type: AuditEventType,
        admin_id: str,
        admin_email: str,
        target_user_id: Optional[str],
        action: str,
        request_method: Optional[str] = None,
        request_url: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Log admin action (high severity)."""
        event = AuditEvent(
            event_type=event_type,
            timestamp=datetime.utcnow(),
            user_id=target_user_id,
            severity=AuditSeverity.HIGH,
            actor_id=admin_id,
            actor_email=admin_email,
            target_user_id=target_user_id,
            request_method=request_method,
            request_url=request_url,
            action=action,
            metadata=metadata or {},
            compliance_tags=["ADMIN_ACTION", "PRIVILEGED_ACCESS"],
        )
        self.log_event(event)

    def log_security_event(
        self,
        event_type: AuditEventType,
        user_id: Optional[str],
        action: str,
        ip_address: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Log security event (critical severity)."""
        event = AuditEvent(
            event_type=event_type,
            timestamp=datetime.utcnow(),
            user_id=user_id,
            severity=AuditSeverity.CRITICAL,
            ip_address=ip_address,
            action=action,
            metadata=metadata or {},
            compliance_tags=["SECURITY_INCIDENT"],
        )
        self.log_event(event)

    def log_bulk_operation(
        self,
        user_id: str,
        operation_type: str,
        affected_count: int,
        resource_type: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Log bulk operation (requires audit trail)."""
        event = AuditEvent(
            event_type=AuditEventType.BULK_OPERATION_EXECUTED,
            timestamp=datetime.utcnow(),
            user_id=user_id,
            severity=AuditSeverity.HIGH,
            target_resource_type=resource_type,
            action=f"Bulk {operation_type} on {affected_count} {resource_type}(s)",
            metadata={
                **(metadata or {}),
                "affected_count": affected_count,
                "operation_type": operation_type,
            },
            compliance_tags=["BULK_OPERATION", "DATA_MODIFICATION"],
        )
        self.log_event(event)


# Global audit logger instance
_audit_logger: Optional[AuditLogger] = None


def get_audit_logger() -> AuditLogger:
    """Get global audit logger instance."""
    global _audit_logger
    if _audit_logger is None:
        _audit_logger = AuditLogger()
    return _audit_logger


# Convenience function
def audit_log(event: AuditEvent) -> None:
    """Convenience function to log audit event."""
    get_audit_logger().log_event(event)
