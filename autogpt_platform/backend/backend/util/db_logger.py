"""
Database Query Logging and Performance Monitoring

Tracks database queries, detects slow queries, and provides performance insights.
"""

import logging
import time
from contextlib import asynccontextmanager, contextmanager
from typing import Any, Dict, Optional

from backend.monitoring.instrumentation import record_database_query
from backend.util.settings import Settings

logger = logging.getLogger(__name__)


class QueryLogger:
    """
    Database query logger with performance tracking.

    Features:
    - Logs slow queries automatically
    - Records query duration metrics
    - Captures query context and parameters
    - Integrates with Prometheus
    """

    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or Settings()
        # Threshold for slow queries (in seconds)
        self.slow_query_threshold = 1.0  # 1 second
        # Threshold for very slow queries (in seconds)
        self.very_slow_query_threshold = 5.0  # 5 seconds
        # Enable query logging
        self.enable_query_logging = True
        # Enable parameter logging (may contain sensitive data)
        self.log_query_parameters = False

    @contextmanager
    def log_query(
        self,
        operation: str,
        table: Optional[str] = None,
        description: Optional[str] = None,
        parameters: Optional[Dict[str, Any]] = None,
    ):
        """
        Context manager for logging synchronous database queries.

        Usage:
            with query_logger.log_query("SELECT", "users", "Get user by ID", {"id": user_id}):
                result = db.query(...)

        Args:
            operation: SQL operation (SELECT, INSERT, UPDATE, DELETE, etc.)
            table: Database table name
            description: Human-readable description of the query
            parameters: Query parameters (optional, may contain sensitive data)
        """
        start_time = time.time()
        error: Optional[Exception] = None

        try:
            yield
        except Exception as e:
            error = e
            raise
        finally:
            duration = time.time() - start_time
            self._record_query(
                operation=operation,
                table=table or "unknown",
                description=description,
                duration=duration,
                parameters=parameters,
                error=error,
            )

    @asynccontextmanager
    async def log_query_async(
        self,
        operation: str,
        table: Optional[str] = None,
        description: Optional[str] = None,
        parameters: Optional[Dict[str, Any]] = None,
    ):
        """
        Async context manager for logging database queries.

        Usage:
            async with query_logger.log_query_async("SELECT", "users"):
                result = await db.query_async(...)

        Args:
            operation: SQL operation type
            table: Database table name
            description: Query description
            parameters: Query parameters
        """
        start_time = time.time()
        error: Optional[Exception] = None

        try:
            yield
        except Exception as e:
            error = e
            raise
        finally:
            duration = time.time() - start_time
            self._record_query(
                operation=operation,
                table=table or "unknown",
                description=description,
                duration=duration,
                parameters=parameters,
                error=error,
            )

    def _record_query(
        self,
        operation: str,
        table: str,
        description: Optional[str],
        duration: float,
        parameters: Optional[Dict[str, Any]],
        error: Optional[Exception],
    ) -> None:
        """Record query metrics and log if necessary."""
        # Record Prometheus metric
        try:
            record_database_query(operation, table, duration)
        except Exception as e:
            logger.warning(f"Failed to record database query metric: {e}")

        # Determine if we should log this query
        should_log = False
        log_level = logging.INFO

        if error:
            should_log = True
            log_level = logging.ERROR
        elif duration >= self.very_slow_query_threshold:
            should_log = True
            log_level = logging.WARNING
        elif duration >= self.slow_query_threshold:
            should_log = True
            log_level = logging.INFO
        elif self.enable_query_logging and operation not in ["SELECT"]:
            # Always log write operations
            should_log = True
            log_level = logging.INFO

        if should_log:
            self._log_query_details(
                operation=operation,
                table=table,
                description=description,
                duration=duration,
                parameters=parameters,
                error=error,
                level=log_level,
            )

    def _log_query_details(
        self,
        operation: str,
        table: str,
        description: Optional[str],
        duration: float,
        parameters: Optional[Dict[str, Any]],
        error: Optional[Exception],
        level: int,
    ) -> None:
        """Log query details at specified level."""
        duration_ms = duration * 1000

        log_data = {
            "query_operation": operation,
            "query_table": table,
            "query_duration_ms": round(duration_ms, 2),
        }

        if description:
            log_data["query_description"] = description

        if error:
            log_data["query_error"] = str(error)
            log_data["query_error_type"] = type(error).__name__

        if self.log_query_parameters and parameters:
            # Sanitize parameters to avoid logging sensitive data
            log_data["query_parameters"] = self._sanitize_parameters(parameters)

        # Build log message
        msg_parts = [f"{operation} on {table}"]
        if description:
            msg_parts.append(f"({description})")
        msg_parts.append(f"took {duration_ms:.2f}ms")

        if error:
            msg_parts.append(f"and failed with {type(error).__name__}")

        message = " ".join(msg_parts)

        # Log with structured data
        logger.log(level, message, extra=log_data)

    def _sanitize_parameters(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Sanitize query parameters to avoid logging sensitive data."""
        sensitive_keys = {
            "password",
            "token",
            "secret",
            "api_key",
            "apiKey",
            "auth",
            "credential",
        }

        sanitized = {}
        for key, value in parameters.items():
            if any(sensitive in key.lower() for sensitive in sensitive_keys):
                sanitized[key] = "***REDACTED***"
            elif isinstance(value, str) and len(value) > 100:
                # Truncate very long strings
                sanitized[key] = value[:100] + "..."
            else:
                sanitized[key] = value

        return sanitized


# Global query logger instance
_query_logger: Optional[QueryLogger] = None


def get_query_logger() -> QueryLogger:
    """Get global query logger instance."""
    global _query_logger
    if _query_logger is None:
        _query_logger = QueryLogger()
    return _query_logger


# Convenience decorators
def log_db_query(operation: str, table: str, description: Optional[str] = None):
    """
    Decorator for logging database query methods.

    Usage:
        @log_db_query("SELECT", "users", "Get user by ID")
        def get_user(user_id: str):
            return db.query(...)
    """

    def decorator(func):
        if asyncio.iscoroutinefunction(func):

            async def async_wrapper(*args, **kwargs):
                query_logger = get_query_logger()
                async with query_logger.log_query_async(operation, table, description):
                    return await func(*args, **kwargs)

            return async_wrapper
        else:

            def sync_wrapper(*args, **kwargs):
                query_logger = get_query_logger()
                with query_logger.log_query(operation, table, description):
                    return func(*args, **kwargs)

            return sync_wrapper

    return decorator


# Import asyncio for coroutine check
import asyncio
