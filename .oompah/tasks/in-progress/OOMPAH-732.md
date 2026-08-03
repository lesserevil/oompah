---
id: OOMPAH-732
type: task
status: In Progress
priority: null
title: Prevent standalone Ready delivery starvation after restart
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-03T17:50:33.429591Z'
updated_at: '2026-08-03T18:50:06.513254Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 1ead466f6b075a490ac65852a7c07a00a2fb85b329ff34b25e6401d64b7e3251
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-08-03T18:01:38.122140+00:00'
  matched_identifiers: []
  evidence: 'Focus handoff: duplicate_detector

    Duplicate preflight verdict: no_duplicate

    Matches: none

    Evidence: The current project task corpus contains only OOMPAH-732 in Open state.
    All 175+ peer tasks are archived/terminal and therefore ineligible as duplicate
    targets. The referenced regression source OOMPAH-598 is absent from the authoritative
    corpus; if it exists in the tracker, it has been merged and would be terminal.
    No active Open task addresses the specific standalone delivery starvation mechanism
    (authority revocation before review lookup during shared-epic queue starvation)
    described in OOMPAH-732.

    # Duplicate Investigation Results


    I need to analyze OOMPAH-732 against the provided project task corpus to determine
    if it''s a duplicate of any active issue.


    ## Current Task Summary

    **OOMPAH-732** is marked as **Open** and describes:

    - A live regression from merged OOMPAH-598 (post-2026-08-03 service restart)

    - Standalone Ready tasks (OOMPAH-724, OOMPAH-726, OOMPAH-729) stuck without delivery
    paths

    - Root cause: delivery authority being revoked before review lookup, repeating
    with no competing worker/tracker transition

    - No gate, review, queue activity, or standalone-delivery alert despite having
    capacity


    ## Corpus Analysis


    I reviewed all 175+ tasks in the provided current project task corpus for active
    duplicates. The task corpus explicitly states `"availability": "authoritative"`
    and `"scope": "current project tracker"`.


    **Finding:** No active Open task in the corpus describes the same standalone Ready
    delivery starvation problem.


    ### Key Observations:


    1. **All other tasks are terminal** (Archived/Done/Merged): OOMPAH-1, OOMPAH-10
    through OOMPAH-175 are all explicitly marked Archived or Done, making them historical
    context rather than active duplicate targets per the investigation rules.


    2. **OOMPAH-598 is not in the corpus**: The issue description references OOMPAH-598
    as the source of the regression ("Live regression of merged OOMPAH-598"), but
    this task does not appear in the provided authoritative corpus. If OOMPAH-598
    exists, it has been merged/archived (terminal state) and would not qualify as
    a duplicate candidate anyway.


    3. **No related Open task covers this scope**: The closest archived tasks touch
    orchestrator delivery, reconciliation scheduling, quality gates, and review capacity
    (OOMPAH-162 through OOMPAH-175), but all are terminal and none describe the specific
    starvation pattern of standalone Ready records being skipped during shared-epic
    queue processing.


    ---


    Focus handoff: duplicate_detector


    Duplicate preflight verdict: no_duplicate


    Ma'
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: 2a43b5d3-d498-4126-817a-93a7d08768ed
oompah.task_costs:
  total_input_tokens: 10
  total_output_tokens: 1882
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 10
      output_tokens: 1882
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 10
    output_tokens: 1882
    cost_usd: 0.0
    recorded_at: '2026-08-03T18:01:38.119231+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-732__20260803T175332Z
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: duplicate_detector
    source_branch: OOMPAH-732
    source_sha: f035aa3e64db9e6c71e6538c0c4fd7fcffa2de8c
    completed_at: '2026-08-03T18:01:38.150950+00:00'
---
## Summary

Live regression of merged OOMPAH-598 observed after the 2026-08-03 service restart. Standalone tasks OOMPAH-724, OOMPAH-726, and OOMPAH-729 are Ready to Integrate with exact pushed branch/head metadata, no parent epic, no open review, no integration queue row, no active or recent quality gate, no running worker, and no standalone-delivery alert. OOMPAH-724 and OOMPAH-726 remained invisible for more than 40 minutes while shared-epic integration continued processing other projects. The project is healthy, unpaused, and has review capacity.\n\nImplementation scope:\n- Reproduce persisted standalone Ready records across startup and during a large shared-epic queue workload.\n- Ensure the standalone Ready reconciler runs on every bounded reconciliation interval independently of shared-epic claim success, cycle repair, project queue volume, and maintenance lane starvation.\n- Wake reconciliation immediately when a same-head accepted submission is restored or resubmitted.\n- Create exactly one gate/review delivery path, or emit one actionable standalone-delivery alert when delivery is impossible.\n- Reconcile records already in Ready at startup even when their submission predates the current service instance.\n- Preserve project review-capacity reservations, finish dependencies, exact-head gates, idempotent PR discovery, and no duplicate reviews.\n\nRelevant code: Orchestrator integration processing and standalone Ready reconciliation, tick-pool scheduling, startup recovery, state-change wakeups, integration metadata persistence, quality-gate scheduling, review cache/capacity, and standalone delivery alerts.\n\nRequired tests:\n- Restart with three persisted standalone Ready tasks and no PR/queue/gate; each obtains a bounded delivery path.\n- Keep a large shared-epic Ready queue and container-cycle repair active while proving standalone reconciliation is not starved.\n- Cover same-head resubmit wakeup, duplicate ticks, existing review, active/recent gate, unavailable SCM, review-capacity wait, gate failure/retry, and successful merge/audit.\n- Assert one review per available slot, no duplicate gate, no silent Ready row beyond the reconciliation interval, and actionable alert lifecycle.\n- Run focused standalone delivery, integration queue, maintenance scheduler, restart recovery, quality gate, review capacity, and state wakeup suites plus make test.\n\nAcceptance criteria:\n- A pushed standalone Ready task cannot remain without a gate, review, queue activity, or actionable alert beyond one bounded reconciliation interval.\n- OOMPAH-724, OOMPAH-726, and OOMPAH-729 converge through normal delivery after live rearming.\n- Busy shared-epic work cannot starve standalone delivery.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-03 17:52
---
Root evidence from the live log: capacity deferral was initially legitimate at 1/1, but after review capacity cleared every standalone sweep fetched each exact remote head and then logged Cancelled superseded standalone delivery ... delivery authority was revoked before review lookup for OOMPAH-724/726/729. This repeated at 17:40, 17:43, and 17:46 with no competing worker or tracker transition, no alert, and zero open Oompah reviews. The permanent fix must make evidence-revision/authority refresh stable across the remote-head and PR-lookup boundary, or atomically replace the authority without cancelling the same current generation. Add a concurrent tracker refresh/comment/update regression proving benign revision reads cannot revoke an otherwise identical exact-head delivery.
---
author: oompah
created: 2026-08-03 17:53
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-03 17:53
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-03 17:57
---
The regression also immediately captured newly submitted OOMPAH-730: its worker submitted exact head and authority was revoked at 17:54:55, task is now Ready to Integrate with no gate/review while the runtime still lacks its container-cycle repair. Keep this live row in regression acceptance. Manual fallback respects max_in_flight_prs=1: OOMPAH-729 is PR #686 with CI running; OOMPAH-724/726/730 remain Ready until that slot frees.
---
author: oompah
created: 2026-08-03 17:58
---
Additional live scheduling defect: after same-head rearm, the standalone reconciler correctly began the exact OOMPAH-724 make test gate in isolated bwrap (active gate PID 3130590), but _process_integration_queues awaits the entire standalone reconciliation before recover/claim of shared-epic rows. While this several-minute gate runs, 39 Ready integration rows have no claimant. Make the permanent scheduling fix bidirectional: shared-epic volume must not starve standalone delivery, and a long standalone exact-head gate must not pause unrelated shared-epic queue claims. Preserve per-project review/gate serialization while allowing unrelated groups/projects to progress.
---
author: oompah
created: 2026-08-03 18:01
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 2, Tool calls: 0
- Tokens: 10 in / 1.9K out [1.9K total]
- Cost: $0.0000
- Exit: normal, Duration: 8m 14s
- Log: OOMPAH-732__20260803T175332Z.jsonl
---
author: oompah
created: 2026-08-03 18:03
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-08-03 18:03
---
Focus: Software Engineer
---
author: oompah
created: 2026-08-03 18:26
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 0, Tool calls: 52
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: terminated, Duration: 22m 36s
- Log: OOMPAH-732__20260803T180337Z.jsonl
---
author: oompah
created: 2026-08-03 18:26
---
Agent dispatched (profile: standard)
---
author: oompah
created: 2026-08-03 18:26
---
Focus: Software Engineer
---
author: oompah
created: 2026-08-03 18:29
---
Understanding (continuation run): Reviewing the recovery checkpoint from the previous agent. Three root fixes have been partially implemented: (1) removed updated_at from the standalone delivery evidence revision fingerprint to prevent benign tracker bookkeeping from revoking live delivery authority; (2) added _standalone_delivery_future to decouple standalone reconciliation from the shared-epic _integration_future so neither blocks the other; (3) moved standalone reconciliation launch to the start of _tick so maintenance lane starvation cannot defer it. Need to verify all tests pass, check startup recovery is wired correctly, verify wakeup on same-head resubmit, and ensure the new tests meet all acceptance criteria before submitting.
---
author: oompah
created: 2026-08-03 18:49
---
Discovery: Three root causes identified from live log evidence.

1. **Evidence revision instability** (primary): `_standalone_delivery_evidence_revision` included `updated_at`, which is advanced by tracker comments, cache refreshes, and other benign bookkeeping. Every standalone sweep fetched the remote head, then read the fresh issue whose `updated_at` had just been advanced, causing the revision comparison to fail with 'Cancelled superseded standalone delivery'—repeatedly, with no competing worker and no lifecycle change.

2. **Bidirectional scheduling starvation** (secondary): `_reconcile_standalone_ready_to_integrate_tasks` was called inside `_process_integration_queues` as a sequential `await run_in_executor`. A long standalone make-test gate (several minutes) would block all shared-epic queue claims. Conversely, if `_integration_future` was busy, standalone reconciliation was deferred.

3. **Reconciler scheduling position** (secondary): Standalone reconciliation launched only after the epic integration coroutine, so maintenance lane or dispatch starvation could defer the bounded Ready sweep interval.

Relevant files: `oompah/orchestrator.py` (methods `_standalone_delivery_evidence_revision`, `_tick`, `_process_integration_queues`); tests in `tests/test_standalone_ready_to_integrate.py` and `tests/test_orchestrator_handlers.py`.
---
author: oompah
created: 2026-08-03 18:50
---
Implementation: Three coordinated fixes in oompah/orchestrator.py.

**Fix 1 — Evidence revision stability (root cause fix)**:
Removed `updated_at` from `_standalone_delivery_evidence_revision()`. The remaining fields (work_branch, branch_name, target_branch, review_number, review_url, integration.head_sha) are the delivery-relevant submission and review evidence; a lifecycle or exact-head change still fences the claim correctly. This prevents benign tracker comments/bookkeeping from revoking a live delivery authority.

**Fix 2 — Bidirectional scheduling decoupling**:
Added `_standalone_delivery_future` (separate from `_integration_future`) so that a long standalone exact-head quality gate cannot block shared-epic queue recovery/claim, and vice versa. Removed the sequential `await run_in_executor(_reconcile_standalone_ready_to_integrate_tasks)` from `_process_integration_queues`.

**Fix 3 — Reconciler priority in tick**:
Moved standalone delivery `run_in_executor` arm to the very start of `_tick()`, before dispatch, maintenance, and watchdog lanes. The future itself coalesces duplicate ticks while one sweep is active.

**New tests**:
- `test_standalone_gate_does_not_hold_shared_queue_driver`: proves concurrent future separation—standalone reconciler and shared-epic queue driver launch and run independently in the same tick.
- `test_benign_tracker_timestamp_change_keeps_exact_head_authority`: concurrent tracker timestamp advances (comments, refreshes) on a live exact-head delivery cannot revoke the current authority generation.
---
<!-- COMMENTS:END -->
