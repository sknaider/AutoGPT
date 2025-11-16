"""
HTTPS Enforcement Middleware for Enterprise Security

Redirects all HTTP traffic to HTTPS in production environments.
Includes HSTS (HTTP Strict Transport Security) headers.
"""

from typing import Optional

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import RedirectResponse

from backend.util.settings import Settings


class HTTPSEnforcementMiddleware(BaseHTTPMiddleware):
    """
    Enterprise HTTPS enforcement middleware.

    Features:
    - Automatic HTTP -> HTTPS redirects
    - HSTS headers with preload support
    - Configurable by environment
    - Proxy-aware (respects X-Forwarded-Proto header)
    """

    # HSTS max-age: 2 years (recommended for preload list)
    HSTS_MAX_AGE = 63072000

    def __init__(self, app, settings: Optional[Settings] = None):
        super().__init__(app)
        self.settings = settings or Settings()
        self.enabled = (
            self.settings.config.enforce_https
            and self.settings.config.environment == "production"
        )

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        """Process request with HTTPS enforcement."""

        if not self.enabled:
            return await call_next(request)

        # Check if request is already HTTPS
        # Support both direct connections and proxy setups
        forwarded_proto = request.headers.get("X-Forwarded-Proto", "").lower()
        is_https = (
            request.url.scheme == "https"
            or forwarded_proto == "https"
            or request.headers.get("X-Forwarded-SSL") == "on"
        )

        if not is_https:
            # Redirect to HTTPS
            url = request.url.replace(scheme="https")
            return RedirectResponse(
                url=str(url),
                status_code=301,  # Permanent redirect
                headers={
                    "X-Content-Type-Options": "nosniff",
                }
            )

        # Process request
        response = await call_next(request)

        # Add HSTS header for HTTPS responses
        response.headers["Strict-Transport-Security"] = (
            f"max-age={self.HSTS_MAX_AGE}; "
            "includeSubDomains; "
            "preload"
        )

        return response


def add_security_headers(response: Response) -> Response:
    """
    Add comprehensive security headers to response.

    This is a standalone function that can be used independently
    or integrated into middleware.
    """
    # Prevent MIME-sniffing
    response.headers["X-Content-Type-Options"] = "nosniff"

    # Prevent clickjacking
    response.headers["X-Frame-Options"] = "DENY"

    # Enable XSS protection (legacy, but doesn't hurt)
    response.headers["X-XSS-Protection"] = "1; mode=block"

    # Referrer policy
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

    # Content Security Policy (restrictive default)
    # Note: This may need to be customized based on application needs
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' 'unsafe-eval'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data: https:; "
        "font-src 'self' data:; "
        "connect-src 'self' https:; "
        "frame-ancestors 'none'; "
        "base-uri 'self'; "
        "form-action 'self'"
    )

    # Permissions Policy (formerly Feature-Policy)
    response.headers["Permissions-Policy"] = (
        "geolocation=(), "
        "microphone=(), "
        "camera=(), "
        "payment=(), "
        "usb=(), "
        "magnetometer=(), "
        "gyroscope=(), "
        "accelerometer=()"
    )

    return response
