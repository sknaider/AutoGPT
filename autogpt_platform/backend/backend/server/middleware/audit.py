"""
Audit Logging Middleware

Automatically captures audit events for API requests.
"""

import time
from typing import Callable, Optional

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from backend.util.audit_logger import (
    AuditEvent,
    AuditEventType,
    AuditSeverity,
    get_audit_logger,
)


class AuditLoggingMiddleware(BaseHTTPMiddleware):
    """
    Middleware for automatic audit logging of API requests.

    Features:
    - Logs sensitive operations automatically
    - Captures request context (IP, User-Agent, etc.)
    - Associates events with authenticated users
    - Configurable event types
    """

    # Paths that should be audit logged
    AUDIT_PATHS = {
        # Credential operations
        "/api/integrations/oauth": AuditEventType.CREDENTIAL_CREATED,
        "/api/integrations/credentials": AuditEventType.CREDENTIAL_ACCESSED,
        # User operations
        "/api/auth": AuditEventType.USER_LOGIN,
        # Agent operations
        "/api/store/submit": AuditEventType.STORE_LISTING_CREATED,
    }

    # Methods that indicate write operations
    WRITE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}

    def __init__(self, app, enabled: bool = True):
        super().__init__(app)
        self.enabled = enabled
        self.audit_logger = get_audit_logger()

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        """Process request with audit logging."""

        if not self.enabled:
            return await call_next(request)

        start_time = time.time()

        # Extract request context
        user_id = self._get_user_id(request)
        ip_address = self._get_client_ip(request)
        user_agent = request.headers.get("user-agent")

        # Process request
        response = await call_next(request)

        # Log if this is an auditable operation
        if self._should_audit(request, response):
            event_type = self._determine_event_type(request, response)
            if event_type:
                duration = time.time() - start_time
                self._log_audit_event(
                    event_type=event_type,
                    request=request,
                    response=response,
                    user_id=user_id,
                    ip_address=ip_address,
                    user_agent=user_agent,
                    duration=duration,
                )

        return response

    def _should_audit(self, request: Request, response: Response) -> bool:
        """Determine if request should be audit logged."""
        # Skip health checks and metrics
        if request.url.path in ["/health", "/metrics"]:
            return False

        # Skip successful GET requests (read-only)
        if request.method == "GET" and 200 <= response.status_code < 300:
            return False

        # Audit all write operations
        if request.method in self.WRITE_METHODS:
            return True

        # Audit failed requests
        if response.status_code >= 400:
            return True

        # Audit specific paths
        for path in self.AUDIT_PATHS:
            if request.url.path.startswith(path):
                return True

        return False

    def _determine_event_type(
        self, request: Request, response: Response
    ) -> Optional[AuditEventType]:
        """Determine the audit event type."""
        # Check specific paths first
        for path, event_type in self.AUDIT_PATHS.items():
            if request.url.path.startswith(path):
                return event_type

        # Determine based on path and method
        if "/credential" in request.url.path:
            if request.method == "POST":
                return AuditEventType.CREDENTIAL_CREATED
            elif request.method == "DELETE":
                return AuditEventType.CREDENTIAL_DELETED
            elif request.method in ["PUT", "PATCH"]:
                return AuditEventType.CREDENTIAL_UPDATED

        if "/agent" in request.url.path or "/graph" in request.url.path:
            if request.method == "POST":
                return AuditEventType.AGENT_CREATED
            elif request.method == "DELETE":
                return AuditEventType.AGENT_DELETED
            elif request.method in ["PUT", "PATCH"]:
                return AuditEventType.AGENT_UPDATED

        # Security events
        if response.status_code == 401:
            return AuditEventType.USER_LOGIN_FAILED
        if response.status_code == 403:
            if "csrf" in response.headers.get("X-Error-Type", "").lower():
                return AuditEventType.CSRF_VIOLATION
            return AuditEventType.SUSPICIOUS_ACTIVITY
        if response.status_code == 429:
            return AuditEventType.RATE_LIMIT_EXCEEDED

        return None

    def _log_audit_event(
        self,
        event_type: AuditEventType,
        request: Request,
        response: Response,
        user_id: Optional[str],
        ip_address: Optional[str],
        user_agent: Optional[str],
        duration: float,
    ) -> None:
        """Log audit event."""
        # Determine severity
        severity = AuditSeverity.MEDIUM
        if response.status_code >= 500:
            severity = AuditSeverity.HIGH
        elif response.status_code >= 400:
            severity = AuditSeverity.MEDIUM
        elif event_type in [
            AuditEventType.CREDENTIAL_CREATED,
            AuditEventType.CREDENTIAL_DELETED,
            AuditEventType.USER_DATA_DELETED,
        ]:
            severity = AuditSeverity.HIGH

        # Build action description
        action = f"{request.method} {request.url.path}"
        if response.status_code >= 400:
            action += f" (HTTP {response.status_code})"

        # Create audit event
        event = AuditEvent(
            event_type=event_type,
            timestamp=request.state.start_time
            if hasattr(request.state, "start_time")
            else None,
            user_id=user_id,
            severity=severity,
            ip_address=ip_address,
            user_agent=user_agent,
            request_method=request.method,
            request_url=str(request.url),
            action=action,
            result="success" if response.status_code < 400 else "failure",
            metadata={
                "status_code": response.status_code,
                "duration_ms": round(duration * 1000, 2),
            },
        )

        self.audit_logger.log_event(event)

    def _get_user_id(self, request: Request) -> Optional[str]:
        """Extract user ID from request."""
        # Try to get from request state (set by auth middleware)
        if hasattr(request.state, "user_id"):
            return request.state.user_id

        # Try to parse from JWT token
        auth_header = request.headers.get("authorization", "")
        if auth_header.startswith("Bearer "):
            # Token parsing would go here
            # For now, return None
            pass

        return None

    def _get_client_ip(self, request: Request) -> Optional[str]:
        """Extract client IP address."""
        # Check for proxy headers
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            # Return first IP in the chain
            return forwarded_for.split(",")[0].strip()

        real_ip = request.headers.get("x-real-ip")
        if real_ip:
            return real_ip

        # Fall back to direct connection
        if request.client:
            return request.client.host

        return None
