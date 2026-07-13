---
id: OOMPAH-171
type: task
status: In Progress
priority: 2
title: Remove automatic draft-epic lifecycle
parent: OOMPAH-166
children: []
blocked_by: []
labels: []
assignee: null
created_at: '2026-07-13T02:26:02.750063Z'
updated_at: '2026-07-13T04:46:24.817401Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: 3c2043cb-5ceb-4ecd-85a4-6634643d0b27
oompah.task_costs:
  total_input_tokens: 326
  total_output_tokens: 9193
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 326
      output_tokens: 9193
      cost_usd: 0.0
  runs:
  - profile: default
    model: unknown
    input_tokens: 326
    output_tokens: 9193
    cost_usd: 0.0
    recorded_at: '2026-07-13T04:17:16.619760+00:00'
---
## Summary

Stop automatically adding the draft label whenever an epic is created. Remove the dashboard Draft Epic badge, swimlane draft badge, and Mark as Draft/Finalize controls, plus the corresponding label endpoints and client state where they are only used for epic drafting. Existing epics carrying the draft label must remain valid during rollout; provide a migration or compatibility cleanup that removes the label without changing their type, parent/child links, state, or shared-workflow behavior. Add server, tracker, and dashboard regression coverage.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-13 03:15
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-13 03:15
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-13 03:15
---
Understanding: Investigating whether OOMPAH-171 ('Remove automatic draft-epic lifecycle') is a duplicate of an existing task. Will search for prior tasks covering draft label removal, epic draft lifecycle, draft badges, or draft controls before proceeding with any implementation.
---
author: oompah
created: 2026-07-13 03:21
---
DISCOVERY: Not a duplicate. OOMPAH-171 is a legitimate unique child of OOMPAH-166 ('Standardize epic workflow on shared strategy'), created to remove the draft-epic lifecycle. Siblings OOMPAH-168 (orchestration cleanup) and OOMPAH-169 (epic-strategy UI removal) cover different areas — neither removes draft labels, draft badges, or Mark as Draft/Finalize controls. No archived task covers this scope. Proceeding with implementation: (1) find automatic draft label assignment on epic creation, (2) find Draft Epic badge/swimlane badge/controls, (3) find draft label endpoints, (4) implement removal + migration, (5) add tests.
---
author: oompah
created: 2026-07-13 03:25
---
IMPLEMENTATION starting. Confirmed scope: (1) server.py line 2697-2699 — remove auto-add draft label on epic create; (2) focus.py — remove draft label from epic_planner must_do and labels filter; (3) dashboard.html — remove .draft-epic-badge CSS, .swimlane-draft-badge CSS, toggleEpicDraft(), hasDraftLabel(), draft badge in swimlane header, Mark as Draft/Finalize button, draftEpicBadgeHtml in createCard(); update isEpicMergeFlowCard() and shouldShowIssueAsWorkCard() to remove draft checks; (4) add migration function to clean up existing epics carrying the draft label; (5) update 5 draft-epic test files + test_server_create_issue.py + test_focus.py to reflect removal, add new regression coverage.
---
author: oompah
created: 2026-07-13 04:17
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/default]
- Turns: 316, Tool calls: 203
- Tokens: 326 in / 9.2K out [9.5K total]
- Cost: $0.0000
- Exit: stalled, Duration: 1h 1m 54s
- Log: OOMPAH-171__20260713T031541Z.jsonl
---
author: oompah
created: 2026-07-13 04:17
---
Agent stalled 1 time(s) (3714s (9519 tokens)). Escalating from 'default' to 'standard'. Retrying in 10s (attempt #1)
---
author: oompah
created: 2026-07-13 04:28
---
Retrying (attempt #3, agent: standard)
---
author: oompah
created: 2026-07-13 04:28
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-13 04:46
---
VERIFICATION: All 7248 tests pass (0 failures). The 9 previously failing regression tests now pass after fixing:
1. _make_mock_orchestrator() helpers in test files — added _tracker_for_project.return_value and project_store.list_all.return_value=[] so server code resolves to the configured mock tracker
2. GET /api/v1/issues test assertions — API returns board format {state: [issues]} not {issues: [...]}, updated tests to use _all_issues_from_board() helper to flatten the board
---
author: oompah
created: 2026-07-13 04:46
---
COMPLETION: Delivered removal of automatic draft-epic lifecycle (OOMPAH-171).

Changes:
- server.py: Removed auto-add 'draft' label on epic creation (lines 2697-2699). Added remove_draft_labels_from_epics() migration function called at startup to strip draft labels from existing epics without modifying type, parent/child links, state, or any other fields.
- focus.py: Removed 'draft' label from epic_planner must_do list and labels filter.
- dashboard.html: Removed .draft-epic-badge CSS, .swimlane-draft-badge CSS, hasDraftLabel() JS function, toggleEpicDraft() JS function, draftEpicBadgeHtml variable, Mark as Draft/Finalize buttons, swimlane draft badge spans, and draft checks in shouldShowIssueAsWorkCard()/isEpicMergeFlowCard().

Tests: Rewrote 5 draft-epic test files as regression tests (no draft UI/auto-label behavior). Added test_epic_draft_migration.py for migration coverage. Fixed mock orchestrator setup and API response format assertions. All 7248 tests pass.
---
<!-- COMMENTS:END -->
