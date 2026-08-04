---
id: OOMPAH-496
type: chore
status: In Validation
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
updated_at: '2026-08-04T17:31:26.170956Z'
work_branch: epic-OOMPAH-490
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: 777ea576-66d6-4ceb-94fa-f8d04ef072bc
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
oompah.terminal_audit:
  queued_comment_posted: true
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-d98d3a4af4ba
    project_id: proj-14849f1b
    task_id: OOMPAH-496
    target_state: Archived
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 89b900d705681485e5a047701580def68e7c2765bc07eedb8c959717e156d346
    attempts:
    - version: 1
      attempt_id: attempt-5e9e180e1b57
      target_state: Archived
      request_state: in_progress
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: 89b900d705681485e5a047701580def68e7c2765bc07eedb8c959717e156d346
      created_at: '2026-08-04T17:31:16.167747+00:00'
      provider_id: prov-651d553c
      model: opus
      started_at: '2026-08-04T17:31:16.167747+00:00'
      branch_key: epic-OOMPAH-490
    requested_by:
      version: 1
      identity: oompah
      source: auto_archive
    previous_state: Merged
    created_at: '2026-08-04T17:26:30.466347+00:00'
    updated_at: '2026-08-04T17:31:16.167747+00:00'
  attempt_history:
  - version: 1
    attempt_id: attempt-5e9e180e1b57
    target_state: Archived
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 89b900d705681485e5a047701580def68e7c2765bc07eedb8c959717e156d346
    created_at: '2026-08-04T17:31:16.167747+00:00'
    provider_id: prov-651d553c
    model: opus
    started_at: '2026-08-04T17:31:16.167747+00:00'
    branch_key: epic-OOMPAH-490
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
author: oompah
created: 2026-07-28 16:04
---
Understanding: This is a test-contract consolidation only. I will baseline collection across the five named modules, retain the four dashboard API cases plus focused positive smoke coverage, collapse static absence assertions into marker loops (including saveProject() scoping), remove only redundant draft-only modules, then run focused tests and make test before committing and pushing.
---
author: oompah
created: 2026-07-28 16:07
---
Run #2 [attempt=2, profile=quick, role=fast -> Codex/gpt-5.6-luna]
- Turns: 0, Tool calls: 24
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: terminated, Duration: 3m 12s
- Log: OOMPAH-496__20260728T160428Z.jsonl
---
author: oompah
created: 2026-07-28 16:07
---
Agent dispatched (profile: quick)
---
author: oompah
created: 2026-07-28 16:08
---
Focus: Maintenance Engineer
---
author: oompah
created: 2026-07-28 16:08
---
Agent failed: errored. Retrying in 20s (attempt #2)
---
author: oompah
created: 2026-07-28 16:08
---
Run #2 [attempt=2, profile=quick, role=fast -> Claude/fable]
- Turns: 1, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 8s
- Log: OOMPAH-496__20260728T160802Z.jsonl
---
author: oompah
created: 2026-07-28 16:08
---
Retrying (attempt #2, agent: quick)
---
author: oompah
created: 2026-07-28 16:08
---
Focus: Maintenance Engineer
---
author: oompah
created: 2026-07-28 16:08
---
Understanding: I will consolidate the five named retired-interface test modules without changing production behavior: baseline their collection counts, preserve the four dashboard API cases and positive smoke checks, collapse absence assertions into marker-driven contracts (scoping epic-strategy markers to saveProject()), remove only redundant draft-only modules, then run focused tests and make test.
---
author: oompah
created: 2026-07-28 16:10
---
Implementation: retained tests/test_dashboard_draft_epics.py as the canonical module with 8 named dashboard forbidden markers, marker-specific failures, one card/swimlane smoke test, and all four existing API cases; deleted test_draft_epic_swimlane.py, test_draft_epic_badge.py, and test_draft_swimlane_toggle.py; consolidated tests/test_projects_epic_strategy_ui.py into one page-wide marker contract and one saveProject()-scoped contract. Focused suite: 8 passed.
---
author: oompah
created: 2026-07-28 16:13
---
Completion: Consolidated retired UI contracts in tests/test_dashboard_draft_epics.py and tests/test_projects_epic_strategy_ui.py; deleted the three redundant draft-only modules. Baseline was 59 collected tests across five files; surviving contracts collect 8. Focused 8/8 and focused UI/backend regression set 355/355 pass. Full equivalent suite: 12,269 passed, 7 skipped, 1 unrelated ACP failure; make test could not start pytest because uv hit the environment DBus transient-scope error. Commit bba2829f0 is pushed to epic-OOMPAH-490, and git status is clean/up to date.
---
author: oompah
created: 2026-07-28 16:13
---
Run #3 [attempt=3, profile=quick, role=fast -> Codex/gpt-5.6-luna]
- Turns: 0, Tool calls: 21
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: terminated, Duration: 5m 16s
- Log: OOMPAH-496__20260728T160835Z.jsonl
---
author: oompah
created: 2026-07-28 16:13
---
Consolidated draft-removal and epic-strategy UI contracts from 59 tests to 8; preserved API and shared-only backend coverage; focused checks pass and commit bba2829f0 is pushed.
---
author: oompah
created: 2026-07-28 16:14
---
Verification: baseline HEAD suite across all five named modules: 59 passed. After consolidation: 8 collected, 8 passed. make test was attempted after OOMPAH-491 completed but uv failed before pytest with DBus transient-scope error (exit 46); direct pytest tests/ -q reached 12268 passed, 7 skipped, 2 unrelated environment/order failures (tests/test_acp_agent.py log path is read-only; tests/test_dashboard_task_display_identifier.py returned an empty cached board). git diff --check passes.
---
author: oompah
created: 2026-07-28 16:15
---
Completion: pushed bba2829f0 (OOMPAH-496: consolidate retired UI contract tests) to epic-OOMPAH-490. The canonical dashboard contract now covers all retired draft markers in one loop, keeps four API cases plus positive smoke coverage, and the three redundant draft-only modules are deleted. Projects-page coverage is consolidated into page markers plus saveProject() scoping. Baseline was 59/59; surviving area is 8/8; working tree is clean and up to date with origin.
---
author: oompah
created: 2026-07-28 16:15
---
Consolidated retired draft-epic and epic-strategy UI regression contracts; baseline 59 tests reduced to 8, focused suite passes, and commit bba2829f0 is pushed.
---
author: oompah
created: 2026-08-04 17:26
---
Queued Archived audit: Aged Merged auto-archive (closed 7 days ago). An auditor will review before the task is retired.
---
author: oompah
created: 2026-08-04 17:31
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/opus)
---
author: oompah
created: 2026-08-04 17:31
---
Focus: Completion Auditor
---
<!-- COMMENTS:END -->
