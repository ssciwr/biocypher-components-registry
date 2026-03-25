"""Health-check routes for the HTTP API."""

from fastapi import APIRouter

from src.api.schemas.common import HealthResponse
from src.api.settings import settings


router = APIRouter()


# ===========================================================
# Health Routes
# ===========================================================


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Check API health",
    description="Return a lightweight liveness response for the API process.",
)
def health_check() -> HealthResponse:
    """Return a lightweight API health-check response."""
    return HealthResponse(
        status="ok",
        service=settings.service_name,
    )
