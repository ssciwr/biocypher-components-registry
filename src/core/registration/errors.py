"""Registration-specific error types."""

from __future__ import annotations

DUPLICATE_REPOSITORY_URL_MESSAGE = "This repository url already exists in the system"


class DuplicateRegistrationError(ValueError):
    """Raised when a registration would duplicate an existing adapter/source."""
