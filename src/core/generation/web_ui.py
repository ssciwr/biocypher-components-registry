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
from src.core.generation.inference import infer_fields_from_file
from src.core.validator import validate


_TEMPLATE = r"""
<!doctype html>
<html>
  <head>
    <meta charset="utf-8">
    <title>BioCypher Metadata Generator</title>
    <style>
      :root {
        --bg: #060b1a;
        --panel: #0a1022;
        --panel-2: #0e152b;
        --ink: #e7edf8;
        --muted: #93a1b8;
        --accent: #4c8dff;
        --accent-2: #2b5df5;
        --line: rgba(255, 255, 255, 0.08);
        --glow: rgba(76, 141, 255, 0.25);
      }
      body.light {
        --bg: #f7f8fb;
        --panel: #ffffff;
        --panel-2: #f4f6fb;
        --ink: #131722;
        --muted: #5b6472;
        --accent: #2b5df5;
        --accent-2: #1d3fbf;
        --line: rgba(0, 0, 0, 0.08);
        --glow: rgba(43, 93, 245, 0.2);
        background: linear-gradient(180deg, #f7f8fb 0%, #ffffff 100%);
      }
      * { box-sizing: border-box; }
      body {
        font-family: "Inter", "Segoe UI", "Helvetica Neue", sans-serif;
        background: radial-gradient(1200px 800px at 10% -10%, #162341 0%, var(--bg) 45%);
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
        border: 1px solid rgba(255,255,255,0.08);
        background: #0b1226;
        color: var(--ink);
        margin-top: 0.35rem;
        pointer-events: auto;
        user-select: text;
        caret-color: var(--ink);
      }
      body.light input,
      body.light textarea,
      body.light select {
        border: 1px solid rgba(0,0,0,0.12);
        background: #ffffff;
        color: var(--ink);
      }
      body.light input::placeholder,
      body.light textarea::placeholder {
        color: #7a879b;
      }
      input::placeholder, textarea::placeholder { color: #6d7a92; }
      .badge {
        display: inline-block;
        font-size: 0.72rem;
        padding: 0.15rem 0.5rem;
        border-radius: 999px;
        margin-left: 0.4rem;
      }
      .req { background: #2b5df5; color: #fff; }
      .opt { background: rgba(255,255,255,0.08); color: #c7d2e8; }
      .rec { background: rgba(255, 200, 120, 0.15); color: #ffcf8a; }
      .actions { display: flex; gap: 0.75rem; justify-content: flex-end; }
      button {
        background: var(--accent);
        color: #0b1020;
        border: none;
        padding: 0.75rem 1.25rem;
        border-radius: 10px;
        font-size: 1rem;
        cursor: pointer;
        margin-top: 1rem;
      }
      button:hover { background: #3a7cff; }
      .ghost { background: transparent; color: var(--ink); border: 1px solid rgba(255,255,255,0.15); }
      .ghost:hover { background: rgba(255,255,255,0.06); }
      .button {
        display: inline-block;
        text-decoration: none;
        background: var(--accent);
        color: #0b1020;
        border-radius: 10px;
        padding: 0.75rem 1.25rem;
        border: 1px solid transparent;
        margin-top: 1rem;
      }
      .button.ghost {
        background: transparent;
        color: var(--ink);
        border: 1px solid rgba(255,255,255,0.15);
      }
      .step-panel { display: none; }
      .step-panel.active { display: block; }
      .list { margin-top: 0.75rem; padding-left: 1.25rem; }
      .list li { margin-bottom: 0.25rem; }
      .grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 0.75rem; }
      .note { color: var(--muted); font-size: 0.9rem; }
      .notice {
        background: rgba(255, 200, 120, 0.1);
        border: 1px solid rgba(255, 200, 120, 0.3);
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
      }
    </style>
  </head>
  <body>
    <div class="wrap">
    <h1>BioCypher Metadata Generator</h1>
    <div class="subtitle">Create a Croissant metadata file with a guided form.</div>
    <div class="actions" style="justify-content:flex-start; gap: 0.5rem;">
      <button type="button" class="ghost" id="theme_toggle" onclick="toggleTheme()">Toggle theme</button>
      <button type="button" class="ghost" id="clear_state" onclick="clearState()">Clear saved data</button>
    </div>
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
          <div class="grid-2">
            <label>Name <span class="badge req">required</span><input id="creator_name"></label>
            <label>Affiliation <span class="badge opt">optional</span><input id="creator_affiliation"></label>
          </div>
          <label>ORCID <span class="badge opt">optional</span><input id="creator_orcid"></label>
          <div class="actions">
            <button type="button" class="ghost" id="add_creator">Add creator</button>
          </div>
          <ul class="list" id="creators_list"></ul>
        </div>
        <div class="actions">
          <button type="button" class="ghost" data-prev>Back</button>
          <button type="button" data-next>Next</button>
        </div>
      </div>

      <div class="section step-panel" data-panel="1">
        <h2>Datasets</h2>
        <div class="note">Add each dataset first. Details are added in the next step.</div>
        <label>Dataset name <span class="badge req">required</span><input id="ds_name"></label>
        <label>Description <span class="badge req">required</span><input id="ds_description"></label>
        <div class="grid-2">
          <label>Version <span class="badge req">required</span><input id="ds_version"></label>
          <label>License <span class="badge req">required</span><input id="ds_license"></label>
        </div>
        <label>URL <span class="badge req">required</span><input id="ds_url"></label>
        <div class="actions">
          <button type="button" class="ghost" id="add_dataset">Add dataset</button>
          <button type="button" class="ghost" id="clear_datasets">Clear list</button>
        </div>
        <ul class="list" id="datasets_list"></ul>
        <div class="actions">
          <button type="button" class="ghost" data-prev>Back</button>
          <button type="button" data-next>Next</button>
        </div>
      </div>

      <div class="section step-panel" data-panel="2">
        <h2>Dataset Details</h2>
        <div class="note">Apply details to a selected dataset.</div>
        <label>Choose dataset <span class="badge req">required</span>
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
        <label>Infer fields from local file path (CSV/TSV) <span class="badge opt">optional</span>
          <input id="infer_path">
          <span class="hint">Uses server file system path.</span>
        </label>
        <label>Or load a local file (max 1MB) <span class="badge opt">optional</span>
          <input id="infer_file" type="file" accept=".csv,.tsv,.tab">
        </label>
        <div class="actions">
          <button type="button" class="ghost" id="analyze_file" onclick="analyzeFile()">Analyze file</button>
        </div>
        <div class="section">
          <h3>Detected fields</h3>
          <div class="note" id="fields_report_note">No file analyzed yet.</div>
          <ul class="list" id="fields_report"></ul>
        </div>
        <div class="actions">
          <button type="button" class="ghost" id="apply_details">Apply details</button>
        </div>
        <div class="note" id="details_status"></div>
        <h3>Manual fields (optional)</h3>
        <div class="grid-2">
          <label>Field name <span class="badge opt">optional</span><input id="field_name"></label>
          <label>Data type <span class="badge opt">optional</span>
            <select id="field_type">
              <option value="sc:Text">sc:Text</option>
              <option value="sc:Integer">sc:Integer</option>
              <option value="sc:Float">sc:Float</option>
              <option value="sc:Boolean">sc:Boolean</option>
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
      let idx = 0;
      function show(i) {
        if (idx === 2 && i !== 2) {
          applyDetails(true);
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
      const creatorsList = document.getElementById('creators_list');
      const datasetsList = document.getElementById('datasets_list');
      const datasetSelect = document.getElementById('dataset_select');
      const creatorsInput = document.getElementById('creators_data');
      const datasetsInput = document.getElementById('datasets_data');

      function syncCreators() {
        creatorsInput.value = JSON.stringify(creators);
        creatorsList.innerHTML = creators.map((c, i) => `<li>${c.name} <button type="button" data-remove-creator="${i}">remove</button></li>`).join('');
        creatorsList.querySelectorAll('button').forEach(btn => {
          btn.addEventListener('click', () => {
            creators.splice(Number(btn.dataset.removeCreator), 1);
            syncCreators();
          });
        });
        if (!restoring) {
          saveState();
        }
      }

      function syncDatasets() {
        datasetsInput.value = JSON.stringify(datasets);
        datasetsList.innerHTML = datasets.map((d, i) => `<li>${d.name} <button type="button" data-remove-dataset="${i}">remove</button></li>`).join('');
        datasetsList.querySelectorAll('button').forEach(btn => {
          btn.addEventListener('click', () => {
            datasets.splice(Number(btn.dataset.removeDataset), 1);
            syncDatasets();
          });
        });
        datasetSelect.innerHTML = datasets.map((d, i) => `<option value="${i}">${d.name}</option>`).join('');
        if (!restoring) {
          saveState();
        }
      }

      document.getElementById('add_creator').addEventListener('click', () => {
        const name = document.getElementById('creator_name').value.trim();
        if (!name) return;
        creators.push({
          name,
          affiliation: document.getElementById('creator_affiliation').value.trim(),
          identifier: document.getElementById('creator_orcid').value.trim(),
        });
        document.getElementById('creator_name').value = '';
        document.getElementById('creator_affiliation').value = '';
        document.getElementById('creator_orcid').value = '';
        syncCreators();
      });

      document.getElementById('add_dataset').addEventListener('click', () => {
        const name = document.getElementById('ds_name').value.trim();
        const description = document.getElementById('ds_description').value.trim();
        const version = document.getElementById('ds_version').value.trim();
        const license = document.getElementById('ds_license').value.trim();
        const url = document.getElementById('ds_url').value.trim();
        if (!(name && description && version && license && url)) return;
        datasets.push({ name, description, version, license, url });
        document.getElementById('ds_name').value = '';
        document.getElementById('ds_description').value = '';
        document.getElementById('ds_version').value = '';
        document.getElementById('ds_license').value = '';
        document.getElementById('ds_url').value = '';
        syncDatasets();
      });

      document.getElementById('clear_datasets').addEventListener('click', () => {
        datasets.length = 0;
        syncDatasets();
      });

      function applyDetails(silent = false) {
        const selected = Number(datasetSelect.value || 0);
        const target = datasets[selected];
        const status = document.getElementById('details_status');
        if (!target) {
          if (status) status.textContent = 'Select a dataset first.';
          return;
        }
        const date = document.getElementById('ds_date').value.trim();
        const cite = document.getElementById('ds_cite').value.trim();
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
        }
        if (status && !silent) status.textContent = 'Details applied.';
        syncDatasets();
      }
      document.getElementById('apply_details').addEventListener('click', () => {
        applyDetails();
      });

      document.getElementById('add_field').addEventListener('click', () => {
        const selected = Number(datasetSelect.value || 0);
        const target = datasets[selected];
        if (!target) return;
        const rsName = document.getElementById('rs_name').value.trim();
        if (!rsName) return;
        const fieldName = document.getElementById('field_name').value.trim();
        if (!fieldName) return;
        const fileObjectId = target.distribution && target.distribution[0] && target.distribution[0]['@id'] ? target.distribution[0]['@id'] : 'file';
        const field = {
          '@type': 'cr:Field',
          name: fieldName,
          description: document.getElementById('field_desc').value.trim(),
          dataType: document.getElementById('field_type').value,
          examples: [document.getElementById('field_example').value.trim()].filter(Boolean),
          source: {
            fileObject: { '@id': fileObjectId },
            extract: { column: fieldName },
          },
        };
        target.recordSet = target.recordSet || [{ '@type': 'cr:RecordSet', name: rsName, field: [] }];
        target.recordSet[0].field.push(field);
        document.getElementById('field_name').value = '';
        document.getElementById('field_desc').value = '';
        document.getElementById('field_example').value = '';
        syncDatasets();
      });

      const STORAGE_KEY = 'biocypher_form_state';
      function saveState() {
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
          datasets.splice(0, datasets.length, ...(state.datasets || []));
          syncCreators();
          syncDatasets();
          restoring = false;
        } catch (e) {
          restoring = false;
          localStorage.removeItem(STORAGE_KEY);
        }
      }
      function clearState() {
        localStorage.removeItem(STORAGE_KEY);
        creators.splice(0, creators.length);
        datasets.splice(0, datasets.length);
        document.querySelector('[name="name"]').value = '';
        document.querySelector('[name="description"]').value = '';
        document.querySelector('[name="version"]').value = '';
        document.querySelector('[name="license"]').value = '';
        document.querySelector('[name="code_repository"]').value = '';
        document.querySelector('[name="keywords"]').value = '';
        syncCreators();
        syncDatasets();
      }
      restoreState();
      syncCreators();
      syncDatasets();
      document.querySelectorAll('input, textarea').forEach(el => {
        el.addEventListener('input', saveState);
      });

      function inferType(values) {
        if (!values.length) return 'sc:Text';
        const isInt = values.every(v => /^-?\d+$/.test(v));
        if (isInt) return 'sc:Integer';
        const isFloat = values.every(v => /^-?\d+(\.\d+)?$/.test(v));
        if (isFloat) return 'sc:Float';
        const isBool = values.every(v => /^(true|false)$/i.test(v));
        if (isBool) return 'sc:Boolean';
        return 'sc:Text';
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
          const dataType = inferType(values);
          return { name: h, dataType, example: values[0] || '' };
        });
        note.textContent = `Detected ${fieldSummaries.length} fields.`;
        fieldSummaries.forEach(f => {
          const li = document.createElement('li');
          li.textContent = `${f.name} — ${f.dataType}${f.example ? ' (e.g. ' + f.example + ')' : ''}`;
          report.appendChild(li);
        });
        const selected = Number(datasetSelect.value || 0);
        const target = datasets[selected];
        if (target) {
          const rsName = document.getElementById('rs_name').value.trim() || 'records';
          target.recordSet = target.recordSet || [{ '@type': 'cr:RecordSet', name: rsName, field: [] }];
          const fileObjectId = target.distribution && target.distribution[0] && target.distribution[0]['@id'] ? target.distribution[0]['@id'] : 'file';
          target.recordSet[0].field = fieldSummaries.map(f => ({
            '@type': 'cr:Field',
            name: f.name,
            description: '',
            dataType: f.dataType,
            examples: f.example ? [f.example] : [],
            source: {
              fileObject: { '@id': fileObjectId },
              extract: { column: f.name },
            },
          }));
          syncDatasets();
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
          themeToggle.textContent = mode === 'light' ? 'Switch to Dark' : 'Switch to Light';
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

            if "infer_path" in data and data["infer_path"]:
                for dataset in datasets:
                    if "recordSet" in dataset:
                        rs_name = dataset.get("recordSet", [{}])[0].get("name", "records")
                        record_set_id = rs_name.lower().replace(" ", "-")
                        fields, _ = infer_fields_from_file(
                            data["infer_path"], record_set_id, "file"
                        )
                        record_set = dataset.setdefault(
                            "recordSet", [{"@type": "cr:RecordSet", "name": rs_name}]
                        )[0]
                        record_set["field"] = fields

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
        f"<pre class='codeblock'>{html.escape(file_contents)}</pre>"
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
        "const savedTheme = localStorage.getItem('biocypher_theme');"
        "if (savedTheme === 'light') {"
        "document.body.classList.add('light');"
        "document.documentElement.classList.add('light');"
        "}"
        "</script>"
    )
