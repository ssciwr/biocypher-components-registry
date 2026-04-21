"""HTTP error mapping helpers for the FastAPI application."""

from __future__ import annotations

from fastapi import HTTPException, status

from src.core.registration.errors import DuplicateRegistrationError
from src.core.shared.errors import InvalidRepoURLError


# ===========================================================
# Error Mapping
# ===========================================================


def registration_submission_http_error(exc: Exception) -> HTTPException:
    """Map expected registration submission errors to HTTP responses."""
    if isinstance(exc, (FileNotFoundError, InvalidRepoURLError, ValueError)):
        return HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )

    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Unexpected registration submission error.",
    )


def registration_not_found_http_error(registration_id: str) -> HTTPException:
    """Return a 404 response for an unknown registration identifier."""
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Registration not found: {registration_id}",
    )


def registration_processing_http_error(
    registration_id: str,
    exc: Exception,
) -> HTTPException:
    """Map expected registration processing errors to HTTP responses."""
    not_found_message = f"Registration not found: {registration_id}"
    if isinstance(exc, ValueError) and str(exc) == not_found_message:
        return registration_not_found_http_error(registration_id)

    if isinstance(exc, DuplicateRegistrationError):
        return HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        )

    if isinstance(exc, (FileNotFoundError, ValueError)):
        return HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )

    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Unexpected registration processing error.",
    )


def registry_entry_not_found_http_error(entry_id: str) -> HTTPException:
    """Return a 404 response for an unknown canonical registry entry."""
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Registry entry not found: {entry_id}",
    )


def registry_refresh_not_found_http_error() -> HTTPException:
    """Return a 404 response when no registry refresh has been recorded."""
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="No registry refresh has been recorded.",
    )


def adapter_not_found_http_error(adapter_id: str) -> HTTPException:
    """Return a 404 response for an unknown public adapter identifier."""
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Adapter not found: {adapter_id}",
    )


def adapter_version_not_found_http_error(
    adapter_id: str,
    version: str,
) -> HTTPException:
    """Return a 404 response for an unknown public adapter version."""
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Adapter version not found: {adapter_id} {version}",
    )
