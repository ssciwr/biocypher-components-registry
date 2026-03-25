from __future__ import annotations

from subprocess import CompletedProcess

import typer
from typer.testing import CliRunner

from src.core.dataset import cli as dataset_cli
from src.core.dataset.request import GenerationRequest as DatasetGenerationRequest


runner = CliRunner()


def test_direct_command_wraps_known_and_passthrough_args(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_execute_request(
        request: DatasetGenerationRequest,
        generator: str,
        executable: str = "croissant-baker",
    ) -> CompletedProcess[str]:
        captured["request"] = request
        captured["generator"] = generator
        captured["executable"] = executable
        return CompletedProcess(args=[], returncode=0, stdout="ok", stderr="")

    monkeypatch.setattr(dataset_cli, "execute_request", fake_execute_request)

    result = runner.invoke(
        dataset_cli.app,
        [
            "direct",
            "--generator",
            "croissant-baker",
            "--input",
            "/tmp/data",
            "--output",
            "croissant.jsonld",
            "--validate",
            "--description",
            "OmniPath dataset",
            "--creator",
            "Denes Turei,denes@gmail.com",
            "--",
            "--custom-flag",
            "value",
        ],
    )

    assert result.exit_code == 0, result.output
    assert captured["generator"] == "croissant-baker"
    assert captured["request"] == DatasetGenerationRequest(
        input_path="/tmp/data",
        output_path="croissant.jsonld",
        validate=True,
        description="OmniPath dataset",
        creators=["Denes Turei,denes@gmail.com"],
        extra_args=["--custom-flag", "value"],
    )


def test_direct_command_accepts_auto_generator(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_execute_request(
        request: DatasetGenerationRequest,
        generator: str,
        executable: str = "croissant-baker",
    ) -> CompletedProcess[str]:
        captured["generator"] = generator
        return CompletedProcess(args=[], returncode=0, stdout="ok", stderr="")

    monkeypatch.setattr(dataset_cli, "execute_request", fake_execute_request)

    result = runner.invoke(
        dataset_cli.app,
        [
            "direct",
            "--generator",
            "auto",
            "--input",
            "/tmp/data",
        ],
    )

    assert result.exit_code == 0, result.output
    assert captured["generator"] == "auto"


def test_direct_command_validates_by_default(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_execute_request(
        request: DatasetGenerationRequest,
        generator: str,
        executable: str = "croissant-baker",
    ) -> CompletedProcess[str]:
        captured["request"] = request
        return CompletedProcess(args=[], returncode=0, stdout="ok", stderr="")

    monkeypatch.setattr(dataset_cli, "execute_request", fake_execute_request)

    result = runner.invoke(
        dataset_cli.app,
        [
            "direct",
            "--input",
            "/tmp/data",
        ],
    )

    assert result.exit_code == 0, result.output
    assert captured["request"].validate is True


def test_guided_retries_after_backend_failure(monkeypatch) -> None:
    request = DatasetGenerationRequest(
        input_path="/tmp/data",
        output_path="croissant.jsonld",
        description="initial",
    )
    calls = {"count": 0}

    def fake_execute_request(
        request: DatasetGenerationRequest,
        generator: str,
        executable: str = "croissant-baker",
    ) -> CompletedProcess[str]:
        calls["count"] += 1
        if calls["count"] == 1:
            raise RuntimeError("backend failed")
        return CompletedProcess(args=[], returncode=0, stdout="ok", stderr="")

    def fake_review_request(current_request: DatasetGenerationRequest) -> None:
        current_request.description = "fixed"

    monkeypatch.setattr(dataset_cli, "execute_request", fake_execute_request)
    monkeypatch.setattr(
        "src.core.dataset.cli.review_request",
        fake_review_request,
    )
    monkeypatch.setattr(typer, "confirm", lambda message, default=True: True)

    dataset_cli._run_request_with_recovery(request=request, generator="croissant-baker")

    assert calls["count"] == 2
    assert request.description == "fixed"
