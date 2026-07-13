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
updated_at: '2026-07-13T04:17:25.429019Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: b6e5cb5b-aa16-45e0-919f-f0431ec3e8a2
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
<!-- COMMENTS:END -->
