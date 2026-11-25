"""In-memory validation reporting; it never changes acceptance or persistence."""

import logging
from collections.abc import Callable
from dataclasses import replace
from functools import cache
from importlib.metadata import version

from src.core.validation.results import ValidationCheckReport

CheckObserver = Callable[[ValidationCheckReport], None]
logger = logging.getLogger(__name__)


class ValidationProgress:
    """Collect ordered check snapshots and optionally publish each transition."""

    def __init__(
        self,
        observer: CheckObserver | None = None,
        *,
        include_file: bool = False,
        include_datasets: bool = False,
    ) -> None:
        checks = []
        if include_file:
            checks.append(
                ValidationCheckReport("file", "File retrieval and JSON parsing")
            )
        checks.extend(
            [
                ValidationCheckReport("croissant", "Croissant compliance"),
                ValidationCheckReport("schema", "Adapter schema"),
                ValidationCheckReport(
                    "semantics",
                    "Adapter semantics",
                    description="Checks duplicate node identifiers and broken fileObject references.",
                ),
            ]
        )
        if include_datasets:
            checks.append(ValidationCheckReport("datasets", "Embedded datasets"))
        self._checks = {check.id: check for check in checks}
        self.observer = observer

    @property
    def reports(self) -> list[ValidationCheckReport]:
        return list(self._checks.values())

    def put(self, check: ValidationCheckReport) -> None:
        self._checks[check.id] = check
        if self.observer:
            try:
                self.observer(check)
            except Exception:
                # Reporting is best effort and must never change acceptance.
                logger.exception(
                    "Could not publish validation progress for %s", check.id
                )

    def update(self, check_id: str, **changes) -> None:
        self.put(replace(self._checks[check_id], **changes))

    def stop_unfinished(self, reason: str) -> None:
        for check in self.reports:
            if check.status in {"PENDING", "RUNNING"}:
                self.put(replace(check, status="NOT_RUN", reason=reason))


@cache
def croissant_validator_info() -> dict[str, str]:
    """Report the implementation version, never an inferred specification version."""
    return {
        "validator_name": "mlcroissant",
        "validator_version": version("mlcroissant"),
    }
