---
id: OOMPAH-659
type: task
status: Ready to Integrate
priority: null
title: Defer standalone full gates until finish dependencies are satisfied
parent: null
children: []
blocked_by: []
start_blocked_by: &id001
- OOMPAH-657
labels: []
assignee: null
created_at: '2026-07-31T12:15:02.565914Z'
updated_at: '2026-07-31T13:19:07.559907Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.start_blocked_by: *id001
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 903f68bf1e5410244cf5b06395503984aed024890c87202e33be151b4e57ccf2
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-07-31T13:03:56.243622+00:00'
  matched_identifiers: []
  evidence: "Based on my comprehensive search, I have enough information to provide\
    \ my verdict.\n\n**Summary of investigation:**\n\n1. **Active tasks searched**:\
    \ Only two non-terminal tasks exist in `.oompah/tasks`:\n   - OOMPAH-281 (Open):\
    \ Containerized GitHub Actions runner \u2014 completely unrelated\n   - OOMPAH-282\
    \ (Backlog): State branch migration UnicodeEncodeError \u2014 completely unrelated\n\
    \n2. **Merged/Archived tasks**: All tasks OOMPAH-1 through OOMPAH-280 are in terminal\
    \ states (Archived or Merged). None can be duplicate targets per the rules.\n\n\
    3. **Keyword searches**: Exhaustive searches for `standalone gate`, `finish dependency`,\
    \ `ready-to-integrate`, `defer gate`, `quality gate`, `effective_depend`, `watchdog\
    \ churn`, `needs CI fix`, `integration queue` \u2014 all returned **zero matches**\
    \ in `.oompah/tasks`.\n\n4. **OOMPAH-657 context**: Tests in `test_delivery_plane_recovery.py`\
    \ and `test_quality_gate.py` reference OOMPAH-657, confirming it was already implemented\
    \ and submitted (per coordination comment: \"OOMPAH-657 submitted 0212dada64768ed8f89e7b27f461f121c4a42299\"\
    ). It is a terminal/submitted task \u2014 not an active duplicate target. OOMPAH-658\
    \ is the triggering task that spawned this investigation.\n\n5. **OOMPAH-659's\
    \ scope** (deferring standalone full gates until finish dependencies are satisfied)\
    \ is a **new, distinct problem** not covered by any active task.\n\n---\n\nFocus\
    \ handoff: duplicate_detector\n\nDuplicate preflight verdict: no_duplicate\n\n\
    Matches: none\n\nEvidence: Searched all active, non-terminal tasks in `.oompah/tasks`\
    \ (OOMPAH-281/Open, OOMPAH-282/Backlog) \u2014 both are unrelated (containerized\
    \ runner and state branch migration error respectively). Exhaustive keyword searches\
    \ for standalone gate deferral, finish-order dependencies, ready-to-integrate\
    \ waiting, quality gate, effective_dependencies, and watchdog churn returned zero\
    \ matches across all task folders (open, backlog, merged, archived). OOMPAH-657,\
    \ the closest related task, is in a submitted/terminal state (confirmed by coor"
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
oompah.agent_run_id: c07feddf-478e-4f4c-b40a-33529654f7b1
oompah.task_costs:
  total_input_tokens: 21
  total_output_tokens: 4865
  total_cost_usd: 0.0
  by_model:
    sonnet:
      input_tokens: 21
      output_tokens: 4865
      cost_usd: 0.0
  runs:
  - profile: standard
    model: sonnet
    input_tokens: 21
    output_tokens: 4865
    cost_usd: 0.0
    recorded_at: '2026-07-31T13:03:56.242390+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-659__20260731T130144Z
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: sonnet
    focus: duplicate_detector
    source_branch: OOMPAH-659
    source_sha: 3316ec40933d1c387619d534e607a3b0100df7dc
    completed_at: '2026-07-31T13:03:56.254699+00:00'
oompah.integration:
  version: 2
  state: ready
  attempts: 0
  task_branch: OOMPAH-659
  head_sha: cbbc1a5a14faaec32dfdf93e7e6043c3c0074f50
  submitted_at: '2026-07-31T13:19:04.263341+00:00'
  updated_at: '2026-07-31T13:19:04.263341+00:00'
---
## Summary

Triggered by: OOMPAH-658\n\nLive production reproduction on 2026-07-31: standalone task OOMPAH-658 has a normal finish-order dependency on OOMPAH-657, but each worker submission immediately starts the configured repository-wide quality gate. When the premature gate is operator-terminated, the task moves to Needs CI Fix, the stalled-task watchdog reopens it, another worker resubmits the unchanged head, and the loop repeats. Epic integration queues already wait for effective finish dependencies; standalone Ready-to-Integrate delivery does not.\n\nImplementation scope: before any standalone branch quality gate or review creation, compute the task's effective finish-order dependencies (including inherited parent constraints) using the same canonical dependency/status/audit-satisfaction semantics as ordered integration. If any dependency is unfinished, leave the exact submitted task/head durably in Ready to Integrate, do not run the gate, do not create a review, do not route to Needs CI Fix, and expose one idempotent non-actionable waiting reason that clears when dependencies become satisfied or the task/head changes. On dependency completion, restart, or explicit refresh, resume exactly once from the same submitted head through the normal immutable gate/review flow. Hard-start dependencies must continue to govern implementation dispatch separately.\n\nRelevant code: oompah/orchestrator.py standalone Ready-to-Integrate reconciliation and review-quality-gate entry points, dependency indexing/effective_dependencies helpers, delivery alerts/state surfaces, and tests/test_standalone_ready_to_integrate.py. Required deterministic tests: unfinished normal dependency causes zero gate/review calls across repeated ticks and restart; terminal-audit-satisfied dependency releases exactly one gate; inherited dependency behaves identically; dependency regression or head/status change cancels stale authority; project/task isolation; no Needs CI Fix/watchdog churn. Acceptance: standalone work may implement in parallel but can never consume its one full gate or create a review before every finish-order dependency is satisfied, and focused scheduler tests plus make test pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-31 12:15
---
Hard-start ordered after OOMPAH-657 because both tasks change standalone gate authority/cancellation code; implementation before that integration would create a conflict and test against obsolete lifecycle semantics.
---
author: oompah
created: 2026-07-31 13:01
---
Duplicate screening dispatched (profile: standard, task remains Open)
---
author: oompah
created: 2026-07-31 13:01
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-31 13:03
---
Run #1 [attempt=1, profile=standard, role=standard -> Claude/sonnet]
- Turns: 43, Tool calls: 29
- Tokens: 21 in / 4.9K out [4.9K total]
- Cost: $0.0000
- Exit: normal, Duration: 2m 14s
- Log: OOMPAH-659__20260731T130144Z.jsonl
---
author: oompah
created: 2026-07-31 13:04
---
Agent dispatched (profile: standard)
---
author: oompah
created: 2026-07-31 13:04
---
Focus: CI Failure Fixer
---
author: oompah
created: 2026-07-31 13:19
---
Deferred standalone gates until effective finish dependencies are terminal-audit satisfied.
---
<!-- COMMENTS:END -->
