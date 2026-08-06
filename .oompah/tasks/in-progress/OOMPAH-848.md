---
id: OOMPAH-848
type: bug
status: In Progress
priority: 1
title: Isolate free-tier budget snapshot tests from heavyweight live state
parent: OOMPAH-763
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-06T04:35:27.470578Z'
updated_at: '2026-08-06T04:43:11.824830Z'
work_branch: epic-OOMPAH-763--task-OOMPAH-848
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 2b726a5ec2c196022230a244f15350ffc8de6ac84acf9ae25312ca06f007ff39
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-08-06T04:42:13.385395+00:00'
  matched_identifiers: []
  evidence: "Focus handoff: duplicate_detector\nDuplicate preflight verdict: no_duplicate\n\
    Matches: none\nEvidence: ** OOMPAH-848 is the only active task in the corpus addressing\
    \ free-tier snapshot test isolation. OOMPAH-849 (same title, archived) was an\
    \ accidental duplicate already cleaned up by the operator. All 11 active non-terminal\
    \ sibling tasks address workflow architecture, capacity scheduling, integration\
    \ ownership, or tool contracts\u2014different problems. The infrastructure fixes\
    \ (OOMPAH-846, 831, 809) may reduce the timeout pressure but do not isolate the\
    \ test itself. No active duplicate candidate exists.\n# Duplicate Screening Analysis\
    \ for OOMPAH-848\n\nI'll systematically compare OOMPAH-848 against the provided\
    \ task corpus to determine if an active duplicate exists.\n\n## Current Task Summary\n\
    \n**OOMPAH-848**: \"Isolate free-tier budget snapshot tests from heavyweight live\
    \ state\"\n- **Type**: bug  \n- **Status**: Open  \n- **Scope**: Isolate `test_should_dispatch_increments_and_snapshot_reflects_it`\
    \ (from `test_budget_free_tier_dispatch.py`) from unrelated heavyweight live-state\
    \ dependencies (storage, terminal-audit, maintenance, SCM, corpus paths) without\
    \ weakening free-tier counter assertions or changing production semantics.\n\n\
    ## Corpus Review\n\nI've reviewed all 32 tasks in the supplied corpus. Here's\
    \ my filtering:\n\n### Terminal (excluded):\nOOMPAH-764, 765, 766, 806, 807, 814,\
    \ 815, 816, 817, 822, 840, 841, 849 (Archived), 1 (Archived)\n\n### Active Non-Terminal\
    \ Tasks Analyzed:\n\n| Task | Status | Title | Relevance to OOMPAH-848 |\n|------|--------|-------|--------------------------|\n\
    | OOMPAH-763 | In Progress | Build unified workflow engine | Epic parent (architecture)\
    \ |\n| OOMPAH-767 | In Progress | Model-based fault testing | Workflow verification\
    \ (different scope) |\n| OOMPAH-768 | In Progress | Migrate workflow domains |\
    \ Workflow architecture (different scope) |\n| OOMPAH-769 | Open | Transition\
    \ service writer | Workflow architecture (different scope) |\n| OOMPAH-770 | In\
    \ Progress | Liveness and alerts | Workflow infrastructure (different scope) |\n\
    | OOMPAH-771 | Backlog | Retire legacy reconcilers | Workflow modularization (different\
    \ scope) |\n| OOMPAH-808 | In Progress | Fence nested-epic dispatch | Epic prerequisite\
    \ reachability (different problem) |\n| OOMPAH-809 | Open | Reserve workflow capacity\
    \ | Scheduler lane reservation (different problem) |\n| OOMPAH-811 | Open | Rearm\
    \ integration ownership | Integration head rewriting (different problem) |\n|\
    \ OOMPAH-831 | Needs CI Fix | Auditor search/inspection | Tool contract consistency\
    \ (different problem) |\n| OOMPAH-846 | In Progres"
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: 59d7e31e-c94e-4d3f-a00d-1475abe0cf6f
oompah.work_branch: epic-OOMPAH-763--task-OOMPAH-848
oompah.integration:
  version: 2
  state: working
  attempts: 0
  task_branch: epic-OOMPAH-763--task-OOMPAH-848
  base_branch: epic-OOMPAH-763
  base_sha: 93cc4c85664bfba06c82ac04ab66329c7f378832
  updated_at: '2026-08-06T04:40:10.052323+00:00'
oompah.task_costs:
  total_input_tokens: 10
  total_output_tokens: 2298
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 10
      output_tokens: 2298
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 10
    output_tokens: 2298
    cost_usd: 0.0
    recorded_at: '2026-08-06T04:42:02.511155+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-848__20260806T044132Z
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: duplicate_detector
    source_branch: epic-OOMPAH-763--task-OOMPAH-848
    source_sha: 93cc4c85664bfba06c82ac04ab66329c7f378832
    completed_at: '2026-08-06T04:42:12.383090+00:00'
---
## Summary

Regression evidence: the authoritative OOMPAH-791 exact-head gate at 0b5b039a reached 16,192 passes before tests/test_budget_free_tier_dispatch.py::TestGetSnapshotFreeTierActive::test_should_dispatch_increments_and_snapshot_reflects_it failed while unrelated worker test commands were concurrently bypassing the validation-resource lease. The test exercises only the free-tier counter and snapshot projection, yet it constructs a full Orchestrator and calls the complete get_snapshot path twice. Implementation scope: reproduce and identify whether construction or snapshot collection crosses unrelated storage, terminal-audit, maintenance, SCM, or corpus paths; isolate this unit test and adjacent free-tier snapshot tests from those dependencies without weakening the free-tier counter assertion or changing production semantics. If production get_snapshot contains avoidable unbounded synchronous work, move that work behind cached/bounded projections with explicit failure behavior. Relevant files: tests/test_budget_free_tier_dispatch.py, oompah/orchestrator.py snapshot/budget projection, and shared test helpers. Required tests: the named test repeatedly in serial and four-way concurrency, the complete budget module serial and -n 4, explicit assertions that unrelated live-state collectors are not invoked, and make test at the exact review head. Acceptance criteria: _should_dispatch still increments exactly once for an eligible free provider after budget exhaustion; the snapshot immediately reports free_tier_active and the counter; the unit test has no unrelated external/corpus dependency; it passes deterministically under a saturated canonical gate; no global timeout is raised.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-06 04:40
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-06 04:40
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-06 04:42
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 2, Tool calls: 0
- Tokens: 10 in / 2.3K out [2.3K total]
- Cost: $0.0000
- Exit: normal, Duration: 2m 2s
- Log: OOMPAH-848__20260806T044132Z.jsonl
---
<!-- COMMENTS:END -->
