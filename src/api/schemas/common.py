"""Shared Pydantic request and response schemas for the HTTP API."""

from pydantic import BaseModel


# ===========================================================
# Output Models
# ===========================================================


class HealthResponse(BaseModel):
    """Health-check response returned by the API."""

    status: str
    service: str
