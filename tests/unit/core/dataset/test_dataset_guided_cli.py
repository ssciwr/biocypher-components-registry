from __future__ import annotations

from pathlib import Path

from src.core.dataset.cli import _format_command_preview
from src.core.dataset.config import request_from_config
from src.core.dataset.request import GenerationRequest as DatasetGenerationRequest
from src.core.dataset.service import build_croissant_baker_command


def test_build_croissant_baker_command_includes_known_flags() -> None:
    request = DatasetGenerationRequest(
        input_path="/tmp/data",
        output_path="croissant.jsonld",
        validate=True,
        description="OmniPath dataset",
        citation="https://www.omnipathdb.org/",
        dataset_version="1.0.0",
        date_published="2016-11-01",
        creators=[
            "Denes Turei,denes@gmail.com",
            "Saezlab,saezlab@gmail.com,https://www.saezlab.org",
        ],
        extra_args=["--custom-flag", "value"],
    )

    command = build_croissant_baker_command(request)

    assert command == [
        "croissant-baker",
        "--input",
        "/tmp/data",
        "--output",
        "croissant.jsonld",
        "--validate",
        "--description",
        "OmniPath dataset",
        "--citation",
        "https://www.omnipathdb.org/",
        "--dataset-version",
        "1.0.0",
        "--date-published",
        "2016-11-01",
        "--creator",
        "Denes Turei,denes@gmail.com",
        "--creator",
        "Saezlab,saezlab@gmail.com,https://www.saezlab.org",
        "--custom-flag",
        "value",
    ]


def test_request_from_config_parses_nested_metadata(tmp_path: Path) -> None:
    config_path = tmp_path / "dataset.yaml"
    config_path.write_text(
        """
input: /data/omnipath
metadata:
  description: OmniPath dataset
  citation: https://www.omnipathdb.org/
  dataset_version: 1.0.0
  date_published: 2016-11-01
  creators:
    - name: Denes Turei
      email: denes@gmail.com
    - Saezlab,saezlab@gmail.com,https://www.saezlab.org
extra_args:
  - --verbose
""".strip(),
        encoding="utf-8",
    )

    request = request_from_config(str(config_path), output_override="out.jsonld")

    assert request == DatasetGenerationRequest(
        input_path="/data/omnipath",
        output_path="out.jsonld",
        validate=True,
        description="OmniPath dataset",
        citation="https://www.omnipathdb.org/",
        dataset_version="1.0.0",
        date_published="2016-11-01",
        creators=[
            "Denes Turei,denes@gmail.com",
            "Saezlab,saezlab@gmail.com,https://www.saezlab.org",
        ],
        extra_args=["--verbose"],
    )


def test_request_from_config_allows_validation_opt_out(tmp_path: Path) -> None:
    config_path = tmp_path / "dataset.yaml"
    config_path.write_text(
        """
input: /data/omnipath
validate: false
""".strip(),
        encoding="utf-8",
    )

    request = request_from_config(str(config_path))

    assert request.validate is False


def test_format_command_preview_uses_multiline_shell_layout() -> None:
    command = [
        "croissant-baker",
        "--input",
        "/tmp/data dir",
        "--output",
        "croissant.jsonld",
        "--validate",
    ]

    preview = _format_command_preview(command)

    assert preview == (
        "```bash\n"
        "croissant-baker \\\n"
        "--input '/tmp/data dir' \\\n"
        "--output croissant.jsonld \\\n"
        "--validate\n"
        "```"
    )
