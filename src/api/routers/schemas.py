"""Serve the bundled registry schemas, independently of external schema IDs."""

from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from src.core.schema.profile import load_schema

router = APIRouter()


class SchemaResponse(JSONResponse):
    media_type = "application/schema+json"


@router.get("/schemas/{version}", response_class=SchemaResponse)
def get_validation_schema(version: str) -> dict[str, Any]:
    """Return the exact deployed schema for a registered profile version."""
    try:
        return load_schema(version)
    except ValueError as exc:
        raise HTTPException(404, "Unknown registry schema version.") from exc
