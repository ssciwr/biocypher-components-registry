"""FastAPI application entry point."""

from fastapi import FastAPI

from src.api.routers import adapters, health, metadata, registrations, registry
from src.api.settings import settings


# ===========================================================
# Application Factory
# ===========================================================


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title=settings.app_title,
        version=settings.app_version,
    )

    app.include_router(
        health.router,
        prefix=settings.api_v1_prefix,
        tags=["health"],
    )
    app.include_router(
        adapters.router,
        prefix=settings.api_v1_prefix,
        tags=["adapters"],
    )
    app.include_router(
        metadata.router,
        prefix=settings.api_v1_prefix,
        tags=["metadata"],
    )
    app.include_router(
        registrations.router,
        prefix=settings.api_v1_prefix,
        tags=["registrations"],
    )
    app.include_router(
        registry.router,
        prefix=settings.api_v1_prefix,
        tags=["registry"],
    )

    return app


# ===========================================================
# ASGI Application
# ===========================================================


app = create_app()
