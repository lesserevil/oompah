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
labels:
- focus-complete:duplicate_detector
assignee: null
created_at: '2026-07-28T13:53:31.446905Z'
updated_at: '2026-07-28T16:04:28.537580Z'
work_branch: epic-OOMPAH-490
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: d3deb7f6-12ab-49a7-8a05-eede667709ff
oompah.work_branch: epic-OOMPAH-490
oompah.task_costs:
  total_input_tokens: 505166
  total_output_tokens: 3230
  total_cost_usd: 0.0
  by_model:
    fable:
      input_tokens: 505166
      output_tokens: 3230
      cost_usd: 0.0
  runs:
  - profile: default
    model: fable
    input_tokens: 505166
    output_tokens: 3230
    cost_usd: 0.0
    recorded_at: '2026-07-28T16:03:53.321132+00:00'
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
author: oompah
created: 2026-07-28 16:03
---
Discovery: No confirmed duplicate. Full task views show OOMPAH-171 uniquely removed the draft-epic lifecycle and rewrote the five draft regression modules; OOMPAH-169 uniquely removed the projects-page epic-strategy UI; OOMPAH-167/168 cover backend/configuration and orchestration, not test consolidation. The current five files collect 59 cases, including repeated static absence checks plus four API cases in test_dashboard_draft_epics.py, matching OOMPAH-496’s distinct pruning scope.
---
author: oompah
created: 2026-07-28 16:03
---
Focus handoff: duplicate_detector\n\n1. Outcome: No confirmed duplicate; OOMPAH-496 should proceed to implementation.\n2. Evidence: Searched .oompah/tasks, docs, plans, README.md, and WORKFLOW.md for draft-epic/epic-strategy and the named test modules. Read OOMPAH-171, OOMPAH-169, OOMPAH-167, OOMPAH-168, OOMPAH-166, OOMPAH-490, and blocker OOMPAH-491 with full descriptions/comments. The five current target files collect 59 cases. OOMPAH-171 owns retired draft behavior, OOMPAH-169 owns retired strategy UI, and OOMPAH-167/168 preserve backend/shared-only behavior; none owns this consolidation.\n3. Remaining work/risks: Implement the requested canonical test_dashboard_draft_epics.py consolidation, delete the three draft-only duplicates, consolidate epic-strategy markers/saveProject() coverage, preserve API/generic-label and positive smoke tests, and run the specified focused tests plus make test after the safety prerequisite.\n4. Recommended next focus: chore or test (implementation), followed by verification.
---
author: oompah
created: 2026-07-28 16:03
---
Agent completed successfully in 85s (508396 tokens)
---
author: oompah
created: 2026-07-28 16:03
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 17
- Tokens: 505.2K in / 3.2K out [508.4K total]
- Cost: $0.0000
- Exit: normal, Duration: 1m 25s
- Log: OOMPAH-496__20260728T160232Z.jsonl
---
author: oompah
created: 2026-07-28 16:03
---
Focus handoff from `duplicate_detector` is complete. Queued a fresh agent run for the next applicable focus. The next agent should begin with the preceding Focus handoff comment.
---
author: oompah
created: 2026-07-28 16:04
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-28 16:04
---
Focus: Maintenance Engineer
---
author: oompah
created: 2026-07-28 16:04
---
Agent failed: errored. Retrying in 10s (attempt #1)
---
author: oompah
created: 2026-07-28 16:04
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/fable]
- Turns: 1, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 4s
- Log: OOMPAH-496__20260728T160408Z.jsonl
---
author: oompah
created: 2026-07-28 16:04
---
Agent dispatched (profile: quick)
---
author: oompah
created: 2026-07-28 16:04
---
Focus: Maintenance Engineer
---
<!-- COMMENTS:END -->
