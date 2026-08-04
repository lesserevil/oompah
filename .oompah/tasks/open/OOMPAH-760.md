---
id: OOMPAH-760
type: bug
status: Open
priority: 1
title: Persist completed focus before a task handoff reopens work
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-04T11:25:45.766223Z'
updated_at: '2026-08-04T11:29:39.014900Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: b618e2de7a17cf673ff221e1bd18c0cdbaea44a2ebb4ac1e0e1125298329f0e8
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-08-04T11:29:29.614024+00:00'
  matched_identifiers: []
  evidence: 'Focus handoff: duplicate_detector

    Duplicate preflight verdict: no_duplicate

    Matches: none

    Evidence: All 31 similarity candidates in the provided corpus are in Archived
    (terminal) state and therefore ineligible as active duplicate targets. The task
    corpus searched 612 candidates but omitted 581; those omitted identifiers are
    not named in the selection diagnostic, so no structural peers can be confirmed.
    Tasks OOMPAH-757, OOMPAH-402, and OOMPAH-430 referenced in the description are
    outside this corpus and remain unverified.

    Looking at the task corpus provided, I need to determine whether OOMPAH-760 is
    a duplicate of any active issue.


    **Analysis:**


    OOMPAH-760 describes a bug where task handoffs loop back to the same inapplicable
    focus (docs) instead of advancing to the requested focus (feature), caused by:

    - Handoff operations (comment, status, label, focus marker) not being atomic

    - Worker termination before focus-complete:docs metadata persisted

    - Fresh dispatch re-selecting the old focus instead of the requested new one


    The task references:

    - Triggered by: OOMPAH-757 (not in corpus)

    - Related to: OOMPAH-402, OOMPAH-430 (not in corpus)


    **Corpus Review:**


    I examined all 31 similar candidates included in the corpus. Every candidate task
    is in a **terminal state** (Archived), making them ineligible as duplicate targets:

    - OOMPAH-1 through OOMPAH-185, OOMPAH-270: all Archived


    The corpus selection diagnostic shows 581 omitted similarity candidates from 612
    total searches, but names no specific omitted identifiers.


    **Conclusion:**


    No active (non-terminal) duplicate exists in the authoritative corpus. All referenced
    related tasks (OOMPAH-757, OOMPAH-402, OOMPAH-430) fall outside the provided corpus
    scope and would need separate verification.


    ---


    Focus handoff: duplicate_detector

    Duplicate preflight verdict: no_duplicate

    Matches: none


    Evidence: All 31 similarity candidates in the provided corpus are in Archived
    (terminal) state and therefore ineligible as active duplicate targets. The task
    corpus searched 612 candidates but omitted 581; those omitted identifiers are
    not named in the selection diagnostic, so no structural peers can be confirmed.
    Tasks OOMPAH-757, OOMPAH-402, and OOMPAH-430 referenced in the description are
    outside this corpus and remain unverified.'
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: d917a910-5de3-4bec-adf1-0b59914e90e6
oompah.task_costs:
  total_input_tokens: 10
  total_output_tokens: 2071
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 10
      output_tokens: 2071
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 10
    output_tokens: 2071
    cost_usd: 0.0
    recorded_at: '2026-08-04T11:29:29.598893+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-760__20260804T112834Z
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: duplicate_detector
    source_branch: OOMPAH-760
    source_sha: 5368e23617a98569caf7370b0f2eb63d41c8ba6b
    completed_at: '2026-08-04T11:29:29.638885+00:00'
---
## Summary

Triggered by: OOMPAH-757

Triggered by: OOMPAH-757

Live recurrence/incomplete case of OOMPAH-402 and OOMPAH-430 on revision 5368e236. OOMPAH-757 was first assigned to Technical Writer. The worker correctly posted a structured HANDOFF saying the work requires a backend Feature Developer and used the supported task-handoff path, which changed the tracker to Open. Reconciliation observed Open while the docs worker was still registered and terminated it before worker-result handling persisted focus-complete:docs. The task retained needs:feature but no durable completed-focus marker. After operator recovery from the separate retry self-abort tracked by OOMPAH-759, a fresh normal dispatch selected Technical Writer again at 11:24:42 UTC. Thus a valid handoff loops to the same inapplicable focus and can repeatedly consume agents without advancing implementation.

Implementation scope: make accepted task-handoff mutation, structured handoff comment, successor focus/request, completed-focus marker, tracker Open transition, running-worker retirement, retry cancellation, and dispatch wake one atomic/idempotent authority transition. Reconciliation and worker-exit handling must recognize an accepted handoff generation and must not terminate it as an unexpected state revert before completion metadata is durable. Focus selection must honor the exact completed focus and explicit requested/needs:* successor on fresh dispatch. Backfill bounded trusted Oompah-authored HANDOFF comments that predate the marker without trusting arbitrary human text; handle duplicate handoff, late worker exit, restart, and concurrent status refresh exactly once.

Relevant code: worker task-handoff API/CLI authentication path, _handoff_completed_focus, worker completion, reconcile no-longer-in-progress branch, focus-complete labels/metadata, retry scheduling, focus selection, and dispatch wake.

Required tests: exact OOMPAH-757 docs -> feature handoff where Open becomes visible before worker exit; reconcile during handoff; late/forced worker termination; retry and normal-dispatch paths; restart between comment/label/status writes; duplicate handoff; forged human HANDOFF comment rejection; already-completed focus; explicit needs:feature selection. Acceptance criteria: a valid focus handoff durably completes the old focus before the task is dispatchable, starts the requested applicable focus exactly once, never loops back to the old focus, and never leaves an orphaned In Progress claim; focused handoff/reconcile/focus-selection/retry/restart tests and make test pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-04 11:28
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-04 11:28
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-04 11:29
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 2, Tool calls: 0
- Tokens: 10 in / 2.1K out [2.1K total]
- Cost: $0.0000
- Exit: normal, Duration: 1m 5s
- Log: OOMPAH-760__20260804T112834Z.jsonl
---
<!-- COMMENTS:END -->
