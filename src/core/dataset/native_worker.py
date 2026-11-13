"""Private subprocess entry point for bounded native upload generation."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from src.core.dataset.backends.native import NativeDatasetBuilder
from src.core.dataset.request import GenerationRequest


def main() -> None:
    """Load a tmpfs request and execute the independent native backend."""
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--request", required=True)
    arguments = parser.parse_args()
    request_path = Path(arguments.request)
    payload = json.loads(request_path.read_text(encoding="utf-8"))
    request_path.unlink()
    result = NativeDatasetBuilder().generate(GenerationRequest(**payload))
    if result.stdout:
        print(result.stdout)
    if result.stderr:
        print(result.stderr, file=sys.stderr)


if __name__ == "__main__":  # pragma: no cover - exercised as a child process
    main()
