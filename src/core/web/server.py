"""Minimal HTTP server for the metadata generation web interface."""

from __future__ import annotations

from email.parser import BytesParser
from email.policy import default
import html
import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

import yaml
from croissant_baker.handlers.utils import compute_file_hash

from src.core.adapter.config import build_adapter_request_from_mapping
from src.core.adapter.request import AdapterGenerationRequest
from src.core.adapter.service import execute_request as execute_adapter_request
from src.core.dataset.inference import infer_fields_from_file
from src.core.registration.models import (
    RegistrationEvent,
    RegistryEntry,
    StoredRegistration,
)
from src.core.registration.store import RegistrationStore
from src.core.registration.service import (
    finish_registration,
    refresh_active_registrations,
    revalidate_registration,
    submit_registration,
)
from src.core.shared.constants import METADATA_FILENAME
from src.core.settings import settings as core_settings
from src.persistence.factory import build_registration_store
from src.core.web.forms import (
    build_normalized_adapter_input_from_web_form,
)
from src.core.web.pages import (
    render_form as shell_render_form,
)
from src.core.web.pages import (
    render_start_page as shell_render_start_page,
)
from src.core.shared.ids import slugify_identifier


_ADAPTER_GENERATOR = "native"
_STORAGE_KEY = "biocypher_form_state_new"

_ADVANCED_SCRIPT = f"""
<script>
  (function() {{
    const key = '{_STORAGE_KEY}';
    const fieldDefaults = {{
      dataset_generator: 'croissant-baker',
      validate: 'true',
      output: 'croissant_adapter.jsonld',
      adapter_id: '',
    }};

    function readState() {{
      try {{
        const raw = localStorage.getItem(key);
        if (!raw) return {{}};
        return JSON.parse(raw) || {{}};
      }} catch (error) {{
        localStorage.removeItem(key);
        return {{}};
      }}
    }}

    function writeState(patch) {{
      const current = readState();
      localStorage.setItem(key, JSON.stringify({{ ...current, ...patch }}));
    }}

    function byId(id) {{
      return document.getElementById(id);
    }}

    function applyAdvancedState() {{
      const state = readState();
      Object.entries(fieldDefaults).forEach(([id, fallback]) => {{
        const node = byId(id);
        if (!node) return;
        const value = state[id];
        node.value = value === undefined || value === null || value === '' ? fallback : String(value);
      }});
    }}

    function persistAdvancedState() {{
      writeState({{
        dataset_generator: byId('dataset_generator')?.value || fieldDefaults.dataset_generator,
        validate: byId('validate')?.value || fieldDefaults.validate,
        output: byId('output')?.value || fieldDefaults.output,
        adapter_id: byId('adapter_id')?.value || fieldDefaults.adapter_id,
      }});
    }}

    const originalSaveState = window.saveState;
    if (typeof originalSaveState === 'function') {{
      window.saveState = function patchedSaveState() {{
        originalSaveState();
        persistAdvancedState();
      }};
    }}

    const originalClearState = window.clearState;
    if (typeof originalClearState === 'function') {{
      window.clearState = function patchedClearState() {{
        originalClearState();
        applyAdvancedState();
        persistAdvancedState();
      }};
    }}

    applyAdvancedState();
    ['dataset_generator', 'validate', 'output', 'adapter_id'].forEach(id => {{
      const node = byId(id);
      if (!node) return;
      node.addEventListener('input', persistAdvancedState);
      node.addEventListener('change', persistAdvancedState);
    }});
    persistAdvancedState();
  }})();
</script>
"""


def _render_form(message: str = "", preload_state: dict[str, Any] | None = None) -> str:
    """Render the form page with server-specific client-side enhancements."""
    content = shell_render_form(message=message, preload_state=preload_state)
    content = content.replace("biocypher_form_state", _STORAGE_KEY)
    if "{{SCRIPT}}" in content:
        return content.replace("{{SCRIPT}}", _ADVANCED_SCRIPT)
    return content.replace("</body>", _ADVANCED_SCRIPT + "\n  </body>", 1)


def _render_start_page(message: str = "") -> str:
    """Render the landing page with the server-specific storage key."""
    return shell_render_start_page(message=message).replace(
        "biocypher_form_state",
        _STORAGE_KEY,
    )


def _render_registration_page(
    message: str = "",
    form_state: dict[str, str] | None = None,
) -> str:
    """Render the adapter registration form page."""
    form_state = form_state or {}
    notice = f"<div class='notice'>{html.escape(message)}</div>" if message else ""
    adapter_name = html.escape(form_state.get("adapter_name", ""))
    contact_email = html.escape(form_state.get("contact_email", ""))
    repository_location = html.escape(form_state.get("repository_location", ""))
    confirm_croissant_root = (
        "checked" if form_state.get("confirm_croissant_root") else ""
    )
    return f"""<!doctype html>
<html>
  <head>
    <meta charset="utf-8">
    <title>Register Adapter</title>
    <style>
      :root {{
        --bg: #0b1220;
        --panel: #111827;
        --panel-2: #172133;
        --ink: #e5edf6;
        --muted: #93a1b2;
        --accent: #60a5fa;
        --line: #273244;
      }}
      * {{ box-sizing: border-box; }}
      body {{
        margin: 0;
        font-family: "IBM Plex Sans", "Segoe UI", "Helvetica Neue", sans-serif;
        background: radial-gradient(1200px 800px at 10% -10%, #1a2740 0%, var(--bg) 46%);
        color: var(--ink);
        padding: 2.5rem 1.5rem;
      }}
      .wrap {{ max-width: 760px; margin: 0 auto; }}
      .card {{
        background: linear-gradient(180deg, rgba(255,255,255,0.02), transparent 60%), var(--panel);
        border: 1px solid var(--line);
        border-radius: 18px;
        padding: 1.5rem;
      }}
      h1 {{ margin: 0 0 0.35rem 0; font-size: 2rem; }}
      p {{ color: var(--muted); line-height: 1.5; }}
      .notice {{
        background: rgba(245, 158, 11, 0.14);
        border: 1px solid rgba(245, 158, 11, 0.24);
        padding: 0.75rem 1rem;
        border-radius: 10px;
        margin: 1rem 0;
      }}
      .field {{ margin: 1rem 0; }}
      label {{
        display: block;
        margin-bottom: 0.45rem;
        font-weight: 600;
      }}
      input {{
        width: 100%;
        padding: 0.85rem 0.9rem;
        border-radius: 12px;
        border: 1px solid var(--line);
        background: var(--panel-2);
        color: var(--ink);
      }}
      input[type="checkbox"] {{ width: auto; }}
      .checkbox {{
        display: flex;
        align-items: flex-start;
        gap: 0.6rem;
      }}
      .checkbox label {{ margin: 0; }}
      .hint {{ color: var(--muted); font-size: 0.92rem; margin-top: 0.4rem; }}
      .actions {{
        display: flex;
        gap: 0.75rem;
        margin-top: 1.25rem;
        flex-wrap: wrap;
      }}
      .button {{
        display: inline-block;
        text-decoration: none;
        background: var(--accent);
        color: #f8fafc;
        padding: 0.8rem 1.2rem;
        border-radius: 12px;
        border: 0;
        font-weight: 600;
        cursor: pointer;
      }}
      .button.ghost {{
        background: transparent;
        border: 1px solid var(--line);
        color: var(--ink);
      }}
    </style>
  </head>
  <body>
    <div class="wrap">
      <div class="card">
        <h1>Register Adapter</h1>
        <p>Submit a repository location and adapter name to create a tracked registration request in the local registry database.</p>
        {notice}
        <form method="post" action="/register">
          <div class="field">
            <label for="adapter_name">Adapter name</label>
            <input id="adapter_name" name="adapter_name" value="{adapter_name}" required>
          </div>
          <div class="field">
            <label for="repository_location">Repository location</label>
            <input id="repository_location" name="repository_location" value="{repository_location}" required>
            <div class="hint">Use either a local repository path or a supported GitHub repository URL.</div>
          </div>
          <div class="field">
            <label for="contact_email">Contact email</label>
            <input id="contact_email" name="contact_email" type="email" value="{contact_email}">
            <div class="hint">Optional maintainer contact for registration follow-up.</div>
          </div>
          <div class="field checkbox">
            <input id="confirm_croissant_root" name="confirm_croissant_root" type="checkbox" value="yes" {confirm_croissant_root} required>
            <label for="confirm_croissant_root">I confirm that croissant.jsonld is located at the repository root.</label>
          </div>
          <div class="actions">
            <button class="button" type="submit">Create registration request</button>
            <a class="button ghost" href="/registry">Registry operations</a>
            <a class="button ghost" href="/">Back to landing page</a>
          </div>
        </form>
      </div>
    </div>
  </body>
</html>"""


def _render_registration_result(registration: StoredRegistration) -> str:
    """Render the stored registration summary page."""
    return f"""<!doctype html>
<html>
  <head>
    <meta charset="utf-8">
    <title>Registration Saved</title>
    <style>
      :root {{
        --bg: #0b1220;
        --panel: #111827;
        --panel-2: #172133;
        --ink: #e5edf6;
        --muted: #93a1b2;
        --accent: #60a5fa;
        --line: #273244;
        --success-soft: rgba(74, 222, 128, 0.12);
        --success-line: rgba(74, 222, 128, 0.35);
      }}
      * {{ box-sizing: border-box; }}
      body {{
        margin: 0;
        font-family: "IBM Plex Sans", "Segoe UI", "Helvetica Neue", sans-serif;
        background: radial-gradient(1200px 800px at 10% -10%, #1a2740 0%, var(--bg) 46%);
        color: var(--ink);
        padding: 2.5rem 1.5rem;
      }}
      .wrap {{ max-width: 760px; margin: 0 auto; }}
      .card {{
        background: linear-gradient(180deg, rgba(255,255,255,0.02), transparent 60%), var(--panel);
        border: 1px solid var(--line);
        border-radius: 18px;
        padding: 1.5rem;
      }}
      .status {{
        display: inline-block;
        padding: 0.38rem 0.72rem;
        border-radius: 999px;
        background: var(--success-soft);
        border: 1px solid var(--success-line);
        font-weight: 700;
        margin-bottom: 1rem;
      }}
      .grid {{
        display: grid;
        grid-template-columns: repeat(2, minmax(0, 1fr));
        gap: 0.85rem;
      }}
      .metric {{
        border: 1px solid var(--line);
        border-radius: 12px;
        background: var(--panel-2);
        padding: 0.9rem;
      }}
      .label {{
        color: var(--muted);
        font-size: 0.78rem;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        margin-bottom: 0.3rem;
      }}
      .value {{ word-break: break-word; }}
      .actions {{ margin-top: 1.25rem; display: flex; gap: 0.75rem; flex-wrap: wrap; }}
      .button {{
        display: inline-block;
        text-decoration: none;
        background: var(--accent);
        color: #f8fafc;
        padding: 0.8rem 1.2rem;
        border-radius: 12px;
        font-weight: 600;
      }}
      .button.ghost {{
        background: transparent;
        border: 1px solid var(--line);
        color: var(--ink);
      }}
    </style>
  </head>
  <body>
    <div class="wrap">
      <div class="card">
        <div class="status">{html.escape(registration.status.value)}</div>
        <h1>Registration request stored</h1>
        <p>Your adapter submission has been saved in the registry database and is ready for later discovery and validation.</p>
        <div class="grid">
          <div class="metric"><div class="label">Registration ID</div><div class="value">{html.escape(registration.registration_id)}</div></div>
          <div class="metric"><div class="label">Adapter</div><div class="value">{html.escape(registration.adapter_name)}</div></div>
          <div class="metric"><div class="label">Adapter ID</div><div class="value">{html.escape(registration.adapter_id)}</div></div>
          <div class="metric"><div class="label">Repository Kind</div><div class="value">{html.escape(registration.repository_kind)}</div></div>
          <div class="metric"><div class="label">Repository Location</div><div class="value">{html.escape(registration.repository_location)}</div></div>
          <div class="metric"><div class="label">Contact Email</div><div class="value">{html.escape(registration.contact_email or "n/a")}</div></div>
          <div class="metric"><div class="label">Created At</div><div class="value">{html.escape(registration.created_at.isoformat())}</div></div>
        </div>
        <div class="actions">
          <a class="button" href="/register">Register another adapter</a>
          <a class="button ghost" href="/">Back to landing page</a>
        </div>
      </div>
    </div>
  </body>
</html>"""


def _render_registration_detail(
    registration: StoredRegistration,
    current_entry: RegistryEntry | None,
    events: list[RegistrationEvent],
    message: str = "",
) -> str:
    """Render a thin status and history page for one registration."""
    notice = f"<div class='notice'>{html.escape(message)}</div>" if message else ""
    latest_event_type = events[-1].event_type if events else "SUBMITTED"
    status_tone = (
        "warning"
        if registration.status.value == "INVALID"
        else "success"
        if registration.status.value == "VALID"
        else "neutral"
    )
    source_checked = (
        html.escape(registration.last_checked_at.isoformat())
        if registration.last_checked_at is not None
        else "Not processed yet"
    )
    current_entry_block = "<p class='empty'>No canonical valid registry entry exists yet.</p>"
    if current_entry is not None:
        current_entry_block = f"""
        <div class="grid">
          <div class="metric"><div class="label">Entry ID</div><div class="value">{html.escape(current_entry.entry_id)}</div></div>
          <div class="metric"><div class="label">Adapter Name</div><div class="value">{html.escape(current_entry.adapter_name)}</div></div>
          <div class="metric"><div class="label">Version</div><div class="value">{html.escape(current_entry.adapter_version)}</div></div>
          <div class="metric"><div class="label">Uniqueness Key</div><div class="value">{html.escape(current_entry.uniqueness_key)}</div></div>
          <div class="metric"><div class="label">Profile</div><div class="value">{html.escape(current_entry.profile_version or "n/a")}</div></div>
          <div class="metric"><div class="label">Checksum</div><div class="value">{html.escape(current_entry.metadata_checksum or "n/a")}</div></div>
        </div>
        """

    event_cards: list[str] = []
    for event in events:
        error_block = ""
        if event.error_details:
            error_block = (
                "<div class='event-errors'>"
                f"{html.escape(chr(10).join(event.error_details))}"
                "</div>"
            )
        event_cards.append(
            "<div class='event-card'>"
            f"<div class='event-type'>{html.escape(event.event_type)}</div>"
            f"<div class='event-copy'>{html.escape(event.message or '')}</div>"
            "<div class='event-meta'>"
            f"<span>Profile: {html.escape(event.profile_version or 'n/a')}</span>"
            f"<span>Checksum: {html.escape(event.observed_checksum or 'n/a')}</span>"
            f"<span>Finished: {html.escape(event.finished_at.isoformat())}</span>"
            "</div>"
            f"{error_block}"
            "</div>"
        )
    events_block = "".join(event_cards) if event_cards else "<p class='empty'>No event history yet.</p>"

    process_action = "/register/process"
    process_label = "Process registration" if registration.status.value == "SUBMITTED" else "Process again"
    if latest_event_type.startswith("INVALID_") or latest_event_type == "FETCH_FAILED":
        process_action = "/register/revalidate"
        process_label = "Revalidate now"
    validation_errors = ""
    if registration.validation_errors:
        validation_errors = (
            "<div class='section'>"
            "<h2>Validation Errors</h2>"
            "<div class='event-errors'>"
            f"{html.escape(chr(10).join(registration.validation_errors))}"
            "</div>"
            "</div>"
        )

    return f"""<!doctype html>
<html>
  <head>
    <meta charset="utf-8">
    <title>Registration Detail</title>
    <style>
      :root {{
        --bg: #0b1220;
        --panel: #111827;
        --panel-2: #172133;
        --ink: #e5edf6;
        --muted: #93a1b2;
        --accent: #60a5fa;
        --line: #273244;
        --success-soft: rgba(74, 222, 128, 0.12);
        --success-line: rgba(74, 222, 128, 0.35);
        --warn-soft: rgba(245, 158, 11, 0.14);
        --warn-line: rgba(245, 158, 11, 0.32);
        --neutral-soft: rgba(148, 163, 184, 0.12);
        --neutral-line: rgba(148, 163, 184, 0.28);
      }}
      * {{ box-sizing: border-box; }}
      body {{
        margin: 0;
        font-family: "IBM Plex Sans", "Segoe UI", "Helvetica Neue", sans-serif;
        background: radial-gradient(1200px 800px at 10% -10%, #1a2740 0%, var(--bg) 46%);
        color: var(--ink);
        padding: 2.5rem 1.5rem;
      }}
      .wrap {{ max-width: 900px; margin: 0 auto; }}
      .section {{
        background: linear-gradient(180deg, rgba(255,255,255,0.02), transparent 60%), var(--panel);
        border: 1px solid var(--line);
        border-radius: 18px;
        padding: 1.5rem;
        margin-bottom: 1rem;
      }}
      h1, h2 {{ margin: 0 0 0.55rem 0; }}
      p {{ color: var(--muted); line-height: 1.5; }}
      .notice {{
        background: var(--warn-soft);
        border: 1px solid var(--warn-line);
        padding: 0.75rem 1rem;
        border-radius: 10px;
        margin: 1rem 0;
      }}
      .status {{
        display: inline-block;
        padding: 0.38rem 0.72rem;
        border-radius: 999px;
        font-weight: 700;
        margin-bottom: 1rem;
      }}
      .status.success {{ background: var(--success-soft); border: 1px solid var(--success-line); }}
      .status.warning {{ background: var(--warn-soft); border: 1px solid var(--warn-line); }}
      .status.neutral {{ background: var(--neutral-soft); border: 1px solid var(--neutral-line); }}
      .grid {{
        display: grid;
        grid-template-columns: repeat(2, minmax(0, 1fr));
        gap: 0.85rem;
      }}
      .metric {{
        border: 1px solid var(--line);
        border-radius: 12px;
        background: var(--panel-2);
        padding: 0.9rem;
      }}
      .label {{
        color: var(--muted);
        font-size: 0.78rem;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        margin-bottom: 0.3rem;
      }}
      .value {{ word-break: break-word; }}
      .actions {{ display: flex; gap: 0.75rem; flex-wrap: wrap; margin-top: 1.2rem; }}
      .button {{
        display: inline-block;
        text-decoration: none;
        background: var(--accent);
        color: #f8fafc;
        padding: 0.8rem 1.2rem;
        border-radius: 12px;
        border: 0;
        font-weight: 600;
        cursor: pointer;
      }}
      .button.ghost {{
        background: transparent;
        border: 1px solid var(--line);
        color: var(--ink);
      }}
      .event-list {{ display: grid; gap: 0.75rem; }}
      .event-card {{
        border: 1px solid var(--line);
        border-radius: 12px;
        background: var(--panel-2);
        padding: 0.95rem;
      }}
      .event-type {{ font-weight: 700; margin-bottom: 0.35rem; }}
      .event-copy {{ color: var(--muted); margin-bottom: 0.55rem; }}
      .event-meta {{
        display: flex;
        flex-wrap: wrap;
        gap: 0.75rem;
        color: var(--muted);
        font-size: 0.88rem;
      }}
      .event-errors {{
        margin-top: 0.7rem;
        padding: 0.75rem;
        border-radius: 10px;
        background: rgba(239, 68, 68, 0.1);
        border: 1px solid rgba(239, 68, 68, 0.18);
        white-space: pre-wrap;
      }}
      .empty {{ color: var(--muted); }}
      @media (max-width: 720px) {{
        .grid {{ grid-template-columns: 1fr; }}
      }}
    </style>
  </head>
  <body>
    <div class="wrap">
      <div class="section">
        <div class="status {status_tone}">{html.escape(registration.status.value)}</div>
        <h1>Registration Detail</h1>
        <p>Review the current registration status, inspect processing history, and trigger processing from the web UI.</p>
        {notice}
        <div class="grid">
          <div class="metric"><div class="label">Registration ID</div><div class="value">{html.escape(registration.registration_id)}</div></div>
          <div class="metric"><div class="label">Adapter</div><div class="value">{html.escape(registration.adapter_name)}</div></div>
          <div class="metric"><div class="label">Adapter ID</div><div class="value">{html.escape(registration.adapter_id)}</div></div>
          <div class="metric"><div class="label">Repository Kind</div><div class="value">{html.escape(registration.repository_kind)}</div></div>
          <div class="metric"><div class="label">Repository Location</div><div class="value">{html.escape(registration.repository_location)}</div></div>
          <div class="metric"><div class="label">Contact Email</div><div class="value">{html.escape(registration.contact_email or "n/a")}</div></div>
          <div class="metric"><div class="label">Last Checked</div><div class="value">{source_checked}</div></div>
          <div class="metric"><div class="label">Profile Version</div><div class="value">{html.escape(registration.profile_version or "n/a")}</div></div>
          <div class="metric"><div class="label">Uniqueness Key</div><div class="value">{html.escape(registration.uniqueness_key or "n/a")}</div></div>
        </div>
        <div class="actions">
          <form method="post" action="{process_action}">
            <input type="hidden" name="registration_id" value="{html.escape(registration.registration_id)}">
            <button class="button" type="submit">{process_label}</button>
          </form>
          <a class="button ghost" href="/registry">Registry operations</a>
          <a class="button ghost" href="/register">Register another adapter</a>
          <a class="button ghost" href="/">Back to landing page</a>
        </div>
      </div>
      {validation_errors}
      <div class="section">
        <h2>Current Canonical Entry</h2>
        {current_entry_block}
      </div>
      <div class="section">
        <h2>Event History</h2>
        <div class="event-list">
          {events_block}
        </div>
      </div>
    </div>
  </body>
</html>"""


def _render_registry_overview(
    rows: list[dict[str, Any]],
    summary: dict[str, int] | None = None,
    message: str = "",
) -> str:
    """Render a thin registry operations page with batch refresh controls."""
    notice = f"<div class='notice'>{html.escape(message)}</div>" if message else ""
    summary_block = "<p class='empty'>No batch refresh has been run from the web UI yet.</p>"
    if summary is not None:
        summary_block = f"""
        <div class="grid">
          <div class="metric"><div class="label">Active Sources</div><div class="value">{summary["active_sources"]}</div></div>
          <div class="metric"><div class="label">Processed</div><div class="value">{summary["processed"]}</div></div>
          <div class="metric"><div class="label">VALID_CREATED</div><div class="value">{summary["valid_created"]}</div></div>
          <div class="metric"><div class="label">UNCHANGED</div><div class="value">{summary["unchanged"]}</div></div>
          <div class="metric"><div class="label">INVALID</div><div class="value">{summary["invalid"]}</div></div>
          <div class="metric"><div class="label">DUPLICATE</div><div class="value">{summary["duplicate"]}</div></div>
          <div class="metric"><div class="label">REJECTED_SAME_VERSION_CHANGED</div><div class="value">{summary["rejected_same_version_changed"]}</div></div>
          <div class="metric"><div class="label">FETCH_FAILED</div><div class="value">{summary["fetch_failed"]}</div></div>
        </div>
        """

    if rows:
        rendered_rows = []
        for row in rows:
            detail_href = f"/register?registration_id={html.escape(row['registration_id'])}"
            rendered_rows.append(
                "<tr>"
                f"<td><a href=\"{detail_href}\">{html.escape(row['registration_id'])}</a></td>"
                f"<td>{html.escape(row['adapter_name'])}</td>"
                f"<td>{html.escape(row['status'])}</td>"
                f"<td>{html.escape(row['latest_event_type'])}</td>"
                f"<td>{html.escape(row['repository_kind'])}</td>"
                f"<td>{html.escape(row['last_checked_at'])}</td>"
                "</tr>"
            )
        rows_block = "".join(rendered_rows)
    else:
        rows_block = (
            "<tr><td colspan='6' class='empty-cell'>"
            "No active sources are registered yet."
            "</td></tr>"
        )

    return f"""<!doctype html>
<html>
  <head>
    <meta charset="utf-8">
    <title>Registry Operations</title>
    <style>
      :root {{
        --bg: #0b1220;
        --panel: #111827;
        --panel-2: #172133;
        --ink: #e5edf6;
        --muted: #93a1b2;
        --accent: #60a5fa;
        --line: #273244;
        --warn-soft: rgba(245, 158, 11, 0.14);
        --warn-line: rgba(245, 158, 11, 0.32);
      }}
      * {{ box-sizing: border-box; }}
      body {{
        margin: 0;
        font-family: "IBM Plex Sans", "Segoe UI", "Helvetica Neue", sans-serif;
        background: radial-gradient(1200px 800px at 10% -10%, #1a2740 0%, var(--bg) 46%);
        color: var(--ink);
        padding: 2.5rem 1.5rem;
      }}
      .wrap {{ max-width: 980px; margin: 0 auto; }}
      .section {{
        background: linear-gradient(180deg, rgba(255,255,255,0.02), transparent 60%), var(--panel);
        border: 1px solid var(--line);
        border-radius: 18px;
        padding: 1.5rem;
        margin-bottom: 1rem;
      }}
      .notice {{
        background: var(--warn-soft);
        border: 1px solid var(--warn-line);
        padding: 0.75rem 1rem;
        border-radius: 10px;
        margin: 1rem 0;
      }}
      h1, h2 {{ margin: 0 0 0.55rem 0; }}
      p {{ color: var(--muted); line-height: 1.5; }}
      .actions {{ display: flex; gap: 0.75rem; flex-wrap: wrap; margin-top: 1rem; }}
      .button {{
        display: inline-block;
        text-decoration: none;
        background: var(--accent);
        color: #f8fafc;
        padding: 0.8rem 1.2rem;
        border-radius: 12px;
        border: 0;
        font-weight: 600;
        cursor: pointer;
      }}
      .button.ghost {{
        background: transparent;
        border: 1px solid var(--line);
        color: var(--ink);
      }}
      .grid {{
        display: grid;
        grid-template-columns: repeat(4, minmax(0, 1fr));
        gap: 0.85rem;
      }}
      .metric {{
        border: 1px solid var(--line);
        border-radius: 12px;
        background: var(--panel-2);
        padding: 0.9rem;
      }}
      .label {{
        color: var(--muted);
        font-size: 0.78rem;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        margin-bottom: 0.3rem;
      }}
      .value {{ word-break: break-word; }}
      table {{ width: 100%; border-collapse: collapse; }}
      th, td {{
        text-align: left;
        padding: 0.85rem 0.7rem;
        border-bottom: 1px solid var(--line);
        vertical-align: top;
      }}
      th {{ color: var(--muted); font-size: 0.82rem; text-transform: uppercase; letter-spacing: 0.05em; }}
      td a {{ color: var(--accent); text-decoration: none; }}
      .empty, .empty-cell {{ color: var(--muted); }}
      @media (max-width: 820px) {{
        .grid {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
      }}
      @media (max-width: 580px) {{
        .grid {{ grid-template-columns: 1fr; }}
      }}
    </style>
  </head>
  <body>
    <div class="wrap">
      <div class="section">
        <h1>Registry Operations</h1>
        <p>Trigger a manual batch refresh and inspect the latest outcome for each active source.</p>
        {notice}
        <div class="actions">
          <form method="post" action="/registry/refresh">
            <button class="button" type="submit">Run Batch Refresh</button>
          </form>
          <a class="button ghost" href="/register">Register adapter</a>
          <a class="button ghost" href="/">Back to landing page</a>
        </div>
      </div>
      <div class="section">
        <h2>Latest Batch Summary</h2>
        {summary_block}
      </div>
      <div class="section">
        <h2>Active Sources</h2>
        <table>
          <thead>
            <tr>
              <th>Registration</th>
              <th>Adapter</th>
              <th>Status</th>
              <th>Latest Event</th>
              <th>Kind</th>
              <th>Last Checked</th>
            </tr>
          </thead>
          <tbody>
            {rows_block}
          </tbody>
        </table>
      </div>
    </div>
  </body>
</html>"""


def _build_registration_store(database_path: Path) -> RegistrationStore:
    """Create the configured registration store for the web server."""
    return build_registration_store(database_path)


def _load_registration_detail(
    registration_id: str,
    database_path: Path,
) -> tuple[StoredRegistration, RegistryEntry | None, list[RegistrationEvent]]:
    """Load the registration record, current canonical entry, and event history."""
    store = _build_registration_store(database_path)
    registration = store.get_registration(registration_id)
    if registration is None:
        raise ValueError(f"Registration not found: {registration_id}")

    current_entry = (
        store.get_registry_entry(registration.current_registry_entry_id)
        if registration.current_registry_entry_id is not None
        else None
    )
    events = store.list_registration_events(registration_id)
    return registration, current_entry, events


def _load_registry_overview(database_path: Path) -> list[dict[str, Any]]:
    """Load active sources with their current status and latest event type."""
    store = _build_registration_store(database_path)
    rows: list[dict[str, Any]] = []
    for registration in store.list_active_registrations():
        latest_event_type = store.get_latest_event_type(registration.registration_id)
        rows.append(
            {
                "registration_id": registration.registration_id,
                "adapter_name": registration.adapter_name,
                "status": registration.status.value,
                "latest_event_type": latest_event_type or "SUBMITTED",
                "repository_kind": registration.repository_kind,
                "last_checked_at": (
                    registration.last_checked_at.isoformat()
                    if registration.last_checked_at is not None
                    else "Not processed yet"
                ),
            }
            )
    return rows


def _summary_to_dict(summary: Any) -> dict[str, int]:
    """Convert a batch summary object into a render-friendly mapping."""
    return {
        "active_sources": int(summary.active_sources),
        "processed": int(summary.processed),
        "valid_created": int(summary.valid_created),
        "unchanged": int(summary.unchanged),
        "invalid": int(summary.invalid),
        "duplicate": int(summary.duplicate),
        "rejected_same_version_changed": int(summary.rejected_same_version_changed),
        "fetch_failed": int(summary.fetch_failed),
    }


def _load_latest_refresh_summary(database_path: Path) -> dict[str, int] | None:
    """Load the latest persisted batch refresh summary for the registry page."""
    refresh = _build_registration_store(database_path).get_latest_batch_refresh()
    if refresh is None:
        return None
    return _summary_to_dict(refresh)


def _format_event_errors(error_details: str) -> str:
    """Format stored event error details for human-readable display."""
    try:
        parsed = json.loads(error_details)
    except json.JSONDecodeError:
        return error_details
    if isinstance(parsed, list):
        return "\n".join(str(item) for item in parsed)
    return str(parsed)


def _optional_string(mapping: dict[str, Any], key: str) -> str | None:
    """Read an optional non-empty string from a mapping."""
    value = mapping.get(key)
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _parse_keyword_list(raw: str) -> list[str]:
    """Split a comma-separated keyword string into normalized values."""
    return [item.strip() for item in raw.split(",") if item.strip()]


def _creator_strings_from_legacy(creators: list[dict[str, Any]]) -> list[str]:
    """Serialize legacy creator mappings into compact adapter creator strings."""
    values: list[str] = []
    for creator in creators:
        if not isinstance(creator, dict):
            continue
        parts = [
            str(creator.get("name", "")).strip(),
            str(creator.get("affiliation", "")).strip(),
            str(creator.get("identifier", "")).strip(),
        ]
        joined = ", ".join(part for part in parts if part)
        if joined:
            values.append(joined)
    return values


def _slugify_id(text: str) -> str:
    """Normalize text into a stable identifier fragment."""
    return slugify_identifier(text)


def _distribution_name_from_url(url: str) -> str:
    """Derive a display-friendly filename from a content URL."""
    candidate = str(url or "").strip().split("?")[0].rstrip("/").split("/")[-1]
    return candidate or "file"


def _resolve_tabular_sample_path(input_path: str) -> Path | None:
    """Find a representative tabular file from a path or dataset directory."""
    path = Path(input_path)
    if path.is_file():
        return path
    if not path.is_dir():
        return None
    candidates = sorted(
        item
        for item in path.rglob("*")
        if item.is_file()
        and (
            item.suffix.lower() in {".csv", ".tsv", ".tab"}
            or item.name.lower().endswith((".csv.gz", ".tsv.gz", ".tab.gz"))
        )
    )
    return candidates[0] if candidates else None


def _field_previews_from_input(
    input_path: str,
    dataset_name: str,
    record_set_name: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], str | None]:
    """Infer field previews and draft distribution data from a source path."""
    path = _resolve_tabular_sample_path(input_path)
    if not input_path or path is None or not path.exists():
        return [], [], [], None

    dataset_id = _slugify_id(dataset_name or "dataset")
    record_name = record_set_name or "records"
    record_set_id = f"{dataset_id}-{_slugify_id(record_name)}"
    file_object_id = _slugify_id(path.name or "file")
    sha256 = compute_file_hash(path)
    try:
        fields, encoding_format = infer_fields_from_file(
            file_path=path,
            record_set_id=record_set_id,
            file_object_id=file_object_id,
        )
    except Exception:
        return [], [], [], None

    previews: list[dict[str, Any]] = []
    for field in fields:
        examples = field.get("examples", [])
        example = examples[0] if isinstance(examples, list) and examples else ""
        previews.append(
            {
                "name": str(field.get("name", "")).strip(),
                "detectedType": str(field.get("dataType", "sc:Text")).strip(),
                "mappedType": str(field.get("dataType", "sc:Text")).strip(),
                "example": str(example or "").strip(),
                "description": str(field.get("description", "") or "").strip(),
                "source": "inferred",
            }
        )

    distribution = [
        {
            "@type": "cr:FileObject",
            "@id": file_object_id,
            "contentUrl": str(path),
            "encodingFormat": encoding_format,
            "name": path.name,
            "sha256": sha256,
        }
    ]
    record_set = [
        {
            "@type": "cr:RecordSet",
            "@id": record_set_id,
            "name": record_name,
            "field": fields,
        }
    ]
    return previews, distribution, record_set, path.name


def _build_request_from_form(
    data: dict[str, str],
    output_dir: Path | None = None,
) -> AdapterGenerationRequest:
    """Build an adapter generation request from submitted form data."""
    output_dir = output_dir or Path(".")
    normalized = build_normalized_adapter_input_from_web_form(
        data=data,
        output_dir=output_dir,
    )
    request = build_adapter_request_from_mapping(normalized)
    request.output_path = str(output_dir / Path(request.output_path).name)
    return request


def _state_from_adapter_config(payload: dict[str, Any]) -> dict[str, Any]:
    """Convert adapter config YAML into the UI preload state shape."""
    if not isinstance(payload, dict):
        raise ValueError("The preload YAML must contain a top-level mapping.")

    adapter = payload.get("adapter")
    if not isinstance(adapter, dict):
        raise ValueError(
            "The preload YAML must follow the current adapter config schema and contain an 'adapter' mapping."
        )

    datasets_raw = payload.get("datasets", [])
    if datasets_raw in (None, ""):
        datasets_raw = []
    if not isinstance(datasets_raw, list):
        raise ValueError("The preload YAML must contain a 'datasets' list in the current adapter config schema.")

    creators = adapter.get("creators", [])
    if creators in (None, ""):
        creators = []
    if not isinstance(creators, list):
        raise ValueError("'adapter.creators' must be a list.")

    normalized_creators: list[dict[str, Any]] = []
    for creator in creators:
        if isinstance(creator, dict):
            normalized_creators.append(
                {
                    "creator_type": str(
                        creator.get("creator_type", creator.get("type", "Person"))
                    ).strip()
                    or "Person",
                    "name": str(creator.get("name", "")).strip(),
                    "affiliation": str(
                        creator.get("affiliation", creator.get("email", ""))
                    ).strip(),
                    "identifier": str(
                        creator.get("identifier", creator.get("url", ""))
                    ).strip(),
                }
            )
        elif isinstance(creator, str):
            parts = [part.strip() for part in creator.split(",")]
            normalized_creators.append(
                {
                    "creator_type": "Person",
                    "name": parts[0] if parts else "",
                    "affiliation": parts[1] if len(parts) > 1 else "",
                    "identifier": ",".join(parts[2:]).strip() if len(parts) > 2 else "",
                }
            )

    normalized_datasets: list[dict[str, Any]] = []
    for entry in datasets_raw:
        if not isinstance(entry, dict):
            raise ValueError("Each dataset entry must be a mapping.")
        mode_raw = entry.get("mode")
        if not isinstance(mode_raw, str) or not mode_raw.strip():
            raise ValueError(
                "Each dataset entry in the preload YAML must declare a dataset 'mode' in the current adapter config schema."
            )
        mode = mode_raw.strip().lower()
        if mode == "existing":
            path = str(entry.get("path", "")).strip()
            normalized_datasets.append(
                {
                    "name": Path(path).stem or "Existing dataset",
                    "description": "Existing Croissant metadata file",
                    "version": "",
                    "license": "",
                    "url": "",
                    "uiStatus": "detailed",
                    "uiMode": "existing",
                    "uiExistingPath": path,
                }
            )
            continue

        creators_raw = entry.get("creators", [])
        if creators_raw in (None, ""):
            creators_raw = []
        if not isinstance(creators_raw, list):
            raise ValueError("Generated dataset creators must be a list.")
        dataset_creators: list[str] = []
        for creator in creators_raw:
            if isinstance(creator, str):
                parts = [part.strip() for part in creator.split("|")]
                if parts and parts[0].lower() in {"person", "organization"}:
                    dataset_creators.append(
                        {
                            "creator_type": parts[0].capitalize(),
                            "name": parts[1] if len(parts) > 1 else "",
                            "affiliations": parts[2] if len(parts) > 2 else "",
                            "email": parts[3] if len(parts) > 3 else "",
                            "url": parts[4] if len(parts) > 4 else "",
                        }
                    )
                else:
                    plain_parts = [part.strip() for part in creator.split(",")]
                    dataset_creators.append(
                        {
                            "creator_type": "Person",
                            "name": plain_parts[0] if plain_parts else "",
                            "affiliations": "",
                            "email": plain_parts[1] if len(plain_parts) > 1 else "",
                            "url": ",".join(plain_parts[2:]).strip() if len(plain_parts) > 2 else "",
                        }
                    )
            elif isinstance(creator, dict):
                dataset_creators.append(
                    {
                        "creator_type": str(
                            creator.get("creator_type", creator.get("type", "Person"))
                        ).strip()
                        or "Person",
                        "name": str(creator.get("name", "")).strip(),
                        "affiliations": str(
                            creator.get("affiliations", creator.get("affiliation", ""))
                        ).strip(),
                        "email": str(creator.get("email", "")).strip(),
                        "url": str(creator.get("url", "")).strip(),
                    }
                )

        distribution = entry.get("distribution")
        normalized_distribution: list[dict[str, Any]] = []
        if isinstance(distribution, list):
            for item in distribution:
                if isinstance(item, dict):
                    normalized_distribution.append(dict(item))

        record_set = entry.get("recordSet", entry.get("record_set"))
        normalized_record_set: list[dict[str, Any]] = []
        if isinstance(record_set, list):
            for item in record_set:
                if isinstance(item, dict):
                    normalized_record_set.append(dict(item))

        record_set_name = (
            str(normalized_record_set[0].get("name", "")).strip()
            if normalized_record_set and isinstance(normalized_record_set[0], dict)
            else ""
        ) or "records"

        ui_field_preview: list[dict[str, Any]] = []
        inferred_file_name: str | None = None
        if normalized_record_set:
            first_record_set = normalized_record_set[0]
            fields = first_record_set.get("field")
            if isinstance(fields, list):
                for field in fields:
                    if not isinstance(field, dict):
                        continue
                    examples = field.get("examples", [])
                    example = examples[0] if isinstance(examples, list) and examples else ""
                    ui_field_preview.append(
                        {
                            "name": str(field.get("name", "")).strip(),
                            "detectedType": str(field.get("dataType", "sc:Text")).strip(),
                            "mappedType": str(field.get("dataType", "sc:Text")).strip(),
                            "example": str(example or "").strip(),
                            "description": str(field.get("description", "") or "").strip(),
                            "source": "preloaded",
                        }
                    )

        if not ui_field_preview:
            (
                ui_field_preview,
                inferred_distribution,
                inferred_record_set,
                inferred_file_name,
            ) = _field_previews_from_input(
                input_path=str(entry.get("input", "")).strip(),
                dataset_name=str(entry.get("name", "")).strip(),
                record_set_name=record_set_name,
            )
            if not normalized_distribution:
                normalized_distribution = inferred_distribution
            if not normalized_record_set:
                normalized_record_set = inferred_record_set

        if not normalized_distribution:
            content_url = str(entry.get("url", "")).strip()
            if content_url:
                normalized_distribution = [
                    {
                        "@type": "cr:FileObject",
                        "@id": _slugify_id(_distribution_name_from_url(content_url)),
                        "contentUrl": content_url,
                        "name": _distribution_name_from_url(content_url),
                    }
                ]

        normalized_datasets.append(
            {
                "name": str(entry.get("name", "")).strip(),
                "description": str(entry.get("description", "")).strip(),
                "version": str(entry.get("dataset_version", "") or "").strip(),
                "license": str(entry.get("license", "")).strip(),
                "url": str(entry.get("url", "")).strip(),
                "datePublished": str(entry.get("date_published", "") or "").strip(),
                "citeAs": str(entry.get("citation", "")).strip(),
                "uiStatus": (
                    "detailed"
                    if normalized_distribution or normalized_record_set or ui_field_preview
                    else "pending"
                ),
                "uiMode": "generate",
                "uiInputPath": str(entry.get("input", "")).strip(),
                "uiCreators": [
                    item
                    for item in dataset_creators
                    if isinstance(item, dict) and str(item.get("name", "")).strip()
                ],
                "distribution": normalized_distribution,
                "recordSet": normalized_record_set,
                "uiFieldPreview": ui_field_preview,
                "uiInferenceFileName": inferred_file_name,
            }
        )

    return {
        "name": str(adapter.get("name", "")),
        "description": str(adapter.get("description", "")),
        "version": str(adapter.get("version", "")),
        "license": str(adapter.get("license", "")),
        "code_repository": str(
            adapter.get("code_repository", adapter.get("code-repository", ""))
        ),
        "keywords": ", ".join(adapter.get("keywords", [])),
        "creators": normalized_creators,
        "datasets": normalized_datasets,
        "dataset_generator": str(
            payload.get("dataset_generator", payload.get("dataset-generator", "croissant-baker"))
        ),
        "validate": bool(payload.get("validate", adapter.get("validate", True))),
        "output": str(adapter.get("output", METADATA_FILENAME)),
        "adapter_id": str(adapter.get("adapter_id", adapter.get("adapter-id", ""))),
    }


def _load_yaml_upload(headers: Any, body: bytes) -> dict[str, Any]:
    """Extract and parse a YAML preload file from a multipart upload."""
    content_type = headers.get("Content-Type", "")
    if "multipart/form-data" not in content_type:
        raise ValueError("Please upload a YAML file using the preload form.")

    message = BytesParser(policy=default).parsebytes(
        f"Content-Type: {content_type}\r\nMIME-Version: 1.0\r\n\r\n".encode("utf-8") + body
    )
    for part in message.iter_parts():
        if part.get_content_disposition() != "form-data":
            continue
        if part.get_param("name", header="content-disposition") != "metadata_yaml":
            continue
        payload = part.get_payload(decode=True)
        if not payload:
            raise ValueError("Please choose a YAML file to preload.")
        loaded = yaml.safe_load(payload.decode("utf-8")) or {}
        if not isinstance(loaded, dict):
            raise ValueError("The uploaded YAML must contain a top-level mapping.")
        return loaded
    raise ValueError("Please choose a YAML file to preload.")


def _state_from_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Normalize uploaded preload content into UI state."""
    state = _state_from_adapter_config(payload)
    state.setdefault("dataset_generator", "croissant-baker")
    state.setdefault("validate", True)
    state.setdefault("output", METADATA_FILENAME)
    state.setdefault("adapter_id", "")
    return state


def _render_result(file_name: str, file_contents: str, report: str) -> str:
    """Render the post-generation result page."""
    def section_card(title: str, body: str, tone: str = "") -> str:
        tone_class = f" {tone}" if tone else ""
        return (
            f"<div class='report-card{tone_class}'>"
            f"<div class='report-card-title'>{html.escape(title)}</div>"
            f"<div class='report-card-body'>{body}</div>"
            "</div>"
        )

    report_lines = [line.strip() for line in report.splitlines() if line.strip()]
    summary_lines: list[str] = []
    dataset_cards: list[str] = []
    current_dataset_name: str | None = None
    current_lines: list[str] = []

    for line in report_lines:
        if line.startswith("Generated dataset '") and line.endswith("'"):
            if current_dataset_name is not None:
                dataset_cards.append(
                    section_card(
                        current_dataset_name,
                        "".join(
                            f"<div class='report-row'>{html.escape(item)}</div>"
                            for item in current_lines
                        ),
                    )
                )
            current_dataset_name = line[len("Generated dataset '") : -1]
            current_lines = []
            continue
        if current_dataset_name is None:
            summary_lines.append(line)
        else:
            current_lines.append(line)

    if current_dataset_name is not None:
        dataset_cards.append(
            section_card(
                current_dataset_name,
                "".join(
                    f"<div class='report-row'>{html.escape(item)}</div>"
                    for item in current_lines
                ),
            )
        )

    summary_metrics: list[str] = []
    summary_details: list[str] = []
    for line in summary_lines:
        if ":" in line and any(line.startswith(prefix) for prefix in ["Datasets", "Saved to", "Files", "Record sets"]):
            label, value = line.split(":", 1)
            summary_metrics.append(
                f"<div class='metric'><div class='metric-label'>{html.escape(label)}</div><div class='metric-value'>{html.escape(value.strip())}</div></div>"
            )
        else:
            summary_details.append(f"<div class='report-row'>{html.escape(line)}</div>")

    summary_block = ""
    if summary_metrics or summary_details:
        summary_block = (
            "<div class='summary-grid'>"
            + "".join(summary_metrics)
            + "</div>"
            + ("<div class='summary-copy'>" + "".join(summary_details) + "</div>" if summary_details else "")
        )
    else:
        summary_block = "<div class='report-row'>No additional report output.</div>"

    dataset_reports_block = (
        "<div class='dataset-report-grid'>"
        + "".join(dataset_cards)
        + "</div>"
        if dataset_cards
        else "<div class='empty-report'>No dataset-specific report details.</div>"
    )

    return f"""<!doctype html>
<html>
  <head>
    <meta charset="utf-8">
    <title>BioCypher Metadata Generator</title>
    <style>
      :root {{
        --bg: #0f1722;
        --panel: #161f2b;
        --panel-2: #1c2735;
        --ink: #e8eef5;
        --muted: #9aa8b7;
        --accent: #60a5fa;
        --accent-2: #93c5fd;
        --line: #2d3948;
      }}
      body.light {{
        --bg: #f6f8fb;
        --panel: #ffffff;
        --panel-2: #eef2f7;
        --ink: #17202a;
        --muted: #5f6c7b;
        --accent: #2563eb;
        --accent-2: #1d4ed8;
        --line: #d7dee8;
        background: linear-gradient(180deg, #f6f8fb 0%, #ffffff 100%);
      }}
      * {{ box-sizing: border-box; }}
      body {{
        font-family: "IBM Plex Sans", "Segoe UI", "Helvetica Neue", sans-serif;
        background: radial-gradient(1200px 800px at 10% -10%, #1a2740 0%, var(--bg) 46%);
        color: var(--ink);
        margin: 0;
        padding: 2.25rem 1.5rem;
      }}
      .wrap {{ max-width: 1100px; margin: 0 auto; }}
      .topbar {{
        display: flex;
        justify-content: flex-end;
        align-items: center;
        gap: 0.85rem;
        margin-bottom: 0.5rem;
      }}
      .switch-wrap {{
        display: inline-flex;
        align-items: center;
        gap: 0.65rem;
        color: var(--muted);
        font-size: 0.92rem;
      }}
      .theme-switch {{
        position: relative;
        width: 3.35rem;
        height: 1.9rem;
        display: inline-block;
      }}
      .theme-switch input {{
        position: absolute;
        opacity: 0;
        width: 0;
        height: 0;
      }}
      .theme-slider {{
        position: absolute;
        inset: 0;
        cursor: pointer;
        background: var(--panel-2);
        border: 1px solid var(--line);
        border-radius: 999px;
        transition: background 150ms ease, border-color 150ms ease;
      }}
      .theme-slider::before {{
        content: "";
        position: absolute;
        width: 1.35rem;
        height: 1.35rem;
        left: 0.2rem;
        top: 0.2rem;
        border-radius: 50%;
        background: var(--accent);
        box-shadow: 0 2px 10px rgba(0, 0, 0, 0.22);
        transition: transform 150ms ease, background 150ms ease;
      }}
      .theme-switch input:checked + .theme-slider::before {{ transform: translateX(1.4rem); }}
      .hero {{
        display: flex;
        flex-wrap: wrap;
        align-items: end;
        justify-content: space-between;
        gap: 1rem;
        margin-bottom: 1rem;
      }}
      h1 {{ margin: 0; font-size: 2rem; line-height: 1.1; }}
      .subtitle {{ color: var(--muted); font-size: 0.95rem; max-width: 46rem; line-height: 1.5; margin-top: 0.45rem; }}
      .section {{
        background: var(--panel);
        border: 1px solid var(--line);
        border-radius: 14px;
        padding: 1.2rem;
        margin: 1rem 0;
        box-shadow: 0 8px 24px rgba(0, 0, 0, 0.35);
      }}
      h2 {{ margin: 0 0 0.8rem 0; font-size: 1.28rem; }}
      .button {{
        display: inline-block;
        text-decoration: none;
        background: var(--accent);
        color: #f8fafc;
        border-radius: 10px;
        padding: 0.62rem 1rem;
        border: 1px solid transparent;
        margin-top: 1rem;
        font-size: 0.92rem;
        font-weight: 500;
      }}
      .button.ghost {{
        background: transparent;
        color: var(--ink);
        border: 1px solid var(--line);
      }}
      button.button {{
        cursor: pointer;
      }}
      .actions {{ display: flex; gap: 0.75rem; justify-content: flex-end; }}
      .summary-grid {{
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
        gap: 0.75rem;
        margin-bottom: 0.9rem;
      }}
      .metric {{
        border: 1px solid var(--line);
        border-radius: 12px;
        background: var(--panel-2);
        padding: 0.85rem 0.9rem;
      }}
      .metric-label {{
        color: var(--muted);
        font-size: 0.76rem;
        text-transform: uppercase;
        letter-spacing: 0.04em;
        margin-bottom: 0.22rem;
      }}
      .metric-value {{
        color: var(--ink);
        font-size: 0.98rem;
        font-weight: 600;
        word-break: break-word;
      }}
      .summary-copy {{
        display: grid;
        gap: 0.42rem;
      }}
      .report-row {{
        color: var(--ink);
        line-height: 1.45;
        word-break: break-word;
      }}
      .dataset-report-grid {{
        display: grid;
        gap: 0.8rem;
      }}
      .report-card {{
        border: 1px solid var(--line);
        border-radius: 12px;
        background: var(--panel-2);
        padding: 0.9rem 1rem;
      }}
      .report-card-title {{
        font-size: 1rem;
        font-weight: 700;
        color: var(--accent-2);
        margin-bottom: 0.55rem;
      }}
      .report-card-body {{
        display: grid;
        gap: 0.35rem;
      }}
      .empty-report {{
        color: var(--muted);
        font-size: 0.92rem;
      }}
      .codeblock {{
        white-space: pre;
        background: var(--panel-2);
        color: var(--ink);
        padding: 1rem;
        border-radius: 12px;
        border: 1px solid var(--line);
        max-height: 22rem;
        overflow: auto;
        font-size: 0.88rem;
        line-height: 1.45;
      }}
      .preview-head {{
        display: flex;
        flex-wrap: wrap;
        align-items: center;
        justify-content: space-between;
        gap: 0.75rem;
        margin-bottom: 0.8rem;
      }}
      .file-pill {{
        display: inline-flex;
        align-items: center;
        padding: 0.28rem 0.65rem;
        border-radius: 999px;
        border: 1px solid var(--line);
        background: var(--panel-2);
        color: var(--muted);
        font-size: 0.8rem;
      }}
      .note {{ color: var(--muted); font-size: 0.9rem; line-height: 1.45; }}
      @media (max-width: 800px) {{
        .actions {{ justify-content: stretch; flex-direction: column; }}
        .button {{ text-align: center; }}
      }}
    </style>
  </head>
  <body>
    <div class="wrap">
      <div class="topbar">
        <button type="button" class="button ghost" onclick="window.location.href='/'">Return to landing page</button>
        <div class="switch-wrap">
          <span id="theme_label">Dark mode</span>
          <label class="theme-switch" for="theme_toggle">
            <input type="checkbox" id="theme_toggle" onchange="toggleTheme()">
            <span class="theme-slider"></span>
          </label>
        </div>
      </div>
      <div class="hero">
        <div>
          <h1>Adapter Ready</h1>
          <div class="subtitle">Your adapter metadata was generated successfully. Review the summary, inspect the dataset reports, and download the final JSON-LD file.</div>
        </div>
        <div class="file-pill">{html.escape(file_name)}</div>
      </div>
      <div class="section">
        <h2>Summary</h2>
        {summary_block}
      </div>
      <div class="section">
        <h2>Dataset Reports</h2>
        {dataset_reports_block}
      </div>
      <div class="section">
        <div class="preview-head">
          <div>
            <h2>JSON-LD Preview</h2>
            <div class="note">A shortened, scrollable preview of the generated file.</div>
          </div>
          <button class="button ghost" type="button" onclick="copyPreview()">Copy JSON-LD</button>
        </div>
        <pre class="codeblock" id="json_preview">{html.escape(file_contents)}</pre>
        <div class="actions">
          <a class="button" href="/download" download="{html.escape(file_name)}">Download</a>
          <a class="button ghost" href="/?form=1">Back to form</a>
        </div>
      </div>
    </div>
    <script>
      function setTheme(mode) {{
        document.body.classList.toggle('light', mode === 'light');
        const toggle = document.getElementById('theme_toggle');
        if (toggle) toggle.checked = mode === 'light';
        const label = document.getElementById('theme_label');
        if (label) label.textContent = mode === 'light' ? 'Light mode' : 'Dark mode';
        localStorage.setItem('biocypher_theme_new', mode);
      }}

      window.toggleTheme = function toggleTheme() {{
        const current = document.body.classList.contains('light') ? 'light' : 'dark';
        setTheme(current === 'light' ? 'dark' : 'light');
      }};

      function copyPreview() {{
        const preview = document.getElementById('json_preview');
        if (!preview) return;
        const text = preview.textContent || '';
        if (navigator.clipboard && navigator.clipboard.writeText) {{
          navigator.clipboard.writeText(text);
          return;
        }}
        const textarea = document.createElement('textarea');
        textarea.value = text;
        textarea.setAttribute('readonly', '');
        textarea.style.position = 'absolute';
        textarea.style.left = '-9999px';
        document.body.appendChild(textarea);
        textarea.select();
        document.execCommand('copy');
        document.body.removeChild(textarea);
      }}

      setTheme(localStorage.getItem('biocypher_theme_new') === 'light' ? 'light' : 'dark');
    </script>
  </body>
</html>"""


class _Handler(BaseHTTPRequestHandler):
    """Serve the form, preload endpoint, result page, and download endpoint."""

    output_dir: Path
    last_output_path: Path
    registration_db_path: Path

    def _send(self, content: str, status: int = 200) -> None:
        """Send an HTML response with the given status code."""
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(content.encode("utf-8"))

    def do_GET(self) -> None:  # noqa: N802
        """Handle the landing page and generated-file download."""
        parsed = urlparse(self.path)
        if self.path == "/download":
            file_path = getattr(type(self), "last_output_path", self.output_dir / METADATA_FILENAME)
            if not file_path.exists():
                self._send(_render_form("No generated file found."), status=404)
                return
            data = file_path.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "application/ld+json")
            self.send_header(
                "Content-Disposition",
                f'attachment; filename="{file_path.name}"',
            )
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return
        if parsed.path == "/registry":
            self._send(
                _render_registry_overview(
                    rows=_load_registry_overview(self.registration_db_path),
                    summary=_load_latest_refresh_summary(self.registration_db_path),
                )
            )
            return
        if parsed.path == "/register":
            params = parse_qs(parsed.query)
            registration_id = params.get("registration_id", [""])[0].strip()
            if registration_id:
                try:
                    registration, current_entry, events = _load_registration_detail(
                        registration_id=registration_id,
                        database_path=self.registration_db_path,
                    )
                except ValueError as exc:
                    self._send(_render_registration_page(str(exc)), status=404)
                    return
                self._send(
                    _render_registration_detail(
                        registration=registration,
                        current_entry=current_entry,
                        events=events,
                    )
                )
                return
            self._send(_render_registration_page())
            return

        params = parse_qs(parsed.query)
        mode = params.get("mode", [""])[0]
        if mode == "scratch" or params.get("form", [""])[0] == "1":
            self._send(_render_form())
            return
        self._send(_render_start_page())

    def do_POST(self) -> None:  # noqa: N802
        """Handle YAML preload uploads and form submissions."""
        if self.path == "/preload":
            try:
                length = int(self.headers.get("Content-Length", "0"))
                body = self.rfile.read(length)
                payload = _load_yaml_upload(self.headers, body)
                preload_state = _state_from_payload(payload)
            except Exception as exc:  # noqa: BLE001
                self._send(_render_start_page(str(exc)), status=200)
                return
            self._send(_render_form(preload_state=preload_state))
            return

        if self.path == "/register":
            length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(length).decode("utf-8")
            data = {key: values[0] for key, values in parse_qs(body).items()}
            if not data.get("confirm_croissant_root"):
                self._send(
                    _render_registration_page(
                        "Please confirm that croissant.jsonld is located at the repository root.",
                        form_state=data,
                    ),
                    status=200,
                )
                return
            try:
                registration = submit_registration(
                    adapter_name=data.get("adapter_name", ""),
                    repository_location=data.get("repository_location", ""),
                    store=_build_registration_store(self.registration_db_path),
                    contact_email=data.get("contact_email"),
                )
            except Exception as exc:  # noqa: BLE001
                self._send(_render_registration_page(str(exc), form_state=data), status=200)
                return
            detail_registration, current_entry, events = _load_registration_detail(
                registration_id=registration.registration_id,
                database_path=self.registration_db_path,
            )
            self._send(
                _render_registration_detail(
                    registration=detail_registration,
                    current_entry=current_entry,
                    events=events,
                    message="Registration request stored successfully.",
                )
            )
            return

        if self.path == "/register/process":
            length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(length).decode("utf-8")
            data = {key: values[0] for key, values in parse_qs(body).items()}
            registration_id = data.get("registration_id", "").strip()
            if not registration_id:
                self._send(_render_registration_page("Registration ID is required."), status=400)
                return
            message = "Registration processed successfully."
            try:
                processed_registration = finish_registration(
                    registration_id=registration_id,
                    store=_build_registration_store(self.registration_db_path),
                )
                message = (
                    "Registration validated successfully."
                    if processed_registration.status.value == "VALID"
                    else "Registration finished with validation errors."
                )
            except Exception as exc:  # noqa: BLE001
                message = str(exc)
            try:
                registration, current_entry, events = _load_registration_detail(
                    registration_id=registration_id,
                    database_path=self.registration_db_path,
                )
            except ValueError as exc:
                self._send(_render_registration_page(str(exc)), status=404)
                return
            self._send(
                _render_registration_detail(
                    registration=registration,
                    current_entry=current_entry,
                    events=events,
                    message=message,
                )
            )
            return

        if self.path == "/register/revalidate":
            length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(length).decode("utf-8")
            data = {key: values[0] for key, values in parse_qs(body).items()}
            registration_id = data.get("registration_id", "").strip()
            if not registration_id:
                self._send(_render_registration_page("Registration ID is required."), status=400)
                return
            message = "Registration revalidated successfully."
            try:
                processed_registration = revalidate_registration(
                    registration_id=registration_id,
                    store=_build_registration_store(self.registration_db_path),
                )
                message = (
                    "Registration revalidated successfully."
                    if processed_registration.status.value == "VALID"
                    else "Registration revalidation finished with validation errors."
                )
            except Exception as exc:  # noqa: BLE001
                message = str(exc)
            try:
                registration, current_entry, events = _load_registration_detail(
                    registration_id=registration_id,
                    database_path=self.registration_db_path,
                )
            except ValueError as exc:
                self._send(_render_registration_page(str(exc)), status=404)
                return
            self._send(
                _render_registration_detail(
                    registration=registration,
                    current_entry=current_entry,
                    events=events,
                    message=message,
                )
            )
            return

        if self.path == "/registry/refresh":
            try:
                summary = refresh_active_registrations(
                    store=_build_registration_store(self.registration_db_path),
                )
                self._send(
                    _render_registry_overview(
                        rows=_load_registry_overview(self.registration_db_path),
                        summary=_summary_to_dict(summary),
                        message="Batch refresh finished.",
                    )
                )
            except Exception as exc:  # noqa: BLE001
                self._send(
                    _render_registry_overview(
                        rows=_load_registry_overview(self.registration_db_path),
                        summary=None,
                        message=str(exc),
                    ),
                    status=200,
                )
            return

        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length).decode("utf-8")
        data = {key: values[0] for key, values in parse_qs(body).items()}

        try:
            request = _build_request_from_form(data, self.output_dir)
            result = execute_adapter_request(request=request, generator=_ADAPTER_GENERATOR)
        except Exception as exc:  # noqa: BLE001
            self._send(_render_form(str(exc)), status=200)
            return

        output_path = Path(result.output_path)
        type(self).last_output_path = output_path
        contents = output_path.read_text(encoding="utf-8")
        report_parts = [part for part in [result.stdout.strip(), result.stderr.strip()] if part]
        self._send(
            _render_result(
                file_name=output_path.name,
                file_contents=contents,
                report="\n\n".join(report_parts),
            )
        )


def run_server(host: str = "127.0.0.1", port: int = 8001, output_dir: str = ".") -> None:
    """Start the local HTTP server for the web metadata generation flow."""
    handler = _Handler
    handler.output_dir = Path(output_dir)
    handler.last_output_path = Path(output_dir) / METADATA_FILENAME
    handler.registration_db_path = (
        Path(output_dir) / core_settings.default_registry_db_path
    )
    server = HTTPServer((host, port), handler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
