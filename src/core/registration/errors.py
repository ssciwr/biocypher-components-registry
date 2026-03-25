"""Registration-specific error types."""

from __future__ import annotations


class DuplicateRegistrationError(ValueError):
    """Raised when a registration would duplicate an existing valid adapter."""

