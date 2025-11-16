from typing import Mapping


class MissingConfigError(Exception):
    """The attempted operation requires configuration which is not available"""


class NotFoundError(ValueError):
    """The requested record was not found, resulting in an error condition"""


class NeedConfirmation(Exception):
    """The user must explicitly confirm that they want to proceed"""


class NotAuthorizedError(ValueError):
    """The user is not authorized to perform the requested operation"""


class GraphNotAccessibleError(NotAuthorizedError):
    """Raised when attempting to execute a graph that is not accessible to the user."""


class GraphNotInLibraryError(GraphNotAccessibleError):
    """Raised when attempting to execute a graph that is not / no longer in the user's library."""


class InsufficientBalanceError(ValueError):
    user_id: str
    message: str
    balance: float
    amount: float

    def __init__(self, message: str, user_id: str, balance: float, amount: float):
        super().__init__(message)
        self.args = (message, user_id, balance, amount)
        self.message = message
        self.user_id = user_id
        self.balance = balance
        self.amount = amount

    def __str__(self):
        """Used to display the error message in the frontend, because we str() the error when sending the execution update"""
        return self.message


class ModerationError(ValueError):
    """Content moderation failure during execution"""

    user_id: str
    message: str
    graph_exec_id: str
    moderation_type: str
    content_id: str | None

    def __init__(
        self,
        message: str,
        user_id: str,
        graph_exec_id: str,
        moderation_type: str = "content",
        content_id: str | None = None,
    ):
        super().__init__(message)
        self.args = (message, user_id, graph_exec_id, moderation_type, content_id)
        self.message = message
        self.user_id = user_id
        self.graph_exec_id = graph_exec_id
        self.moderation_type = moderation_type
        self.content_id = content_id

    def __str__(self):
        """Used to display the error message in the frontend, because we str() the error when sending the execution update"""
        if self.content_id:
            return f"{self.message} (Moderation ID: {self.content_id})"
        return self.message


class GraphValidationError(ValueError):
    """Structured validation error for graph validation failures"""

    def __init__(
        self, message: str, node_errors: Mapping[str, Mapping[str, str]] | None = None
    ):
        super().__init__(message)
        self.message = message
        self.node_errors = node_errors or {}

    def __str__(self):
        return self.message + "".join(
            [
                f"\n  {node_id}:"
                + "".join([f"\n    {k}: {e}" for k, e in errors.items()])
                for node_id, errors in self.node_errors.items()
            ]
        )


class DatabaseError(Exception):
    """Raised when there is an error interacting with the database"""

    pass


class RedisError(Exception):
    """Raised when there is an error interacting with Redis"""

    pass


# ============================================================================
# ENTERPRISE EXCEPTION HIERARCHY
# ============================================================================
# Comprehensive exception hierarchy for better error handling and debugging
# ============================================================================


class AutoGPTException(Exception):
    """Base exception for all AutoGPT custom exceptions.

    Provides structured error handling with:
    - Error codes for programmatic handling
    - User-friendly messages
    - Debug details for logging
    - HTTP status code mapping
    """

    error_code: str = "AUTOGPT_ERROR"
    http_status: int = 500
    user_message: str = "An error occurred"

    def __init__(
        self,
        message: str | None = None,
        error_code: str | None = None,
        debug_details: dict | None = None,
    ):
        """
        Initialize AutoGPT exception.

        Args:
            message: Human-readable error message
            error_code: Machine-readable error code
            debug_details: Additional context for debugging
        """
        self.message = message or self.user_message
        if error_code:
            self.error_code = error_code
        self.debug_details = debug_details or {}
        super().__init__(self.message)

    def to_dict(self) -> dict:
        """Convert exception to dictionary for API responses."""
        return {
            "error": self.error_code,
            "message": self.message,
            "http_status": self.http_status,
            "details": self.debug_details,
        }


# ============================================================================
# VALIDATION ERRORS (400-level)
# ============================================================================


class ValidationError(AutoGPTException):
    """Base class for validation errors."""

    error_code = "VALIDATION_ERROR"
    http_status = 400


class InvalidInputError(ValidationError):
    """Raised when user input is invalid."""

    error_code = "INVALID_INPUT"
    user_message = "The provided input is invalid"


class SchemaValidationError(ValidationError):
    """Raised when data doesn't match expected schema."""

    error_code = "SCHEMA_VALIDATION_FAILED"
    user_message = "Data validation failed"


class RateLimitExceededError(AutoGPTException):
    """Raised when rate limit is exceeded."""

    error_code = "RATE_LIMIT_EXCEEDED"
    http_status = 429
    user_message = "Rate limit exceeded. Please try again later"


# ============================================================================
# AUTHENTICATION & AUTHORIZATION ERRORS (401, 403)
# ============================================================================


class AuthenticationError(AutoGPTException):
    """Base class for authentication errors."""

    error_code = "AUTHENTICATION_FAILED"
    http_status = 401
    user_message = "Authentication required"


class InvalidTokenError(AuthenticationError):
    """Raised when JWT token is invalid."""

    error_code = "INVALID_TOKEN"
    user_message = "Invalid or expired authentication token"


class AuthorizationError(AutoGPTException):
    """Base class for authorization errors."""

    error_code = "AUTHORIZATION_FAILED"
    http_status = 403
    user_message = "You don't have permission to perform this action"


class InsufficientPermissionsError(AuthorizationError):
    """Raised when user lacks required permissions."""

    error_code = "INSUFFICIENT_PERMISSIONS"
    user_message = "Insufficient permissions"


# ============================================================================
# RESOURCE ERRORS (404, 409)
# ============================================================================


class ResourceNotFoundError(AutoGPTException):
    """Base class for resource not found errors."""

    error_code = "RESOURCE_NOT_FOUND"
    http_status = 404
    user_message = "The requested resource was not found"


class AgentNotFoundError(ResourceNotFoundError):
    """Raised when agent is not found."""

    error_code = "AGENT_NOT_FOUND"
    user_message = "Agent not found"


class GraphNotFoundError(ResourceNotFoundError):
    """Raised when graph is not found."""

    error_code = "GRAPH_NOT_FOUND"
    user_message = "Graph not found"


class UserNotFoundError(ResourceNotFoundError):
    """Raised when user is not found."""

    error_code = "USER_NOT_FOUND"
    user_message = "User not found"


class ResourceConflictError(AutoGPTException):
    """Raised when there's a conflict with existing resource."""

    error_code = "RESOURCE_CONFLICT"
    http_status = 409
    user_message = "Resource already exists or conflicts with existing data"


class DuplicateResourceError(ResourceConflictError):
    """Raised when attempting to create duplicate resource."""

    error_code = "DUPLICATE_RESOURCE"
    user_message = "A resource with this identifier already exists"


# ============================================================================
# BUSINESS LOGIC ERRORS (422)
# ============================================================================


class BusinessLogicError(AutoGPTException):
    """Base class for business logic errors."""

    error_code = "BUSINESS_LOGIC_ERROR"
    http_status = 422
    user_message = "Business rule violation"


class ExecutionError(BusinessLogicError):
    """Raised when graph/node execution fails."""

    error_code = "EXECUTION_FAILED"
    user_message = "Execution failed"


class CreditsError(BusinessLogicError):
    """Raised when there's a credits-related error."""

    error_code = "CREDITS_ERROR"
    user_message = "Credits operation failed"


# ============================================================================
# EXTERNAL SERVICE ERRORS (502, 503, 504)
# ============================================================================


class ExternalServiceError(AutoGPTException):
    """Base class for external service errors."""

    error_code = "EXTERNAL_SERVICE_ERROR"
    http_status = 502
    user_message = "External service error"


class LLMProviderError(ExternalServiceError):
    """Raised when LLM provider fails."""

    error_code = "LLM_PROVIDER_ERROR"
    user_message = "AI service temporarily unavailable"


class IntegrationError(ExternalServiceError):
    """Raised when third-party integration fails."""

    error_code = "INTEGRATION_ERROR"
    user_message = "Third-party service error"


class ServiceUnavailableError(AutoGPTException):
    """Raised when service is temporarily unavailable."""

    error_code = "SERVICE_UNAVAILABLE"
    http_status = 503
    user_message = "Service temporarily unavailable"


class TimeoutError(AutoGPTException):
    """Raised when operation times out."""

    error_code = "OPERATION_TIMEOUT"
    http_status = 504
    user_message = "Operation timed out"


# ============================================================================
# INTERNAL SERVER ERRORS (500)
# ============================================================================


class InternalServerError(AutoGPTException):
    """Base class for internal server errors."""

    error_code = "INTERNAL_SERVER_ERROR"
    http_status = 500
    user_message = "An internal error occurred"


class ConfigurationError(InternalServerError):
    """Raised when system configuration is invalid."""

    error_code = "CONFIGURATION_ERROR"
    user_message = "System configuration error"


class DataConsistencyError(InternalServerError):
    """Raised when data is in inconsistent state."""

    error_code = "DATA_CONSISTENCY_ERROR"
    user_message = "Data consistency error detected"


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================


def handle_exception(exc: Exception) -> AutoGPTException:
    """
    Convert any exception to AutoGPTException for consistent handling.

    Args:
        exc: The exception to handle

    Returns:
        AutoGPTException or subclass
    """
    if isinstance(exc, AutoGPTException):
        return exc

    # Map common exceptions to AutoGPT exceptions
    exception_mapping = {
        ValueError: InvalidInputError,
        KeyError: ResourceNotFoundError,
        PermissionError: InsufficientPermissionsError,
        ConnectionError: ServiceUnavailableError,
    }

    for exc_type, autogpt_exc_type in exception_mapping.items():
        if isinstance(exc, exc_type):
            return autogpt_exc_type(
                message=str(exc), debug_details={"original_type": type(exc).__name__}
            )

    # Default to internal server error
    return InternalServerError(
        message=str(exc), debug_details={"original_type": type(exc).__name__}
    )
