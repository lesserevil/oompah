---
id: OOMPAH-169
type: task
status: Done
priority: 2
title: Remove epic-strategy controls and stale dashboard copy
parent: OOMPAH-166
children: []
blocked_by:
- OOMPAH-167
labels: []
assignee: null
created_at: '2026-07-13T02:23:10.333133Z'
updated_at: '2026-07-13T04:50:50.149469Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: 8a048b33-4ece-4690-beec-cf797a9c870b
oompah.task_costs:
  total_input_tokens: 121241
  total_output_tokens: 5688
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 121241
      output_tokens: 5688
      cost_usd: 0.0
  runs:
  - profile: default
    model: unknown
    input_tokens: 121075
    output_tokens: 1214
    cost_usd: 0.0
    recorded_at: '2026-07-13T03:15:02.145493+00:00'
  - profile: standard
    model: unknown
    input_tokens: 166
    output_tokens: 4474
    cost_usd: 0.0
    recorded_at: '2026-07-13T04:50:49.453435+00:00'
---
## Summary

Remove the epic-strategy selector and any flat/stacked/shared choice from project create/edit UI, dashboard views, API forms, and client-side state. The UI must present shared behavior as the only workflow without a selectable strategy. Remove stale labels, help text, badges, and conditional rendering. Add dashboard/API contract tests that verify no strategy control is rendered or accepted and shared epic behavior remains visible.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-13 03:14
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-13 03:14
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-13 03:15
---
Agent completed successfully in 59s (122289 tokens)
---
author: oompah
created: 2026-07-13 03:15
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/default]
- Turns: 1, Tool calls: 2
- Tokens: 121.1K in / 1.2K out [122.3K total]
- Cost: $0.0000
- Exit: normal, Duration: 59s
- Log: OOMPAH-169__20260713T031407Z.jsonl
---
author: oompah
created: 2026-07-13 03:15
---
Agent completed without closing this issue (59s (122289 tokens)). Escalating from 'default' to 'standard'. Retrying in 10s (1/3).
---
author: oompah
created: 2026-07-13 04:17
---
Retrying (attempt #13, agent: standard)
---
author: oompah
created: 2026-07-13 04:17
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-13 04:32
---
UNDERSTANDING: This task is NOT a duplicate — OOMPAH-167 covered the backend (domain model, persistence, API validation) and OOMPAH-168 covered orchestration. OOMPAH-169 covers the UI layer.

Work to do:
1. oompah/templates/projects.html: Remove epic-strategy CSS classes, the 'Epic Strategy:' display row, the flat/stacked/shared radio button group from the edit form, and epic_strategy field from saveProject() JS
2. dashboard.html: The 'flat' references there are VIEW MODES (kanban flat vs swimlane), not epic strategies — leave them
3. Add tests (test_projects_epic_strategy_ui.py) verifying no strategy controls are rendered and saveProject() doesn't include the epic_strategy field

There are already uncommitted changes in this worktree from previous work (OOMPAH-168: removing draft-epic lifecycle from dashboard, focus.py, server.py). I will keep those and add the OOMPAH-169 changes on top.
---
author: oompah
created: 2026-07-13 04:50
---
IMPLEMENTATION: Removed epic-strategy selector and all stale UI content from oompah/templates/projects.html:

1. CSS removed: .epic-strategy-group, .epic-strategy-option, .epic-strategy-label, .epic-strategy-name, .epic-strategy-desc, .epic-strategy-tag classes and input[type='radio'] override (exclusively used by strategy form)

2. Display row removed: The 'Epic Strategy:' field-row in the project card (was showing 'flat' by default)

3. Edit form controls removed: The entire flat/stacked/shared radio button group from the project edit form

4. JS changes: Removed epicStrategyEl, epicStrategy variables and epic_strategy from the PATCH body in saveProject()

Added tests/test_projects_epic_strategy_ui.py with 14 tests verifying:
- No CSS classes present
- No display row or radio buttons in HTML
- No epic_strategy in saveProject() body

Also fixed 4 failing test regressions in draft-epic test files (OOMPAH-171 work):
- Added _populate_snapshot() helper and clear_issues_snapshot fixture
- Fixed test_issues_api_returns_issue_type_field to use board format correctly
---
author: oompah
created: 2026-07-13 04:50
---
VERIFICATION: Full test suite passes — 7248 passed, 28 skipped, 0 failed. New tests test_projects_epic_strategy_ui.py all pass (14 tests). All 4 previously-failing draft-epic regression tests now pass.
---
author: oompah
created: 2026-07-13 04:50
---
COMPLETION: OOMPAH-169 is done. Delivered:

1. oompah/templates/projects.html: Removed all epic-strategy UI controls:
   - All .epic-strategy-* CSS classes
   - The 'Epic Strategy:' read-only display row
   - The flat/stacked/shared radio button group from the edit form
   - epicStrategy reading and epic_strategy from the PATCH body in saveProject()
   
   The UI now presents no epic strategy choice. Projects always use 'shared' (enforced by backend from OOMPAH-167).

2. tests/test_projects_epic_strategy_ui.py: 14 new contract tests verifying no epic-strategy controls are rendered or sent in API calls.

3. Fixed 4 failing regression tests from the OOMPAH-171 draft-epic removal work: added _populate_snapshot() helper and clear_issues_snapshot autouse fixture so tests that call GET /api/v1/issues correctly pre-populate the snapshot cache.

All 7248 tests pass. Branch epic-OOMPAH-166 is pushed.
---
author: oompah
created: 2026-07-13 04:50
---
Removed epic-strategy selector, display row, CSS, and JS from projects.html. Added 14 contract tests. Fixed 4 failing draft-epic regression tests. 7248 tests pass.
---
<!-- COMMENTS:END -->
