"""Web UI for guided metadata generation.

Provides a step-based form with dynamic lists (creators, datasets,
distributions, fields) without requiring users to edit JSON.
"""

from __future__ import annotations

import html
import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs

from src.core.constants import METADATA_FILENAME
from src.core.generation.builder import build_adapter, build_creator, build_dataset
from src.core.validator import validate


_TEMPLATE = r"""
<!doctype html>
<html>
  <head>
    <meta charset="utf-8">
    <title>BioCypher Metadata Generator</title>
    <style>
      :root {
        --bg: #0b1220;
        --panel: #111827;
        --panel-2: #172133;
        --ink: #e5edf6;
        --muted: #93a1b2;
        --accent: #60a5fa;
        --accent-2: #3b82f6;
        --accent-soft: rgba(96, 165, 250, 0.16);
        --line: #273244;
        --glow: rgba(96, 165, 250, 0.22);
        --success: #4ade80;
        --success-soft: rgba(74, 222, 128, 0.14);
        --warning: #f59e0b;
        --warning-soft: rgba(245, 158, 11, 0.14);
        --draft: #38bdf8;
        --draft-soft: rgba(56, 189, 248, 0.14);
        --neutral-soft: rgba(148, 163, 184, 0.12);
      }
      body.light {
        --bg: #f5f7fa;
        --panel: #ffffff;
        --panel-2: #eef2f7;
        --ink: #16202b;
        --muted: #5f6b7a;
        --accent: #2563eb;
        --accent-2: #1d4ed8;
        --accent-soft: #dbeafe;
        --line: #d9e1ea;
        --glow: rgba(37, 99, 235, 0.16);
        --success: #15803d;
        --success-soft: #dcfce7;
        --warning: #b45309;
        --warning-soft: #fef3c7;
        --draft: #0369a1;
        --draft-soft: #e0f2fe;
        --neutral-soft: #e5e7eb;
        background: linear-gradient(180deg, #f5f7fa 0%, #ffffff 100%);
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
      h1 { font-size: 2.1rem; margin: 0 0 0.35rem 0; }
      .subtitle { color: var(--muted); margin-bottom: 1.75rem; }
      .steps {
        display: grid;
        grid-template-columns: repeat(4, minmax(0, 1fr));
        gap: 1rem;
        margin: 1.25rem 0 1.75rem 0;
      }
      .step {
        position: relative;
        padding-left: 2.75rem;
        color: var(--muted);
        font-size: 0.95rem;
      }
      .step::before {
        content: attr(data-step-num);
        position: absolute;
        left: 0;
        top: -0.1rem;
        width: 2rem;
        height: 2rem;
        border-radius: 999px;
        display: grid;
        place-items: center;
        background: var(--panel-2);
        border: 1px solid var(--line);
        color: var(--muted);
        box-shadow: inset 0 0 0 1px rgba(255,255,255,0.03);
      }
      .step.active {
        color: var(--ink);
      }
      .step.active::before {
        background: var(--accent);
        color: #0b1020;
        box-shadow: 0 0 0 3px var(--glow);
      }
      .section {
        background: var(--panel);
        border: 1px solid var(--line);
        border-radius: 14px;
        padding: 1.25rem 1.25rem 1rem 1.25rem;
        margin: 1.25rem 0;
        box-shadow: 0 8px 24px rgba(0, 0, 0, 0.35);
      }
      .section h2 { margin: 0 0 0.5rem 0; color: var(--ink); }
      label { display: block; margin-top: 0.75rem; font-weight: 600; }
      .hint { color: var(--muted); font-weight: 400; }
      input, textarea, select {
        width: 100%;
        padding: 0.6rem 0.7rem;
        border-radius: 10px;
        border: 1px solid var(--line);
        background: #0f172a;
        color: var(--ink);
        margin-top: 0.35rem;
        pointer-events: auto;
        user-select: text;
        caret-color: var(--ink);
      }
      input:focus, textarea:focus, select:focus {
        outline: none;
        border-color: var(--accent);
        box-shadow: 0 0 0 3px var(--glow);
      }
      body.light input,
      body.light textarea,
      body.light select {
        border: 1px solid #cfd8e3;
        background: #ffffff;
        color: var(--ink);
      }
      body.light input::placeholder,
      body.light textarea::placeholder {
        color: #8a94a6;
      }
      input::placeholder, textarea::placeholder { color: #748196; }
      .badge {
        display: inline-block;
        font-size: 0.72rem;
        padding: 0.15rem 0.5rem;
        border-radius: 999px;
        margin-left: 0.4rem;
      }
      .req { background: var(--accent); color: #fff; }
      .opt { background: var(--neutral-soft); color: var(--muted); }
      .rec { background: var(--warning-soft); color: var(--warning); }
      .actions { display: flex; gap: 0.75rem; justify-content: flex-end; }
      button {
        background: var(--accent);
        color: #f8fafc;
        border: none;
        padding: 0.75rem 1.25rem;
        border-radius: 10px;
        font-size: 1rem;
        cursor: pointer;
        margin-top: 1rem;
      }
      button:hover { background: var(--accent-2); }
      .ghost { background: transparent; color: var(--ink); border: 1px solid var(--line); }
      .ghost:hover { background: var(--neutral-soft); }
      .button {
        display: inline-block;
        text-decoration: none;
        background: var(--accent);
        color: #f8fafc;
        border-radius: 10px;
        padding: 0.75rem 1.25rem;
        border: 1px solid transparent;
        margin-top: 1rem;
      }
      .button.ghost {
        background: transparent;
        color: var(--ink);
        border: 1px solid var(--line);
      }
      .step-panel { display: none; }
      .step-panel.active { display: block; }
      .list { margin-top: 0.75rem; padding-left: 1.25rem; }
      .list li { margin-bottom: 0.25rem; }
      .grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 0.75rem; }
      .note { color: var(--muted); font-size: 0.9rem; }
      .status-row {
        display: flex;
        flex-wrap: wrap;
        align-items: center;
        gap: 0.5rem;
        margin: 0.75rem 0 0.25rem 0;
      }
      .status-pill {
        display: inline-flex;
        align-items: center;
        gap: 0.35rem;
        font-size: 0.8rem;
        padding: 0.25rem 0.65rem;
        border-radius: 999px;
        border: 1px solid var(--line);
        background: var(--panel-2);
      }
      .status-pill.pending {
        color: var(--warning);
        border-color: var(--warning-soft);
        background: var(--warning-soft);
      }
      .status-pill.detailed {
        color: var(--success);
        border-color: var(--success-soft);
        background: var(--success-soft);
      }
      .status-pill.skipped {
        color: var(--muted);
        border-color: var(--neutral-soft);
        background: var(--neutral-soft);
      }
      .status-pill.draft {
        color: var(--draft);
        border-color: var(--draft-soft);
        background: var(--draft-soft);
      }
      .tiny-badge {
        display: inline-flex;
        align-items: center;
        font-size: 0.72rem;
        padding: 0.14rem 0.45rem;
        border-radius: 999px;
        border: 1px solid var(--draft-soft);
        color: var(--draft);
        background: var(--draft-soft);
        margin-left: 0.45rem;
      }
      .compact-list {
        list-style: none;
        padding-left: 0;
        margin: 0.75rem 0 0 0;
      }
      .compact-list li {
        display: flex;
        flex-wrap: wrap;
        justify-content: space-between;
        gap: 0.75rem;
        padding: 0.55rem 0.75rem;
        border: 1px solid var(--line);
        border-radius: 10px;
        margin-bottom: 0.5rem;
        background: var(--panel-2);
      }
      .table-wrap {
        margin-top: 0.9rem;
        border: 1px solid var(--line);
        border-radius: 14px;
        overflow: hidden;
        background: var(--panel-2);
      }
      table {
        width: 100%;
        border-collapse: collapse;
      }
      th, td {
        text-align: left;
        padding: 0.8rem 0.9rem;
        border-bottom: 1px solid var(--line);
        vertical-align: top;
      }
      th {
        font-size: 0.82rem;
        color: var(--muted);
        letter-spacing: 0.02em;
      }
      td strong {
        display: inline-block;
        margin-bottom: 0.2rem;
      }
      .table-actions {
        display: flex;
        flex-wrap: wrap;
        gap: 0.5rem;
      }
      .table-actions button {
        margin-top: 0;
        padding: 0.45rem 0.75rem;
        font-size: 0.9rem;
      }
      .editing-banner {
        display: none;
        margin: 0.85rem 0;
        padding: 0.8rem 0.95rem;
        border-radius: 12px;
        border: 1px solid var(--accent-soft);
        background: var(--accent-soft);
      }
      .editing-banner.active {
        display: block;
      }
      .editing-title {
        font-weight: 700;
        margin-bottom: 0.2rem;
      }
      .editing-text {
        color: var(--muted);
        font-size: 0.92rem;
      }
      .current-row {
        background: var(--accent-soft);
      }
      .report-row td {
        background: rgba(255, 255, 255, 0.03);
      }
      .inline-report {
        border: 1px solid var(--line);
        border-radius: 12px;
        padding: 0.85rem;
        background: var(--panel);
      }
      .report-title {
        display: flex;
        flex-wrap: wrap;
        align-items: center;
        justify-content: space-between;
        gap: 0.5rem;
        margin-bottom: 0.75rem;
      }
      .report-meta {
        color: var(--muted);
        font-size: 0.88rem;
      }
      .report-empty {
        color: var(--muted);
        padding: 0.4rem 0;
      }
      .mini-table th, .mini-table td {
        padding: 0.55rem 0.65rem;
        font-size: 0.92rem;
      }
      .muted-cell {
        color: var(--muted);
      }
      .sr-only {
        position: absolute;
        width: 1px;
        height: 1px;
        padding: 0;
        margin: -1px;
        overflow: hidden;
        clip: rect(0, 0, 0, 0);
        white-space: nowrap;
        border: 0;
      }
      @media (max-width: 800px) {
        .table-wrap {
          overflow-x: auto;
        }
        table {
          min-width: 760px;
        }
      }
      .notice {
        background: var(--warning-soft);
        border: 1px solid rgba(180, 83, 9, 0.18);
        padding: 0.75rem 1rem;
        border-radius: 10px;
        margin-bottom: 1rem;
      }
      .codeblock {
        white-space: pre-wrap;
        background: var(--panel-2);
        color: var(--ink);
        padding: 1rem;
        border-radius: 10px;
        border: 1px solid var(--line);
        max-height: 28rem;
        overflow: auto;
      }
      .copy-status {
        color: var(--muted);
        font-size: 0.88rem;
        margin-top: 0.5rem;
      }
      .scroll-panel {
        max-height: 140rem;
        overflow: auto;
        border: 1px solid var(--line);
        border-radius: 12px;
        background: var(--panel-2);
      }
      .scroll-panel table {
        margin: 0;
      }
      .scroll-panel thead th {
        position: sticky;
        top: 0;
        z-index: 5;
        background: var(--panel-2);
        box-shadow: 0 1px 0 var(--line);
      }
      .help-button {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        min-width: 2rem;
        padding: 0.3rem 0.55rem;
        margin-top: 0;
        border-radius: 999px;
        font-size: 0.85rem;
        line-height: 1;
      }
      .example-help {
        position: relative;
        display: inline-flex;
        align-items: center;
      }
      .example-tooltip {
        position: absolute;
        left: 0;
        top: calc(100% + 0.45rem);
        z-index: 20;
        min-width: 14rem;
        max-width: 28rem;
        padding: 0.65rem 0.75rem;
        border-radius: 10px;
        border: 1px solid var(--line);
        background: var(--panel);
        color: var(--ink);
        box-shadow: 0 12px 30px rgba(0, 0, 0, 0.24);
        white-space: normal;
        word-break: break-word;
        opacity: 0;
        pointer-events: none;
        transform: translateY(4px);
        transition: opacity 120ms ease, transform 120ms ease;
      }
      .example-help:hover .example-tooltip,
      .example-help:focus-within .example-tooltip {
        opacity: 1;
        transform: translateY(0);
      }
      .topbar {
        display: flex;
        justify-content: flex-end;
        align-items: center;
        gap: 0.85rem;
        margin-bottom: 0.5rem;
      }
      .switch-wrap {
        display: inline-flex;
        align-items: center;
        gap: 0.65rem;
        color: var(--muted);
        font-size: 0.92rem;
      }
      .theme-switch {
        position: relative;
        width: 3.35rem;
        height: 1.9rem;
        display: inline-block;
      }
      .theme-switch input {
        position: absolute;
        opacity: 0;
        width: 0;
        height: 0;
      }
      .theme-slider {
        position: absolute;
        inset: 0;
        cursor: pointer;
        background: var(--panel-2);
        border: 1px solid var(--line);
        border-radius: 999px;
        transition: background 150ms ease, border-color 150ms ease;
      }
      .theme-slider::before {
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
      }
      .theme-switch input:checked + .theme-slider::before {
        transform: translateX(1.4rem);
      }
      .theme-switch input:focus + .theme-slider {
        box-shadow: 0 0 0 3px var(--glow);
      }
    </style>
  </head>
  <body>
    <div class="wrap">
    <div class="topbar">
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
    <div class="steps">
      <div class="step active" data-step="0" data-step-num="1">Adapter</div>
      <div class="step" data-step="1" data-step-num="2">Datasets</div>
      <div class="step" data-step="2" data-step-num="3">Dataset Details</div>
      <div class="step" data-step="3" data-step-num="4">Validate & Download</div>
    </div>
    <form method="post">
      <input type="hidden" name="creators_data" id="creators_data" value="">
      <input type="hidden" name="datasets_data" id="datasets_data" value="">
      <div class="section step-panel active" data-panel="0">
        <h2>Adapter</h2>
        <label>Name <span class="badge req">required</span><input name="name" required></label>
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
          <div class="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Affiliation</th>
                  <th>ORCID</th>
                  <th>Preview</th>
                  <th>Remove</th>
                </tr>
              </thead>
              <tbody id="creators_table"></tbody>
            </table>
          </div>
        </div>
        <div class="actions">
          <button type="button" class="ghost" data-prev>Back</button>
          <button type="button" data-next>Next</button>
        </div>
      </div>

      <div class="section step-panel" data-panel="1">
        <h2>Datasets</h2>
        <div class="note">Add each dataset first. Details are added in the next step.</div>
        <div class="note" id="dataset_meta_status">Add a dataset to begin.</div>
        <div class="editing-banner" id="dataset_edit_banner">
          <div class="editing-title" id="dataset_edit_title">Editing dataset</div>
          <div class="editing-text">Update the fields below and click Update dataset to save your changes.</div>
        </div>
        <label>Dataset name <span class="badge req">required</span><input id="ds_name"></label>
        <label>Description <span class="badge req">required</span><input id="ds_description"></label>
        <div class="grid-2">
          <label>Version <span class="badge req">required</span><input id="ds_version"></label>
          <label>License <span class="badge req">required</span><input id="ds_license"></label>
        </div>
        <label>URL <span class="badge req">required</span><input id="ds_url"></label>
        <div class="actions">
          <button type="button" id="add_dataset">Add dataset</button>
          <button type="button" class="ghost" id="clear_dataset_form">Cancel editing</button>
          <button type="button" class="ghost" id="clear_datasets">Clear list</button>
        </div>
        <div class="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Dataset</th>
                <th>Version</th>
                <th>License</th>
                <th>URL</th>
                <th>Preview</th>
                <th>Remove</th>
              </tr>
            </thead>
            <tbody id="dataset_meta_table"></tbody>
          </table>
        </div>
        <div class="actions">
          <button type="button" class="ghost" data-prev>Back</button>
          <button type="button" data-next>Next</button>
        </div>
      </div>

      <div class="section step-panel" data-panel="2">
        <h2>Dataset Details</h2>
        <div class="note">Apply details to a selected dataset.</div>
        <div class="status-row">
          <div class="status-pill pending" id="selected_dataset_status">Pending</div>
          <div class="note" id="dataset_progress">No datasets added yet.</div>
        </div>
        <div class="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Dataset</th>
                <th>Status</th>
                <th>File used</th>
                <th>Fields</th>
                <th>Report</th>
                <th>Review</th>
              </tr>
            </thead>
            <tbody id="dataset_detail_table"></tbody>
          </table>
        </div>
        <label class="sr-only">Choose dataset
          <select id="dataset_select"></select>
        </label>
        <label>Date published <span class="badge rec">recommended</span><input id="ds_date"></label>
        <label>Citation (DOI or string) <span class="badge rec">recommended</span><input id="ds_cite"></label>
        <h3>Distribution (optional)</h3>
        <label>Content URL <span class="badge opt">optional</span><input id="dist_url"></label>
        <label>Encoding format (e.g. text/csv) <span class="badge opt">optional</span><input id="dist_format"></label>
        <label>File name <span class="badge opt">optional</span><input id="dist_name"></label>
        <div class="grid-2">
          <label>MD5 <span class="badge opt">optional</span><input id="dist_md5"></label>
          <label>SHA-256 <span class="badge opt">optional</span><input id="dist_sha256"></label>
        </div>
        <h3>Record Set & Fields (optional)</h3>
        <label>Record set name <span class="badge opt">optional</span><input id="rs_name"></label>
        <label>Load a sample to infer the fields (max 5MB) <span class="badge opt">optional</span>
          <input id="infer_file" type="file" accept=".csv,.tsv,.tab">
        </label>
        <div class="actions">
          <button type="button" class="ghost" id="analyze_file" onclick="analyzeFile()">Analyze file</button>
        </div>
        <div class="section">
          <h3>Detected fields</h3>
          <div class="note" id="fields_report_note">No file analyzed yet.</div>
          <div class="scroll-panel">
            <table>
              <thead>
                <tr>
                  <th>Field Name</th>
                  <th>Datatype detected</th>
                  <th>Example</th>
                  <th>Suggested Datatype</th>
                  <th></th>
                </tr>
              </thead>
              <tbody id="fields_report"></tbody>
            </table>
          </div>
        </div>
        <div class="actions">
          <button type="button" class="ghost" id="apply_details">Apply details</button>
          <button type="button" class="ghost" id="clear_details">Clear details</button>
          <button type="button" class="ghost" id="skip_details">Skip details</button>
          <button type="button" class="ghost" id="mark_pending">Mark pending</button>
        </div>
        <div class="note" id="details_status"></div>
        <h3>Manual fields (optional)</h3>
        <div class="grid-2">
          <label>Field name <span class="badge opt">optional</span><input id="field_name"></label>
          <label>Data type <span class="badge opt">optional</span>
            <select id="field_type">
              <option value="sc:Boolean">sc:Boolean</option>
              <option value="sc:CssSelectorType">sc:CssSelectorType</option>
              <option value="sc:Date">sc:Date</option>
              <option value="sc:DateTime">sc:DateTime</option>
              <option value="sc:Float">sc:Float</option>
              <option value="sc:Integer">sc:Integer</option>
              <option value="sc:Number">sc:Number</option>
              <option value="sc:PronounceableText">sc:PronounceableText</option>
              <option value="sc:Text">sc:Text</option>
              <option value="sc:Time">sc:Time</option>
              <option value="sc:URL">sc:URL</option>
              <option value="sc:XPathType">sc:XPathType</option>
            </select>
          </label>
        </div>
        <label>Description <span class="badge opt">optional</span><input id="field_desc"></label>
        <label>Example <span class="badge opt">optional</span><input id="field_example"></label>
        <div class="actions">
          <button type="button" class="ghost" id="add_field">Add field</button>
        </div>
        <ul class="list" id="fields_list"></ul>
        <div class="actions">
          <button type="button" class="ghost" data-prev>Back</button>
          <button type="button" data-next>Next</button>
        </div>
      </div>

      <div class="section step-panel" data-panel="3">
        <h2>Validate & Download</h2>
        <div class="note">Submit the form to generate and validate your file.</div>
        <div class="actions">
          <button type="button" class="ghost" data-prev>Back</button>
          <button type="submit">Generate</button>
        </div>
      </div>
    </form>
    </div>
    <script>
      const steps = Array.from(document.querySelectorAll('.step'));
      const panels = Array.from(document.querySelectorAll('.step-panel'));
      const SCHEMA_DATATYPES = [
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
      let idx = 0;
      function show(i) {
        if (idx === 2 && i !== 2) {
          persistCurrentDraft();
        }
        idx = Math.max(0, Math.min(panels.length - 1, i));
        panels.forEach((p, pi) => p.classList.toggle('active', pi === idx));
        steps.forEach((s, si) => s.classList.toggle('active', si === idx));
      }
      document.querySelectorAll('[data-next]').forEach(btn => {
        btn.addEventListener('click', () => show(idx + 1));
      });
      document.querySelectorAll('[data-prev]').forEach(btn => {
        btn.addEventListener('click', () => show(idx - 1));
      });
      steps.forEach((s, i) => s.addEventListener('click', () => show(i)));
      show(0);

      const creators = [];
      const datasets = [];
      let restoring = false;
      const creatorsTable = document.getElementById('creators_table');
      const creatorMetaStatus = document.getElementById('creator_meta_status');
      const creatorEditBanner = document.getElementById('creator_edit_banner');
      const creatorEditTitle = document.getElementById('creator_edit_title');
      const datasetMetaTable = document.getElementById('dataset_meta_table');
      const datasetMetaStatus = document.getElementById('dataset_meta_status');
      const datasetSelect = document.getElementById('dataset_select');
      const creatorsInput = document.getElementById('creators_data');
      const datasetsInput = document.getElementById('datasets_data');
      const detailTable = document.getElementById('dataset_detail_table');
      const datasetProgress = document.getElementById('dataset_progress');
      const selectedDatasetStatus = document.getElementById('selected_dataset_status');
      const datasetEditBanner = document.getElementById('dataset_edit_banner');
      const datasetEditTitle = document.getElementById('dataset_edit_title');
      let expandedReportIndex = -1;
      let currentDetailIndex = -1;
      let currentMetaIndex = -1;
      let currentCreatorIndex = -1;
      let expandedFieldDescriptionIndex = -1;

      function normalizeDatasetState(dataset) {
        if (!dataset || typeof dataset !== 'object') return dataset;
        if (!['pending', 'detailed', 'skipped'].includes(dataset.uiStatus)) {
          dataset.uiStatus = 'pending';
        }
        return dataset;
      }

      function getDatasetStatus(dataset) {
        const normalized = normalizeDatasetState(dataset);
        return normalized ? normalized.uiStatus : 'pending';
      }

      function getStatusLabel(status) {
        if (status === 'detailed') return 'Detailed';
        if (status === 'skipped') return 'Skipped';
        return 'Pending';
      }

      function escapeHtml(value) {
        return String(value ?? '')
          .replace(/&/g, '&amp;')
          .replace(/</g, '&lt;')
          .replace(/>/g, '&gt;')
          .replace(/"/g, '&quot;')
          .replace(/'/g, '&#39;');
      }

      function summarizeFields(dataset) {
        if (Array.isArray(dataset?.uiFieldPreview) && dataset.uiFieldPreview.length) {
          return dataset.uiFieldPreview.map(field => ({
            ...field,
            detectedType: normalizeDetectedType(field.detectedType || field.mappedType || 'string'),
            mappedType: field.mappedType || schemaDatatypeFromRaw(normalizeDetectedType(field.detectedType || 'string')),
            description: field.description || '',
            source: field.source || 'manual',
          }));
        }
        const fields = Array.isArray(dataset?.recordSet?.[0]?.field) ? dataset.recordSet[0].field : [];
        return fields.map(field => ({
          name: field.name || '',
          detectedType: rawDatatypeFromSchema(field.dataType || 'sc:Text'),
          example: Array.isArray(field.examples) ? (field.examples[0] || '') : '',
          mappedType: field.dataType || 'sc:Text',
          description: field.description || '',
          source: 'manual',
        }));
      }

      function normalizeDetectedType(value) {
        if (!value) return 'string';
        if (String(value).startsWith('sc:')) {
          return rawDatatypeFromSchema(value);
        }
        return String(value).toLowerCase();
      }

      function rawDatatypeFromSchema(schemaType) {
        if (schemaType === 'sc:Boolean') return 'boolean';
        if (schemaType === 'sc:Integer') return 'integer';
        if (schemaType === 'sc:Float' || schemaType === 'sc:Number') return 'float';
        if (schemaType === 'sc:Date') return 'date';
        if (schemaType === 'sc:DateTime') return 'datetime';
        if (schemaType === 'sc:Time') return 'time';
        if (schemaType === 'sc:URL') return 'url';
        return 'string';
      }

      function schemaDatatypeFromRaw(rawType) {
        if (rawType === 'boolean') return 'sc:Boolean';
        if (rawType === 'integer') return 'sc:Integer';
        if (rawType === 'float') return 'sc:Float';
        if (rawType === 'date') return 'sc:Date';
        if (rawType === 'datetime') return 'sc:DateTime';
        if (rawType === 'time') return 'sc:Time';
        if (rawType === 'url') return 'sc:URL';
        return 'sc:Text';
      }

      function schemaDatatypeOptions(selectedValue) {
        return SCHEMA_DATATYPES.map(value => `<option value="${value}" ${value === selectedValue ? 'selected' : ''}>${value}</option>`).join('');
      }

      function buildRecordSetFields(dataset) {
        const previews = summarizeFields(dataset);
        const rsName = document.getElementById('rs_name').value.trim() || dataset?.recordSet?.[0]?.name || 'records';
        const fileObjectId = dataset?.distribution?.[0]?.['@id'] || 'file';
        dataset.uiFieldPreview = previews;
        dataset.recordSet = dataset.recordSet || [{ '@type': 'cr:RecordSet', name: rsName, field: [] }];
        if (dataset.recordSet[0]) {
          dataset.recordSet[0].name = rsName;
          dataset.recordSet[0].field = previews.map(field => {
            const builtField = {
              '@type': 'cr:Field',
              name: field.name || '',
              dataType: field.mappedType || 'sc:Text',
              examples: field.example ? [field.example] : [],
              source: {
                fileObject: { '@id': fileObjectId },
                extract: { column: field.name || '' },
              },
            };
            if (field.description) {
              builtField.description = field.description;
            }
            return builtField;
          });
        }
      }

      function updateFieldPreviewMapping(dataset, fieldIndex, mappedType) {
        if (!dataset) return;
        const previews = Array.isArray(dataset.uiFieldPreview) ? dataset.uiFieldPreview : summarizeFields(dataset);
        dataset.uiFieldPreview = previews.map((field, index) => {
          if (index !== fieldIndex) return field;
          return { ...field, mappedType };
        });
        buildRecordSetFields(dataset);
        dataset.uiStatus = 'detailed';
        saveDraftForDataset(Number(datasetSelect.value || 0));
        syncDatasets();
        renderDetectedFieldsTable(dataset);
      }

      function updateFieldDescription(dataset, fieldIndex, description) {
        if (!dataset) return;
        const previews = Array.isArray(dataset.uiFieldPreview) ? dataset.uiFieldPreview : summarizeFields(dataset);
        dataset.uiFieldPreview = previews.map((field, index) => {
          if (index !== fieldIndex) return field;
          return { ...field, description: description.trim() };
        });
        buildRecordSetFields(dataset);
        dataset.uiStatus = 'detailed';
        saveDraftForDataset(Number(datasetSelect.value || 0));
        syncDatasets();
        renderDetectedFieldsTable(dataset);
      }

      function removeFieldFromDataset(dataset, fieldIndex) {
        if (!dataset) return;
        const previews = summarizeFields(dataset);
        dataset.uiFieldPreview = previews.filter((_, index) => index !== fieldIndex);
        expandedFieldDescriptionIndex = -1;
        buildRecordSetFields(dataset);
        dataset.uiStatus = dataset.uiFieldPreview.length ? 'detailed' : 'pending';
        saveDraftForDataset(Number(datasetSelect.value || 0));
        syncDatasets();
        renderDetectedFieldsTable(dataset);
      }

      function renderDetectedFieldsTable(dataset) {
        const report = document.getElementById('fields_report');
        const note = document.getElementById('fields_report_note');
        if (!report || !note) return;
        const fields = summarizeFields(dataset);
        if (!fields.length) {
          note.textContent = dataset ? 'No detected fields available for this dataset yet.' : 'No file analyzed yet.';
          report.innerHTML = '';
          return;
        }
        note.textContent = `${fields.length} field${fields.length === 1 ? '' : 's'} available for review and editing.`;
        report.innerHTML = fields.map((field, index) => {
          const isExpanded = expandedFieldDescriptionIndex === index;
          return `
            <tr>
              <td>${escapeHtml(field.name || '')}</td>
              <td>${escapeHtml(normalizeDetectedType(field.detectedType || field.mappedType || 'string'))}</td>
              <td>${field.example ? (field.example.length <= 30
                ? escapeHtml(field.example)
                : `<span class="example-help"><button type="button" class="ghost help-button" aria-label="See example">See example</button><span class="example-tooltip">${escapeHtml(field.example)}</span></span>`)
                : '<span class="muted-cell">-</span>'}</td>
              <td>${escapeHtml(field.mappedType || field.detectedType || 'sc:Text')}</td>
              <td>
                <div class="table-actions">
                  <select data-field-datatype="${index}">
                    ${schemaDatatypeOptions(field.mappedType || field.detectedType || 'sc:Text')}
                  </select>
                  <button type="button" class="ghost" data-toggle-field-description="${index}">${field.description ? 'Edit description' : 'Add description'}</button>
                  <button type="button" class="ghost" data-remove-field="${index}">Remove</button>
                </div>
              </td>
            </tr>
            ${isExpanded ? `
              <tr class="report-row">
                <td colspan="5">
                  <label>Description <span class="badge rec">recommended</span>
                    <textarea data-field-description="${index}" rows="4" placeholder="Add a description for this field.">${escapeHtml(field.description || '')}</textarea>
                  </label>
                  <div class="actions">
                    <button type="button" class="ghost" data-save-field-description="${index}">Save description</button>
                    <button type="button" class="ghost" data-clear-field-description="${index}">Clear description</button>
                  </div>
                </td>
              </tr>
            ` : ''}
          `;
        }).join('');
        report.querySelectorAll('[data-field-datatype]').forEach(select => {
          select.addEventListener('change', () => {
            updateFieldPreviewMapping(dataset, Number(select.dataset.fieldDatatype), select.value);
          });
        });
        report.querySelectorAll('[data-toggle-field-description]').forEach(button => {
          button.addEventListener('click', () => {
            const fieldIndex = Number(button.dataset.toggleFieldDescription);
            expandedFieldDescriptionIndex = expandedFieldDescriptionIndex === fieldIndex ? -1 : fieldIndex;
            renderDetectedFieldsTable(dataset);
          });
        });
        report.querySelectorAll('[data-save-field-description]').forEach(button => {
          button.addEventListener('click', () => {
            const fieldIndex = Number(button.dataset.saveFieldDescription);
            const textarea = report.querySelector(`[data-field-description="${fieldIndex}"]`);
            updateFieldDescription(dataset, fieldIndex, textarea ? textarea.value : '');
            expandedFieldDescriptionIndex = fieldIndex;
            renderDetectedFieldsTable(dataset);
          });
        });
        report.querySelectorAll('[data-clear-field-description]').forEach(button => {
          button.addEventListener('click', () => {
            const fieldIndex = Number(button.dataset.clearFieldDescription);
            updateFieldDescription(dataset, fieldIndex, '');
            expandedFieldDescriptionIndex = fieldIndex;
            renderDetectedFieldsTable(dataset);
          });
        });
        report.querySelectorAll('[data-remove-field]').forEach(button => {
          button.addEventListener('click', () => {
            removeFieldFromDataset(dataset, Number(button.dataset.removeField));
          });
        });
      }

      function getFileUsedLabel(dataset) {
        if (dataset?.uiInferenceFileName) return dataset.uiInferenceFileName;
        return 'No file used';
      }

      function truncateText(value, maxLength = 110) {
        const text = String(value || '').trim();
        if (!text) return '';
        if (text.length <= maxLength) return text;
        return `${text.slice(0, maxLength - 1)}...`;
      }

      function resetCreatorForm() {
        document.getElementById('creator_name').value = '';
        document.getElementById('creator_affiliation').value = '';
        document.getElementById('creator_orcid').value = '';
        currentCreatorIndex = -1;
        const addButton = document.getElementById('add_creator');
        if (addButton) {
          addButton.textContent = 'Add creator';
        }
        const clearButton = document.getElementById('clear_creator_form');
        if (clearButton) {
          clearButton.textContent = 'Clear form';
        }
        if (creatorEditBanner) {
          creatorEditBanner.classList.remove('active');
        }
        if (creatorMetaStatus) {
          creatorMetaStatus.textContent = creators.length ? 'Add another creator or preview one to edit it.' : 'Add a creator to begin.';
        }
      }

      function loadCreator(index) {
        const target = creators[index];
        if (!target) {
          resetCreatorForm();
          renderCreatorsTable();
          return;
        }
        currentCreatorIndex = index;
        document.getElementById('creator_name').value = target.name || '';
        document.getElementById('creator_affiliation').value = target.affiliation || '';
        document.getElementById('creator_orcid').value = target.identifier || '';
        const addButton = document.getElementById('add_creator');
        if (addButton) {
          addButton.textContent = 'Update creator';
        }
        const clearButton = document.getElementById('clear_creator_form');
        if (clearButton) {
          clearButton.textContent = 'Cancel editing';
        }
        if (creatorEditBanner) {
          creatorEditBanner.classList.add('active');
        }
        if (creatorEditTitle) {
          creatorEditTitle.textContent = `Editing creator ${index + 1}: ${target.name || 'Unnamed creator'}`;
        }
        if (creatorMetaStatus) {
          creatorMetaStatus.textContent = 'Preview a creator to edit it, or clear the form to add a new one.';
        }
        renderCreatorsTable();
      }

      function renderCreatorsTable() {
        if (!creatorsTable) return;
        if (!creators.length) {
          creatorsTable.innerHTML = `<tr><td colspan="5" class="muted-cell">No creators added yet.</td></tr>`;
          return;
        }
        creatorsTable.innerHTML = creators.map((creator, index) => `
          <tr class="${index === currentCreatorIndex ? 'current-row' : ''}">
            <td><strong>${escapeHtml(creator.name || `Creator ${index + 1}`)}</strong></td>
            <td>${escapeHtml(creator.affiliation || '')}</td>
            <td>${escapeHtml(creator.identifier || '')}</td>
            <td><div class="table-actions"><button type="button" data-preview-creator="${index}">Preview</button></div></td>
            <td><div class="table-actions"><button type="button" class="ghost" data-remove-creator-row="${index}">Remove</button></div></td>
          </tr>
        `).join('');
        creatorsTable.querySelectorAll('[data-preview-creator]').forEach(btn => {
          btn.addEventListener('click', () => {
            loadCreator(Number(btn.dataset.previewCreator));
          });
        });
        creatorsTable.querySelectorAll('[data-remove-creator-row]').forEach(btn => {
          btn.addEventListener('click', () => {
            const removeIndex = Number(btn.dataset.removeCreatorRow);
            creators.splice(removeIndex, 1);
            if (currentCreatorIndex === removeIndex) {
              resetCreatorForm();
            } else if (currentCreatorIndex > removeIndex) {
              currentCreatorIndex -= 1;
            }
            syncCreators();
          });
        });
      }

      function resetDatasetMetaForm() {
        document.getElementById('ds_name').value = '';
        document.getElementById('ds_description').value = '';
        document.getElementById('ds_version').value = '';
        document.getElementById('ds_license').value = '';
        document.getElementById('ds_url').value = '';
        currentMetaIndex = -1;
        const addButton = document.getElementById('add_dataset');
        if (addButton) {
          addButton.textContent = 'Add dataset';
        }
        const clearButton = document.getElementById('clear_dataset_form');
        if (clearButton) {
          clearButton.textContent = 'Clear form';
        }
        if (datasetEditBanner) {
          datasetEditBanner.classList.remove('active');
        }
        if (datasetMetaStatus) {
          datasetMetaStatus.textContent = datasets.length ? 'Add another dataset or preview one to edit it.' : 'Add a dataset to begin.';
        }
      }

      function loadDatasetMeta(index) {
        const target = datasets[index];
        if (!target) {
          resetDatasetMetaForm();
          renderDatasetMetaTable();
          return;
        }
        currentMetaIndex = index;
        document.getElementById('ds_name').value = target.name || '';
        document.getElementById('ds_description').value = target.description || '';
        document.getElementById('ds_version').value = target.version || '';
        document.getElementById('ds_license').value = target.license || '';
        document.getElementById('ds_url').value = target.url || '';
        const addButton = document.getElementById('add_dataset');
        if (addButton) {
          addButton.textContent = 'Update dataset';
        }
        const clearButton = document.getElementById('clear_dataset_form');
        if (clearButton) {
          clearButton.textContent = 'Cancel editing';
        }
        if (datasetEditBanner) {
          datasetEditBanner.classList.add('active');
        }
        if (datasetEditTitle) {
          datasetEditTitle.textContent = `Editing dataset ${index + 1}: ${target.name || 'Unnamed dataset'}`;
        }
        if (datasetMetaStatus) {
          datasetMetaStatus.textContent = 'Preview a dataset to edit it, or clear the form to add a new one.';
        }
        renderDatasetMetaTable();
      }

      function renderDatasetMetaTable() {
        if (!datasetMetaTable) return;
        if (!datasets.length) {
          datasetMetaTable.innerHTML = `<tr><td colspan="6" class="muted-cell">No datasets added yet.</td></tr>`;
          return;
        }
        datasetMetaTable.innerHTML = datasets.map((dataset, index) => `
          <tr class="${index === currentMetaIndex ? 'current-row' : ''}">
            <td><strong>${escapeHtml(dataset.name || `Dataset ${index + 1}`)}</strong><div class="note">${escapeHtml(truncateText(dataset.description || ''))}</div></td>
            <td>${escapeHtml(dataset.version || '')}</td>
            <td>${escapeHtml(dataset.license || '')}</td>
            <td>${escapeHtml(dataset.url || '')}</td>
            <td><div class="table-actions"><button type="button" data-preview-dataset-meta="${index}">Preview</button></div></td>
            <td><div class="table-actions"><button type="button" class="ghost" data-remove-dataset-meta="${index}">Remove</button></div></td>
          </tr>
        `).join('');
        datasetMetaTable.querySelectorAll('[data-preview-dataset-meta]').forEach(btn => {
          btn.addEventListener('click', () => {
            loadDatasetMeta(Number(btn.dataset.previewDatasetMeta));
          });
        });
        datasetMetaTable.querySelectorAll('[data-remove-dataset-meta]').forEach(btn => {
          btn.addEventListener('click', () => {
            const removeIndex = Number(btn.dataset.removeDatasetMeta);
            datasets.splice(removeIndex, 1);
            if (currentMetaIndex === removeIndex) {
              resetDatasetMetaForm();
            } else if (currentMetaIndex > removeIndex) {
              currentMetaIndex -= 1;
            }
            if (currentDetailIndex === removeIndex) {
              currentDetailIndex = -1;
            } else if (currentDetailIndex > removeIndex) {
              currentDetailIndex -= 1;
            }
            syncDatasets();
            loadDatasetDetails(Number(datasetSelect.value || 0));
          });
        });
      }

      function getFieldCount(dataset) {
        return summarizeFields(dataset).length;
      }

      function hasDraftDetails(dataset) {
        return formStateHasContent(dataset?.uiDraftDetails);
      }

      function getDetailFormState() {
        return {
          datePublished: document.getElementById('ds_date').value.trim(),
          citeAs: document.getElementById('ds_cite').value.trim(),
          distribution: {
            contentUrl: document.getElementById('dist_url').value.trim(),
            encodingFormat: document.getElementById('dist_format').value.trim(),
            name: document.getElementById('dist_name').value.trim(),
            md5: document.getElementById('dist_md5').value.trim(),
            sha256: document.getElementById('dist_sha256').value.trim(),
          },
          recordSetName: document.getElementById('rs_name').value.trim(),
        };
      }

      function getSavedDetailState(dataset) {
        const distribution = Array.isArray(dataset?.distribution) ? dataset.distribution[0] || {} : {};
        const recordSet = Array.isArray(dataset?.recordSet) ? dataset.recordSet[0] || {} : {};
        return {
          datePublished: dataset?.datePublished || '',
          citeAs: dataset?.citeAs || '',
          distribution: {
            contentUrl: distribution.contentUrl || '',
            encodingFormat: distribution.encodingFormat || '',
            name: distribution.name || '',
            md5: distribution.md5 || '',
            sha256: distribution.sha256 || '',
          },
          recordSetName: recordSet.name || '',
        };
      }

      function detailStatesEqual(left, right) {
        return JSON.stringify(left || {}) === JSON.stringify(right || {});
      }

      function formStateHasContent(formState) {
        if (!formState) return false;
        return Boolean(
          formState.datePublished ||
          formState.citeAs ||
          formState.distribution.contentUrl ||
          formState.distribution.encodingFormat ||
          formState.distribution.name ||
          formState.distribution.md5 ||
          formState.distribution.sha256 ||
          formState.recordSetName
        );
      }

      function saveDraftForDataset(index) {
        const target = datasets[index];
        if (!target) return;
        const formState = getDetailFormState();
        const savedState = getSavedDetailState(target);
        if (formStateHasContent(formState) && !detailStatesEqual(formState, savedState)) {
          target.uiDraftDetails = formState;
        } else {
          delete target.uiDraftDetails;
        }
      }

      function persistCurrentDraft() {
        if (currentDetailIndex >= 0) {
          saveDraftForDataset(currentDetailIndex);
        }
      }

      function hasDatasetDetails(dataset) {
        if (!dataset || typeof dataset !== 'object') return false;
        return Boolean(
          dataset.datePublished ||
          dataset.citeAs ||
          (Array.isArray(dataset.distribution) && dataset.distribution.length) ||
          (Array.isArray(dataset.recordSet) && dataset.recordSet.length)
        );
      }

      function updateSelectedDatasetStatus() {
        if (!selectedDatasetStatus) return;
        const selected = Number(datasetSelect.value || 0);
        const target = datasets[selected];
        const status = getDatasetStatus(target);
        selectedDatasetStatus.className = `status-pill ${status}`;
        if (!target) {
          selectedDatasetStatus.textContent = 'No dataset selected';
          return;
        }
        selectedDatasetStatus.textContent = getStatusLabel(status);
        if (hasDraftDetails(target)) {
          selectedDatasetStatus.textContent += ' + Draft';
          selectedDatasetStatus.className = 'status-pill draft';
        }
      }

      function updateDatasetProgress() {
        if (!datasetProgress) return;
        const total = datasets.length;
        if (!total) {
          datasetProgress.textContent = 'No datasets added yet.';
          updateSelectedDatasetStatus();
          return;
        }
        const detailed = datasets.filter(d => getDatasetStatus(d) === 'detailed').length;
        const skipped = datasets.filter(d => getDatasetStatus(d) === 'skipped').length;
        const drafts = datasets.filter(d => hasDraftDetails(d)).length;
        const pending = datasets.filter(d => getDatasetStatus(d) === 'pending' && !hasDraftDetails(d)).length;
        datasetProgress.textContent = `${total} datasets total - ${detailed} detailed - ${drafts} draft - ${skipped} skipped - ${pending} pending`;
        updateSelectedDatasetStatus();
      }

      function renderDetailTable() {
        if (!detailTable) return;
        if (!datasets.length) {
          detailTable.innerHTML = `<tr><td colspan="6" class="muted-cell">No datasets added yet.</td></tr>`;
          return;
        }
        const selectedIndex = Number(datasetSelect.value || 0);
        const rows = [];
        datasets.forEach((dataset, index) => {
          const status = getDatasetStatus(dataset);
          const hasDraft = hasDraftDetails(dataset);
          const fileUsed = getFileUsedLabel(dataset);
          const fieldCount = getFieldCount(dataset);
          const isCurrent = index === selectedIndex;
          const isExpanded = expandedReportIndex === index;
          rows.push(`
            <tr class="${isCurrent ? 'current-row' : ''}">
              <td><strong>${escapeHtml(dataset.name || `Dataset ${index + 1}`)}</strong>${hasDraft ? '<span class="tiny-badge">Draft</span>' : ''}<div class="note">${isCurrent ? 'Currently selected' : 'Select Review to edit this dataset.'}</div></td>
              <td><span class="status-pill ${hasDraft ? 'draft' : status}">${getStatusLabel(status)}${hasDraft ? ' + Draft' : ''}</span></td>
              <td>${escapeHtml(fileUsed)}</td>
              <td>${fieldCount ? `${fieldCount} field${fieldCount === 1 ? '' : 's'}` : '<span class="muted-cell">No fields detected</span>'}</td>
              <td><div class="table-actions"><button type="button" class="ghost" data-toggle-report="${index}">${isExpanded ? 'Hide report' : 'Show report'}</button></div></td>
              <td><div class="table-actions"><button type="button" data-review-dataset="${index}">Review</button></div></td>
            </tr>
          `);
          if (isExpanded) {
            rows.push(`
              <tr class="report-row">
                <td colspan="6">${renderInlineReport(dataset, index)}</td>
              </tr>
            `);
          }
        });
        detailTable.innerHTML = rows.join('');
        detailTable.querySelectorAll('[data-review-dataset]').forEach(btn => {
          btn.addEventListener('click', () => {
            const index = Number(btn.dataset.reviewDataset);
            persistCurrentDraft();
            loadDatasetDetails(index);
          });
        });
        detailTable.querySelectorAll('[data-toggle-report]').forEach(btn => {
          btn.addEventListener('click', () => {
            const index = Number(btn.dataset.toggleReport);
            expandedReportIndex = expandedReportIndex === index ? -1 : index;
            renderDetailTable();
          });
        });
      }

      function renderInlineReport(dataset, index) {
        const fields = summarizeFields(dataset);
        const rows = fields.map(field => `
          <tr>
            <td>${escapeHtml(field.name || '')}</td>
            <td>${escapeHtml(field.detectedType || field.mappedType || 'sc:Text')}</td>
            <td>${escapeHtml(field.example || '') || '<span class="muted-cell">No example</span>'}</td>
            <td>${escapeHtml(field.mappedType || field.detectedType || 'sc:Text')}</td>
          </tr>
        `).join('');
        return `
          <div class="inline-report">
            <div class="report-title">
              <strong>${escapeHtml(dataset.name || `Dataset ${index + 1}`)}</strong>
              <div class="report-meta">File used: ${escapeHtml(getFileUsedLabel(dataset))}</div>
            </div>
            ${fields.length ? `
              <table class="mini-table">
                <thead>
                  <tr>
                    <th>Field</th>
                    <th>Type</th>
                    <th>Example</th>
                    <th>Mapped sc datatype</th>
                  </tr>
                </thead>
                <tbody>${rows}</tbody>
              </table>
            ` : '<div class="report-empty">No detected fields available for this dataset yet.</div>'}
          </div>
        `;
      }

      function clearDetailInputs() {
        expandedFieldDescriptionIndex = -1;
        document.getElementById('ds_date').value = '';
        document.getElementById('ds_cite').value = '';
        document.getElementById('dist_url').value = '';
        document.getElementById('dist_format').value = '';
        document.getElementById('dist_name').value = '';
        document.getElementById('dist_md5').value = '';
        document.getElementById('dist_sha256').value = '';
        document.getElementById('rs_name').value = '';
        document.getElementById('field_name').value = '';
        document.getElementById('field_desc').value = '';
        document.getElementById('field_example').value = '';
        document.getElementById('field_type').value = 'sc:Text';
        document.getElementById('infer_file').value = '';
        document.getElementById('fields_report_note').textContent = 'No file analyzed yet.';
        document.getElementById('fields_report').innerHTML = '';
      }

      function loadDatasetDetails(index) {
        const target = datasets[index];
        clearDetailInputs();
        const status = document.getElementById('details_status');
        if (!target) {
          currentDetailIndex = -1;
          if (status) status.textContent = 'Select a dataset first.';
          updateDatasetProgress();
          renderDetailTable();
          return;
        }
        currentDetailIndex = index;
        datasetSelect.value = String(index);
        const draft = target.uiDraftDetails || {};
        document.getElementById('ds_date').value = draft.datePublished || target.datePublished || '';
        document.getElementById('ds_cite').value = draft.citeAs || target.citeAs || '';
        const distribution = Array.isArray(target.distribution) ? target.distribution[0] : null;
        const draftDistribution = draft.distribution || {};
        if (distribution) {
          document.getElementById('dist_url').value = draftDistribution.contentUrl || distribution.contentUrl || '';
          document.getElementById('dist_format').value = draftDistribution.encodingFormat || distribution.encodingFormat || '';
          document.getElementById('dist_name').value = draftDistribution.name || distribution.name || '';
          document.getElementById('dist_md5').value = draftDistribution.md5 || distribution.md5 || '';
          document.getElementById('dist_sha256').value = draftDistribution.sha256 || distribution.sha256 || '';
        } else {
          document.getElementById('dist_url').value = draftDistribution.contentUrl || '';
          document.getElementById('dist_format').value = draftDistribution.encodingFormat || '';
          document.getElementById('dist_name').value = draftDistribution.name || '';
          document.getElementById('dist_md5').value = draftDistribution.md5 || '';
          document.getElementById('dist_sha256').value = draftDistribution.sha256 || '';
        }
        const recordSet = Array.isArray(target.recordSet) ? target.recordSet[0] : null;
        if (recordSet) {
          document.getElementById('rs_name').value = draft.recordSetName || recordSet.name || '';
        } else {
          document.getElementById('rs_name').value = draft.recordSetName || '';
        }
        renderDetectedFieldsTable(target);
        if (status) {
          const uiStatus = getDatasetStatus(target);
          if (uiStatus === 'skipped') {
            status.textContent = 'Details skipped for this dataset. Use Mark pending or Apply details to change that.';
          } else if (uiStatus === 'detailed') {
            status.textContent = 'Details already saved for this dataset.';
          } else {
            status.textContent = 'Dataset is pending details.';
          }
        }
        updateDatasetProgress();
        renderDetailTable();
      }

      function moveToNextPendingDataset() {
        if (!datasets.length) return;
        const current = Number(datasetSelect.value || 0);
        const next = datasets.findIndex((dataset, index) => index > current && getDatasetStatus(dataset) === 'pending');
        if (next !== -1) {
          datasetSelect.value = String(next);
          loadDatasetDetails(next);
          return;
        }
        const firstPending = datasets.findIndex(dataset => getDatasetStatus(dataset) === 'pending');
        if (firstPending !== -1) {
          datasetSelect.value = String(firstPending);
          loadDatasetDetails(firstPending);
          return;
        }
        loadDatasetDetails(current);
      }

      function syncCreators() {
        creatorsInput.value = JSON.stringify(creators);
        renderCreatorsTable();
        if (!restoring) {
          saveState();
        }
      }

      function syncDatasets() {
        datasets.forEach(normalizeDatasetState);
        if (expandedReportIndex >= datasets.length) {
          expandedReportIndex = -1;
        }
        const selectedBefore = currentDetailIndex >= 0 ? currentDetailIndex : Math.max(0, Number(datasetSelect.value || 0));
        datasetsInput.value = JSON.stringify(datasets);
        datasetSelect.innerHTML = datasets.map((d, i) => {
          const label = `${d.name} (${getStatusLabel(getDatasetStatus(d))}${hasDraftDetails(d) ? ' + Draft' : ''})`;
          return `<option value="${i}">${label}</option>`;
        }).join('');
        if (datasets.length) {
          datasetSelect.value = String(Math.min(selectedBefore, datasets.length - 1));
        }
        renderDatasetMetaTable();
        updateDatasetProgress();
        renderDetailTable();
        if (!restoring) {
          saveState();
        }
      }

      document.getElementById('add_creator').addEventListener('click', () => {
        const name = document.getElementById('creator_name').value.trim();
        if (!name) return;
        const affiliation = document.getElementById('creator_affiliation').value.trim();
        const identifier = document.getElementById('creator_orcid').value.trim();
        const currentCreator = currentCreatorIndex >= 0 ? creators[currentCreatorIndex] : null;
        if (currentCreator) {
          currentCreator.name = name;
          currentCreator.affiliation = affiliation;
          currentCreator.identifier = identifier;
        } else {
          creators.push({ name, affiliation, identifier });
        }
        syncCreators();
        resetCreatorForm();
        if (creatorMetaStatus) {
          creatorMetaStatus.textContent = currentCreator ? 'Creator updated.' : 'Creator added.';
        }
      });

      document.getElementById('clear_creator_form').addEventListener('click', () => {
        resetCreatorForm();
        renderCreatorsTable();
      });

      document.getElementById('add_dataset').addEventListener('click', () => {
        const name = document.getElementById('ds_name').value.trim();
        const description = document.getElementById('ds_description').value.trim();
        const version = document.getElementById('ds_version').value.trim();
        const license = document.getElementById('ds_license').value.trim();
        const url = document.getElementById('ds_url').value.trim();
        if (!(name && description && version && license && url)) return;
        persistCurrentDraft();
        const currentDataset = currentMetaIndex >= 0 ? datasets[currentMetaIndex] : null;
        if (currentDataset) {
          currentDataset.name = name;
          currentDataset.description = description;
          currentDataset.version = version;
          currentDataset.license = license;
          currentDataset.url = url;
        } else {
          datasets.push({ name, description, version, license, url, uiStatus: 'pending' });
        }
        const targetIndex = currentDataset ? currentMetaIndex : datasets.length - 1;
        currentMetaIndex = -1;
        syncDatasets();
        datasetSelect.value = String(targetIndex);
        loadDatasetDetails(targetIndex);
        resetDatasetMetaForm();
        if (datasetMetaStatus) {
          datasetMetaStatus.textContent = currentDataset ? 'Dataset updated.' : 'Dataset added.';
        }
      });

      document.getElementById('clear_dataset_form').addEventListener('click', () => {
        resetDatasetMetaForm();
        renderDatasetMetaTable();
      });

      document.getElementById('clear_datasets').addEventListener('click', () => {
        datasets.length = 0;
        expandedReportIndex = -1;
        currentDetailIndex = -1;
        currentMetaIndex = -1;
        expandedFieldDescriptionIndex = -1;
        syncDatasets();
        clearDetailInputs();
        resetDatasetMetaForm();
      });

      function applyDetails(silent = false) {
        const selected = Number(datasetSelect.value || 0);
        const target = datasets[selected];
        const status = document.getElementById('details_status');
        if (!target) {
          if (status) status.textContent = 'Select a dataset first.';
          return;
        }
        saveDraftForDataset(selected);
        const date = document.getElementById('ds_date').value.trim();
        const cite = document.getElementById('ds_cite').value.trim();
        const hasExistingDetails = hasDatasetDetails(target);
        const currentStatus = getDatasetStatus(target);
        const hasInputDetails = Boolean(
          date ||
          cite ||
          document.getElementById('dist_url').value.trim() ||
          document.getElementById('rs_name').value.trim()
        );
        if (currentStatus === 'skipped' && !(hasExistingDetails || hasInputDetails)) {
          if (status && !silent) status.textContent = 'Details remain skipped for this dataset.';
          syncDatasets();
          return false;
        }
        if (!(hasExistingDetails || hasInputDetails)) {
          target.uiStatus = 'pending';
          if (status && !silent) status.textContent = 'No details entered yet. Dataset remains pending.';
          syncDatasets();
          return false;
        }
        if (date) target.datePublished = date;
        if (cite) target.citeAs = cite;
        const distUrl = document.getElementById('dist_url').value.trim();
        if (distUrl) {
          const md5 = document.getElementById('dist_md5').value.trim();
          const sha256 = document.getElementById('dist_sha256').value.trim();
          if (!(md5 || sha256)) {
            if (status && !silent) status.textContent = 'Distribution added without checksum (not recommended).';
          }
          const distNameInput = document.getElementById('dist_name').value.trim();
          let derivedName = distNameInput;
          if (!derivedName) {
            const match = distUrl.split('?')[0].split('/').pop();
            derivedName = match || 'file';
          }
          const fileId = (derivedName || 'file').toLowerCase().replace(/\\s+/g, '-');
          target.distribution = [{
            '@type': 'cr:FileObject',
            '@id': fileId,
            contentUrl: distUrl,
            encodingFormat: document.getElementById('dist_format').value.trim() || 'text/csv',
            name: derivedName,
            md5: md5 || undefined,
            sha256: sha256 || undefined,
          }];
          if (target.recordSet && target.recordSet[0] && Array.isArray(target.recordSet[0].field)) {
            target.recordSet[0].field.forEach(f => {
              if (!f.source) {
                f.source = { fileObject: { '@id': fileId }, extract: { column: f.name || '' } };
              } else if (f.source.fileObject) {
                f.source.fileObject['@id'] = fileId;
              }
            });
          }
        }
        const rsName = document.getElementById('rs_name').value.trim();
        if (rsName) {
          target.recordSet = target.recordSet || [{ '@type': 'cr:RecordSet', name: rsName, field: [] }];
          if (target.recordSet[0]) {
            target.recordSet[0].name = rsName;
          }
        }
        delete target.uiDraftDetails;
        target.uiStatus = 'detailed';
        if (status && !silent) status.textContent = 'Details applied.';
        syncDatasets();
        return true;
      }
      document.getElementById('apply_details').addEventListener('click', () => {
        if (applyDetails()) {
          moveToNextPendingDataset();
        }
      });

      document.getElementById('clear_details').addEventListener('click', () => {
        const selected = Number(datasetSelect.value || 0);
        const target = datasets[selected];
        const status = document.getElementById('details_status');
        if (!target) {
          if (status) status.textContent = 'Select a dataset first.';
          return;
        }
        delete target.datePublished;
        delete target.citeAs;
        delete target.distribution;
        delete target.recordSet;
        delete target.uiDraftDetails;
        delete target.uiFieldPreview;
        delete target.uiInferenceFileName;
        expandedFieldDescriptionIndex = -1;
        target.uiStatus = 'pending';
        clearDetailInputs();
        syncDatasets();
        loadDatasetDetails(selected);
        if (status) status.textContent = 'Details cleared for this dataset.';
      });

      document.getElementById('skip_details').addEventListener('click', () => {
        const selected = Number(datasetSelect.value || 0);
        const target = datasets[selected];
        const status = document.getElementById('details_status');
        if (!target) {
          if (status) status.textContent = 'Select a dataset first.';
          return;
        }
        saveDraftForDataset(selected);
        target.uiStatus = 'skipped';
        syncDatasets();
        if (status) status.textContent = 'Details skipped. This dataset will keep its base metadata only.';
        moveToNextPendingDataset();
      });

      document.getElementById('mark_pending').addEventListener('click', () => {
        const selected = Number(datasetSelect.value || 0);
        const target = datasets[selected];
        const status = document.getElementById('details_status');
        if (!target) {
          if (status) status.textContent = 'Select a dataset first.';
          return;
        }
        saveDraftForDataset(selected);
        target.uiStatus = 'pending';
        syncDatasets();
        if (status) status.textContent = 'Dataset marked as pending again.';
        loadDatasetDetails(selected);
      });

      document.getElementById('add_field').addEventListener('click', () => {
        const selected = Number(datasetSelect.value || 0);
        const target = datasets[selected];
        if (!target) return;
        const rsName = document.getElementById('rs_name').value.trim();
        if (!rsName) return;
        const fieldName = document.getElementById('field_name').value.trim();
        if (!fieldName) return;
        const field = {
          name: fieldName,
          description: document.getElementById('field_desc').value.trim(),
          detectedType: rawDatatypeFromSchema(document.getElementById('field_type').value),
          mappedType: document.getElementById('field_type').value,
          example: document.getElementById('field_example').value.trim(),
          source: 'manual',
        };
        target.uiFieldPreview = [...summarizeFields(target), field];
        buildRecordSetFields(target);
        saveDraftForDataset(selected);
        delete target.uiDraftDetails;
        target.uiStatus = 'detailed';
        document.getElementById('field_name').value = '';
        document.getElementById('field_desc').value = '';
        document.getElementById('field_example').value = '';
        syncDatasets();
        loadDatasetDetails(selected);
      });

      const STORAGE_KEY = 'biocypher_form_state';
      function saveState() {
        persistCurrentDraft();
        const state = {
          name: document.querySelector('[name="name"]').value,
          description: document.querySelector('[name="description"]').value,
          version: document.querySelector('[name="version"]').value,
          license: document.querySelector('[name="license"]').value,
          code_repository: document.querySelector('[name="code_repository"]').value,
          keywords: document.querySelector('[name="keywords"]').value,
          creators,
          datasets,
        };
        localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
      }
      function restoreState() {
        const raw = localStorage.getItem(STORAGE_KEY);
        if (!raw) return;
        try {
          restoring = true;
          const state = JSON.parse(raw);
          document.querySelector('[name="name"]').value = state.name || '';
          document.querySelector('[name="description"]').value = state.description || '';
          document.querySelector('[name="version"]').value = state.version || '';
          document.querySelector('[name="license"]').value = state.license || '';
          document.querySelector('[name="code_repository"]').value = state.code_repository || '';
          document.querySelector('[name="keywords"]').value = state.keywords || '';
        creators.splice(0, creators.length, ...(state.creators || []));
        datasets.splice(0, datasets.length, ...((state.datasets || []).map(normalizeDatasetState)));
          syncCreators();
          syncDatasets();
          restoring = false;
        } catch (e) {
          restoring = false;
          localStorage.removeItem(STORAGE_KEY);
        }
      }
      function clearState() {
        const confirmed = window.confirm(
          'Clear all saved form data?\n\nThis will remove the adapter, creators, datasets, and dataset details currently stored in this browser.'
        );
        if (!confirmed) {
          return;
        }
        localStorage.removeItem(STORAGE_KEY);
        creators.splice(0, creators.length);
        datasets.splice(0, datasets.length);
        expandedReportIndex = -1;
        currentDetailIndex = -1;
        currentCreatorIndex = -1;
        document.querySelector('[name="name"]').value = '';
        document.querySelector('[name="description"]').value = '';
        document.querySelector('[name="version"]').value = '';
        document.querySelector('[name="license"]').value = '';
        document.querySelector('[name="code_repository"]').value = '';
        document.querySelector('[name="keywords"]').value = '';
        resetCreatorForm();
        clearDetailInputs();
        syncCreators();
        syncDatasets();
        loadDatasetDetails(0);
      }
      restoreState();
      syncCreators();
      syncDatasets();
      datasetSelect.addEventListener('change', () => {
        persistCurrentDraft();
        loadDatasetDetails(Number(datasetSelect.value || 0));
      });
      loadDatasetDetails(0);
      document.querySelectorAll('input, textarea').forEach(el => {
        el.addEventListener('input', saveState);
      });

      function inferType(values) {
        if (!values.length) return 'string';
        const isInt = values.every(v => /^-?\d+$/.test(v));
        if (isInt) return 'integer';
        const isFloat = values.every(v => /^-?\d+(\.\d+)?$/.test(v));
        if (isFloat) return 'float';
        const isBool = values.every(v => /^(true|false)$/i.test(v));
        if (isBool) return 'boolean';
        const isDate = values.every(v => /^\d{4}-\d{2}-\d{2}$/.test(v));
        if (isDate) return 'date';
        const isDateTime = values.every(v => !Number.isNaN(Date.parse(v)) && /[tT ]/.test(v));
        if (isDateTime) return 'datetime';
        const isTime = values.every(v => /^\d{2}:\d{2}(:\d{2})?$/.test(v));
        if (isTime) return 'time';
        const isUrl = values.every(v => /^https?:\/\/\S+$/i.test(v));
        if (isUrl) return 'url';
        return 'string';
      }

      function parseDelimited(text) {
        const lines = text.split(/\r?\n/).filter(l => l.trim().length);
        if (!lines.length) return { headers: [], rows: [] };
        const header = lines[0];
        const tabCount = (header.match(/\t/g) || []).length;
        const commaCount = (header.match(/,/g) || []).length;
        const sep = tabCount > commaCount ? '\t' : ',';
        const headers = header.split(sep).map(h => h.trim()).filter(Boolean);
        const rows = lines.slice(1, 51).map(line => line.split(sep));
        return { headers, rows };
      }

      async function analyzeFile() {
        const fileInput = document.getElementById('infer_file');
        const file = fileInput.files && fileInput.files[0];
        const note = document.getElementById('fields_report_note');
        const report = document.getElementById('fields_report');
        report.innerHTML = '';
        if (!file) {
          note.textContent = 'No file selected.';
          return;
        }
        if (file.size > 5 * 1024 * 1024) {
          note.textContent = 'File too large. Max size is 5MB.';
          return;
        }
        const text = await file.text();
        const { headers, rows } = parseDelimited(text);
        if (!headers.length) {
          note.textContent = 'No headers detected.';
          return;
        }
        const fieldSummaries = headers.map((h, idx) => {
          const values = rows.map(r => (r[idx] || '').trim()).filter(Boolean);
          const detectedType = inferType(values);
          return {
            name: h,
            detectedType,
            example: values[0] || '',
            mappedType: schemaDatatypeFromRaw(detectedType),
          };
        });
        const selected = Number(datasetSelect.value || 0);
        const target = datasets[selected];
        if (target) {
          const rsName = document.getElementById('rs_name').value.trim() || 'records';
          target.recordSet = target.recordSet || [{ '@type': 'cr:RecordSet', name: rsName, field: [] }];
          if (target.recordSet[0]) {
            target.recordSet[0].name = rsName;
          }
          target.uiInferenceFileName = file.name;
          target.uiFieldPreview = fieldSummaries.map(f => ({
            name: f.name,
            detectedType: f.detectedType,
            example: f.example,
            mappedType: f.mappedType,
            description: '',
            source: 'detected',
          }));
          buildRecordSetFields(target);
          saveDraftForDataset(selected);
          delete target.uiDraftDetails;
          target.uiStatus = 'detailed';
          syncDatasets();
          loadDatasetDetails(selected);
          renderDetectedFieldsTable(target);
        } else {
          note.textContent = `Detected ${fieldSummaries.length} fields.`;
        }
      }
      window.analyzeFile = analyzeFile;

      document.querySelector('form').addEventListener('submit', (e) => {
        saveState();
        const hasDetailsInput = Boolean(
          document.getElementById('ds_date').value.trim() ||
          document.getElementById('ds_cite').value.trim() ||
          document.getElementById('dist_url').value.trim() ||
          document.getElementById('rs_name').value.trim()
        );
        if (hasDetailsInput) {
          applyDetails();
        }
        if (!creators.length) {
          e.preventDefault();
          alert('Please add at least one creator.');
          show(0);
          return;
        }
        if (!datasets.length) {
          e.preventDefault();
          alert('Please add at least one dataset.');
          show(1);
          return;
        }
      });

      const themeToggle = document.getElementById('theme_toggle');
      function setTheme(mode) {
        document.body.classList.toggle('light', mode === 'light');
        document.documentElement.classList.toggle('light', mode === 'light');
        if (themeToggle) {
          themeToggle.checked = mode === 'light';
        }
        const themeLabel = document.getElementById('theme_label');
        if (themeLabel) {
          themeLabel.textContent = mode === 'light' ? 'Light mode' : 'Dark mode';
        }
        const status = document.getElementById('theme_status');
        if (status) {
          status.textContent = `Theme: ${mode}`;
        }
        localStorage.setItem('biocypher_theme', mode);
      }
      function toggleTheme() {
        const current = document.body.classList.contains('light') ? 'light' : 'dark';
        setTheme(current === 'light' ? 'dark' : 'light');
      }
      window.toggleTheme = toggleTheme;
      const savedTheme = localStorage.getItem('biocypher_theme');
      if (savedTheme) {
        setTheme(savedTheme);
      } else {
        setTheme('dark');
      }
      const status = document.getElementById('theme_status');
      if (status && !status.textContent) {
        status.textContent = 'Theme: dark';
      }
    </script>
  </body>
</html>
"""


def _render_form(message: str = "") -> str:
    notice = f"<div class='notice'>{html.escape(message)}</div>" if message else ""
    return _TEMPLATE.replace("{{NOTICE}}", notice)


def _parse_list(raw: str) -> list[str]:
    return [item.strip() for item in raw.split(",") if item.strip()]


def _load_creators(data: dict[str, str]) -> list[dict[str, Any]]:
    raw = data.get("creators_data", "")
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid creators data: {exc}") from exc
    if not isinstance(parsed, list):
        raise ValueError("Creators data must be a list.")
    return parsed


def _load_datasets(data: dict[str, str]) -> list[dict[str, Any]]:
    raw = data.get("datasets_data", "")
    if not raw:
        raise ValueError("At least one dataset is required.")
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid datasets data: {exc}") from exc
    if not isinstance(parsed, list) or not parsed:
        raise ValueError("Datasets data must be a non-empty list.")
    return parsed


class _Handler(BaseHTTPRequestHandler):
    output_dir: Path

    def _send(self, content: str, status: int = 200) -> None:
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(content.encode("utf-8"))

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/download":
            file_path = self.output_dir / METADATA_FILENAME
            if not file_path.exists():
                self._send(_render_form("No generated file found."), status=404)
                return
            data = file_path.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "application/ld+json")
            self.send_header(
                "Content-Disposition", f'attachment; filename="{METADATA_FILENAME}"'
            )
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return
        self._send(_render_form())

    def do_POST(self) -> None:  # noqa: N802
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length).decode("utf-8")
        data = {k: v[0] for k, v in parse_qs(body).items()}

        try:
            creators = _load_creators(data)
            keywords = _parse_list(data["keywords"])
            datasets = _load_datasets(data)

            doc = build_adapter(
                name=data["name"],
                description=data["description"],
                version=data["version"],
                license_url=data["license"],
                code_repository=data["code_repository"],
                creators=[build_creator(
                    name=c.get("name", ""),
                    affiliation=c.get("affiliation", ""),
                    orcid=c.get("identifier", ""),
                ) for c in creators],
                keywords=keywords,
                datasets=[_coerce_dataset(d) for d in datasets],
            )
        except Exception as exc:  # noqa: BLE001
            self._send(_render_form(str(exc)), status=200)
            return

        output_path = self.output_dir / METADATA_FILENAME
        output_path.write_text(json.dumps(doc, indent=2), encoding="utf-8")
        result = validate(doc)

        if not result.is_valid:
            items = "".join(f"<li>{html.escape(err)}</li>" for err in result.errors)
            content = _render_result(
                file_name=output_path.name,
                file_contents=output_path.read_text(encoding="utf-8"),
                is_valid=False,
                errors_html=f"<ul>{items}</ul>",
                profile_version=result.profile_version,
                error_count=len(result.errors),
                warnings_html="<p class='note'>No warnings reported.</p>",
            )
            self._send(content, status=200)
            return

        content = _render_result(
            file_name=output_path.name,
            file_contents=output_path.read_text(encoding="utf-8"),
            is_valid=True,
            errors_html="",
            profile_version=result.profile_version,
            error_count=0,
            warnings_html="<p class='note'>No warnings reported.</p>",
        )
        self._send(content, status=200)


def _coerce_dataset(data: dict[str, Any]) -> dict[str, Any]:
    distribution = data.get("distribution")
    record_set = data.get("recordSet")
    if isinstance(distribution, list):
        for entry in distribution:
            if isinstance(entry, dict):
                entry.setdefault("@type", "cr:FileObject")
                if "@id" not in entry:
                    name = entry.get("name")
                    if not name and isinstance(entry.get("contentUrl"), str):
                        name = entry["contentUrl"].split("?")[0].split("/")[-1]
                    entry["@id"] = name or "file"
    if isinstance(record_set, list):
        for entry in record_set:
            if isinstance(entry, dict):
                if "@type" not in entry:
                    entry["@type"] = "cr:RecordSet"
                fields = entry.get("field")
                if isinstance(fields, list):
                    file_object_id = "file"
                    if isinstance(distribution, list) and distribution:
                        file_object_id = distribution[0].get("@id", "file")
                    for field in fields:
                        if isinstance(field, dict) and "@type" not in field:
                            field["@type"] = "cr:Field"
                        if isinstance(field, dict) and "source" not in field:
                            field["source"] = {
                                "fileObject": {"@id": file_object_id},
                                "extract": {"column": field.get("name", "")},
                            }
    return build_dataset(
        name=data["name"],
        description=data["description"],
        version=data["version"],
        license_url=data["license"],
        url=data["url"],
        date_published=data.get("datePublished", ""),
        cite_as=data.get("citeAs", ""),
        creators=data.get("creator"),
        distribution=distribution,
        record_set=record_set,
    )


def run_server(host: str = "127.0.0.1", port: int = 8000, output_dir: str = ".") -> None:
    handler = _Handler
    handler.output_dir = Path(output_dir)
    server = HTTPServer((host, port), handler)
    try:
        server.serve_forever()
    finally:
        server.server_close()


def _render_result(
    file_name: str,
    file_contents: str,
    is_valid: bool,
    errors_html: str,
    profile_version: str,
    error_count: int,
    warnings_html: str,
) -> str:
    status = "VALID" if is_valid else "INVALID"
    status_class = "badge req" if is_valid else "badge rec"
    validation_block = (
        f"<div class='section'><h2>Validation result</h2>"
        f"<p><span class='{status_class}'>{status}</span> "
        f"<span class='note'>Profile: {html.escape(profile_version)} · "
        f"Errors: {error_count}</span></p>"
        f"{errors_html}</div>"
    )
    warnings_block = (
        "<div class='section'><h2>Warnings</h2>"
        f"{warnings_html}</div>"
    )
    result_block = (
        "<div class='section'>"
        f"<h2>Generated {html.escape(file_name)}</h2>"
        "<div class='actions'>"
        "<button type='button' class='ghost' id='copy_preview'>Copy</button>"
        "</div>"
        f"<pre class='codeblock' id='generated_preview'>{html.escape(file_contents)}</pre>"
        "<div class='copy-status' id='copy_status'></div>"
        "<div class='actions'>"
        f"<a class='button' href='/download' download='{html.escape(file_name)}'>Download</a>"
        f"<a class='button ghost' href='/?form=1'>Back to form</a>"
        "</div></div>"
    )
    base = _TEMPLATE.replace("{{NOTICE}}", "")
    if "<form method=\"post\">" in base:
        head, tail = base.split("<form method=\"post\">", 1)
        if "</form>" in tail:
            _, rest = tail.split("</form>", 1)
            return head + validation_block + warnings_block + result_block + _result_theme_script() + rest
    return base + validation_block + warnings_block + result_block + _result_theme_script()


def _result_theme_script() -> str:
    return (
        "<script>"
        "function resultSetTheme(mode) {"
        "document.body.classList.toggle('light', mode === 'light');"
        "document.documentElement.classList.toggle('light', mode === 'light');"
        "const themeToggle = document.getElementById('theme_toggle');"
        "if (themeToggle) themeToggle.checked = mode === 'light';"
        "const themeLabel = document.getElementById('theme_label');"
        "if (themeLabel) themeLabel.textContent = mode === 'light' ? 'Light mode' : 'Dark mode';"
        "const status = document.getElementById('theme_status');"
        "if (status) status.textContent = `Theme: ${mode}`;"
        "localStorage.setItem('biocypher_theme', mode);"
        "}"
        "window.toggleTheme = function toggleTheme() {"
        "const current = document.body.classList.contains('light') ? 'light' : 'dark';"
        "resultSetTheme(current === 'light' ? 'dark' : 'light');"
        "};"
        "window.clearState = function clearState() {"
        "const confirmed = window.confirm('Clear all saved form data?\\n\\nThis will remove the adapter, creators, datasets, and dataset details currently stored in this browser.');"
        "if (!confirmed) return;"
        "localStorage.removeItem('biocypher_form_state');"
        "window.location.href = '/?form=1';"
        "};"
        "document.querySelectorAll('.step').forEach((step, index) => {"
        "step.classList.toggle('active', index === 3);"
        "});"
        "const savedTheme = localStorage.getItem('biocypher_theme');"
        "resultSetTheme(savedTheme === 'light' ? 'light' : 'dark');"
        "const copyButton = document.getElementById('copy_preview');"
        "const preview = document.getElementById('generated_preview');"
        "const copyStatus = document.getElementById('copy_status');"
        "if (copyButton && preview) {"
        "copyButton.addEventListener('click', async () => {"
        "try {"
        "await navigator.clipboard.writeText(preview.textContent || '');"
        "if (copyStatus) copyStatus.textContent = 'Preview copied to clipboard.';"
        "} catch (error) {"
        "if (copyStatus) copyStatus.textContent = 'Copy failed. Please select and copy manually.';"
        "}"
        "});"
        "}"
        "</script>"
    )
