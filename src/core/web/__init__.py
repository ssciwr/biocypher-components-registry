"""Exports for the lightweight web metadata generation interface."""

from __future__ import annotations

from src.core.web.forms import build_normalized_adapter_input_from_web_form
from src.core.web.pages import render_form, render_start_page
from src.core.web.server import run_server

__all__ = [
    "build_normalized_adapter_input_from_web_form",
    "render_form",
    "render_start_page",
    "run_server",
]
