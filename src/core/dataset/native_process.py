"""Bounded process adapter for native generation in the web upload flow."""

from __future__ import annotations

import json
import os
import secrets
import sys
from dataclasses import asdict
from pathlib import Path

from src.core.dataset.process import run_bounded_process
from src.core.dataset.request import GenerationRequest, GenerationResult
from src.core.shared.errors import GeneratorError


def generate_native_in_bounded_process(request: GenerationRequest) -> GenerationResult:
    """Run native generation under the same limits used for Baker."""
    scratch = Path(request.output_path).parent
    request_path = scratch / f".native-request-{secrets.token_hex(6)}.json"
    request_path.write_text(
        json.dumps(asdict(request), ensure_ascii=False), encoding="utf-8"
    )
    os.chmod(request_path, 0o600)
    try:
        result = run_bounded_process(
            [
                sys.executable,
                "-m",
                "src.core.dataset.native_worker",
                "--request",
                str(request_path),
            ],
            scratch_directory=scratch,
        )
    finally:
        request_path.unlink(missing_ok=True)
    if result.timed_out:
        raise GeneratorError("Native generation exceeded the generation time limit.")
    if result.returncode != 0:
        raise GeneratorError("Native dataset generation failed.")
    try:
        document = json.loads(Path(request.output_path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise GeneratorError(
            "Native generation did not produce valid JSON-LD."
        ) from exc
    return GenerationResult(
        output_path=request.output_path,
        stdout=result.stdout,
        stderr=result.stderr,
        document=document,
    )
