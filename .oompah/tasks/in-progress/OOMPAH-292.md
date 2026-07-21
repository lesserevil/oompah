---
id: OOMPAH-292
type: task
status: In Progress
priority: null
title: Show mergeable-item summaries and full task details in Release Delivery
parent: null
children: []
blocked_by: []
labels:
- focus-complete:duplicate_detector
assignee: null
created_at: '2026-07-21T15:01:48.947973Z'
updated_at: '2026-07-21T15:07:21.899397Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: d2128a10-68e4-44cc-a888-fdbe84156888
oompah.task_costs:
  total_input_tokens: 110189
  total_output_tokens: 6167
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 110189
      output_tokens: 6167
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
<!-- COMMENTS:END -->
