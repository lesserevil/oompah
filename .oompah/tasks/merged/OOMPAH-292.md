---
id: OOMPAH-292
type: task
status: Merged
priority: null
title: Show mergeable-item summaries and full task details in Release Delivery
parent: null
children: []
blocked_by: []
labels:
- focus-complete:duplicate_detector
assignee: null
created_at: '2026-07-21T15:01:48.947973Z'
updated_at: '2026-07-21T15:39:44.932069Z'
work_branch: OOMPAH-292
target_branch: main
review_url: https://github.com/lesserevil/oompah/pull/463
review_number: '463'
merged_at: null
oompah.agent_run_id: e16c63a5-ac08-4f4e-9d81-d8e3833c06c3
oompah.task_costs:
  total_input_tokens: 386732
  total_output_tokens: 40132
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 386732
      output_tokens: 40132
      cost_usd: 0.0
  runs:
  - profile: default
    model: unknown
    input_tokens: 21
    output_tokens: 5506
    cost_usd: 0.0
    recorded_at: '2026-07-21T15:06:13.383223+00:00'
  - profile: default
    model: unknown
    input_tokens: 110168
    output_tokens: 661
    cost_usd: 0.0
    recorded_at: '2026-07-21T15:06:54.688761+00:00'
  - profile: standard
    model: unknown
    input_tokens: 82
    output_tokens: 30360
    cost_usd: 0.0
    recorded_at: '2026-07-21T15:23:28.865851+00:00'
  - profile: default
    model: unknown
    input_tokens: 8
    output_tokens: 1856
    cost_usd: 0.0
    recorded_at: '2026-07-21T15:24:30.580931+00:00'
  - profile: default
    model: unknown
    input_tokens: 97949
    output_tokens: 648
    cost_usd: 0.0
    recorded_at: '2026-07-21T15:27:51.530893+00:00'
  - profile: standard
    model: unknown
    input_tokens: 178504
    output_tokens: 1101
    cost_usd: 0.0
    recorded_at: '2026-07-21T15:29:07.177102+00:00'
oompah.review_url: https://github.com/lesserevil/oompah/pull/463
oompah.review_number: '463'
oompah.work_branch: OOMPAH-292
oompah.target_branch: main
---
## Summary

Problem

Release Delivery rows show only identifier/title/commit metadata, so users must leave the page to understand a mergeable task or epic. Clicking an identifier opens a narrow 420px evidence drawer that shows only release evidence, not the full task detail available on the dashboard.

Implement

- Extend the Release Delivery backlog payload with a concise, safely derived task or epic summary for every associated mergeable item. Use the task description/summary, normalize whitespace, and truncate to a documented bounded length; preserve a clear fallback when no description exists.
- Render that summary directly beneath or alongside the title in each Release Delivery item row. It must be readable without opening the detail drawer and must not expose raw HTML.
- Change the Release Delivery drawer width to match the dashboard detail panel: width min(800px, 40vw), retaining an appropriate narrow-viewport fallback.
- On opening an associated task/epic drawer, request GET /api/v1/issues/{identifier}/detail with the selected project ID and render the same core information as the dashboard: title, state, priority, labels, type, parent, description, children where applicable, comments, source/repository links, and task metadata. Keep delivery status and source-commit evidence as an additional Release Delivery section.
- Show an in-drawer loading/error state without losing already rendered delivery evidence. Do not fetch task details for unassociated commits.

Tests

- Backlog service/API tests for summary extraction, normalization, truncation, missing-description fallback, and HTML-safe transport.
- Template tests asserting the summary is rendered for every item row.
- Drawer tests asserting the full-detail endpoint is called with project_id, all core dashboard fields are rendered, delivery evidence remains visible, and errors are displayed safely.
- CSS test asserting the drawer uses min(800px, 40vw).

Acceptance criteria

A user can understand the purpose of every mergeable task/epic from the Release Delivery list, and clicking it shows substantially the same task information as the dashboard without leaving the page. The drawer is no wider than 40% of the viewport and no narrower than the dashboard detail-panel behavior at normal desktop widths.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-21 15:04
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-21 15:04
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-21 15:06
---
Focus handoff: duplicate_detector

1. Outcome: No duplicate confirmed. OOMPAH-292 is a fresh feature task with no existing equivalent.

2. Evidence reviewed:
   - Searched .oompah/tasks/ (merged, archived, backlog, done) for: 'Release Delivery', 'summary', 'truncat', 'drawer', 'drawer width', '420px', '800px', '40vw', 'task detail', 'full detail', 'item description', 'mergeable'.
   - Reviewed full content of all candidate tasks.

   Closest related tasks (not duplicates):
   - OOMPAH-263 (Merged): 'Widen the dashboard task detail pane' — widened the dashboard right-side detail pane to min(800px, 40vw). OOMPAH-292 applies the same width to the Release Delivery drawer (a separate component on release_delivery.html) and additionally adds task summaries in rows and full task-detail loading. Different scope, different component.
   - OOMPAH-252 (Merged): 'Move Release Delivery from dashboard dialog to a dedicated page' — created the dedicated Release Delivery page with an evidence drawer. Does not include summaries in rows, full task details, or drawer width changes.
   - OOMPAH-236 (Merged): 'Replace Release Delivery commit pagination with item-centric release backlog' — made rows item-centric (one row per task/epic). Does not include summaries or drawer width changes.
   - OOMPAH-200 (Merged): Added the evidence drawer to Release Delivery. Does not include full task details or summary fields.

3. Remaining work: Full implementation — backend (backlog payload summary field, normalization, truncation, HTML safety) + frontend (summary in rows, drawer width, full task details via GET /api/v1/issues/{identifier}/detail, loading/error states) + tests per spec.

4. Recommended next focus: feature (backend + frontend implementation).
---
author: oompah
created: 2026-07-21 15:06
---
Agent completed successfully in 125s (5527 tokens)
---
author: oompah
created: 2026-07-21 15:06
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/default]
- Turns: 47, Tool calls: 32
- Tokens: 21 in / 5.5K out [5.5K total]
- Cost: $0.0000
- Exit: normal, Duration: 2m 5s
- Log: OOMPAH-292__20260721T150409Z.jsonl
---
author: oompah
created: 2026-07-21 15:06
---
Focus handoff from `duplicate_detector` is complete. Queued a fresh agent run for the next applicable focus. The next agent should begin with the preceding Focus handoff comment.
---
author: oompah
created: 2026-07-21 15:06
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-21 15:06
---
Focus: Frontend Developer
---
author: oompah
created: 2026-07-21 15:06
---
Agent completed successfully in 33s (110829 tokens)
---
author: oompah
created: 2026-07-21 15:06
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/default]
- Turns: 1, Tool calls: 0
- Tokens: 110.2K in / 661 out [110.8K total]
- Cost: $0.0000
- Exit: normal, Duration: 33s
- Log: OOMPAH-292__20260721T150623Z.jsonl
---
author: oompah
created: 2026-07-21 15:06
---
Agent completed without landing — no commits found on origin for branch `OOMPAH-292`. Escalating from 'default' to 'standard'. Retrying in 10s (1/3).
---
author: oompah
created: 2026-07-21 15:07
---
Agent dispatched (profile: standard)
---
author: oompah
created: 2026-07-21 15:07
---
Focus: Frontend Developer
---
author: oompah
created: 2026-07-21 15:07
---
Understanding: I'm the frontend developer agent for OOMPAH-292. My task is to implement: (1) summary field in Release Delivery backlog rows (backend + frontend), (2) widen the Release Delivery drawer to min(800px, 40vw), (3) load full task details via GET /api/v1/issues/{identifier}/detail in the drawer, and (4) tests for all of the above. Starting by exploring the codebase to find relevant files.
---
author: oompah
created: 2026-07-21 15:09
---
Discovery: Found all relevant files. Key locations: (1) oompah/release_delivery_backlog.py - ItemRow dataclass and get_backlog(), need to add summary field; (2) oompah/server.py line ~4050, backlog JSON serialization, need to add summary; (3) oompah/templates/release_delivery.html - CSS drawer width at line 367 (420px → min(800px,40vw)), row rendering at line 1110, drawer logic at line 1455+; (4) tests/test_release_delivery_backlog.py, tests/test_release_delivery_page.py, tests/test_server_release_delivery_backlog.py for new tests. Dashboard uses GET /api/v1/issues/{identifier}/detail with project_id and renders title/type/state/priority/description/labels/parent/children/comments/links. Starting implementation.
---
author: oompah
created: 2026-07-21 15:22
---
Implementation complete. Changes made:

1. **oompah/release_delivery_backlog.py**: Added ITEM_SUMMARY_MAX_LENGTH=280 constant, _extract_item_summary() helper (strips HTML, normalises whitespace, truncates, returns None for no description), summary: str | None = None field to ItemRow, summary_map populated in get_backlog() alongside title_map.

2. **oompah/server.py**: Added 'summary': item.summary to backlog JSON serialization.

3. **oompah/templates/release_delivery.html**: (a) Drawer width changed from 420px to min(800px, 40vw) with max-width: 90vw fallback; (b) Added .rdi-item-summary CSS class and summary rendered beneath title in each item row via textContent (HTML-safe, aria-label added); (c) Complete drawer overhaul: _rdiOpenItemDrawer shows loading state, calls _rdiFetchTaskDetail, renders full task detail (title/type/state/priority/labels/parent/description/children/comments/links/metadata) via _rdiRenderTaskDetail, and keeps delivery evidence always visible via _rdiBuildDeliverySection; _rdiEsc helper added for safe error rendering.

4. **tests/**: Added TestExtractItemSummary (12 tests), TestItemRowSummaryField (4 tests), TestSummaryInApiResponse (3 tests), TestItemSummaryInRow (5 tests), TestDrawerWidth (3 tests), TestFullTaskDetailInDrawer (17 tests); updated 2 existing tests in test_dashboard_release_delivery_ui.py to reflect new delivery-section architecture.
---
author: oompah
created: 2026-07-21 15:22
---
Verification: All 9918 tests pass (36 skipped, 0 failed). New tests added:
- TestExtractItemSummary (12 tests): HTML stripping, whitespace normalisation, truncation at ITEM_SUMMARY_MAX_LENGTH, None fallbacks, custom max_length, XSS safety
- TestItemRowSummaryField (4 tests): summary populated from tracker, None when no description, None without tracker, HTML stripped
- TestSummaryInApiResponse (3 tests): summary field present/null/always-keyed in JSON
- TestItemSummaryInRow (5 tests): CSS class defined, textContent usage, aria-label, conditional rendering
- TestDrawerWidth (3 tests): min(800px,40vw), max-width fallback, 420px removed
- TestFullTaskDetailInDrawer (17 tests): detail endpoint called, project_id passed, all core fields rendered, loading state, error display, delivery evidence preserved
Branch pushed to origin/OOMPAH-292.
---
author: oompah
created: 2026-07-21 15:23
---
Completion: Delivered all items specified in OOMPAH-292:

1. Backend (release_delivery_backlog.py): ITEM_SUMMARY_MAX_LENGTH=280, _extract_item_summary() with HTML stripping/whitespace normalisation/truncation/None-fallback, summary field on ItemRow.

2. API (server.py): summary included in every item row in backlog JSON response.

3. Frontend — summary in rows (release_delivery.html): .rdi-item-summary span rendered below title via textContent (never innerHTML), with aria-label for accessibility.

4. Frontend — drawer width: min(800px, 40vw) with max-width: 90vw fallback — matches dashboard detail panel exactly (OOMPAH-263 parity).

5. Frontend — full task detail in drawer: _rdiFetchTaskDetail() calls GET /api/v1/issues/{identifier}/detail?project_id=... and _rdiRenderTaskDetail() renders title, type, state, priority, labels, parent, description (pre-wrapped), children, source/repository links, tracker metadata, created/updated timestamps, and comments. Loading state shown while fetching; errors rendered safely via _rdiEsc(); delivery evidence (_rdiBuildDeliverySection) always appended synchronously so it is never lost. Unassociated commits do not trigger a detail fetch.

6. Tests: 44 new tests added across backlog unit tests, server API tests, and template tests. 2 existing tests updated. All 9918 tests pass.
---
author: oompah
created: 2026-07-21 15:23
---
Implemented all OOMPAH-292 features: (1) ItemRow.summary field extracted from tracker descriptions (HTML-stripped, whitespace-normalised, truncated to 280 chars, None fallback); (2) summary in backlog JSON API; (3) summary rendered in Release Delivery rows beneath title via textContent; (4) drawer width widened to min(800px, 40vw) with 90vw fallback; (5) full task detail loaded via GET /api/v1/issues/{identifier}/detail in drawer (title/type/state/priority/labels/parent/description/children/comments/links/metadata); (6) delivery evidence always visible (synchronous, before async fetch); (7) 44 new tests, 2 updated tests, all 9918 tests pass.
---
author: oompah
created: 2026-07-21 15:23
---
Agent completed successfully in 977s (30442 tokens)
---
author: oompah
created: 2026-07-21 15:23
---
Run #2 [attempt=2, profile=standard, role=standard -> Claude/default]
- Turns: 138, Tool calls: 95
- Tokens: 82 in / 30.4K out [30.4K total]
- Cost: $0.0000
- Exit: normal, Duration: 16m 17s
- Log: OOMPAH-292__20260721T150713Z.jsonl
---
author: oompah
created: 2026-07-21 15:23
---
Close refused by orchestrator: branch `OOMPAH-292` has 1 commit not on `main` and no open PR targets `main` from this branch.

Diagnostic:
  Unmerged commits: 1
    b6588f1a3 OOMPAH-292: Show mergeable-item summaries and full task details in Release Delivery
  Open PRs from this branch: 0
  Merged PRs from this branch: 0

Required: open a PR before closing.
  gh pr create --base main --head OOMPAH-292 --title "OOMPAH-292: Show mergeable-item summaries and full task details in Release Delivery" --body "..."

Task reopened. Re-dispatch on the next tick will see this comment in its prompt context.
---
author: oompah
created: 2026-07-21 15:23
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-21 15:23
---
Focus: Frontend Developer
---
author: oompah
created: 2026-07-21 15:24
---
PR opened: https://github.com/lesserevil/oompah/pull/463

All implementation work was completed in the previous agent run. This run created the required PR to unblock task closure. All 9918 tests pass.
---
author: oompah
created: 2026-07-21 15:24
---
Implemented mergeable-item summaries and full task details in Release Delivery. Backend: ITEM_SUMMARY_MAX_LENGTH=280, _extract_item_summary() with HTML stripping/whitespace normalisation/truncation, summary field on ItemRow, included in backlog JSON. Frontend: .rdi-item-summary in rows (textContent, aria-label), drawer widened to min(800px,40vw) with 90vw fallback, full task detail via GET /api/v1/issues/{identifier}/detail with loading/error states and synchronous delivery evidence. 44 new tests, 2 updated, all 9918 pass. PR: https://github.com/lesserevil/oompah/pull/463
---
author: oompah
created: 2026-07-21 15:24
---
Agent completed successfully in 54s (1864 tokens)
---
author: oompah
created: 2026-07-21 15:24
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/default]
- Turns: 10, Tool calls: 5
- Tokens: 8 in / 1.9K out [1.9K total]
- Cost: $0.0000
- Exit: normal, Duration: 54s
- Log: OOMPAH-292__20260721T152338Z.jsonl
---
author: oompah
created: 2026-07-21 15:24
---
Completion refused by orchestrator: unpushed work detected on branch `OOMPAH-292` while task is in a terminal state.

Diagnostic:
  Worktree has uncommitted changes — file(s) created but never committed.

Required: commit the work, push to origin, then close the task.

Steps to resolve:
  git checkout OOMPAH-292
  git add -A
  git commit -m "Descriptive commit message"
  git push origin OOMPAH-292

Task re-opened. Re-dispatch will push a fresh agent to complete the landing.
---
author: oompah
created: 2026-07-21 15:27
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-21 15:27
---
Focus: Frontend Developer
---
author: oompah
created: 2026-07-21 15:27
---
Agent completed successfully in 36s (98597 tokens)
---
author: oompah
created: 2026-07-21 15:27
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/default]
- Turns: 1, Tool calls: 0
- Tokens: 97.9K in / 648 out [98.6K total]
- Cost: $0.0000
- Exit: normal, Duration: 36s
- Log: OOMPAH-292__20260721T152721Z.jsonl
---
author: oompah
created: 2026-07-21 15:27
---
Agent completed without closing this issue (36s (98597 tokens)). Escalating from 'default' to 'standard'. Retrying in 20s (2/3).
---
author: oompah
created: 2026-07-21 15:28
---
Retrying (attempt #2, agent: standard)
---
author: oompah
created: 2026-07-21 15:28
---
Focus: Frontend Developer
---
author: oompah
created: 2026-07-21 15:29
---
Agent completed successfully in 45s (179605 tokens)
---
author: oompah
created: 2026-07-21 15:29
---
Run #3 [attempt=3, profile=standard, role=standard -> Codex/default]
- Turns: 1, Tool calls: 0
- Tokens: 178.5K in / 1.1K out [179.6K total]
- Cost: $0.0000
- Exit: normal, Duration: 45s
- Log: OOMPAH-292__20260721T152823Z.jsonl
---
author: oompah
created: 2026-07-21 15:29
---
Agent completed 3 times without closing this issue. Human action required: review the agent run history and task state, then either close the task if the work is done or add specific guidance and move it back to Open.
---
author: oompah
created: 2026-07-21 15:39
---
YOLO: merged PR #463.
---
<!-- COMMENTS:END -->
