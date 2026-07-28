---
id: OOMPAH-496
type: chore
status: In Progress
priority: 2
title: Consolidate removed draft-epic and epic-strategy UI contracts
parent: OOMPAH-490
children: []
blocked_by:
- OOMPAH-491
labels: []
assignee: null
created_at: '2026-07-28T13:53:31.446905Z'
updated_at: '2026-07-28T16:02:58.326996Z'
work_branch: epic-OOMPAH-490
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: 7dfabf98-e10d-46c8-b019-93dd7e9b9400
oompah.work_branch: epic-OOMPAH-490
---
## Summary

Implementation scope

Consolidate retired-interface regression coverage across `tests/test_dashboard_draft_epics.py`, `tests/test_draft_epic_swimlane.py`, `tests/test_draft_epic_badge.py`, `tests/test_draft_swimlane_toggle.py`, and `tests/test_projects_epic_strategy_ui.py`. Keep `test_dashboard_draft_epics.py` as the canonical draft-removal module: retain its four server/API tests, replace repeated static absence checks with one loop over well-named forbidden markers and one focused positive smoke test, then delete the other three draft-only files. In the epic-strategy file, replace per-CSS-class and per-variable absence cases with one forbidden-marker contract and one test scoped to the `saveProject()` function body. Include marker-specific assertion messages. Do not remove backend tests proving shared is the only supported epic strategy.

Tests

Run all five current files before the change and the surviving files afterward. Record collection counts. Ensure draft labels still behave as generic labels through the API and the projects page cannot submit `epic_strategy`. Run `make test` after the safety prerequisite.

Acceptance criteria

The same retired controls cannot silently return, the four API behavior cases remain, positive dashboard/project-page smoke coverage remains, declared tests across this area fall from 59 to no more than 12, and no deleted file owns unique production behavior.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-28 16:02
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-28 16:02
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-28 16:02
---
Understanding: I’m screening OOMPAH-496 for duplicates before any implementation. I’ll compare its test-consolidation scope with the completed draft-lifecycle and epic-strategy tasks, then either archive a confirmed duplicate or record evidence and hand off.
---
<!-- COMMENTS:END -->
