"""FastAPI application entry point."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.routers import (
    adapters,
    auth,
    health,
    metadata,
    registrations,
    registry,
    workspace,
)
from src.api.settings import settings
from src.core.workspace.service import SessionManager


# ===========================================================
# Application Factory
# ===========================================================


def create_app(workspace_manager: SessionManager | None = None) -> FastAPI:
    """Create and configure the FastAPI application.

    ``workspace_manager`` is an injection seam for tests; production always
    builds a fresh manager in the lifespan below, scoped to the app's
    lifetime the way the standalone agentic-workspace service did.
    """

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.workspace_manager = workspace_manager or SessionManager()
        yield
        await app.state.workspace_manager.shutdown()

    app = FastAPI(
        title=settings.app_title,
        version=settings.app_version,
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_origins),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(
        auth.router,
        prefix=settings.api_v1_prefix,
        tags=["auth"],
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
    app.include_router(
        workspace.router,
        prefix=settings.agent_api_prefix,
        tags=["workspace"],
    )

    return app


# ===========================================================
# ASGI Application
# ===========================================================


app = create_app()
