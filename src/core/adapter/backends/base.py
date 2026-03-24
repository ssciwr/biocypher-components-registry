"""Abstract interfaces for adapter generation backends."""

from __future__ import annotations

from abc import ABC, abstractmethod

from src.core.adapter.request import AdapterGenerationRequest
from src.core.dataset.request import GenerationResult


class AdapterGenerator(ABC):
    """Defines the interface implemented by adapter generation backends."""

    name: str

    @abstractmethod
    def generate(self, request: AdapterGenerationRequest) -> GenerationResult:
        """Generate adapter metadata for one request."""
