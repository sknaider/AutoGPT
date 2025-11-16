"""
CSRF Protection Middleware for Enterprise Security

Implements CSRF protection using double-submit cookie pattern for stateless services.
Supports both cookie-based and header-based token validation.
"""

import secrets
from typing import Optional

from fastapi import Request, Response, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import JSONResponse

from backend.util.settings import Settings


class CSRFProtectionMiddleware(BaseHTTPMiddleware):
    """
    Enterprise-grade CSRF protection middleware.

    Features:
    - Double-submit cookie pattern (stateless)
    - Configurable exempt routes
    - Support for both cookie and header tokens
    - Secure cookie settings
    - Detailed error logging
    """

    CSRF_TOKEN_LENGTH = 32
    CSRF_COOKIE_NAME = "csrf_token"
    CSRF_HEADER_NAME = "X-CSRF-Token"

    # Safe HTTP methods that don't require CSRF protection
    SAFE_METHODS = {"GET", "HEAD", "OPTIONS", "TRACE"}

    # Routes exempt from CSRF protection
    EXEMPT_ROUTES = {
        "/health",
        "/metrics",
        "/api/auth/callback",  # OAuth callbacks
        "/api/webhooks",  # Webhook endpoints (use signature verification)
    }

    def __init__(self, app, settings: Optional[Settings] = None):
        super().__init__(app)
        self.settings = settings or Settings()
        self.enabled = self.settings.config.enable_csrf_protection

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        """Process request with CSRF protection."""

        # Skip if disabled (e.g., in development)
        if not self.enabled:
            return await call_next(request)

        # Skip safe methods
        if request.method in self.SAFE_METHODS:
            response = await call_next(request)
            # Set CSRF token cookie for subsequent requests
            if self.CSRF_COOKIE_NAME not in request.cookies:
                self._set_csrf_cookie(response)
            return response

        # Skip exempt routes
        if self._is_exempt(request.url.path):
            return await call_next(request)

        # Validate CSRF token
        try:
            self._validate_csrf_token(request)
        except HTTPException as e:
            return JSONResponse(
                status_code=e.status_code,
                content={
                    "error": "CSRF validation failed",
                    "detail": e.detail,
                    "type": "csrf_error"
                },
                headers={
                    "X-Content-Type-Options": "nosniff",
                }
            )

        response = await call_next(request)

        # Rotate token after successful mutation
        if response.status_code < 400:
            self._set_csrf_cookie(response)

        return response

    def _validate_csrf_token(self, request: Request) -> None:
        """
        Validate CSRF token using double-submit pattern.

        Raises:
            HTTPException: If validation fails
        """
        # Get token from cookie
        cookie_token = request.cookies.get(self.CSRF_COOKIE_NAME)
        if not cookie_token:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="CSRF token missing from cookie"
            )

        # Get token from header or form data
        header_token = request.headers.get(self.CSRF_HEADER_NAME)

        # Try to get from form data if not in header
        if not header_token and request.method == "POST":
            # Note: This is async, but we're in sync context
            # For form data, frontend should send via header
            pass

        if not header_token:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"CSRF token missing from {self.CSRF_HEADER_NAME} header"
            )

        # Constant-time comparison to prevent timing attacks
        if not secrets.compare_digest(cookie_token, header_token):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="CSRF token validation failed"
            )

    def _set_csrf_cookie(self, response: Response) -> None:
        """Set CSRF token cookie with secure settings."""
        token = secrets.token_urlsafe(self.CSRF_TOKEN_LENGTH)

        response.set_cookie(
            key=self.CSRF_COOKIE_NAME,
            value=token,
            httponly=False,  # JavaScript needs to read this for header
            secure=self.settings.config.environment == "production",
            samesite="strict",
            max_age=86400,  # 24 hours
            path="/",
        )

    def _is_exempt(self, path: str) -> bool:
        """Check if path is exempt from CSRF protection."""
        return any(path.startswith(exempt) for exempt in self.EXEMPT_ROUTES)


def get_csrf_token_from_request(request: Request) -> Optional[str]:
    """Helper function to retrieve CSRF token from request."""
    return request.cookies.get(CSRFProtectionMiddleware.CSRF_COOKIE_NAME)
