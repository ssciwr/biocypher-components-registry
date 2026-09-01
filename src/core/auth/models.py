"""Minimal GitHub authentication models."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class AuthSession:
    """Current authenticated GitHub session."""

    github_user_id: str
