---
id: OOMPAH-959
type: task
status: In Validation
priority: null
title: Continue durable effects when concurrency fills before batch size
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-09T14:08:58.066871Z'
updated_at: '2026-08-09T16:15:54.355342Z'
work_branch: OOMPAH-959
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.integration:
  version: 2
  state: ready
  attempts: 0
  mode: standalone
  task_branch: OOMPAH-959
  head_sha: 42e5355de509b5768668ca2d4462862b57d39e44
  submitted_at: '2026-08-09T15:57:47.038408+00:00'
  updated_at: '2026-08-09T15:57:47.038408+00:00'
oompah.work_branch: OOMPAH-959
oompah.terminal_audit:
  queued_comment_posted: true
  oompah.terminal_audit_tracker_projections:
  - version: 1
    audit_id: audit-5317d8cb7d28
    project_id: proj-14849f1b
    task_id: OOMPAH-959
    digest: 9a998114f7815472d49fefa3db1706de6c4637bd39a4dc56911707d275fccf4e
  - version: 1
    audit_id: audit-98be2b218af8
    project_id: proj-14849f1b
    task_id: OOMPAH-959
    digest: 9a998114f7815472d49fefa3db1706de6c4637bd39a4dc56911707d275fccf4e
  - version: 1
    audit_id: audit-aa7f0f8bfb5e
    project_id: proj-14849f1b
    task_id: OOMPAH-959
    digest: cb200a77409736d9c5bd729981e55649de1ceaafc6f2802d65e09a4796c1414d
  - version: 1
    audit_id: audit-b388d2365ecf
    project_id: proj-14849f1b
    task_id: OOMPAH-959
    digest: cb200a77409736d9c5bd729981e55649de1ceaafc6f2802d65e09a4796c1414d
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-5317d8cb7d28
    project_id: proj-14849f1b
    task_id: OOMPAH-959
    target_state: Done
    request_state: superseded
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 9a998114f7815472d49fefa3db1706de6c4637bd39a4dc56911707d275fccf4e
    attempts: []
    source_generation: 1
    requested_by:
      version: 1
      identity: oompah-cli
      source: api
    previous_state: Open
    created_at: '2026-08-09T15:08:02.089926+00:00'
    selected_ref: 4bd555a74d78a1fb0324a3ed58bcd7c01d342b41
    selected_sha: 4bd555a74d78a1fb0324a3ed58bcd7c01d342b41
  - version: 1
    audit_id: audit-98be2b218af8
    project_id: proj-14849f1b
    task_id: OOMPAH-959
    target_state: Merged
    request_state: superseded
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 9a998114f7815472d49fefa3db1706de6c4637bd39a4dc56911707d275fccf4e
    attempts: []
    source_generation: 2
    requested_by:
      version: 1
      identity: NVShawn
      source: forge
    previous_state: Open
    created_at: '2026-08-09T15:08:15.192012+00:00'
    selected_ref: 4bd555a74d78a1fb0324a3ed58bcd7c01d342b41
    selected_sha: 4bd555a74d78a1fb0324a3ed58bcd7c01d342b41
  - version: 1
    audit_id: audit-aa7f0f8bfb5e
    project_id: proj-14849f1b
    task_id: OOMPAH-959
    target_state: Done
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: cb200a77409736d9c5bd729981e55649de1ceaafc6f2802d65e09a4796c1414d
    attempts: []
    source_generation: 3
    requested_by:
      version: 1
      identity: NVShawn
      source: forge
    previous_state: Open
    created_at: '2026-08-09T16:15:50.152457+00:00'
    selected_ref: 42e5355de509b5768668ca2d4462862b57d39e44
    selected_sha: 42e5355de509b5768668ca2d4462862b57d39e44
  - version: 1
    audit_id: audit-b388d2365ecf
    project_id: proj-14849f1b
    task_id: OOMPAH-959
    target_state: Merged
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: cb200a77409736d9c5bd729981e55649de1ceaafc6f2802d65e09a4796c1414d
    attempts: []
    source_generation: 3
    requested_by:
      version: 1
      identity: NVShawn
      source: forge
    previous_state: Open
    created_at: '2026-08-09T16:15:50.152457+00:00'
    selected_ref: 42e5355de509b5768668ca2d4462862b57d39e44
    selected_sha: 42e5355de509b5768668ca2d4462862b57d39e44
  attempt_history: []
---
## Summary

Live rollout regression on build ba0859da9 after OOMPAH-939/OOMPAH-955: generations 497 and 500 each took 215-223 seconds, admitted exactly four effects (max_concurrent=4), left more than 140 queued plus 24 due retry jobs, but reported worker.batch_saturated=false and did not post the coalesced workflow continuation. Root cause is WorkflowRuntime._run_due defining saturation only as scheduled >= batch_size; when max_concurrent is lower than batch_size, admission fills every lane before reaching batch_size and the continuation signal is impossible. This strands ready durable effects until the next expensive full-sync tick and prevents OOMPAH-940 rollout convergence. Scope: make the runtime truthfully report remaining eligible work when admission stopped because all concurrency lanes filled, including reserved control/shared lanes, without false continuations when no eligible row remains; preserve per-task serialization, fair project claims, pause/drain fencing, coalescing, and non-recursive scheduling. Relevant files: oompah/workflow_runtime.py _run_due/_effect_finished, oompah/orchestrator.py _request_workflow_batch_continuation, workflow job eligibility queries, and tests/test_workflow_runtime.py plus tests/test_orchestrator_full_sync.py. Required tests: max_concurrent < batch_size with more eligible rows reports saturation and requests immediate continuation; exactly capacity rows does not spin; lane-specific exhaustion does not hide eligible work in the other lane; paused/ineligible/future rows do not trigger; completion replenishes capacity and converges through coalesced continuations; restart and concurrent _run_due callers remain fenced. Acceptance: production with max_concurrent=4 drains ready rows through prompt continuations rather than one four-row slice per 3.7-minute full sync, the saturation metric is truthful, no busy loop occurs, focused/full hosted gates pass, and the OOMPAH-940 rollout canary advances.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-09 14:23
---
Implemented exact non-mutating claimability probing shared with claim_next, concurrency-cap saturation signaling with a no-spin admission edge, and focused store/runtime regressions. Full workflow job/runtime modules pass: 155 tests. Ruff passes for changed surfaces aside from one pre-existing unused import excluded from the focused lint run.
---
author: oompah
created: 2026-08-09 14:24
---
Exact claimability probe and concurrency-cap continuation implemented; 155 focused workflow job/runtime tests pass.
---
author: oompah
created: 2026-08-09 15:08
---
Queued for terminal transition to Done. An auditor will review and apply the terminal status.
---
author: oompah
created: 2026-08-09 15:29
---
Acceptance audit found the first-half saturation signal still routed every continuation through a full tracker/controller world scan. Completed the remaining fast-path scope at exact pushed head 54bad7ddd2e467d7d9dae2b48906e945ed09ff91, rebased on origin/main be4ec5d95 (including OOMPAH-960). Pure durable-admission bursts now use a distinct coalesced event and an exact captured+accepted+published generation/project cut; every SQLite claim/probe is atomically fenced to that generation, with topology, pause, quiesce, drain, lane-cap, same-task, and fairness checks preserved. Completion edges drain existing durable rows without a world scan, then trigger one full reconcile only after the published queue empties. Production-shaped coverage proves 5 effects drain across 1 full plus 4 fast slices with one tracker fetch and unchanged snapshot generation; stale-cut, project-pause, mixed-event, fallback, no-spin, restart/concurrency adjacent coverage passes. Verification after rebasing: 503 affected tests passed; task-status mutation scan passed 20/20; secret scan exited successfully; targeted undefined-name lint and diff checks passed.
---
author: oompah
created: 2026-08-09 15:29
---
Implemented generation-fenced fast admission-only continuations; exact head 54bad7ddd2e467d7d9dae2b48906e945ed09ff91 pushed with 503 affected tests and required scans green.
---
author: oompah
created: 2026-08-09 15:57
---
Corrected independent-review blocker at pushed head 42e5355de509b5768668ca2d4462862b57d39e44. Production transition_applied callbacks preserve real ISSUE_STATE_CHANGED delivery while routing scheduler wakes through WORKFLOW_ADMISSION. The actual EpicWorkflowEventRouter now routes its targeted durable-job wake through the same admission lane, preventing the UI event subscriber from recreating REFRESH_REQUESTED/full-scan bursts; compatibility fixtures retain their fallback. End-to-end coverage uses the real EventBus and actual epic router for two transition-bearing completions, proves UI delivery, wake coalescing, three fast slices, exactly one initial and one queue-empty full reconcile, and zero ordinary refreshes. Final verification: 556 affected tests passed; changed-surface Ruff and critical Python lint passed; task-status mutation scan passed 20/20; secret scan exited 0; independent re-review found no blocker.
---
author: oompah
created: 2026-08-09 15:57
---
Corrected transition and subscriber wake routing; exact head 42e5355de with 556 affected tests and independent re-review clear
---
author: oompah
created: 2026-08-09 16:15
---
Final exact head 42e5355de509b5768668ca2d4462862b57d39e44 passed hosted CI on Python 3.11/3.12/3.13 in run 31322428029 and independent final review reported no blockers. After OOMPAH-957 merged, a no-commit composition with current main passed all 456 affected workflow/integration tests. Merging PR #771 now; the later stacked OOMPAH-961 exact-head gate will also qualify the final combined workflow tree.
---
<!-- COMMENTS:END -->
