"""Typed failures for the ephemeral dataset upload workflow."""

from __future__ import annotations


class UploadSessionError(RuntimeError):
    """A client-safe upload error carrying an HTTP-compatible status code."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int = 400,
        retry_after: int | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.retry_after = retry_after
