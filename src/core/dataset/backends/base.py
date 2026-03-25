"""Abstract interfaces for dataset generation backends."""

from __future__ import annotations

from abc import ABC, abstractmethod

from src.core.dataset.request import GenerationRequest, GenerationResult


class DatasetGenerator(ABC):
    """Defines the interface implemented by dataset generation backends."""

    name: str

    @abstractmethod
    def generate(self, request: GenerationRequest) -> GenerationResult:
        """Generate dataset metadata for one request."""
