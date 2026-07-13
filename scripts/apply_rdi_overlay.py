#!/usr/bin/env python3
"""Apply the Release delivery overlay (OOMPAH-200) to dashboard.html.

This script:
1. Removes the old Release branches inspector (RBI) CSS, JS, and HTML
2. Adds the new Release delivery (RDI) overlay CSS, JS, and HTML
3. Updates the toolbar button to open the new overlay

Run from the repo root:
    python3 scripts/apply_rdi_overlay.py
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

DASHBOARD = Path("oompah/templates/dashboard.html")

# ---------------------------------------------------------------------------
# New CSS block to replace the old RBI CSS
# ---------------------------------------------------------------------------

NEW_CSS = '''    /* Release delivery overlay (OOMPAH-200) */
    .rdi-overlay {
      display: none;
      position: fixed;
      inset: 0;
      background: rgba(0, 0, 0, 0.6);
      z-index: 200;
      justify-content: center;
      align-items: flex-start;
      padding-top: 2vh;
    }
    .rdi-overlay.open { display: flex; }
    .rdi-panel {
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: 12px;
      width: min(1200px, 97vw);
      max-height: 94vh;
      display: flex;
      flex-direction: column;
      box-shadow: 0 8px 32px rgba(0, 0, 0, 0.4);
    }
    .rdi-header {
      display: flex;
      align-items: center;
      gap: 0.75rem;
      padding: 0.6rem 1.25rem;
      border-bottom: 1px solid var(--border);
      flex-shrink: 0;
    }
    .rdi-header h3 {
      font-size: 0.9rem;
      color: var(--accent);
      margin: 0;
      white-space: nowrap;
    }
    .rdi-header-meta {
      font-size: 0.72rem;
      color: var(--text-muted);
      flex: 1;
      min-width: 0;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }
    .rdi-close-btn {
      background: none;
      border: none;
      color: var(--text-muted);
      font-size: 1.2rem;
      cursor: pointer;
      padding: 0 4px;
      line-height: 1;
      flex-shrink: 0;
    }
    .rdi-close-btn:hover { color: var(--text); }
    .rdi-controls {
      padding: 0.5rem 1.25rem;
      border-bottom: 1px solid var(--border);
      flex-shrink: 0;
      display: flex;
      flex-direction: column;
      gap: 0.4rem;
    }
    .rdi-control-row {
      display: flex;
      align-items: center;
      gap: 0.6rem;
      flex-wrap: wrap;
    }
    .rdi-label {
      font-size: 0.72rem;
      color: var(--text-muted);
      text-transform: uppercase;
      letter-spacing: 0.05em;
    }
    .rdi-filter-group {
      display: flex;
      gap: 0.4rem;
      align-items: center;
    }
    .rdi-filter-group label {
      display: flex;
      align-items: center;
      gap: 0.25rem;
      font-size: 0.8rem;
      cursor: pointer;
    }
    .rdi-search {
      padding: 3px 8px;
      border-radius: 4px;
      border: 1px solid var(--border);
      background: var(--surface);
      color: var(--text);
      font-size: 0.8rem;
      flex: 1;
      min-width: 140px;
      max-width: 260px;
    }
    .rdi-branch-filters {
      display: flex;
      gap: 0.4rem;
      flex-wrap: wrap;
      align-items: center;
    }
    .rdi-branch-filters label {
      display: flex;
      align-items: center;
      gap: 0.25rem;
      font-size: 0.75rem;
      cursor: pointer;
      background: rgba(125, 133, 144, 0.1);
      border-radius: 4px;
      padding: 2px 6px;
    }
    .rdi-table-wrap {
      overflow: auto;
      flex: 1;
    }
    .rdi-table {
      width: 100%;
      border-collapse: collapse;
      font-size: 0.82rem;
    }
    .rdi-table th {
      position: sticky;
      top: 0;
      background: var(--surface);
      border-bottom: 1px solid var(--border);
      padding: 0.3rem 0.5rem;
      text-align: left;
      font-size: 0.7rem;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      color: var(--text-muted);
      white-space: nowrap;
    }
    .rdi-table td {
      padding: 0.3rem 0.5rem;
      border-bottom: 1px solid rgba(125, 133, 144, 0.1);
      vertical-align: middle;
    }
    .rdi-table tr:hover td { background: rgba(125, 133, 144, 0.05); }
    .rdi-row-merge td {
      color: var(--text-muted);
      font-style: italic;
      font-size: 0.78rem;
    }
    .rdi-sha-link {
      font-family: var(--mono, monospace);
      font-size: 0.78rem;
      color: var(--accent);
      text-decoration: none;
    }
    .rdi-sha-link:hover { text-decoration: underline; }
    .rdi-sha-plain {
      font-family: var(--mono, monospace);
      font-size: 0.78rem;
      color: var(--text-muted);
    }
    .rdi-subject {
      max-width: 260px;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }
    .rdi-author { font-size: 0.75rem; color: var(--text-muted); white-space: nowrap; }
    .rdi-assoc {
      font-size: 0.75rem;
      color: var(--accent);
      cursor: pointer;
      text-decoration: underline;
      white-space: nowrap;
    }
    /* Status cell states */
    .rdi-cell {
      font-size: 0.72rem;
      border-radius: 3px;
      padding: 2px 5px;
      white-space: nowrap;
      display: inline-block;
    }
    .rdi-cell-not_selected { color: var(--text-muted); }
    .rdi-cell-open { color: #58a6ff; background: rgba(88, 166, 255, 0.1); }
    .rdi-cell-in_progress { color: #d29922; background: rgba(210, 153, 34, 0.12); }
    .rdi-cell-in_review { color: #8b949e; background: rgba(139, 148, 158, 0.12); }
    .rdi-cell-blocked { color: var(--red, #f85149); background: rgba(248, 81, 73, 0.1); }
    .rdi-cell-delivered { color: var(--green, #3fb950); background: rgba(63, 185, 80, 0.1); }
    .rdi-cell-delivered-ancestry { color: var(--green, #3fb950); background: rgba(63, 185, 80, 0.06); font-style: italic; }
    .rdi-cell-archived { color: var(--text-muted); background: rgba(125, 133, 144, 0.1); }
    .rdi-cell-clickable { cursor: pointer; text-decoration: underline; }
    .rdi-cell-clickable:hover { opacity: 0.85; }
    .rdi-action-bar {
      display: flex;
      align-items: center;
      gap: 0.6rem;
      flex-wrap: wrap;
      padding: 0.5rem 1.25rem;
      border-top: 1px solid var(--border);
      background: var(--bg);
      flex-shrink: 0;
    }
    .rdi-action-count { font-size: 0.8rem; font-weight: 600; }
    .rdi-target-list {
      display: flex;
      gap: 0.4rem;
      flex-wrap: wrap;
      align-items: center;
    }
    .rdi-target-list label {
      display: flex;
      align-items: center;
      gap: 0.25rem;
      font-size: 0.78rem;
      cursor: pointer;
    }
    .rdi-pagination {
      display: flex;
      align-items: center;
      gap: 0.75rem;
      padding: 0.4rem 1.25rem;
      border-top: 1px solid var(--border);
      flex-shrink: 0;
      font-size: 0.8rem;
      color: var(--text-muted);
    }
    .rdi-loading {
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 3rem;
      color: var(--text-muted);
      font-size: 0.9rem;
      gap: 0.5rem;
    }
    .rdi-empty {
      padding: 2rem;
      text-align: center;
      color: var(--text-muted);
      font-size: 0.88rem;
    }
    .rdi-error {
      padding: 1rem;
      color: var(--red);
      font-size: 0.85rem;
      background: rgba(248, 81, 73, 0.08);
      border-radius: 6px;
      margin: 0.5rem 1.25rem;
    }
    .rdi-no-project {
      padding: 2rem;
      text-align: center;
      color: var(--text-muted);
      font-size: 0.85rem;
    }
    .rdi-stale-note {
      font-size: 0.72rem;
      color: var(--yellow, #d2a520);
      margin-left: 0.25rem;
    }
    /* Evidence drawer */
    .rdi-drawer {
      display: none;
      position: fixed;
      inset: 0;
      background: rgba(0, 0, 0, 0.45);
      z-index: 300;
      justify-content: flex-end;
      align-items: stretch;
    }
    .rdi-drawer.open { display: flex; }
    .rdi-drawer-panel {
      background: var(--surface);
      border-left: 1px solid var(--border);
      width: 420px;
      max-width: 90vw;
      display: flex;
      flex-direction: column;
      overflow: hidden;
    }
    .rdi-drawer-header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 0.6rem 1rem;
      border-bottom: 1px solid var(--border);
      flex-shrink: 0;
    }
    .rdi-drawer-header h4 { margin: 0; font-size: 0.88rem; }
    .rdi-drawer-close {
      background: none;
      border: none;
      color: var(--text-muted);
      font-size: 1.1rem;
      cursor: pointer;
      padding: 0 4px;
    }
    .rdi-drawer-body {
      overflow-y: auto;
      flex: 1;
      padding: 0.75rem 1rem;
      font-size: 0.82rem;
    }
    .rdi-drawer-section { margin-bottom: 0.75rem; }
    .rdi-drawer-section-label {
      font-size: 0.68rem;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.06em;
      color: var(--text-muted);
      margin-bottom: 0.2rem;
    }
    .rdi-drawer-mono {
      font-family: var(--mono, monospace);
      font-size: 0.75rem;
      word-break: break-all;
    }
    .rdi-outcome-row {
      display: flex;
      align-items: center;
      gap: 0.5rem;
      padding: 0.4rem 0.6rem;
      border-radius: 6px;
      margin-bottom: 0.3rem;
      font-size: 0.8rem;
    }
    .rdi-outcome-created { background: rgba(63, 185, 80, 0.1); }
    .rdi-outcome-skipped { background: rgba(125, 133, 144, 0.1); }
    .rdi-outcome-failed { background: rgba(248, 81, 73, 0.08); }
    .rdi-outcome-banner {
      padding: 0.5rem 0.75rem;
      border-radius: 6px;
      font-size: 0.82rem;
      margin-bottom: 0.5rem;
    }
    .rdi-outcome-banner-success { background: rgba(63, 185, 80, 0.1); color: var(--green, #3fb950); }
    .rdi-outcome-banner-partial { background: rgba(210, 153, 34, 0.12); color: #d29922; }
    '''

# ---------------------------------------------------------------------------
# New JS block to replace the old RBI JS
# ---------------------------------------------------------------------------

NEW_JS = '''// ---------------------------------------------------------------------------
// Release delivery overlay (OOMPAH-200)
// Replaces the Release branches inspector (RBI).
// Plan reference: plans/release-delivery-commit-inventory.md sections 2 and 6.
// ---------------------------------------------------------------------------

// ---------------------------------------------------------------------------
// State
// ---------------------------------------------------------------------------
let _rdiProjectId = null;
let _rdiVisibleBranches = [];   // branch names shown as columns
let _rdiFilter = 'needs_delivery';
let _rdiQuery = '';
let _rdiCursor = null;
let _rdiSourceHead = null;
let _rdiSelectedSHAs = new Set();  // full 40-char SHAs of selected rows
let _rdiGen = 0;        // incremented each time we start a new page load
let _rdiLoading = false;
let _rdiCurrentPageData = null;  // last successful page response
let _rdiOpener = null;  // element that opened the overlay (focus restoration)
let _rdiDrawerSHA = null;  // SHA of currently open drawer row

const _RDI_STATUS_LABELS = {
  not_selected: 'Not selected',
  open: 'Open',
  in_progress: 'In progress',
  in_review: 'In review',
  blocked: 'Blocked',
  delivered: 'Delivered',
  archived: 'Archived',
};

// ---------------------------------------------------------------------------
// Open / Close
// ---------------------------------------------------------------------------

function openReleaseDelivery() {
  const overlay = document.getElementById('rdi-overlay');
  if (!overlay) return;
  _rdiOpener = document.activeElement || null;
  overlay.classList.add('open');
  overlay.addEventListener('keydown', _rdiKeyHandler);
  _rdiPopulateProject();
  const closeBtn = document.getElementById('rdi-close-btn');
  if (closeBtn) setTimeout(function() { closeBtn.focus(); }, 50);
}

function closeReleaseDelivery() {
  const overlay = document.getElementById('rdi-overlay');
  if (overlay) {
    overlay.classList.remove('open');
    overlay.removeEventListener('keydown', _rdiKeyHandler);
  }
  _rdiCloseDrawer();
  if (_rdiOpener && typeof _rdiOpener.focus === 'function') {
    try { _rdiOpener.focus(); } catch (_) { /* ignore */ }
  }
  _rdiOpener = null;
}

function _rdiKeyHandler(e) {
  if (e.key === 'Escape') {
    // If drawer is open, close it first
    const drawer = document.getElementById('rdi-drawer');
    if (drawer && drawer.classList.contains('open')) {
      _rdiCloseDrawer();
    } else {
      closeReleaseDelivery();
    }
  }
}

// ---------------------------------------------------------------------------
// Project selection
// ---------------------------------------------------------------------------

function _rdiPopulateProject() {
  const sel = document.getElementById('rdi-project-select');
  if (!sel) return;

  const projects = (typeof currentProjects !== 'undefined' ? currentProjects : []) || [];
  const boardFilter = (typeof selectedProjectFilterValue === 'function') ? selectedProjectFilterValue() : '';

  sel.innerHTML = '';
  if (projects.length === 0) {
    const opt = document.createElement('option');
    opt.value = '';
    opt.textContent = 'No projects configured';
    sel.appendChild(opt);
    _rdiShowNoProject();
    return;
  }

  for (const p of projects) {
    const opt = document.createElement('option');
    opt.value = p.id;
    opt.textContent = p.name || p.id;
    sel.appendChild(opt);
  }

  // Default to the board's active project filter, or the first project
  if (boardFilter && projects.some(function(p) { return p.id === boardFilter; })) {
    sel.value = boardFilter;
  } else {
    sel.value = projects[0].id;
  }

  _rdiOnProjectChange();
}

function _rdiOnProjectChange() {
  const sel = document.getElementById('rdi-project-select');
  if (!sel) return;
  const projectId = sel.value;
  if (!projectId) {
    _rdiShowNoProject();
    return;
  }
  // Reset state for new project
  _rdiProjectId = projectId;
  _rdiVisibleBranches = [];
  _rdiCursor = null;
  _rdiSourceHead = null;
  _rdiSelectedSHAs = new Set();
  _rdiCurrentPageData = null;
  _rdiQuery = '';
  _rdiFilter = 'needs_delivery';
  // Reset filter controls
  const searchEl = document.getElementById('rdi-search');
  if (searchEl) searchEl.value = '';
  const filterNd = document.querySelector('input[name="rdi-filter"][value="needs_delivery"]');
  if (filterNd) filterNd.checked = true;
  // Clear branch filter area until first load
  const branchFilters = document.getElementById('rdi-branch-filters');
  if (branchFilters) branchFilters.innerHTML = '';
  // Show loading and fetch
  _rdiSetBody('<div class="rdi-loading"><svg width="16" height="16" viewBox="0 0 24 24" style="animation:spin 1s linear infinite;"><circle cx="12" cy="12" r="10" stroke="currentColor" stroke-width="3" fill="none" opacity=".25"/><path d="M12 2a10 10 0 0 1 10 10" stroke="currentColor" stroke-width="3" fill="none" stroke-linecap="round"/></svg> Loading…</div>');
  _rdiHideActionBar();
  _rdiLoadPage(null);
}

// ---------------------------------------------------------------------------
// Data loading
// ---------------------------------------------------------------------------

function _rdiLoadPage(cursor) {
  if (!_rdiProjectId) return;
  _rdiLoading = true;
  _rdiCursor = cursor || null;

  const myGen = ++_rdiGen;

  // Build query string
  const params = new URLSearchParams();
  if (_rdiVisibleBranches && _rdiVisibleBranches.length > 0) {
    params.set('branches', _rdiVisibleBranches.join(','));
  }
  if (_rdiFilter && _rdiFilter !== 'needs_delivery') {
    params.set('filter', _rdiFilter);
  }
  if (_rdiQuery) {
    params.set('query', _rdiQuery);
  }
  if (cursor) {
    params.set('cursor', cursor);
  }

  const qs = params.toString();
  const url = '/api/v1/projects/' + encodeURIComponent(_rdiProjectId) + '/release-delivery/commits' + (qs ? '?' + qs : '');

  if (!cursor) {
    // First page: show spinner in body
    _rdiSetBody('<div class="rdi-loading"><svg width="16" height="16" viewBox="0 0 24 24" style="animation:spin 1s linear infinite;"><circle cx="12" cy="12" r="10" stroke="currentColor" stroke-width="3" fill="none" opacity=".25"/><path d="M12 2a10 10 0 0 1 10 10" stroke="currentColor" stroke-width="3" fill="none" stroke-linecap="round"/></svg> Loading release delivery…</div>');
  }

  fetch(url)
    .then(function(resp) { return resp.json().then(function(data) { return { resp: resp, data: data }; }); })
    .then(function(r) {
      _rdiLoading = false;
      if (myGen !== _rdiGen) return;  // superseded request — ignore
      const resp = r.resp, data = r.data;
      if (!resp.ok) {
        if (resp.status === 409 && data.error && data.error.code === 'source_changed') {
          // Source HEAD changed between pages — reload from page one
          _rdiSourceHead = data.error.current_head || null;
          _rdiCursor = null;
          _rdiLoadPage(null);
          return;
        }
        const msg = (data.error && data.error.message) || ('HTTP ' + resp.status);
        _rdiSetBody('<div class="rdi-error">Failed to load release delivery: ' + esc(msg) + '</div>');
        return;
      }
      _rdiSourceHead = data.source_head || null;
      _rdiCurrentPageData = data;
      // On first load, initialise visible branches from configured branches
      if (_rdiVisibleBranches.length === 0 && data.release_branches) {
        _rdiVisibleBranches = (data.release_branches || []).map(function(b) { return b.name; });
      }
      _rdiRenderPage(data);
    })
    .catch(function(err) {
      _rdiLoading = false;
      if (myGen !== _rdiGen) return;
      _rdiSetBody('<div class="rdi-error">Network error: ' + esc(String(err)) + '</div>');
    });
}

function _rdiRefresh() {
  _rdiCursor = null;
  _rdiCurrentPageData = null;
  _rdiLoadPage(null);
}

// ---------------------------------------------------------------------------
// Rendering
// ---------------------------------------------------------------------------

function _rdiSetBody(html) {
  const body = document.getElementById('rdi-body');
  if (body) body.innerHTML = html;
}

function _rdiRenderPage(data) {
  // Update header metadata
  _rdiRenderMeta(data);

  // Render branch filter checkboxes
  _rdiRenderBranchFilters(data.release_branches || []);

  const rows = data.rows || [];
  const branchNames = _rdiVisibleBranches.length > 0
    ? _rdiVisibleBranches
    : (data.release_branches || []).map(function(b) { return b.name; });

  const body = document.getElementById('rdi-body');
  if (!body) return;

  if (branchNames.length === 0) {
    body.innerHTML = '<div class="rdi-empty">No release lines are configured for this project. Add <code>supported_release_branches</code> in the project settings.</div>';
    _rdiHideActionBar();
    _rdiHidePagination();
    return;
  }

  if (rows.length === 0) {
    const filterLabel = _rdiFilter === 'needs_delivery' ? '"Needs delivery"' : '"All commits"';
    body.innerHTML = '<div class="rdi-empty">No commits match the current filter (' + esc(filterLabel) + ').' +
      (_rdiQuery ? ' Try clearing the search.' : '') + '</div>';
    _rdiHideActionBar();
    _rdiHidePagination();
    return;
  }

  // Build table
  const wrap = document.createElement('div');
  wrap.className = 'rdi-table-wrap';

  const table = document.createElement('table');
  table.className = 'rdi-table';
  table.setAttribute('role', 'grid');

  // Header row
  const thead = document.createElement('thead');
  const headerRow = document.createElement('tr');

  // Checkbox select-all
  const thSel = document.createElement('th');
  const selectAll = document.createElement('input');
  selectAll.type = 'checkbox';
  selectAll.setAttribute('aria-label', 'Select all selectable commits');
  selectAll.id = 'rdi-select-all';
  selectAll.addEventListener('change', function() { _rdiSelectAll(this.checked); });
  thSel.appendChild(selectAll);
  headerRow.appendChild(thSel);

  // Fixed columns
  for (const label of ['SHA', 'Subject', 'Author / Date', 'Association']) {
    const th = document.createElement('th');
    th.textContent = label;
    headerRow.appendChild(th);
  }

  // Branch columns
  for (const branch of branchNames) {
    const th = document.createElement('th');
    th.textContent = branch;
    headerRow.appendChild(th);
  }

  thead.appendChild(headerRow);
  table.appendChild(thead);

  // Body rows
  const tbody = document.createElement('tbody');
  for (const row of rows) {
    tbody.appendChild(_rdiRenderRow(row, branchNames, data));
  }
  table.appendChild(tbody);
  wrap.appendChild(table);

  body.innerHTML = '';
  body.appendChild(wrap);

  // Pagination
  _rdiRenderPagination(data.next_cursor);

  // Update action bar
  _rdiUpdateActionBar();
  _rdiUpdateSelectAll();
}

function _rdiRenderMeta(data) {
  const meta = document.getElementById('rdi-meta');
  if (!meta) return;
  const head = data.source_head ? data.source_head.slice(0, 8) : '';
  let text = data.source_branch ? (data.source_branch + (head ? ' @ ' + head : '')) : '';
  if (data.stale) text += ' (stale)';
  if (data.refreshed_at) text += ' · ' + data.refreshed_at.replace('T', ' ').replace(/\.\d+Z$/, 'Z');
  meta.textContent = text;
}

function _rdiRenderBranchFilters(releaseBranches) {
  const container = document.getElementById('rdi-branch-filters');
  if (!container) return;
  container.innerHTML = '';
  if (releaseBranches.length === 0) return;

  const labelEl = document.createElement('span');
  labelEl.className = 'rdi-label';
  labelEl.textContent = 'Columns:';
  container.appendChild(labelEl);

  for (const b of releaseBranches) {
    const lbl = document.createElement('label');
    const cb = document.createElement('input');
    cb.type = 'checkbox';
    cb.checked = _rdiVisibleBranches.length === 0 || _rdiVisibleBranches.includes(b.name);
    cb.setAttribute('aria-label', 'Show column for ' + b.name);
    cb.dataset.branch = b.name;
    cb.addEventListener('change', function() {
      _rdiBranchFilterChange(this.dataset.branch, this.checked);
    });
    lbl.appendChild(cb);
    const nameSpan = document.createElement('span');
    nameSpan.textContent = b.name + (!b.available ? ' (historical)' : b.stale ? ' ⚠' : '');
    lbl.appendChild(nameSpan);
    container.appendChild(lbl);
  }
}

function _rdiRenderRow(row, branchNames, pageData) {
  const tr = document.createElement('tr');
  const isMerge = !row.selectable;
  if (isMerge) tr.className = 'rdi-row-merge';
  tr.dataset.sha = row.sha;

  // Checkbox column
  const tdSel = document.createElement('td');
  if (!isMerge) {
    const cb = document.createElement('input');
    cb.type = 'checkbox';
    cb.checked = _rdiSelectedSHAs.has(row.sha);
    cb.dataset.sha = row.sha;
    cb.setAttribute('aria-label', 'Select commit ' + row.short_sha);
    cb.addEventListener('change', function() {
      _rdiToggleSHA(this.dataset.sha, this.checked);
    });
    tdSel.appendChild(cb);
  } else {
    // Merge commit: informational indicator
    const span = document.createElement('span');
    span.title = 'Merge commit — not selectable';
    span.textContent = '⊕';
    span.style.color = 'var(--text-muted)';
    span.style.fontSize = '0.75rem';
    tdSel.appendChild(span);
  }
  tr.appendChild(tdSel);

  // SHA column
  const tdSha = document.createElement('td');
  const shaText = row.short_sha || row.sha.slice(0, 8);
  if (row.sha_url) {
    const a = document.createElement('a');
    a.href = row.sha_url;
    a.target = '_blank';
    a.rel = 'noopener noreferrer';
    a.className = 'rdi-sha-link';
    a.textContent = shaText;
    tdSha.appendChild(a);
  } else {
    const span = document.createElement('span');
    span.className = 'rdi-sha-plain';
    span.textContent = shaText;
    tdSha.appendChild(span);
  }
  tr.appendChild(tdSha);

  // Subject column — build text node (never innerHTML from API)
  const tdSubj = document.createElement('td');
  const subjSpan = document.createElement('span');
  subjSpan.className = 'rdi-subject';
  subjSpan.textContent = row.subject || '';
  subjSpan.title = row.subject || '';
  tdSubj.appendChild(subjSpan);
  tr.appendChild(tdSubj);

  // Author / Date column
  const tdAuth = document.createElement('td');
  const authSpan = document.createElement('span');
  authSpan.className = 'rdi-author';
  const authorText = (row.author_name || '') + (row.authored_at ? ' · ' + row.authored_at.slice(0, 10) : '');
  authSpan.textContent = authorText;
  tdAuth.appendChild(authSpan);
  tr.appendChild(tdAuth);

  // Association column
  const tdAssoc = document.createElement('td');
  if (row.association && row.association.identifier) {
    const assocSpan = document.createElement('span');
    assocSpan.className = 'rdi-assoc';
    assocSpan.textContent = row.association.identifier;
    assocSpan.dataset.identifier = row.association.identifier;
    assocSpan.setAttribute('role', 'button');
    assocSpan.setAttribute('tabindex', '0');
    assocSpan.setAttribute('aria-label', 'Open ' + row.association.identifier);
    assocSpan.addEventListener('click', function() {
      closeReleaseDelivery();
      if (typeof openDetailPanel === 'function') {
        openDetailPanel(this.dataset.identifier, _rdiProjectId);
      }
    });
    assocSpan.addEventListener('keydown', function(e) {
      if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); this.click(); }
    });
    tdAssoc.appendChild(assocSpan);
  }
  tr.appendChild(tdAssoc);

  // Branch status cells
  const releaseStatus = row.release_status || {};
  for (const branch of branchNames) {
    const tdCell = document.createElement('td');
    const cell = releaseStatus[branch] || { state: 'not_selected' };
    const cellEl = _rdiRenderCell(cell, row.sha, branch, pageData);
    tdCell.appendChild(cellEl);
    tr.appendChild(tdCell);
  }

  // Row click handler — clicking outside checkbox/assoc/cell opens drawer
  if (!isMerge) {
    tr.addEventListener('click', function(e) {
      // Skip clicks on interactive elements
      if (e.target.tagName === 'INPUT' || e.target.tagName === 'A' ||
          e.target.classList.contains('rdi-assoc') ||
          e.target.closest('.rdi-assoc') ||
          e.target.classList.contains('rdi-cell-clickable') ||
          e.target.closest('.rdi-cell-clickable')) {
        return;
      }
      _rdiOpenDrawer(row.sha, row);
    });
  }

  return tr;
}

function _rdiRenderCell(cell, sha, branch, pageData) {
  const state = cell.state || 'not_selected';
  const label = _RDI_STATUS_LABELS[state] || state.replace(/_/g, ' ');
  const span = document.createElement('span');

  // Choose CSS class based on state + evidence
  let cssClass = 'rdi-cell rdi-cell-' + state.replace(/_/g, '_');
  if (state === 'delivered' && cell.evidence === 'ancestry') {
    cssClass = 'rdi-cell rdi-cell-delivered-ancestry';
  }
  span.className = cssClass;

  // Label text
  if (state === 'delivered' && cell.evidence === 'ancestry') {
    span.textContent = 'Delivered (ancestry)';
  } else if (state === 'delivered' && cell.evidence === 'delivery') {
    span.textContent = 'Delivered (cherry-pick)';
  } else {
    span.textContent = label;
  }

  // Clickable for active/delivered states with a delivery_id
  if (cell.delivery_id || (state === 'delivered' && cell.evidence)) {
    span.classList.add('rdi-cell-clickable');
    span.setAttribute('role', 'button');
    span.setAttribute('tabindex', '0');
    span.setAttribute('aria-label', label + ' — click for details');
    span.dataset.sha = sha;
    span.dataset.branch = branch;
    span.addEventListener('click', function(e) {
      e.stopPropagation();
      // Find the row data in the current page
      const rowData = _rdiFindRow(sha);
      _rdiOpenDrawer(sha, rowData);
    });
    span.addEventListener('keydown', function(e) {
      if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); this.click(); }
    });
  }

  return span;
}

function _rdiFindRow(sha) {
  if (!_rdiCurrentPageData) return null;
  const rows = _rdiCurrentPageData.rows || [];
  return rows.find(function(r) { return r.sha === sha; }) || null;
}

function _rdiRenderPagination(nextCursor) {
  const pag = document.getElementById('rdi-pagination');
  if (!pag) return;
  if (nextCursor) {
    pag.innerHTML = '';
    const btn = document.createElement('button');
    btn.textContent = 'Load next page';
    btn.addEventListener('click', function() { _rdiLoadPage(_rdiCurrentPageData && _rdiCurrentPageData.next_cursor); });
    pag.appendChild(btn);
    pag.hidden = false;
  } else {
    pag.hidden = true;
  }
}

function _rdiHidePagination() {
  const pag = document.getElementById('rdi-pagination');
  if (pag) pag.hidden = true;
}

// ---------------------------------------------------------------------------
// Selection
// ---------------------------------------------------------------------------

function _rdiToggleSHA(sha, checked) {
  if (checked) {
    _rdiSelectedSHAs.add(sha);
  } else {
    _rdiSelectedSHAs.delete(sha);
  }
  _rdiUpdateActionBar();
  _rdiUpdateSelectAll();
}

function _rdiSelectAll(checked) {
  if (!_rdiCurrentPageData) return;
  for (const row of (_rdiCurrentPageData.rows || [])) {
    if (!row.selectable) continue;
    if (checked) {
      _rdiSelectedSHAs.add(row.sha);
    } else {
      _rdiSelectedSHAs.delete(row.sha);
    }
  }
  // Update all checkboxes in the table
  const table = document.querySelector('#rdi-body .rdi-table');
  if (table) {
    table.querySelectorAll('input[type="checkbox"][data-sha]').forEach(function(cb) {
      cb.checked = checked;
    });
  }
  _rdiUpdateActionBar();
}

function _rdiUpdateSelectAll() {
  const selectAll = document.getElementById('rdi-select-all');
  if (!selectAll || !_rdiCurrentPageData) return;
  const selectableRows = (_rdiCurrentPageData.rows || []).filter(function(r) { return r.selectable; });
  if (selectableRows.length === 0) {
    selectAll.checked = false;
    selectAll.indeterminate = false;
    return;
  }
  const selectedCount = selectableRows.filter(function(r) { return _rdiSelectedSHAs.has(r.sha); }).length;
  if (selectedCount === 0) {
    selectAll.checked = false;
    selectAll.indeterminate = false;
  } else if (selectedCount === selectableRows.length) {
    selectAll.checked = true;
    selectAll.indeterminate = false;
  } else {
    selectAll.checked = false;
    selectAll.indeterminate = true;
  }
}

function _rdiClearSelection() {
  _rdiSelectedSHAs = new Set();
  // Uncheck all checkboxes
  const table = document.querySelector('#rdi-body .rdi-table');
  if (table) {
    table.querySelectorAll('input[type="checkbox"][data-sha]').forEach(function(cb) {
      cb.checked = false;
    });
  }
  const selectAll = document.getElementById('rdi-select-all');
  if (selectAll) { selectAll.checked = false; selectAll.indeterminate = false; }
  _rdiUpdateActionBar();
}

function _rdiUpdateActionBar() {
  const bar = document.getElementById('rdi-action-bar');
  const countEl = document.getElementById('rdi-action-count');
  if (!bar) return;
  const n = _rdiSelectedSHAs.size;
  if (n === 0) {
    bar.hidden = true;
    return;
  }
  bar.hidden = false;
  if (countEl) {
    countEl.textContent = n + ' commit' + (n !== 1 ? 's' : '') + ' selected';
  }
  // Populate target branch checkboxes for the queue action
  _rdiRenderTargetBranches();
}

function _rdiHideActionBar() {
  const bar = document.getElementById('rdi-action-bar');
  if (bar) bar.hidden = true;
}

function _rdiRenderTargetBranches() {
  const list = document.getElementById('rdi-target-list');
  if (!list) return;
  list.innerHTML = '';
  const branches = _rdiCurrentPageData && _rdiCurrentPageData.release_branches
    ? _rdiCurrentPageData.release_branches.filter(function(b) { return b.available; })
    : [];
  for (const b of branches) {
    const lbl = document.createElement('label');
    const cb = document.createElement('input');
    cb.type = 'checkbox';
    cb.checked = true;
    cb.dataset.branch = b.name;
    cb.setAttribute('aria-label', 'Queue for ' + b.name);
    lbl.appendChild(cb);
    const nameSpan = document.createElement('span');
    nameSpan.textContent = b.name;
    lbl.appendChild(nameSpan);
    list.appendChild(lbl);
  }
}

// ---------------------------------------------------------------------------
// Queue commit delivery
// ---------------------------------------------------------------------------

async function _rdiQueueSelected() {
  if (!_rdiProjectId || _rdiSelectedSHAs.size === 0) return;

  // Collect target branches
  const targetCheckboxes = document.querySelectorAll('#rdi-target-list input[type="checkbox"]:checked');
  const targetBranches = Array.from(targetCheckboxes).map(function(cb) { return cb.dataset.branch; });
  if (targetBranches.length === 0) {
    alert('Select at least one target release branch.');
    return;
  }

  // Build ordered list of SHAs in table row order (preserve table order)
  const orderedSHAs = [];
  if (_rdiCurrentPageData) {
    for (const row of (_rdiCurrentPageData.rows || [])) {
      if (row.selectable && _rdiSelectedSHAs.has(row.sha)) {
        orderedSHAs.push(row.sha);
      }
    }
  }

  if (orderedSHAs.length === 0) return;

  // Confirm: show commit count and target branches
  const confirmMsg = 'Queue ' + orderedSHAs.length + ' commit' + (orderedSHAs.length !== 1 ? 's' : '') +
    ' for ' + targetBranches.map(function(b) { return '"' + b + '"'; }).join(', ') + '?';
  if (!confirm(confirmMsg)) return;

  const submitBtn = document.getElementById('rdi-queue-btn');
  if (submitBtn) submitBtn.disabled = true;

  const idempotencyKey = 'rdi-' + Date.now() + '-' + Math.random().toString(36).slice(2);

  try {
    const resp = await fetch(
      '/api/v1/projects/' + encodeURIComponent(_rdiProjectId) + '/release-delivery/commits',
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Idempotency-Key': idempotencyKey,
        },
        body: JSON.stringify({
          source_head: _rdiSourceHead || '',
          commits: orderedSHAs,
          target_branches: targetBranches,
        }),
      }
    );

    const data = await resp.json();

    if (!resp.ok) {
      const msg = (data.error && data.error.message) || ('HTTP ' + resp.status);
      _rdiShowOutcomeError('Failed to queue: ' + msg);
      if (submitBtn) submitBtn.disabled = false;
      return;
    }

    // On success: clear only successfully-created/already_delivered/already_active SHAs
    // (i.e. those that were accepted — clear their selections)
    const successSHAs = new Set();
    for (const pair of (data.created || [])) { successSHAs.add(pair.commit); }
    for (const pair of (data.already_active || [])) { successSHAs.add(pair.commit); }
    for (const pair of (data.already_delivered || [])) { successSHAs.add(pair.commit); }

    // Remove successful SHAs from selection; leave invalid ones selected
    for (const sha of successSHAs) {
      _rdiSelectedSHAs.delete(sha);
    }

    // Update checkboxes
    const table = document.querySelector('#rdi-body .rdi-table');
    if (table) {
      table.querySelectorAll('input[type="checkbox"][data-sha]').forEach(function(cb) {
        if (successSHAs.has(cb.dataset.sha)) cb.checked = false;
      });
    }

    _rdiUpdateActionBar();
    _rdiUpdateSelectAll();

    // Show outcome summary
    _rdiShowOutcomeSummary(data);

    // Reload page one to reflect new delivery state
    _rdiCursor = null;
    _rdiLoadPage(null);

  } catch (err) {
    _rdiShowOutcomeError('Network error: ' + String(err));
    if (submitBtn) submitBtn.disabled = false;
  } finally {
    if (submitBtn) submitBtn.disabled = false;
  }
}

function _rdiShowOutcomeSummary(data) {
  const created = (data.created || []).length;
  const active = (data.already_active || []).length;
  const delivered = (data.already_delivered || []).length;
  const invalid = (data.invalid || []).length;

  const total = created + active + delivered;
  let text = '';
  if (created > 0) text += created + ' queued. ';
  if (active > 0) text += active + ' already active. ';
  if (delivered > 0) text += delivered + ' already delivered. ';
  if (invalid > 0) text += invalid + ' invalid (kept selected). ';

  const outcomeEl = document.getElementById('rdi-outcome');
  if (outcomeEl) {
    outcomeEl.textContent = text.trim();
    outcomeEl.className = 'rdi-outcome-banner ' + (invalid > 0 && total === 0 ? 'rdi-outcome-banner-partial' : 'rdi-outcome-banner-success');
    outcomeEl.hidden = false;
    setTimeout(function() { if (outcomeEl) outcomeEl.hidden = true; }, 6000);
  }
}

function _rdiShowOutcomeError(msg) {
  const outcomeEl = document.getElementById('rdi-outcome');
  if (outcomeEl) {
    outcomeEl.textContent = msg;
    outcomeEl.className = 'rdi-outcome-banner rdi-outcome-banner-partial';
    outcomeEl.hidden = false;
  }
}

// ---------------------------------------------------------------------------
// Evidence drawer
// ---------------------------------------------------------------------------

function _rdiOpenDrawer(sha, rowData) {
  const drawer = document.getElementById('rdi-drawer');
  if (!drawer) return;
  _rdiDrawerSHA = sha;

  const body = document.getElementById('rdi-drawer-body');
  if (!body) return;

  body.innerHTML = '';

  // If no row data, show minimal info
  if (!rowData) {
    const p = document.createElement('p');
    p.textContent = 'No data for SHA: ' + sha;
    body.appendChild(p);
    drawer.classList.add('open');
    return;
  }

  // Full SHA
  const shaSection = document.createElement('div');
  shaSection.className = 'rdi-drawer-section';
  const shaLabel = document.createElement('div');
  shaLabel.className = 'rdi-drawer-section-label';
  shaLabel.textContent = 'SHA';
  const shaVal = document.createElement('div');
  shaVal.className = 'rdi-drawer-mono';
  shaVal.textContent = rowData.sha || sha;
  shaSection.appendChild(shaLabel);
  shaSection.appendChild(shaVal);
  body.appendChild(shaSection);

  // Parents
  if (rowData.parents && rowData.parents.length > 0) {
    const parentsSection = document.createElement('div');
    parentsSection.className = 'rdi-drawer-section';
    const parentsLabel = document.createElement('div');
    parentsLabel.className = 'rdi-drawer-section-label';
    parentsLabel.textContent = 'Parents';
    parentsSection.appendChild(parentsLabel);
    for (const p of rowData.parents) {
      const pDiv = document.createElement('div');
      pDiv.className = 'rdi-drawer-mono';
      pDiv.textContent = p;
      parentsSection.appendChild(pDiv);
    }
    body.appendChild(parentsSection);
  }

  // Subject
  if (rowData.subject) {
    const subjSection = document.createElement('div');
    subjSection.className = 'rdi-drawer-section';
    const subjLabel = document.createElement('div');
    subjLabel.className = 'rdi-drawer-section-label';
    subjLabel.textContent = 'Subject';
    const subjVal = document.createElement('div');
    subjVal.textContent = rowData.subject;
    subjSection.appendChild(subjLabel);
    subjSection.appendChild(subjVal);
    body.appendChild(subjSection);
  }

  // Author
  if (rowData.author_name) {
    const authSection = document.createElement('div');
    authSection.className = 'rdi-drawer-section';
    const authLabel = document.createElement('div');
    authLabel.className = 'rdi-drawer-section-label';
    authLabel.textContent = 'Author';
    const authVal = document.createElement('div');
    authVal.textContent = rowData.author_name + (rowData.authored_at ? ' · ' + rowData.authored_at : '');
    authSection.appendChild(authLabel);
    authSection.appendChild(authVal);
    body.appendChild(authSection);
  }

  // Association
  if (rowData.association && rowData.association.identifier) {
    const assocSection = document.createElement('div');
    assocSection.className = 'rdi-drawer-section';
    const assocLabel = document.createElement('div');
    assocLabel.className = 'rdi-drawer-section-label';
    assocLabel.textContent = 'Association';
    const assocLink = document.createElement('span');
    assocLink.className = 'rdi-assoc';
    assocLink.textContent = rowData.association.identifier + ' (' + (rowData.association.kind || 'task') + ')';
    assocLink.dataset.identifier = rowData.association.identifier;
    assocLink.setAttribute('role', 'button');
    assocLink.setAttribute('tabindex', '0');
    assocLink.addEventListener('click', function() {
      _rdiCloseDrawer();
      closeReleaseDelivery();
      if (typeof openDetailPanel === 'function') {
        openDetailPanel(this.dataset.identifier, _rdiProjectId);
      }
    });
    assocSection.appendChild(assocLabel);
    assocSection.appendChild(assocLink);
    body.appendChild(assocSection);
  }

  // Per-branch evidence
  const releaseStatus = rowData.release_status || {};
  const branchNames = _rdiVisibleBranches.length > 0 ? _rdiVisibleBranches
    : Object.keys(releaseStatus);

  if (branchNames.length > 0) {
    const evidenceSection = document.createElement('div');
    evidenceSection.className = 'rdi-drawer-section';
    const evidenceLabel = document.createElement('div');
    evidenceLabel.className = 'rdi-drawer-section-label';
    evidenceLabel.textContent = 'Release status per branch';
    evidenceSection.appendChild(evidenceLabel);

    for (const branch of branchNames) {
      const cell = releaseStatus[branch] || { state: 'not_selected' };
      const state = cell.state || 'not_selected';
      const label = _RDI_STATUS_LABELS[state] || state.replace(/_/g, ' ');

      const rowDiv = document.createElement('div');
      rowDiv.style.marginBottom = '0.4rem';

      // Branch name
      const branchSpan = document.createElement('span');
      branchSpan.style.fontWeight = '600';
      branchSpan.style.fontSize = '0.78rem';
      branchSpan.textContent = branch + ': ';
      rowDiv.appendChild(branchSpan);

      // State label
      const stateSpan = document.createElement('span');
      let cssClass = 'rdi-cell rdi-cell-' + state;
      if (state === 'delivered' && cell.evidence === 'ancestry') {
        cssClass = 'rdi-cell rdi-cell-delivered-ancestry';
        stateSpan.textContent = 'Delivered by ancestry';
      } else if (state === 'delivered' && cell.evidence === 'delivery') {
        cssClass = 'rdi-cell rdi-cell-delivered';
        stateSpan.textContent = 'Delivered by cherry-pick';
      } else {
        stateSpan.textContent = label;
      }
      stateSpan.className = cssClass;
      rowDiv.appendChild(stateSpan);

      // PR link
      if (cell.pr_url) {
        const prA = document.createElement('a');
        prA.href = cell.pr_url;
        prA.target = '_blank';
        prA.rel = 'noopener noreferrer';
        prA.textContent = ' PR';
        prA.style.marginLeft = '0.4rem';
        prA.style.fontSize = '0.78rem';
        rowDiv.appendChild(prA);
      }

      // Delivery ID
      if (cell.delivery_id) {
        const idDiv = document.createElement('div');
        idDiv.className = 'rdi-drawer-mono';
        idDiv.style.fontSize = '0.7rem';
        idDiv.style.color = 'var(--text-muted)';
        idDiv.textContent = 'Delivery: ' + cell.delivery_id;
        rowDiv.appendChild(idDiv);
      }

      // Result commits
      if (cell.result_commits && cell.result_commits.length > 0) {
        const rcDiv = document.createElement('div');
        rcDiv.className = 'rdi-drawer-mono';
        rcDiv.style.fontSize = '0.7rem';
        rcDiv.style.color = 'var(--text-muted)';
        rcDiv.textContent = 'Result: ' + cell.result_commits.map(function(s) { return s.slice(0, 8); }).join(', ');
        rowDiv.appendChild(rcDiv);
      }

      evidenceSection.appendChild(rowDiv);
    }
    body.appendChild(evidenceSection);
  }

  drawer.classList.add('open');
  const closeBtn = drawer.querySelector('.rdi-drawer-close');
  if (closeBtn) setTimeout(function() { closeBtn.focus(); }, 50);
}

function _rdiCloseDrawer() {
  const drawer = document.getElementById('rdi-drawer');
  if (drawer) drawer.classList.remove('open');
  _rdiDrawerSHA = null;
}

// ---------------------------------------------------------------------------
// Filter / search handlers
// ---------------------------------------------------------------------------

function _rdiOnFilterChange() {
  const checked = document.querySelector('input[name="rdi-filter"]:checked');
  _rdiFilter = checked ? checked.value : 'needs_delivery';
  _rdiCursor = null;
  _rdiLoadPage(null);
}

let _rdiSearchTimer = null;
function _rdiOnSearchInput() {
  clearTimeout(_rdiSearchTimer);
  _rdiSearchTimer = setTimeout(function() {
    const searchEl = document.getElementById('rdi-search');
    _rdiQuery = searchEl ? searchEl.value : '';
    _rdiCursor = null;
    _rdiLoadPage(null);
  }, 350);
}

function _rdiBranchFilterChange(branch, checked) {
  if (checked) {
    if (!_rdiVisibleBranches.includes(branch)) {
      _rdiVisibleBranches.push(branch);
    }
  } else {
    _rdiVisibleBranches = _rdiVisibleBranches.filter(function(b) { return b !== branch; });
  }
  _rdiCursor = null;
  _rdiLoadPage(null);
}

function _rdiShowNoProject() {
  _rdiSetBody('<div class="rdi-no-project">Select a project to view release delivery status.</div>');
  _rdiHideActionBar();
  _rdiHidePagination();
  const meta = document.getElementById('rdi-meta');
  if (meta) meta.textContent = '';
  const branchFilters = document.getElementById('rdi-branch-filters');
  if (branchFilters) branchFilters.innerHTML = '';
}
// ---------------------------------------------------------------------------
// (end release delivery overlay)
// ---------------------------------------------------------------------------
'''

# ---------------------------------------------------------------------------
# New HTML overlay to replace the old RBI HTML
# ---------------------------------------------------------------------------

NEW_HTML = '''<!-- Release delivery overlay (OOMPAH-200) -->
<div class="rdi-overlay" id="rdi-overlay"
     onclick="if(event.target===this)closeReleaseDelivery()"
     role="dialog" aria-modal="true" aria-labelledby="rdi-title">
  <div class="rdi-panel">
    <!-- Header -->
    <div class="rdi-header">
      <h3 id="rdi-title">Release delivery</h3>
      <span class="rdi-header-meta" id="rdi-meta" aria-live="polite"></span>
      <button id="rdi-refresh-btn" style="font-size:0.75rem;padding:2px 8px;" onclick="_rdiRefresh()" title="Reload commit inventory">Refresh</button>
      <button class="rdi-close-btn" id="rdi-close-btn" onclick="closeReleaseDelivery()" aria-label="Close Release delivery">&times;</button>
    </div>
    <!-- Controls -->
    <div class="rdi-controls" id="rdi-controls">
      <div class="rdi-control-row">
        <label for="rdi-project-select" class="rdi-label">Project:</label>
        <select id="rdi-project-select" onchange="_rdiOnProjectChange()" aria-label="Select project"></select>
        <span class="rdi-label">Filter:</span>
        <span class="rdi-filter-group" role="radiogroup" aria-label="Commit filter">
          <label><input type="radio" name="rdi-filter" value="needs_delivery" checked onchange="_rdiOnFilterChange()"> Needs delivery</label>
          <label><input type="radio" name="rdi-filter" value="all" onchange="_rdiOnFilterChange()"> All commits</label>
        </span>
        <input type="search" id="rdi-search" class="rdi-search" placeholder="Search SHA, subject, author, task…" aria-label="Search commits" oninput="_rdiOnSearchInput()">
      </div>
      <div class="rdi-branch-filters" id="rdi-branch-filters" role="group" aria-label="Release line columns"></div>
    </div>
    <!-- Outcome banner (hidden by default) -->
    <div id="rdi-outcome" class="rdi-outcome-banner rdi-outcome-banner-success" hidden aria-live="polite"></div>
    <!-- Table body -->
    <div class="rdi-table-wrap" id="rdi-body" role="region" aria-live="polite">
      <div class="rdi-no-project">Select a project to view release delivery status.</div>
    </div>
    <!-- Pagination -->
    <div class="rdi-pagination" id="rdi-pagination" hidden></div>
    <!-- Bulk action bar (shown when commits are selected) -->
    <div class="rdi-action-bar" id="rdi-action-bar" hidden>
      <span class="rdi-action-count" id="rdi-action-count">0 commits selected</span>
      <span class="rdi-label">Queue for:</span>
      <div class="rdi-target-list" id="rdi-target-list" role="group" aria-label="Target release branches"></div>
      <button class="btn-primary" id="rdi-queue-btn" onclick="_rdiQueueSelected()">Queue selected commits</button>
      <button onclick="_rdiClearSelection()">Clear selection</button>
    </div>
  </div>
</div>

<!-- Release delivery evidence drawer (OOMPAH-200) -->
<div class="rdi-drawer" id="rdi-drawer"
     onclick="if(event.target===this)_rdiCloseDrawer()"
     role="dialog" aria-modal="true" aria-labelledby="rdi-drawer-title">
  <div class="rdi-drawer-panel">
    <div class="rdi-drawer-header">
      <h4 id="rdi-drawer-title">Commit details</h4>
      <button class="rdi-drawer-close" onclick="_rdiCloseDrawer()" aria-label="Close commit details">&times;</button>
    </div>
    <div class="rdi-drawer-body" id="rdi-drawer-body"></div>
  </div>
</div>
'''

# ---------------------------------------------------------------------------
# Apply all changes
# ---------------------------------------------------------------------------

def main():
    content = DASHBOARD.read_text(encoding="utf-8")
    original_len = len(content)

    # --- 1. Replace RBI CSS with new RDI CSS ---
    rbi_css_start_marker = "    /* Release branches inspector overlay (OOMPAH-182) */"
    rbi_css_end_marker = "    /* Release branches dialog (OOMPAH-180) */"
    css_start = content.index(rbi_css_start_marker)
    css_end = content.index(rbi_css_end_marker)
    content = content[:css_start] + NEW_CSS + "\n    " + content[css_end:]
    print(f"[1] Replaced RBI CSS ({css_end - css_start} bytes) with RDI CSS ({len(NEW_CSS)} bytes)")

    # --- 2. Update toolbar button ---
    old_btn = '      <button id="btn-release-branches" onclick="openReleaseBranchInspector()" title="Inspect release-branch addendums: see queued and delivered work for any configured release line.">Release branches</button>'
    new_btn = '      <button id="btn-release-delivery" onclick="openReleaseDelivery()" title="View release delivery: commit inventory with per-branch delivery status for this project.">Release delivery</button>'
    if old_btn not in content:
        print("ERROR: toolbar button not found!", file=sys.stderr)
        sys.exit(1)
    content = content.replace(old_btn, new_btn, 1)
    print("[2] Updated toolbar button")

    # --- 3. Replace RBI JS with new RDI JS ---
    rbi_js_start = "// ---------------------------------------------------------------------------\n// Release branches inspector (OOMPAH-182)\n// ---------------------------------------------------------------------------"
    rbi_js_end = "// ---------------------------------------------------------------------------\n// (end release branches inspector)\n// ---------------------------------------------------------------------------"
    js_start = content.index(rbi_js_start)
    js_end = content.index(rbi_js_end) + len(rbi_js_end)
    content = content[:js_start] + NEW_JS + content[js_end:]
    print(f"[3] Replaced RBI JS ({js_end - js_start} bytes) with RDI JS ({len(NEW_JS)} bytes)")

    # --- 4. Replace RBI HTML overlay with new RDI HTML ---
    rbi_html_start = "<!-- Release branches inspector overlay (OOMPAH-182) -->"
    rbi_html_end = "</div>\n</body>"
    html_start = content.index(rbi_html_start)
    html_end = content.rindex(rbi_html_end)
    # Replace from the comment to the closing </div> before </body>
    content = content[:html_start] + NEW_HTML + "\n</body>"
    print(f"[4] Replaced RBI HTML with RDI HTML")

    DASHBOARD.write_text(content, encoding="utf-8")
    print(f"Done. File size: {original_len} -> {len(content)} bytes")


if __name__ == "__main__":
    main()
