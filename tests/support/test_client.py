from __future__ import annotations

import warnings

with warnings.catch_warnings():
    warnings.filterwarnings(
        "ignore",
        message=(
            "Using `httpx` with `starlette.testclient` is deprecated; "
            "install `httpx2` instead."
        ),
    )
    from fastapi.testclient import TestClient

__all__ = ["TestClient"]
