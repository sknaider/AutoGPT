"""
Enterprise Secrets Validation System

Validates that secrets are properly configured and not using default values,
especially in production environments.
"""

import logging
import secrets as secrets_module
from typing import Dict, List, Optional, Set

from pydantic import BaseModel

from backend.util.settings import Settings

logger = logging.getLogger(__name__)


class SecretRequirement(BaseModel):
    """Definition of a required secret."""

    name: str
    env_var: str
    required_in_production: bool = True
    required_in_development: bool = False
    min_length: int = 16
    forbidden_values: Set[str] = set()
    description: str = ""


class SecretsValidationError(Exception):
    """Raised when secret validation fails."""

    pass


class SecretsValidator:
    """
    Enterprise secrets validator.

    Features:
    - Validates required secrets are present
    - Checks secrets are not default values
    - Enforces minimum length requirements
    - Environment-specific validation
    - Detailed error reporting
    """

    # Known default/weak values that should never be used in production
    DEFAULT_VALUES = {
        "your-super-secret-and-long-postgres-password",
        "change-me",
        "default",
        "secret",
        "password",
        "admin",
        "test",
        "demo",
        "example",
        "sample",
    }

    # Required secrets for enterprise deployment
    REQUIRED_SECRETS = [
        SecretRequirement(
            name="JWT Signing Key",
            env_var="SUPABASE_JWT_SECRET",
            min_length=32,
            description="JWT token signing secret",
        ),
        SecretRequirement(
            name="Database Password",
            env_var="POSTGRES_PASSWORD",
            min_length=16,
            forbidden_values=DEFAULT_VALUES,
            description="PostgreSQL database password",
        ),
        SecretRequirement(
            name="Encryption Key",
            env_var="FERNET_KEY",
            min_length=32,
            description="Fernet encryption key for sensitive data",
        ),
        SecretRequirement(
            name="Supabase Service Role Key",
            env_var="SUPABASE_SERVICE_ROLE_KEY",
            required_in_production=True,
            required_in_development=False,
            description="Supabase admin service role key",
        ),
    ]

    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or Settings()
        self.errors: List[str] = []
        self.warnings: List[str] = []

    def validate_all(self, strict: bool = True) -> bool:
        """
        Validate all required secrets.

        Args:
            strict: If True, raise exception on validation failure

        Returns:
            True if all validations pass

        Raises:
            SecretsValidationError: If strict=True and validation fails
        """
        self.errors = []
        self.warnings = []

        is_production = self.settings.config.environment == "production"
        is_development = self.settings.config.environment in [
            "development",
            "staging",
        ]

        if not self.settings.config.validate_secrets_on_startup:
            logger.info("Secrets validation is disabled")
            return True

        # Validate each required secret
        for requirement in self.REQUIRED_SECRETS:
            # Check if secret is required for current environment
            if is_production and not requirement.required_in_production:
                continue
            if is_development and not requirement.required_in_development:
                continue

            self._validate_secret(requirement, is_production)

        # Log results
        if self.errors:
            for error in self.errors:
                logger.error(f"Secret validation error: {error}")

        if self.warnings:
            for warning in self.warnings:
                logger.warning(f"Secret validation warning: {warning}")

        # Raise exception if strict mode
        if strict and self.errors:
            raise SecretsValidationError(
                f"Secrets validation failed with {len(self.errors)} error(s):\n"
                + "\n".join(f"  - {err}" for err in self.errors)
            )

        return len(self.errors) == 0

    def _validate_secret(
        self, requirement: SecretRequirement, is_production: bool
    ) -> None:
        """Validate a single secret."""
        import os

        secret_value = os.getenv(requirement.env_var)

        # Check if secret exists
        if not secret_value:
            if is_production and requirement.required_in_production:
                self.errors.append(
                    f"{requirement.name} ({requirement.env_var}) is required in production but not set"
                )
            else:
                self.warnings.append(
                    f"{requirement.name} ({requirement.env_var}) is not set"
                )
            return

        # Check minimum length
        if len(secret_value) < requirement.min_length:
            self.errors.append(
                f"{requirement.name} ({requirement.env_var}) must be at least {requirement.min_length} characters "
                f"(current: {len(secret_value)} characters)"
            )

        # Check for default values
        if self.settings.config.require_strong_secrets:
            # Check against forbidden values
            forbidden = requirement.forbidden_values or self.DEFAULT_VALUES
            if secret_value.lower() in {v.lower() for v in forbidden}:
                error_msg = (
                    f"{requirement.name} ({requirement.env_var}) is using a default/weak value. "
                    f"This is not allowed in production."
                )
                if is_production:
                    self.errors.append(error_msg)
                else:
                    self.warnings.append(error_msg)

            # Check for common patterns that suggest default values
            weak_patterns = ["default", "example", "change", "test", "demo"]
            if any(
                pattern in secret_value.lower() for pattern in weak_patterns
            ):
                warning = (
                    f"{requirement.name} ({requirement.env_var}) may be using a default value. "
                    f"Please ensure you have changed this to a secure value."
                )
                if is_production:
                    self.errors.append(warning)
                else:
                    self.warnings.append(warning)

    def generate_secure_secret(self, length: int = 32) -> str:
        """
        Generate a cryptographically secure random secret.

        Args:
            length: Length of the secret in bytes

        Returns:
            URL-safe base64-encoded secret
        """
        return secrets_module.token_urlsafe(length)

    def get_validation_report(self) -> Dict[str, any]:
        """Get detailed validation report."""
        return {
            "passed": len(self.errors) == 0,
            "errors_count": len(self.errors),
            "warnings_count": len(self.warnings),
            "errors": self.errors,
            "warnings": self.warnings,
            "environment": self.settings.config.environment,
            "validation_enabled": self.settings.config.validate_secrets_on_startup,
        }


def validate_secrets_on_startup(settings: Optional[Settings] = None) -> None:
    """
    Validate secrets on application startup.

    This should be called early in the application lifecycle,
    before any services are initialized.

    Raises:
        SecretsValidationError: If validation fails in strict mode
    """
    validator = SecretsValidator(settings)

    try:
        is_valid = validator.validate_all(strict=True)

        if is_valid:
            logger.info("✅ All secrets validation checks passed")
        else:
            logger.warning("⚠️ Secrets validation completed with warnings")

    except SecretsValidationError as e:
        logger.critical(f"❌ Secrets validation failed: {e}")
        raise


def print_secret_generation_help() -> None:
    """Print help for generating secure secrets."""
    validator = SecretsValidator()

    print("\n" + "=" * 70)
    print("🔐 ENTERPRISE SECRETS GENERATION GUIDE")
    print("=" * 70)

    print("\nGenerate secure secrets using these commands:\n")

    for requirement in SecretsValidator.REQUIRED_SECRETS:
        secret = validator.generate_secure_secret(requirement.min_length)
        print(f"# {requirement.description}")
        print(f"export {requirement.env_var}=\"{secret}\"")
        print()

    print("=" * 70)
    print("\nOr use Python to generate secrets:")
    print("```python")
    print("import secrets")
    print('secret = secrets.token_urlsafe(32)')
    print("```")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    # CLI tool for generating secrets
    print_secret_generation_help()
