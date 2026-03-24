"""HTML page builders for the lightweight metadata generation web UI."""

from __future__ import annotations

import html
import json
from typing import Any


def render_form(message: str = "", preload_state: dict[str, Any] | None = None) -> str:
    """Render the main multi-step metadata generation form."""
    notice = f"<div class='notice'>{html.escape(message)}</div>" if message else ""
    bootstrap = ""
    if preload_state is not None:
        payload = json.dumps(preload_state).replace("</", "<\\/")
        bootstrap = (
            "<script id='preloaded_state' type='application/json'>"
            f"{payload}"
            "</script>"
        )
    return (
        _TEMPLATE.replace("{{NOTICE}}", notice)
        .replace("{{BOOTSTRAP}}", bootstrap)
        .replace("{{SCRIPT}}", _FORM_SCRIPT)
    )


def render_start_page(message: str = "") -> str:
    """Render the web UI landing page and preload uploader."""
    notice = f"<div class='notice'>{html.escape(message)}</div>" if message else ""
    return f"""<!doctype html>
<html>
  <head>
    <meta charset="utf-8">
    <title>BioCypher Metadata Generator</title>
    <style>
      :root {{
        --bg: #0b1220;
        --panel: #111827;
        --panel-2: #172133;
        --ink: #e5edf6;
        --muted: #93a1b2;
        --accent: #60a5fa;
        --accent-2: #3b82f6;
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
      .wrap {{ max-width: 1100px; margin: 0 auto; }}
      .hero {{
        display: grid;
        gap: 1rem;
        margin-bottom: 1.5rem;
      }}
      h1 {{ font-size: 2.2rem; margin: 0; }}
      .subtitle {{ color: var(--muted); max-width: 48rem; }}
      .grid {{
        display: grid;
        grid-template-columns: repeat(4, minmax(0, 1fr));
        gap: 1rem;
      }}
      .card {{
        background: linear-gradient(180deg, rgba(255,255,255,0.02), transparent 60%), var(--panel);
        border: 1px solid var(--line);
        border-radius: 18px;
        padding: 1.4rem;
      }}
      .card.resume {{
        border-color: rgba(96, 165, 250, 0.36);
        box-shadow: 0 0 0 1px rgba(96, 165, 250, 0.12) inset;
      }}
      .eyebrow {{
        color: var(--muted);
        font-size: 0.82rem;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        margin-bottom: 0.6rem;
      }}
      h2 {{ margin: 0 0 0.55rem 0; font-size: 1.25rem; }}
      p {{ color: var(--muted); margin: 0 0 1rem 0; line-height: 1.5; }}
      .session-note {{
        display: none;
        margin: 0 0 0.9rem 0;
        padding: 0.65rem 0.8rem;
        border-radius: 10px;
        background: rgba(96, 165, 250, 0.12);
        color: #bfdbfe;
        font-size: 0.95rem;
      }}
      .session-note.empty {{
        background: rgba(148, 163, 184, 0.12);
        color: #cbd5e1;
      }}
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
      .notice {{
        background: rgba(245, 158, 11, 0.14);
        border: 1px solid rgba(245, 158, 11, 0.24);
        padding: 0.75rem 1rem;
        border-radius: 10px;
        margin-bottom: 1rem;
      }}
      @media (max-width: 800px) {{
        .grid {{ grid-template-columns: 1fr; }}
      }}
    </style>
  </head>
  <body>
    <div class="wrap">
      <div class="hero">
        <h1>BioCypher Metadata Generator</h1>
        <div class="subtitle">Choose how you want to begin. You can preload adapter metadata and continue refining datasets and fields, or start with an empty questionnaire.</div>
      </div>
      {notice}
      <div class="grid">
        <div class="card resume">
          <div class="eyebrow">Continue</div>
          <h2>Resume previous session</h2>
          <p>Open the questionnaire with the metadata already saved in this browser and continue from where you left off.</p>
          <div id="session_note" class="session-note">A saved session is available in this browser.</div>
          <a class="button" id="resume_button" href="/?form=1">Resume previous session</a>
        </div>
        <div class="card">
          <div class="eyebrow">Registry</div>
          <h2>Register an adapter</h2>
          <p>Submit an adapter name and repository location to create a tracked registration request in the registry database.</p>
          <a class="button" href="/register">Open registration form</a>
        </div>
        <div class="card">
          <div class="eyebrow">Recommended</div>
          <h2>Preload metadata yaml</h2>
          <p>Load adapter metadata, creators, and datasets from a YAML file that follows the current config schema, then continue editing.</p>
          <form method="post" action="/preload" enctype="multipart/form-data">
            <input type="file" name="metadata_yaml" accept=".yaml,.yml" required style="margin: 0 0 0.9rem 0;">
            <div>
              <button class="button" type="submit">Preload metadata yaml</button>
            </div>
          </form>
        </div>
        <div class="card">
          <div class="eyebrow">Blank Start</div>
          <h2>Start from scratch</h2>
          <p>Open the questionnaire with empty fields and build the metadata file step by step from the beginning.</p>
          <a class="button ghost" id="scratch_button" href="/?mode=scratch&clear=1">Start from scratch</a>
        </div>
      </div>
    </div>
    <script>
      (function() {{
        const key = 'biocypher_form_state_new';
        const note = document.getElementById('session_note');
        const resumeButton = document.getElementById('resume_button');
        const hasSavedState = (() => {{
          try {{
            const raw = localStorage.getItem(key);
            if (!raw) return false;
            const state = JSON.parse(raw);
            return Boolean(
              state &&
              (
                state.name ||
                (Array.isArray(state.creators) && state.creators.length) ||
                (Array.isArray(state.datasets) && state.datasets.length)
              )
            );
          }} catch (err) {{
            localStorage.removeItem(key);
            return false;
          }}
        }})();
        note.style.display = 'block';
        if (!hasSavedState) {{
          note.textContent = 'No saved session was found in this browser yet.';
          note.classList.add('empty');
          resumeButton.setAttribute('aria-disabled', 'true');
          resumeButton.style.pointerEvents = 'none';
          resumeButton.style.opacity = '0.55';
        }}
      }})();
    </script>
  </body>
</html>"""


# Copied shell/template to preserve legacy look-and-feel without importing legacy runtime logic.
_TEMPLATE = r"""
<!doctype html>
<html>
  <head>
    <meta charset="utf-8">
    <title>BioCypher Metadata Generator</title>
    <style>
      :root {
        --bg: #0f1722;
        --panel: #161f2b;
        --panel-2: #1c2735;
        --ink: #e8eef5;
        --muted: #9aa8b7;
        --accent: #60a5fa;
        --accent-2: #3b82f6;
        --accent-soft: rgba(96, 165, 250, 0.14);
        --line: #2d3948;
        --glow: rgba(96, 165, 250, 0.18);
        --success: #4ade80;
        --success-soft: rgba(74, 222, 128, 0.12);
        --warning: #f59e0b;
        --warning-soft: rgba(245, 158, 11, 0.14);
        --draft: #60a5fa;
        --draft-soft: rgba(96, 165, 250, 0.12);
        --neutral-soft: rgba(148, 163, 184, 0.12);
      }
      body.light {
        --bg: #f6f8fb;
        --panel: #ffffff;
        --panel-2: #eef2f7;
        --ink: #17202a;
        --muted: #5f6c7b;
        --accent: #2563eb;
        --accent-2: #1d4ed8;
        --accent-soft: #e8f0ff;
        --line: #d7dee8;
        --glow: rgba(37, 99, 235, 0.14);
        --success: #15803d;
        --success-soft: #e8f7ec;
        --warning: #b45309;
        --warning-soft: #fff4e5;
        --draft: #2563eb;
        --draft-soft: #e8f0ff;
        --neutral-soft: #eceff3;
        background: linear-gradient(180deg, #f6f8fb 0%, #ffffff 100%);
      }
      * { box-sizing: border-box; }
      body {
        font-family: "IBM Plex Sans", "Segoe UI", "Helvetica Neue", sans-serif;
        background: radial-gradient(1200px 800px at 10% -10%, #1a2740 0%, var(--bg) 46%);
        color: var(--ink);
        margin: 0;
        padding: 2.25rem 1.5rem;
      }
      .wrap { max-width: 1100px; margin: 0 auto; }
      h1 { font-size: 2rem; line-height: 1.15; margin: 0 0 0.35rem 0; font-weight: 700; }
      .subtitle { color: var(--muted); margin-bottom: 1.75rem; font-size: 0.95rem; line-height: 1.5; }
      .steps { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 1rem; margin: 1.25rem 0 1.75rem 0; }
      .step { position: relative; padding-left: 2.75rem; color: var(--muted); font-size: 0.92rem; font-weight: 500; }
      .step::before { content: attr(data-step-num); position: absolute; left: 0; top: -0.1rem; width: 2rem; height: 2rem; border-radius: 999px; display: grid; place-items: center; background: var(--panel-2); border: 1px solid var(--line); color: var(--muted); box-shadow: inset 0 0 0 1px rgba(255,255,255,0.03); }
      .step.active { color: var(--ink); }
      .step.active::before { background: var(--accent); color: #0b1020; box-shadow: 0 0 0 3px var(--glow); }
      .section { background: var(--panel); border: 1px solid var(--line); border-radius: 14px; padding: 1.25rem 1.25rem 1rem 1.25rem; margin: 1.25rem 0; box-shadow: 0 8px 24px rgba(0, 0, 0, 0.35); }
      .section h2 { margin: 0 0 0.5rem 0; color: var(--ink); font-size: 1.35rem; line-height: 1.25; font-weight: 700; }
      .subsection { margin-top: 1rem; padding: 1rem 1rem 0.95rem 1rem; border: 1px solid var(--line); border-radius: 12px; background: linear-gradient(180deg, rgba(255,255,255,0.02), transparent 60%), var(--panel); }
      body.light .subsection { background: linear-gradient(180deg, rgba(255,255,255,0.58), rgba(255,255,255,0.9)); }
      .subsection-title { display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 0.5rem; margin: 0 0 0.2rem 0; }
      .subsection-title h3 { margin: 0; font-size: 1.02rem; line-height: 1.3; color: var(--ink); font-weight: 600; }
      .subsection-toggle { margin-top: 0; padding: 0.32rem 0.68rem; border-radius: 8px; font-size: 0.78rem; font-weight: 500; }
      .subsection-note { color: var(--muted); font-size: 0.88rem; line-height: 1.45; margin: 0 0 0.85rem 0; }
      .step-intro {
        display: grid;
        grid-template-columns: repeat(3, minmax(0, 1fr));
        gap: 0.8rem;
        margin-top: 0.9rem;
      }
      .step-intro-card {
        border: 1px solid var(--line);
        border-radius: 12px;
        background: var(--panel-2);
        padding: 0.9rem 0.95rem;
      }
      .step-intro-kicker {
        color: var(--muted);
        font-size: 0.72rem;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        margin-bottom: 0.3rem;
      }
      .step-intro-title {
        font-size: 0.96rem;
        font-weight: 700;
        color: var(--ink);
        margin-bottom: 0.24rem;
      }
      .step-intro-copy {
        color: var(--muted);
        font-size: 0.84rem;
        line-height: 1.45;
      }
      .overview-toolbar {
        display: flex;
        flex-wrap: wrap;
        align-items: center;
        justify-content: space-between;
        gap: 0.75rem;
        margin: 0.4rem 0 0.2rem 0;
      }
      .overview-summary {
        display: flex;
        flex-wrap: wrap;
        gap: 0.45rem;
        align-items: center;
      }
      .overview-hint {
        color: var(--muted);
        font-size: 0.84rem;
      }
      .selected-overview-row {
        box-shadow: inset 3px 0 0 var(--accent);
        background: var(--accent-soft);
      }
      .recordset-card {
        margin-top: 0.85rem;
        padding: 0.9rem 0.95rem;
        border: 1px solid var(--line);
        border-radius: 12px;
        background: var(--panel-2);
      }
      .recordset-card label { margin-top: 0; }
      .dataset-layout { display: grid; gap: 1rem; }
      .dataset-settings-strip { display: flex; flex-wrap: wrap; align-items: end; gap: 1rem; padding: 0.95rem 1rem; border: 1px solid var(--line); border-radius: 12px; background: var(--panel-2); margin-top: 0.9rem; }
      .dataset-settings-strip label { margin-top: 0; flex: 1 1 18rem; }
      .editor-card, .dataset-list-card { border: 1px solid var(--line); border-radius: 14px; padding: 1rem; }
      .editor-card { background: linear-gradient(180deg, rgba(255,255,255,0.02), transparent 70%), var(--panel); }
      .dataset-list-card { background: var(--panel-2); }
      body.light .editor-card { background: linear-gradient(180deg, rgba(255,255,255,0.58), rgba(255,255,255,0.94)); }
      .editor-header { display: flex; flex-wrap: wrap; align-items: start; justify-content: space-between; gap: 0.8rem; margin-bottom: 0.9rem; }
      .editor-title { margin: 0; font-size: 1.02rem; font-weight: 700; color: var(--ink); }
      .editor-copy { color: var(--muted); font-size: 0.88rem; line-height: 1.45; margin: 0.2rem 0 0 0; max-width: 40rem; }
      .editor-actions { display: flex; flex-wrap: wrap; gap: 0.6rem; }
      .editor-actions button { margin-top: 0; }
      .subtle-separator { height: 1px; background: var(--line); margin: 0.95rem 0; opacity: 0.7; }
      .field-group-title { margin: 0 0 0.2rem 0; font-size: 0.92rem; font-weight: 700; color: var(--ink); }
      .field-group-copy { margin: 0 0 0.75rem 0; color: var(--muted); font-size: 0.85rem; line-height: 1.45; }
      .dataset-summary { display: flex; flex-wrap: wrap; align-items: center; gap: 0.55rem; margin: 0.25rem 0 0.9rem 0; }
      .summary-pill, .meta-pill { display: inline-flex; align-items: center; gap: 0.3rem; padding: 0.22rem 0.6rem; border-radius: 999px; border: 1px solid var(--line); background: var(--panel); color: var(--muted); font-size: 0.76rem; font-weight: 600; }
      .meta-pill { margin-right: 0.35rem; margin-top: 0.35rem; }
      .dataset-row-title { font-size: 0.98rem; font-weight: 700; color: var(--ink); margin-bottom: 0.15rem; }
      .dataset-row-desc { color: var(--muted); font-size: 0.86rem; line-height: 1.45; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
      .dataset-source { color: var(--ink); font-size: 0.86rem; word-break: break-word; }
      .row-highlight { box-shadow: inset 3px 0 0 var(--accent); background: var(--accent-soft); }
      .field-example-cell { white-space: normal; overflow-wrap: anywhere; word-break: break-word; max-width: 22rem; }
      .field-description-input { min-width: 14rem; }
      .creator-list { display: grid; gap: 0.75rem; margin-top: 0.9rem; }
      .creator-item { display: flex; flex-wrap: wrap; align-items: start; justify-content: space-between; gap: 0.8rem; padding: 0.85rem 0.9rem; border: 1px solid var(--line); border-radius: 12px; background: var(--panel-2); }
      .creator-item-main { min-width: 14rem; flex: 1 1 16rem; }
      .creator-item-name { font-weight: 700; color: var(--ink); }
      .creator-item-meta { color: var(--muted); font-size: 0.84rem; margin-top: 0.2rem; line-height: 1.4; word-break: break-word; }
      .creator-item-actions { display: flex; flex-wrap: wrap; gap: 0.5rem; }
      .creator-item-actions button { margin-top: 0; padding: 0.42rem 0.7rem; font-size: 0.82rem; }
      .selected-dataset-card { display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 0.75rem; margin: 0.25rem 0 0.85rem 0; padding: 0.8rem 0.9rem; border: 1px solid var(--line); border-radius: 12px; background: var(--panel-2); }
      .selected-dataset-label { color: var(--muted); font-size: 0.79rem; text-transform: uppercase; letter-spacing: 0.04em; margin-bottom: 0.16rem; }
      .selected-dataset-name { font-size: 1rem; font-weight: 600; color: var(--ink); }
      .field-toolbar { display: flex; flex-wrap: wrap; align-items: end; gap: 0.85rem; margin-bottom: 0.85rem; }
      .field-toolbar .grow { flex: 1 1 18rem; min-width: 16rem; }
      .field-toolbar .actions { margin-left: auto; }
      .detected-fields-body.collapsed { display: none; }
      label { display: block; margin-top: 0.75rem; font-weight: 600; font-size: 0.92rem; }
      input, textarea, select { width: 100%; padding: 0.62rem 0.72rem; border-radius: 10px; border: 1px solid var(--line); background: #132030; color: var(--ink); margin-top: 0.35rem; pointer-events: auto; user-select: text; caret-color: var(--ink); font-size: 0.95rem; }
      input:focus, textarea:focus, select:focus { outline: none; border-color: var(--accent); box-shadow: 0 0 0 3px var(--glow); }
      body.light input, body.light textarea, body.light select { border: 1px solid #cfd8e3; background: #ffffff; color: var(--ink); }
      .badge { display: inline-block; font-size: 0.74rem; padding: 0.15rem 0.5rem; border-radius: 999px; margin-left: 0.4rem; }
      .req { background: var(--accent); color: #fff; }
      .opt { background: var(--neutral-soft); color: var(--muted); }
      .rec { background: var(--warning-soft); color: var(--warning); }
      .actions { display: flex; gap: 0.75rem; justify-content: flex-end; }
      button { background: var(--accent); color: #f8fafc; border: none; padding: 0.62rem 1rem; border-radius: 10px; font-size: 0.92rem; font-weight: 500; line-height: 1.2; cursor: pointer; margin-top: 1rem; }
      button:hover { background: var(--accent-2); }
      .ghost { background: transparent; color: var(--muted); border: 1px solid var(--line); }
      .ghost:hover { background: var(--neutral-soft); }
      .button { display: inline-block; text-decoration: none; background: var(--accent); color: #f8fafc; border-radius: 10px; padding: 0.62rem 1rem; border: 1px solid transparent; margin-top: 1rem; font-size: 0.92rem; font-weight: 500; }
      .button.ghost { background: transparent; color: var(--ink); border: 1px solid var(--line); }
      .step-panel { display: none; }
      .step-panel.active { display: block; }
      .list { margin-top: 0.75rem; padding-left: 1.25rem; }
      .grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 0.75rem; }
      .note { color: var(--muted); font-size: 0.88rem; line-height: 1.45; }
      .status-row { display: flex; flex-wrap: wrap; align-items: center; gap: 0.5rem; margin: 0.25rem 0 0.1rem 0; }
      .status-pill { display: inline-flex; align-items: center; gap: 0.35rem; font-size: 0.74rem; padding: 0.25rem 0.65rem; border-radius: 999px; border: 1px solid var(--line); background: var(--panel-2); }
      .status-pill.pending { color: var(--warning); border-color: var(--warning-soft); background: var(--warning-soft); }
      .status-pill.detailed { color: var(--success); border-color: var(--success-soft); background: var(--success-soft); }
      .status-pill.skipped { color: var(--muted); border-color: var(--neutral-soft); background: var(--neutral-soft); }
      .status-pill.draft { color: var(--draft); border-color: var(--draft-soft); background: var(--draft-soft); }
      .tiny-badge { display: inline-flex; align-items: center; font-size: 0.72rem; padding: 0.14rem 0.45rem; border-radius: 999px; border: 1px solid var(--draft-soft); color: var(--draft); background: var(--draft-soft); margin-left: 0.45rem; }
      .table-wrap { margin-top: 0.75rem; border: 1px solid var(--line); border-radius: 14px; overflow: hidden; background: var(--panel-2); }
      table { width: 100%; border-collapse: collapse; }
      th, td { text-align: left; padding: 0.8rem 0.9rem; border-bottom: 1px solid var(--line); vertical-align: top; }
      th { font-size: 0.78rem; font-weight: 600; color: var(--muted); letter-spacing: 0.03em; }
      .table-actions { display: flex; flex-wrap: wrap; gap: 0.5rem; }
      .table-actions button { margin-top: 0; padding: 0.4rem 0.66rem; font-size: 0.82rem; }
      .editing-banner { display: none; margin: 0.85rem 0; padding: 0.8rem 0.95rem; border-radius: 12px; border: 1px solid var(--accent-soft); background: var(--accent-soft); }
      .editing-banner.active { display: block; }
      .editing-title { font-weight: 700; margin-bottom: 0.2rem; }
      .editing-text { color: var(--muted); font-size: 0.88rem; }
      .mode-note { margin-top: 0.75rem; padding: 0.8rem 0.95rem; border-radius: 12px; border: 1px solid var(--line); background: var(--panel-2); color: var(--muted); }
      .nested-editor { margin-top: 0.9rem; padding: 0.9rem; border: 1px solid var(--line); border-radius: 12px; background: var(--panel-2); }
      .notice { background: var(--warning-soft); border: 1px solid rgba(180, 83, 9, 0.18); padding: 0.75rem 1rem; border-radius: 10px; margin-bottom: 1rem; }
      .scroll-panel { max-height: 140rem; overflow: auto; border: 1px solid var(--line); border-radius: 12px; background: var(--panel-2); margin-top: 0.75rem; }
      .help-button { display: inline-flex; align-items: center; justify-content: center; min-width: 2rem; padding: 0.3rem 0.55rem; margin-top: 0; border-radius: 999px; font-size: 0.85rem; line-height: 1; }
      .example-help { position: relative; display: inline-flex; align-items: center; }
      .example-tooltip { position: absolute; left: 0; top: calc(100% + 0.45rem); z-index: 20; min-width: 14rem; max-width: 28rem; padding: 0.65rem 0.75rem; border-radius: 10px; border: 1px solid var(--line); background: var(--panel); color: var(--ink); box-shadow: 0 12px 30px rgba(0, 0, 0, 0.24); white-space: normal; word-break: break-word; opacity: 0; pointer-events: none; transform: translateY(4px); transition: opacity 120ms ease, transform 120ms ease; }
      .example-help:hover .example-tooltip, .example-help:focus-within .example-tooltip { opacity: 1; transform: translateY(0); }
      .topbar { display: flex; justify-content: flex-end; align-items: center; gap: 0.85rem; margin-bottom: 0.5rem; }
      .switch-wrap { display: inline-flex; align-items: center; gap: 0.65rem; color: var(--muted); font-size: 0.92rem; }
      .theme-switch { position: relative; width: 3.35rem; height: 1.9rem; display: inline-block; }
      .theme-switch input { position: absolute; opacity: 0; width: 0; height: 0; }
      .theme-slider { position: absolute; inset: 0; cursor: pointer; background: var(--panel-2); border: 1px solid var(--line); border-radius: 999px; transition: background 150ms ease, border-color 150ms ease; }
      .theme-slider::before { content: ""; position: absolute; width: 1.35rem; height: 1.35rem; left: 0.2rem; top: 0.2rem; border-radius: 50%; background: var(--accent); box-shadow: 0 2px 10px rgba(0, 0, 0, 0.22); transition: transform 150ms ease, background 150ms ease; }
      .theme-switch input:checked + .theme-slider::before { transform: translateX(1.4rem); }
      .theme-switch input:focus + .theme-slider { box-shadow: 0 0 0 3px var(--glow); }
      .muted-cell { color: var(--muted); }
      .sr-only { position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px; overflow: hidden; clip: rect(0, 0, 0, 0); white-space: nowrap; border: 0; }
      @media (max-width: 800px) { .field-toolbar { flex-direction: column; align-items: stretch; } .table-wrap { overflow-x: auto; } table { min-width: 760px; } .grid-2 { grid-template-columns: 1fr; } .editor-header { flex-direction: column; } .step-intro { grid-template-columns: 1fr; } }
    </style>
  </head>
  <body>
    <div class="wrap">
    <div class="topbar">
      <button type="button" class="ghost" onclick="window.location.href='/'">Return to landing page</button>
      <button type="button" class="ghost" id="clear_state" onclick="clearState()">Clear saved data</button>
      <div class="switch-wrap">
        <span id="theme_label">Dark mode</span>
        <label class="theme-switch" for="theme_toggle">
          <input type="checkbox" id="theme_toggle" onchange="toggleTheme()">
          <span class="theme-slider"></span>
        </label>
      </div>
    </div>
    <h1>BioCypher Metadata Generator</h1>
    <div class="subtitle">Create a Croissant metadata file with a guided form.</div>
    <div class="note" id="theme_status"></div>
    {{NOTICE}}
    {{BOOTSTRAP}}
    <div class="steps">
      <div class="step active" data-step="0" data-step-num="1">Adapter</div>
      <div class="step" data-step="1" data-step-num="2">Datasets</div>
      <div class="step" data-step="2" data-step-num="3">Dataset Details</div>
      <div class="step" data-step="3" data-step-num="4">Validate & Download</div>
    </div>
    <form method="post" action="/">
      <input type="hidden" name="creators_data" id="creators_data" value="">
      <input type="hidden" name="datasets_data" id="datasets_data" value="">
      <input type="hidden" name="validate" id="validate" value="true">
      <input type="hidden" name="output" id="output" value="croissant_adapter.jsonld">
      <input type="hidden" name="adapter_id" id="adapter_id" value="">
      <div class="section step-panel active" data-panel="0">
        <h2>Adapter</h2>
        <label>Name <span class="badge req">required</span><input name="name" required></label>
        <div class="mode-note">
          <strong>Adapter ID</strong>
          <div id="adapter_id_display">-</div>
        </div>
        <label>Description <span class="badge req">required</span><input name="description" required></label>
        <label>Version <span class="badge req">required</span><input name="version" required></label>
        <label>License (URL or SPDX) <span class="badge req">required</span><input name="license" required></label>
        <label>Code repository URL <span class="badge req">required</span><input name="code_repository" required></label>
        <label>Keywords (comma-separated) <span class="badge req">required</span><input name="keywords" required></label>
        <div class="section">
          <h2>Creators</h2>
          <div class="note" id="creator_meta_status">Add a creator to begin.</div>
          <div class="editing-banner" id="creator_edit_banner">
            <div class="editing-title" id="creator_edit_title">Editing creator</div>
            <div class="editing-text">Update the fields below and click Update creator to save your changes.</div>
          </div>
          <div class="grid-2">
            <label>Name <span class="badge req">required</span><input id="creator_name"></label>
            <label>Affiliation <span class="badge opt">optional</span><input id="creator_affiliation"></label>
          </div>
          <label>ORCID <span class="badge opt">optional</span><input id="creator_orcid"></label>
          <div class="actions">
            <button type="button" id="add_creator">Add creator</button>
            <button type="button" class="ghost" id="clear_creator_form">Clear form</button>
          </div>
          <div class="table-wrap"><table><thead><tr><th>Name</th><th>Affiliation</th><th>ORCID</th><th>Preview</th><th>Remove</th></tr></thead><tbody id="creators_table"></tbody></table></div>
        </div>
        <div class="actions"><button type="button" class="ghost" data-prev>Back</button><button type="button" data-next>Next</button></div>
      </div>
      <div class="section step-panel" data-panel="1">
        <h2>Datasets</h2>
        <div class="note">Add each dataset first. Details are added in the next step.</div>
        <div class="dataset-layout">
          <div class="dataset-settings-strip">
            <label>Dataset generator <span class="badge rec">recommended</span>
              <select id="dataset_generator" name="dataset_generator">
                <option value="croissant-baker">croissant-baker</option>
                <option value="native">native</option>
                <option value="auto">auto</option>
              </select>
            </label>
            <div class="note" id="dataset_meta_status">Add a dataset to begin.</div>
          </div>

          <div class="editor-card">
            <div class="editor-header">
              <div>
                <h3 class="editor-title">Dataset Editor</h3>
                <p class="editor-copy">Choose the dataset mode, provide the source, and fill in the reusable metadata before adding the dataset to the list.</p>
              </div>
              <div class="editor-actions">
                <button type="button" id="add_dataset">Add dataset</button>
                <button type="button" class="ghost" id="clear_dataset_form">Cancel editing</button>
              </div>
            </div>
            <div class="editing-banner" id="dataset_edit_banner"><div class="editing-title" id="dataset_edit_title">Editing dataset</div><div class="editing-text">Update the fields below and click Update dataset to save your changes.</div></div>

            <div class="field-group-title">Source</div>
            <p class="field-group-copy">Choose the mode first so the editor matches how the backend will treat this dataset.</p>
            <label>Dataset mode <span class="badge req">required</span>
              <select id="ds_mode">
                <option value="generate">generate</option>
                <option value="existing">existing</option>
              </select>
            </label>
            <div class="grid-2">
              <label id="ds_input_wrap">Input path <span class="badge rec">recommended</span><input id="ds_input_path" placeholder="data/in/sample_networks_omnipath.tsv"></label>
              <label id="ds_existing_wrap">Existing dataset path <span class="badge rec">recommended</span><input id="ds_existing_path" placeholder="/path/to/dataset.jsonld"></label>
            </div>

            <div class="subtle-separator"></div>

            <div class="field-group-title">Core metadata</div>
            <p class="field-group-copy">These values are carried into dataset generation or attached to the existing dataset reference.</p>
            <label>Dataset name <span class="badge req">required</span><input id="ds_name"></label>
            <label>Description <span class="badge req">required</span><input id="ds_description"></label>
            <div class="grid-2">
              <label>Version <span class="badge req">required</span><input id="ds_version"></label>
              <label>License <span class="badge req">required</span><input id="ds_license"></label>
            </div>
            <label>URL <span class="badge req">required</span><input id="ds_url"></label>

            <div class="subtle-separator"></div>

            <div class="field-group-title">Publication</div>
            <p class="field-group-copy">Add publication and citation details once here instead of in the dataset details page.</p>
            <div class="grid-2">
              <label>Date published <span class="badge rec">recommended</span><input id="ds_date"></label>
              <label>Citation (DOI or string) <span class="badge rec">recommended</span><input id="ds_cite"></label>
            </div>

            <div class="subtle-separator"></div>

            <div class="field-group-title">Dataset creators</div>
            <p class="field-group-copy">Manage dataset creators separately from adapter creators. These values are stored with the selected dataset.</p>
            <div class="note" id="dataset_creator_meta_status">Add a dataset creator to begin.</div>
            <div class="editing-banner" id="dataset_creator_edit_banner">
              <div class="editing-title" id="dataset_creator_edit_title">Editing dataset creator</div>
              <div class="editing-text">Update the fields below and click Update dataset creator to save your changes.</div>
            </div>
            <div class="grid-2">
              <label>Creator type <span class="badge req">required</span>
                <select id="dataset_creator_type">
                  <option value="Person">Person</option>
                  <option value="Organization">Organization</option>
                </select>
              </label>
              <label>Name <span class="badge req">required</span><input id="dataset_creator_name"></label>
            </div>
            <div class="grid-2">
              <label>Affiliations <span class="badge opt">optional</span><input id="dataset_creator_affiliations" placeholder="Institute A, Lab B"></label>
              <label>Email <span class="badge opt">optional</span><input id="dataset_creator_email"></label>
            </div>
            <label>URL <span class="badge opt">optional</span><input id="dataset_creator_url"></label>
            <div class="actions">
              <button type="button" id="add_dataset_creator">Add dataset creator</button>
              <button type="button" class="ghost" id="clear_dataset_creator_form">Clear form</button>
            </div>
            <div class="creator-list" id="dataset_creators_table"></div>
          </div>

          <div class="dataset-list-card">
            <div class="editor-header">
              <div>
                <h3 class="editor-title">Dataset List</h3>
                <p class="editor-copy">Review the datasets already added, reopen one in the editor, or clear the list before continuing.</p>
              </div>
              <div class="editor-actions">
                <button type="button" class="ghost" id="clear_datasets">Clear list</button>
              </div>
            </div>
            <div class="dataset-summary" id="dataset_summary"></div>
            <div class="table-wrap"><table><thead><tr><th>Dataset</th><th>Mode</th><th>Source</th><th>Status</th><th>Actions</th></tr></thead><tbody id="dataset_meta_table"></tbody></table></div>
          </div>
        </div>
        <div class="actions"><button type="button" class="ghost" data-prev>Back</button><button type="button" data-next>Next</button></div>
      </div>
      <div class="section step-panel" data-panel="2">
        <h2>Dataset Details</h2>
        <div class="note">Select one dataset, review the generated metadata, and refine fields before moving to validation.</div>
        <div class="step-intro">
          <div class="step-intro-card">
            <div class="step-intro-kicker">1. Choose</div>
            <div class="step-intro-title">Pick a dataset</div>
            <div class="step-intro-copy">Start in the overview table. Open one dataset at a time so the rest of the page stays focused.</div>
          </div>
          <div class="step-intro-card">
            <div class="step-intro-kicker">2. Review</div>
            <div class="step-intro-title">Check distribution metadata</div>
            <div class="step-intro-copy">Confirm the file URL, format, checksum, and record set name before adjusting field metadata.</div>
          </div>
          <div class="step-intro-card">
            <div class="step-intro-kicker">3. Refine</div>
            <div class="step-intro-title">Tune fields only if needed</div>
            <div class="step-intro-copy">Most fields will already be inferred. Only change datatypes or descriptions where the defaults are not good enough.</div>
          </div>
        </div>
        <div class="subsection">
          <div class="subsection-title"><h3>Dataset Overview</h3></div>
          <div class="subsection-note">This is the control table for this step. Use it to choose which dataset you are editing right now.</div>
          <div class="overview-toolbar">
            <div class="overview-summary">
              <div class="status-pill pending" id="selected_dataset_status">Pending</div>
              <div class="note" id="dataset_progress">No datasets added yet.</div>
            </div>
            <div class="overview-hint">Open a row to update the sections below.</div>
          </div>
          <div class="table-wrap"><table><thead><tr><th>Dataset</th><th>Status</th><th>Source</th><th>Fields</th><th>Mode</th><th>Actions</th></tr></thead><tbody id="dataset_detail_table"></tbody></table></div>
          <label class="sr-only">Choose dataset<select id="dataset_select"></select></label>
        </div>
        <div class="subsection">
          <div class="subsection-title"><h3>Distribution Metadata</h3></div>
          <div class="subsection-note">These values describe the selected source file and will be included in the generated Croissant metadata.</div>
          <div class="selected-dataset-card"><div><div class="selected-dataset-label">Editing Dataset</div><div class="selected-dataset-name" id="current_dataset_heading">No dataset selected</div></div><div class="note" id="details_status"></div></div>
          <div class="mode-note" id="dataset_mode_note">Select a dataset to continue.</div>
          <div id="dataset_details_form">
          <label>Content URL <span class="badge opt">optional</span><input id="dist_url"></label>
          <label>Encoding format (e.g. text/csv) <span class="badge opt">optional</span><input id="dist_format"></label>
          <label>File name <span class="badge opt">optional</span><input id="dist_name"></label>
          <div class="grid-2"><label>MD5 <span class="badge opt">optional</span><input id="dist_md5"></label><label>SHA-256 <span class="badge opt">optional</span><input id="dist_sha256"></label></div>
          <div class="actions"><button type="button" class="ghost" id="apply_details">Save metadata</button></div>
          </div>
        </div>
        <div class="subsection" id="field_entries_section">
          <div class="subsection-title"><h3>Field Entries</h3></div>
          <div class="subsection-note">Start by confirming the record set name, then scan the inferred fields. Edit only the rows that need a datatype or description correction.</div>
          <div class="recordset-card">
            <label>Record set name <span class="badge opt">optional</span><input id="rs_name"></label>
          </div>
          <div class="subsection-title"><h3>Detected fields</h3><button type="button" class="ghost subsection-toggle" id="toggle_detected_fields" aria-expanded="true">Collapse</button></div>
          <div class="note" id="fields_report_note">No field information is available yet.</div>
          <div class="detected-fields-body" id="detected_fields_body"><div class="scroll-panel"><table><thead><tr><th>Field Name</th><th>Detected type</th><th>Example</th><th>Suggested Datatype</th><th>Description</th></tr></thead><tbody id="fields_report"></tbody></table></div></div>
          <h3>Manual fields (optional)</h3>
          <div class="subsection-note">Use this only when you need to add a field that was not detected automatically.</div>
          <div class="grid-2"><label>Field name <span class="badge opt">optional</span><input id="field_name"></label><label>Data type <span class="badge opt">optional</span><select id="field_type"><option value="sc:Boolean">sc:Boolean</option><option value="sc:CssSelectorType">sc:CssSelectorType</option><option value="sc:Date">sc:Date</option><option value="sc:DateTime">sc:DateTime</option><option value="sc:Float">sc:Float</option><option value="sc:Integer">sc:Integer</option><option value="sc:Number">sc:Number</option><option value="sc:PronounceableText">sc:PronounceableText</option><option value="sc:Text">sc:Text</option><option value="sc:Time">sc:Time</option><option value="sc:URL">sc:URL</option><option value="sc:XPathType">sc:XPathType</option></select></label></div>
          <label>Description <span class="badge opt">optional</span><input id="field_desc"></label>
          <label>Example <span class="badge opt">optional</span><input id="field_example"></label>
          <div class="actions"><button type="button" class="ghost" id="add_field">Add field</button></div>
          <ul class="list" id="fields_list"></ul>
        </div>
        <div class="actions"><button type="button" class="ghost" data-prev>Back</button><button type="button" data-next>Next</button></div>
      </div>
      <div class="section step-panel" data-panel="3">
        <h2>Validate & Download</h2>
        <div class="note">Submit the form to generate and validate your file.</div>
        <div class="actions"><button type="button" class="ghost" data-prev>Back</button><button type="submit">Generate</button></div>
      </div>
    </form>
    </div>
    {{SCRIPT}}
  </body>
</html>
"""


_FORM_SCRIPT = r"""
<script>
  const steps = Array.from(document.querySelectorAll('.step'));
  const panels = Array.from(document.querySelectorAll('.step-panel'));
  let idx = 0;
  function show(i) {
    idx = Math.max(0, Math.min(panels.length - 1, i));
    panels.forEach((p, pi) => p.classList.toggle('active', pi === idx));
    steps.forEach((s, si) => s.classList.toggle('active', si === idx));
  }
  document.querySelectorAll('[data-next]').forEach(btn => btn.addEventListener('click', () => show(idx + 1)));
  document.querySelectorAll('[data-prev]').forEach(btn => btn.addEventListener('click', () => show(idx - 1)));
  steps.forEach((s, i) => s.addEventListener('click', () => show(i)));
  show(0);

  const STORAGE_KEY = 'biocypher_form_state_new';
  const creators = [];
  const datasets = [];
  let currentCreatorIndex = -1;
  let currentDatasetIndex = -1;
  let currentDatasetCreatorIndex = -1;

  function byId(id) { return document.getElementById(id); }
  function escapeHtml(value) {
    return String(value ?? '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  function splitLines(value) {
    return String(value || '').split(/\r?\n/).map(item => item.trim()).filter(Boolean);
  }

  function slugifyId(text) {
    return String(text || '')
      .trim()
      .toLowerCase()
      .replace(/\s+/g, '-')
      .replace(/_/g, '-')
      .replace(/\//g, '-');
  }

  function defaultRecordSetName(dataset) {
    const datasetName = String(dataset?.name || '').trim();
    return datasetName ? `${datasetName} records` : 'records';
  }

  function resolvedRecordSetName(dataset, currentName) {
    const raw = String(currentName || '').trim();
    if (!raw || raw.toLowerCase() === 'records') return defaultRecordSetName(dataset);
    return raw;
  }

  function displayDetectedType(value) {
    const mapping = {
      'sc:Boolean': 'boolean',
      'sc:Integer': 'integer',
      'sc:Float': 'float',
      'sc:Number': 'number',
      'sc:Date': 'date',
      'sc:DateTime': 'datetime',
      'sc:Time': 'time',
      'sc:URL': 'url',
      'sc:Text': 'string',
      'sc:PronounceableText': 'string',
      'sc:CssSelectorType': 'string',
      'sc:XPathType': 'string',
    };
    return mapping[String(value || '').trim()] || String(value || 'string').replace(/^sc:/, '').toLowerCase() || 'string';
  }

  function datatypeOptions(selected) {
    const values = [
      'sc:Boolean',
      'sc:CssSelectorType',
      'sc:Date',
      'sc:DateTime',
      'sc:Float',
      'sc:Integer',
      'sc:Number',
      'sc:PronounceableText',
      'sc:Text',
      'sc:Time',
      'sc:URL',
      'sc:XPathType',
    ];
    return values.map(value => `<option value="${value}" ${value === selected ? 'selected' : ''}>${value}</option>`).join('');
  }

  function syncAdapterId() {
    const nameValue = document.querySelector('[name="name"]')?.value || '';
    const adapterId = slugifyId(nameValue);
    byId('adapter_id').value = adapterId;
    const display = byId('adapter_id_display');
    if (display) display.textContent = adapterId || '-';
  }

  function setTheme(mode) {
    document.body.classList.toggle('light', mode === 'light');
    const toggle = byId('theme_toggle');
    if (toggle) toggle.checked = mode === 'light';
    const label = byId('theme_label');
    if (label) label.textContent = mode === 'light' ? 'Light mode' : 'Dark mode';
    const status = byId('theme_status');
    if (status) status.textContent = `Theme: ${mode}`;
    localStorage.setItem('biocypher_theme_new', mode);
  }
  window.toggleTheme = function toggleTheme() {
    const current = document.body.classList.contains('light') ? 'light' : 'dark';
    setTheme(current === 'light' ? 'dark' : 'light');
  };
  setTheme(localStorage.getItem('biocypher_theme_new') === 'light' ? 'light' : 'dark');

  function readState() {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (!raw) return null;
      return JSON.parse(raw);
    } catch (error) {
      localStorage.removeItem(STORAGE_KEY);
      return null;
    }
  }

  function persistState() {
    syncAdapterId();
    const state = {
      name: document.querySelector('[name="name"]')?.value || '',
      description: document.querySelector('[name="description"]')?.value || '',
      version: document.querySelector('[name="version"]')?.value || '',
      license: document.querySelector('[name="license"]')?.value || '',
      code_repository: document.querySelector('[name="code_repository"]')?.value || '',
      keywords: document.querySelector('[name="keywords"]')?.value || '',
      creators,
      datasets,
    };
    localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
  }

  function syncCreators() {
    byId('creators_data').value = JSON.stringify(creators);
    renderCreatorsTable();
    persistState();
  }

  function syncDatasets() {
    byId('datasets_data').value = JSON.stringify(datasets);
    renderDatasetMetaTable();
    renderDatasetDetailTable();
    updateDatasetSelect();
    persistState();
  }

  function resetCreatorForm() {
    byId('creator_name').value = '';
    byId('creator_affiliation').value = '';
    byId('creator_orcid').value = '';
    currentCreatorIndex = -1;
    byId('add_creator').textContent = 'Add creator';
    byId('creator_edit_banner').classList.remove('active');
  }

  function renderCreatorsTable() {
    const table = byId('creators_table');
    const status = byId('creator_meta_status');
    if (!creators.length) {
      table.innerHTML = '<tr><td colspan="5" class="muted-cell">No creators added yet.</td></tr>';
      status.textContent = 'Add a creator to begin.';
      return;
    }
    status.textContent = 'Add another creator or preview one to edit it.';
    table.innerHTML = creators.map((creator, index) => `
      <tr>
        <td>${escapeHtml(creator.name || '')}</td>
        <td>${escapeHtml(creator.affiliation || '')}</td>
        <td>${escapeHtml(creator.identifier || '')}</td>
        <td><button type="button" data-preview-creator="${index}">Preview</button></td>
        <td><button type="button" class="ghost" data-remove-creator="${index}">Remove</button></td>
      </tr>
    `).join('');
    table.querySelectorAll('[data-preview-creator]').forEach(btn => {
      btn.addEventListener('click', () => {
        const creator = creators[Number(btn.dataset.previewCreator)];
        currentCreatorIndex = Number(btn.dataset.previewCreator);
        byId('creator_name').value = creator.name || '';
        byId('creator_affiliation').value = creator.affiliation || '';
        byId('creator_orcid').value = creator.identifier || '';
        byId('add_creator').textContent = 'Update creator';
        byId('creator_edit_banner').classList.add('active');
      });
    });
    table.querySelectorAll('[data-remove-creator]').forEach(btn => {
      btn.addEventListener('click', () => {
        creators.splice(Number(btn.dataset.removeCreator), 1);
        resetCreatorForm();
        syncCreators();
      });
    });
  }

  byId('add_creator').addEventListener('click', () => {
    const creator = {
      name: byId('creator_name').value.trim(),
      affiliation: byId('creator_affiliation').value.trim(),
      identifier: byId('creator_orcid').value.trim(),
    };
    if (!creator.name) return;
    if (currentCreatorIndex >= 0) creators[currentCreatorIndex] = creator;
    else creators.push(creator);
    resetCreatorForm();
    syncCreators();
  });
  byId('clear_creator_form').addEventListener('click', () => {
    resetCreatorForm();
    renderCreatorsTable();
  });

  function updateDatasetModeFields() {
    const mode = byId('ds_mode').value;
    byId('ds_input_wrap').style.display = mode === 'generate' ? 'block' : 'none';
    byId('ds_existing_wrap').style.display = mode === 'existing' ? 'block' : 'none';
  }

  function resetDatasetForm() {
    byId('ds_mode').value = 'generate';
    byId('ds_input_path').value = '';
    byId('ds_existing_path').value = '';
    byId('ds_name').value = '';
    byId('ds_description').value = '';
    byId('ds_version').value = '';
    byId('ds_license').value = '';
    byId('ds_url').value = '';
    byId('ds_date').value = '';
    byId('ds_cite').value = '';
    currentDatasetIndex = -1;
    byId('add_dataset').textContent = 'Add dataset';
    byId('dataset_edit_banner').classList.remove('active');
    resetDatasetCreatorForm();
    renderDatasetCreatorsTable([]);
    updateDatasetModeFields();
  }

  function currentDatasetCreators() {
    if (currentDatasetIndex >= 0 && datasets[currentDatasetIndex]) {
      const dataset = datasets[currentDatasetIndex];
      dataset.uiCreators = Array.isArray(dataset.uiCreators) ? dataset.uiCreators : [];
      return dataset.uiCreators;
    }
    return [];
  }

  function normalizeDatasetCreator(creator) {
    if (creator && typeof creator === 'object' && !Array.isArray(creator)) {
      return {
        creator_type: String(creator.creator_type || creator.type || 'Person').trim() || 'Person',
        name: String(creator.name || '').trim(),
        affiliations: String(creator.affiliations || creator.affiliation || '').trim(),
        email: String(creator.email || '').trim(),
        url: String(creator.url || '').trim(),
      };
    }
    const raw = String(creator || '').trim();
    if (!raw) {
      return { creator_type: 'Person', name: '', affiliations: '', email: '', url: '' };
    }
    const pipeParts = raw.split('|').map(part => part.trim());
    if (pipeParts[0] && ['person', 'organization'].includes(pipeParts[0].toLowerCase())) {
      return {
        creator_type: pipeParts[0].charAt(0).toUpperCase() + pipeParts[0].slice(1).toLowerCase(),
        name: pipeParts[1] || '',
        affiliations: pipeParts[2] || '',
        email: pipeParts[3] || '',
        url: pipeParts[4] || '',
      };
    }
    const commaParts = raw.split(',').map(part => part.trim());
    return {
      creator_type: 'Person',
      name: commaParts[0] || '',
      affiliations: '',
      email: commaParts[1] || '',
      url: commaParts.slice(2).join(', ').trim(),
    };
  }

  function resetDatasetCreatorForm() {
    byId('dataset_creator_type').value = 'Person';
    byId('dataset_creator_name').value = '';
    byId('dataset_creator_affiliations').value = '';
    byId('dataset_creator_email').value = '';
    byId('dataset_creator_url').value = '';
    currentDatasetCreatorIndex = -1;
    byId('add_dataset_creator').textContent = 'Add dataset creator';
    byId('dataset_creator_edit_banner').classList.remove('active');
  }

  function renderDatasetCreatorsTable(creatorsList) {
    const table = byId('dataset_creators_table');
    const status = byId('dataset_creator_meta_status');
    if (!creatorsList.length) {
      table.innerHTML = '<div class="muted-cell">No dataset creators added yet.</div>';
      status.textContent = 'Add a dataset creator to begin.';
      return;
    }
    status.textContent = 'Add another dataset creator or preview one to edit it.';
    table.innerHTML = creatorsList.map((creator, index) => {
      const normalized = normalizeDatasetCreator(creator);
      const name = normalized.name || '';
      const email = normalized.email || '';
      const url = normalized.url || '';
      const affiliations = normalized.affiliations || '';
      const creatorType = normalized.creator_type || 'Person';
      return `
        <div class="creator-item">
          <div class="creator-item-main">
            <div class="creator-item-name">${escapeHtml(name)} <span class="meta-pill">${escapeHtml(creatorType)}</span></div>
            <div class="creator-item-meta">
              ${affiliations ? `Affiliations: ${escapeHtml(affiliations)}<br>` : ''}
              ${email ? `Email: ${escapeHtml(email)}` : 'No email provided'}
              ${url ? `<br>URL: ${escapeHtml(url)}` : ''}
            </div>
          </div>
          <div class="creator-item-actions">
            <button type="button" data-preview-dataset-creator="${index}">Edit</button>
            <button type="button" class="ghost" data-remove-dataset-creator="${index}">Remove</button>
          </div>
        </div>
      `;
    }).join('');
    table.querySelectorAll('[data-preview-dataset-creator]').forEach(btn => {
      btn.addEventListener('click', () => {
        const creator = normalizeDatasetCreator(
          creatorsList[Number(btn.dataset.previewDatasetCreator)]
        );
        currentDatasetCreatorIndex = Number(btn.dataset.previewDatasetCreator);
        byId('dataset_creator_type').value = creator.creator_type || 'Person';
        byId('dataset_creator_name').value = creator.name || '';
        byId('dataset_creator_affiliations').value = creator.affiliations || '';
        byId('dataset_creator_email').value = creator.email || '';
        byId('dataset_creator_url').value = creator.url || '';
        byId('add_dataset_creator').textContent = 'Update dataset creator';
        byId('dataset_creator_edit_banner').classList.add('active');
      });
    });
    table.querySelectorAll('[data-remove-dataset-creator]').forEach(btn => {
      btn.addEventListener('click', () => {
        const activeCreators = currentDatasetCreators();
        activeCreators.splice(Number(btn.dataset.removeDatasetCreator), 1);
        resetDatasetCreatorForm();
        renderDatasetCreatorsTable(activeCreators);
        syncDatasets();
      });
    });
  }

  function datasetSource(dataset) {
    if (dataset.uiMode === 'existing') return dataset.uiExistingPath || '-';
    if (dataset.uiMode === 'generate') return dataset.uiInputPath || '-';
    return dataset.url || '-';
  }

  function datasetStatusLabel(dataset) {
    const mode = dataset.uiMode || 'manual';
    if (mode === 'existing') return 'attached';
    return dataset.uiStatus || 'pending';
  }

  function escapeStatusClass(value) {
    const normalized = String(value || 'pending').trim().toLowerCase();
    if (['pending', 'detailed', 'draft', 'skipped'].includes(normalized)) return normalized;
    return 'pending';
  }

  function truncateText(value, limit) {
    const text = String(value || '');
    if (text.length <= limit) return text;
    return `${text.slice(0, limit - 1)}…`;
  }

  function renderDatasetMetaTable() {
    const table = byId('dataset_meta_table');
    const status = byId('dataset_meta_status');
    const summary = byId('dataset_summary');
    if (!datasets.length) {
      table.innerHTML = '<tr><td colspan="5" class="muted-cell">No datasets added yet.</td></tr>';
      summary.innerHTML = '';
      status.textContent = 'Add a dataset to begin.';
      return;
    }
    const generateCount = datasets.filter(dataset => (dataset.uiMode || 'generate') === 'generate').length;
    const existingCount = datasets.filter(dataset => dataset.uiMode === 'existing').length;
    summary.innerHTML = `
      <span class="summary-pill">${datasets.length} dataset${datasets.length === 1 ? '' : 's'}</span>
      <span class="summary-pill">${generateCount} generate</span>
      <span class="summary-pill">${existingCount} existing</span>
    `;
    status.textContent = 'Add another dataset or preview one to edit it.';
    table.innerHTML = datasets.map((dataset, index) => `
      <tr class="${currentDatasetIndex === index ? 'row-highlight' : ''}">
        <td>
          <div class="dataset-row-title">${escapeHtml(dataset.name || `Dataset ${index + 1}`)}${currentDatasetIndex === index ? '<span class="tiny-badge">Currently editing</span>' : ''}</div>
          <div class="dataset-row-desc">${escapeHtml(truncateText(dataset.description || '', 180))}</div>
          <div>
            ${dataset.version ? `<span class="meta-pill">Version ${escapeHtml(dataset.version)}</span>` : ''}
            ${dataset.license ? `<span class="meta-pill">${escapeHtml(dataset.license)}</span>` : ''}
          </div>
        </td>
        <td>${escapeHtml(dataset.uiMode || 'manual')}</td>
        <td><div class="dataset-source">${escapeHtml(datasetSource(dataset))}</div></td>
        <td>${escapeHtml(datasetStatusLabel(dataset))}</td>
        <td><div class="table-actions"><button type="button" data-preview-dataset="${index}">Edit</button><button type="button" class="ghost" data-remove-dataset="${index}">Remove</button></div></td>
      </tr>
    `).join('');
    table.querySelectorAll('[data-preview-dataset]').forEach(btn => {
      btn.addEventListener('click', () => loadDatasetMeta(Number(btn.dataset.previewDataset)));
    });
    table.querySelectorAll('[data-remove-dataset]').forEach(btn => {
      btn.addEventListener('click', () => {
        datasets.splice(Number(btn.dataset.removeDataset), 1);
        resetDatasetForm();
        syncDatasets();
      });
    });
  }

  function loadDatasetMeta(index) {
    const dataset = datasets[index];
    if (!dataset) return;
    currentDatasetIndex = index;
    byId('ds_mode').value = dataset.uiMode || 'generate';
    byId('ds_input_path').value = dataset.uiInputPath || '';
    byId('ds_existing_path').value = dataset.uiExistingPath || '';
    byId('ds_name').value = dataset.name || '';
    byId('ds_description').value = dataset.description || '';
    byId('ds_version').value = dataset.version || '';
    byId('ds_license').value = dataset.license || '';
    byId('ds_url').value = dataset.url || '';
    byId('ds_date').value = dataset.datePublished || '';
    byId('ds_cite').value = dataset.citeAs || '';
    byId('add_dataset').textContent = 'Update dataset';
    byId('dataset_edit_banner').classList.add('active');
    resetDatasetCreatorForm();
    renderDatasetCreatorsTable(Array.isArray(dataset.uiCreators) ? dataset.uiCreators : []);
    updateDatasetModeFields();
    renderDatasetMetaTable();
  }

  byId('ds_mode').addEventListener('change', updateDatasetModeFields);
  byId('add_dataset').addEventListener('click', () => {
    const mode = byId('ds_mode').value;
    const dataset = {
      uiMode: mode,
      uiStatus: 'pending',
      uiInputPath: byId('ds_input_path').value.trim(),
      uiExistingPath: byId('ds_existing_path').value.trim(),
      name: byId('ds_name').value.trim(),
      description: byId('ds_description').value.trim(),
      version: byId('ds_version').value.trim(),
      license: byId('ds_license').value.trim(),
      url: byId('ds_url').value.trim(),
      datePublished: byId('ds_date').value.trim(),
      citeAs: byId('ds_cite').value.trim(),
      uiCreators: [...currentDatasetCreators()],
    };
    if (!dataset.name || !dataset.description) return;
    if (mode === 'generate' && !dataset.uiInputPath) return;
    if (mode === 'existing' && !dataset.uiExistingPath) return;
    if (currentDatasetIndex >= 0) datasets[currentDatasetIndex] = { ...datasets[currentDatasetIndex], ...dataset };
    else datasets.push(dataset);
    resetDatasetForm();
    syncDatasets();
  });
  byId('clear_dataset_form').addEventListener('click', () => {
    resetDatasetForm();
    renderDatasetMetaTable();
  });
  byId('clear_datasets').addEventListener('click', () => {
    datasets.splice(0, datasets.length);
    resetDatasetForm();
    syncDatasets();
    clearDetailInputs();
  });

  function updateDatasetSelect() {
    const select = byId('dataset_select');
    select.innerHTML = datasets.map((dataset, index) => `<option value="${index}">${escapeHtml(dataset.name || `Dataset ${index + 1}`)}</option>`).join('');
    if (datasets.length && select.value === '') select.value = '0';
  }

  function clearDetailInputs() {
    ['dist_url', 'dist_format', 'dist_name', 'dist_md5', 'dist_sha256', 'rs_name', 'field_name', 'field_desc', 'field_example'].forEach(id => { const node = byId(id); if (node) node.value = ''; });
  }

  function updateDetailModeUI(dataset) {
    const detailsForm = byId('dataset_details_form');
    const fieldSection = byId('field_entries_section');
    const modeNote = byId('dataset_mode_note');
    if (!dataset) {
      detailsForm.style.display = 'none';
      fieldSection.style.display = 'none';
      modeNote.textContent = 'Select a dataset to continue.';
      return;
    }
    const mode = dataset.uiMode || 'manual';
    if (mode === 'existing') {
      detailsForm.style.display = 'none';
      fieldSection.style.display = 'none';
      modeNote.textContent = 'Existing datasets are attached by path. Review the selected file in the adapter output rather than editing dataset generation details here.';
      return;
    }
    detailsForm.style.display = 'block';
    fieldSection.style.display = 'block';
    if (mode === 'generate') {
      modeNote.textContent = 'Generated datasets use the selected dataset generator. The metadata below is applied to the generated dataset request.';
    } else {
      modeNote.textContent = 'This dataset uses manual metadata editing.';
    }
  }

  function loadDatasetDetails(index) {
    const dataset = datasets[index];
    const heading = byId('current_dataset_heading');
    const status = byId('details_status');
    const selectedStatus = byId('selected_dataset_status');
    if (!dataset) {
      heading.textContent = 'No dataset selected';
      status.textContent = 'Select a dataset first.';
      selectedStatus.textContent = 'Pending';
      selectedStatus.className = 'status-pill pending';
      clearDetailInputs();
      renderDetectedFieldsTable(null);
      updateDetailModeUI(null);
      renderDatasetDetailTable();
      return;
    }
    heading.textContent = dataset.name || `Dataset ${index + 1}`;
    status.textContent = `Mode: ${dataset.uiMode || 'manual'}`;
    selectedStatus.textContent = datasetStatusLabel(dataset);
    selectedStatus.className = `status-pill ${escapeStatusClass(datasetStatusLabel(dataset))}`;
    const dist = Array.isArray(dataset.distribution) && dataset.distribution.length ? dataset.distribution[0] : {};
    byId('dist_url').value = dist.contentUrl || '';
    byId('dist_format').value = dist.encodingFormat || '';
    byId('dist_name').value = dist.name || '';
    byId('dist_md5').value = dist.md5 || '';
    byId('dist_sha256').value = dist.sha256 || '';
    const rs = Array.isArray(dataset.recordSet) && dataset.recordSet.length ? dataset.recordSet[0] : {};
    byId('rs_name').value = resolvedRecordSetName(dataset, rs.name);
    renderDetectedFieldsTable(dataset);
    updateDetailModeUI(dataset);
    renderDatasetDetailTable();
  }

  function renderDatasetDetailTable() {
    const table = byId('dataset_detail_table');
    const progress = byId('dataset_progress');
    if (!datasets.length) {
      table.innerHTML = '<tr><td colspan="6" class="muted-cell">No datasets added yet.</td></tr>';
      progress.textContent = 'No datasets added yet.';
      return;
    }
    progress.textContent = `${datasets.length} datasets total`;
    const selectedIndex = Number(byId('dataset_select')?.value || -1);
    table.innerHTML = datasets.map((dataset, index) => `
      <tr class="${selectedIndex === index ? 'selected-overview-row' : ''}">
        <td><strong>${escapeHtml(dataset.name || `Dataset ${index + 1}`)}</strong></td>
        <td>${escapeHtml(dataset.uiStatus || 'pending')}</td>
        <td>${escapeHtml(datasetSource(dataset))}</td>
        <td>${Array.isArray(dataset.uiFieldPreview) ? dataset.uiFieldPreview.length : 0}</td>
        <td>${escapeHtml(dataset.uiMode || 'manual')}</td>
        <td><button type="button" data-review-dataset="${index}">${selectedIndex === index ? 'Selected' : 'Open'}</button></td>
      </tr>
    `).join('');
    table.querySelectorAll('[data-review-dataset]').forEach(btn => {
      btn.addEventListener('click', () => {
        byId('dataset_select').value = btn.dataset.reviewDataset;
        loadDatasetDetails(Number(btn.dataset.reviewDataset));
      });
    });
  }

  byId('dataset_select').addEventListener('change', () => loadDatasetDetails(Number(byId('dataset_select').value || 0)));
  byId('apply_details').addEventListener('click', () => {
    const index = Number(byId('dataset_select').value || 0);
    const dataset = datasets[index];
    if (!dataset) return;
    if ((dataset.uiMode || 'manual') === 'existing') return;
    const distUrl = byId('dist_url').value.trim();
    const fileName = byId('dist_name').value.trim() || 'file';
    const fileObjectId = slugifyId(fileName) || 'file';
    dataset.distribution = distUrl ? [{
      '@type': 'cr:FileObject',
      '@id': fileObjectId,
      contentUrl: distUrl,
      encodingFormat: byId('dist_format').value.trim() || 'text/csv',
      name: fileName,
      md5: byId('dist_md5').value.trim() || undefined,
      sha256: byId('dist_sha256').value.trim() || undefined,
    }] : [];
    const rsName = resolvedRecordSetName(dataset, byId('rs_name').value.trim());
    const datasetId = slugifyId(dataset.name || 'dataset') || 'dataset';
    const recordSetId = `${datasetId}-${slugifyId(rsName || 'records') || 'records'}`;
    dataset.recordSet = dataset.recordSet || [{ '@type': 'cr:RecordSet', name: rsName, field: [] }];
    dataset.recordSet[0]['@id'] = recordSetId;
    dataset.recordSet[0].name = rsName;
    if (Array.isArray(dataset.recordSet[0].field)) {
      dataset.recordSet[0].field = dataset.recordSet[0].field.map(field => {
        if (!field || typeof field !== 'object') return field;
        const fieldName = String(field.name || '').trim();
        const fieldId = fieldName ? `${recordSetId}/${slugifyId(fieldName)}` : field['@id'];
        return {
          ...field,
          '@id': fieldId,
          source: {
            ...(field.source || {}),
            fileObject: { '@id': fileObjectId },
            extract: {
              ...((field.source && field.source.extract) || {}),
              column: fieldName || ((field.source && field.source.extract && field.source.extract.column) || ''),
            },
          },
        };
      });
    }
    dataset.uiForceManualMetadata = true;
    dataset.uiStatus = 'detailed';
    syncDatasets();
    loadDatasetDetails(index);
  });

  function renderDetectedFieldsTable(dataset) {
    const report = byId('fields_report');
    const note = byId('fields_report_note');
    if (!dataset) {
      note.textContent = 'No dataset selected.';
      report.innerHTML = '';
      return;
    }
    const fields = Array.isArray(dataset.uiFieldPreview) ? dataset.uiFieldPreview : [];
    if (!fields.length) {
      note.textContent = 'No detected fields available for this dataset yet.';
      report.innerHTML = '';
      return;
    }
    note.textContent = `${fields.length} field${fields.length === 1 ? '' : 's'} available for review and editing.`;
    report.innerHTML = fields.map((field, fieldIndex) => `
      <tr>
        <td>${escapeHtml(field.name || '')}</td>
        <td>${escapeHtml(displayDetectedType(field.detectedType || field.mappedType || 'sc:Text'))}</td>
        <td class="field-example-cell">${escapeHtml(field.example || '')}</td>
        <td>
          <select data-field-type-index="${fieldIndex}">
            ${datatypeOptions(field.mappedType || field.detectedType || 'sc:Text')}
          </select>
        </td>
        <td>
          <input class="field-description-input" type="text" value="${escapeHtml(field.description || '')}" data-field-description-index="${fieldIndex}">
        </td>
      </tr>
    `).join('');
    report.querySelectorAll('[data-field-type-index]').forEach(select => {
      select.addEventListener('change', () => {
        const index = Number(byId('dataset_select').value || 0);
        const activeDataset = datasets[index];
        if (!activeDataset || !Array.isArray(activeDataset.uiFieldPreview)) return;
        const fieldIndex = Number(select.dataset.fieldTypeIndex);
        const nextType = select.value;
        if (!activeDataset.uiFieldPreview[fieldIndex]) return;
        activeDataset.uiFieldPreview[fieldIndex].mappedType = nextType;
        if (
          Array.isArray(activeDataset.recordSet)
          && activeDataset.recordSet[0]
          && Array.isArray(activeDataset.recordSet[0].field)
          && activeDataset.recordSet[0].field[fieldIndex]
        ) {
          activeDataset.recordSet[0].field[fieldIndex].dataType = nextType;
        }
        activeDataset.uiForceManualMetadata = true;
        syncDatasets();
      });
    });
    report.querySelectorAll('[data-field-description-index]').forEach(input => {
      input.addEventListener('input', () => {
        const index = Number(byId('dataset_select').value || 0);
        const activeDataset = datasets[index];
        if (!activeDataset || !Array.isArray(activeDataset.uiFieldPreview)) return;
        const fieldIndex = Number(input.dataset.fieldDescriptionIndex);
        const nextDescription = input.value;
        if (!activeDataset.uiFieldPreview[fieldIndex]) return;
        activeDataset.uiFieldPreview[fieldIndex].description = nextDescription;
        if (
          Array.isArray(activeDataset.recordSet)
          && activeDataset.recordSet[0]
          && Array.isArray(activeDataset.recordSet[0].field)
          && activeDataset.recordSet[0].field[fieldIndex]
        ) {
          activeDataset.recordSet[0].field[fieldIndex].description = nextDescription;
        }
        activeDataset.uiForceManualMetadata = true;
        syncDatasets();
      });
    });
  }

  byId('add_field').addEventListener('click', () => {
    const index = Number(byId('dataset_select').value || 0);
    const dataset = datasets[index];
    if (!dataset) return;
    if ((dataset.uiMode || 'manual') === 'existing') return;
    const fieldName = byId('field_name').value.trim();
    if (!fieldName) return;
    dataset.uiFieldPreview = Array.isArray(dataset.uiFieldPreview) ? dataset.uiFieldPreview : [];
    dataset.uiFieldPreview.push({
      name: fieldName,
      description: byId('field_desc').value.trim(),
      example: byId('field_example').value.trim(),
      mappedType: byId('field_type').value,
      detectedType: byId('field_type').value,
      source: 'manual',
    });
    dataset.uiForceManualMetadata = true;
    dataset.uiStatus = 'detailed';
    syncDatasets();
    loadDatasetDetails(index);
  });

  byId('add_dataset_creator').addEventListener('click', () => {
    const creatorType = byId('dataset_creator_type').value || 'Person';
    const name = byId('dataset_creator_name').value.trim();
    const affiliations = byId('dataset_creator_affiliations').value.trim();
    const email = byId('dataset_creator_email').value.trim();
    const url = byId('dataset_creator_url').value.trim();
    if (!name) return;
    const creatorValue = {
      creator_type: creatorType,
      name,
      affiliations,
      email,
      url,
    };
    const creatorsList = currentDatasetCreators();
    if (currentDatasetIndex < 0) {
      byId('dataset_creator_meta_status').textContent = 'Save the dataset first, then manage its creators.';
      return;
    }
    if (currentDatasetCreatorIndex >= 0) creatorsList[currentDatasetCreatorIndex] = creatorValue;
    else creatorsList.push(creatorValue);
    resetDatasetCreatorForm();
    renderDatasetCreatorsTable(creatorsList);
    syncDatasets();
  });

  byId('clear_dataset_creator_form').addEventListener('click', () => {
    resetDatasetCreatorForm();
    renderDatasetCreatorsTable(currentDatasetCreators());
  });

  function inferType(value) {
    const text = String(value ?? '').trim();
    if (!text) return 'sc:Text';
    if (/^(true|false)$/i.test(text)) return 'sc:Boolean';
    if (/^-?\d+$/.test(text)) return 'sc:Integer';
    if (/^-?\d+\.\d+$/.test(text)) return 'sc:Float';
    if (/^\d{4}-\d{2}-\d{2}$/.test(text)) return 'sc:Date';
    if (/^\d{4}-\d{2}-\d{2}T/.test(text)) return 'sc:DateTime';
    if (/^https?:\/\//i.test(text)) return 'sc:URL';
    return 'sc:Text';
  }

  function chooseDelimiter(sample) {
    const firstLine = (sample.split(/\r?\n/).find(line => line.trim()) || '');
    const commas = (firstLine.match(/,/g) || []).length;
    const tabs = (firstLine.match(/\t/g) || []).length;
    return tabs > commas ? '\t' : ',';
  }

  function parseDelimitedText(text, delimiter) {
    const lines = text.split(/\r?\n/).filter(line => line.trim());
    if (!lines.length) return { headers: [], rows: [] };
    const headers = lines[0].split(delimiter).map(cell => cell.trim());
    const rows = lines.slice(1, 26).map(line => line.split(delimiter));
    return { headers, rows };
  }

  byId('toggle_detected_fields').addEventListener('click', () => {
    const body = byId('detected_fields_body');
    const button = byId('toggle_detected_fields');
    const collapsed = body.classList.toggle('collapsed');
    button.textContent = collapsed ? 'Expand' : 'Collapse';
    button.setAttribute('aria-expanded', collapsed ? 'false' : 'true');
  });

  function restoreState() {
    const preloadNode = byId('preloaded_state');
    let state = null;
    if (preloadNode && preloadNode.textContent) {
      try { state = JSON.parse(preloadNode.textContent); } catch (error) { state = null; }
    }
    if (!state) state = readState();
    if (!state) return;
    document.querySelector('[name="name"]').value = state.name || '';
    document.querySelector('[name="description"]').value = state.description || '';
    document.querySelector('[name="version"]').value = state.version || '';
    document.querySelector('[name="license"]').value = state.license || '';
    document.querySelector('[name="code_repository"]').value = state.code_repository || '';
    document.querySelector('[name="keywords"]').value = state.keywords || '';
    creators.splice(0, creators.length, ...((state.creators || []).map(item => ({ ...item }))));
    datasets.splice(0, datasets.length, ...((state.datasets || []).map(item => ({ ...item }))));
    syncAdapterId();
  }

  window.clearState = function clearState() {
    const confirmed = window.confirm('Clear all saved form data?\n\nThis will remove the adapter, creators, datasets, and dataset details currently stored in this browser.');
    if (!confirmed) return;
    localStorage.removeItem(STORAGE_KEY);
    creators.splice(0, creators.length);
    datasets.splice(0, datasets.length);
    document.querySelector('[name="name"]').value = '';
    document.querySelector('[name="description"]').value = '';
    document.querySelector('[name="version"]').value = '';
    document.querySelector('[name="license"]').value = '';
    document.querySelector('[name="code_repository"]').value = '';
    document.querySelector('[name="keywords"]').value = '';
    resetCreatorForm();
    resetDatasetForm();
    clearDetailInputs();
    syncCreators();
    syncDatasets();
    syncAdapterId();
    loadDatasetDetails(0);
  };

  ['name', 'description', 'version', 'license', 'code_repository', 'keywords'].forEach(name => {
    const node = document.querySelector(`[name="${name}"]`);
    if (!node) return;
    node.addEventListener('input', () => {
      if (name === 'name') syncAdapterId();
      persistState();
    });
    node.addEventListener('change', persistState);
  });

  restoreState();
  updateDatasetModeFields();
  resetCreatorForm();
  syncCreators();
  syncDatasets();
  syncAdapterId();
  if (datasets.length) loadDatasetMeta(0);
  else resetDatasetForm();
  loadDatasetDetails(0);
</script>
"""
