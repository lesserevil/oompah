---
id: OOMPAH-1075
type: bug
status: In Validation
priority: 1
title: Keep branch quality gates off restart reconciliation control ticks
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-11T09:03:11.276660Z'
updated_at: '2026-08-11T10:41:14.352215Z'
work_branch: OOMPAH-1075
target_branch: main
review_url: https://github.com/lesserevil/oompah/pull/812
review_number: '812'
review_head: 00c1df8fa52f409d7249b870204cebb51b350039
merged_at: null
oompah.create_once:
  version: 1
  project_id: proj-14849f1b
  operation_kind: api_task_create
  creation_marker: restart-quality-gate-control-plane-hol-20260811
  request_fingerprint: 482c48aeb6292612f79b0753dd7f1ffca72997a6a0b26b9b9b97e64ee766532b
oompah.review_url: https://github.com/lesserevil/oompah/pull/812
oompah.review_number: '812'
oompah.work_branch: OOMPAH-1075
oompah.target_branch: main
oompah.review_head: 00c1df8fa52f409d7249b870204cebb51b350039
oompah.terminal_audit:
  queued_comment_posted: true
  oompah.terminal_audit_tracker_projections:
  - version: 1
    audit_id: audit-a600a072cf52
    project_id: proj-14849f1b
    task_id: OOMPAH-1075
    digest: d8e7b34a480fc806c23a0fb244242deb9abaa340af54de9c781cf4e200aa62c8
  - version: 1
    audit_id: audit-0432a06f3d32
    project_id: proj-14849f1b
    task_id: OOMPAH-1075
    digest: d8e7b34a480fc806c23a0fb244242deb9abaa340af54de9c781cf4e200aa62c8
  oompah.terminal_override_records:
  - version: 1
    override_id: override-3f2df10e876f
    project_id: proj-14849f1b
    task_id: OOMPAH-1075
    target_state: Merged
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: d8e7b34a480fc806c23a0fb244242deb9abaa340af54de9c781cf4e200aa62c8
    authorized_by:
      version: 1
      identity: oompah-cli
      source: api
    reason: 'Project-owner completion using exact protected delivery evidence. Final
      combined head d912a999d13d4fc739f4c14580b1facd94056382 is contained in protected
      PR #812 merge 4be80277a; Python 3.11/3.12/3.13 checks passed; independent exact-head
      review accepted the gate-lock, cache-authority, runtime-CAS, O1073 interaction,
      and deterministic heartbeat behavior; 481 affected tests plus repeated adversarial
      tests passed. The local gate covered earlier head 00c1df8fa, so a terminal full-suite
      rerun would be redundant.'
    created_at: '2026-08-11T10:41:11.763355+00:00'
    selected_ref: origin/OOMPAH-1075
    selected_sha: d912a999d13d4fc739f4c14580b1facd94056382
    applied: false
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-a600a072cf52
    project_id: proj-14849f1b
    task_id: OOMPAH-1075
    target_state: Done
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: d8e7b34a480fc806c23a0fb244242deb9abaa340af54de9c781cf4e200aa62c8
    attempts: []
    source_generation: 1
    requested_by:
      version: 1
      identity: NVShawn
      source: forge
    previous_state: In Review
    created_at: '2026-08-11T10:03:01.843740+00:00'
    selected_ref: origin/OOMPAH-1075
    selected_sha: d912a999d13d4fc739f4c14580b1facd94056382
  - version: 1
    audit_id: audit-0432a06f3d32
    project_id: proj-14849f1b
    task_id: OOMPAH-1075
    target_state: Merged
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: d8e7b34a480fc806c23a0fb244242deb9abaa340af54de9c781cf4e200aa62c8
    attempts: []
    source_generation: 1
    requested_by:
      version: 1
      identity: NVShawn
      source: forge
    previous_state: In Review
    created_at: '2026-08-11T10:03:01.843740+00:00'
    selected_ref: origin/OOMPAH-1075
    selected_sha: d912a999d13d4fc739f4c14580b1facd94056382
  attempt_history: []
---
## Summary

Triggered by: OOMPAH-1071

Live reproduction on deployed main aafbdac663 at 2026-08-11 08:58 UTC: opening draft PR #810 for exact OOMPAH-1071 head baa287e4 caused the server to run the configured branch quality gate synchronously inside the first post-restart orchestrator tick. The gate passed in 167.8s, but the tick took 137656ms, workflow liveness crossed its 120s reconstruction deadline into restart_overdue, terminal-audit scan/dispatch remained pending, /api/v1/state stayed on the stale pre-restart generation, and the UI showed a running-gate alert plus degraded health. When the gate completed, tracker authority had changed and the expensive publication was superseded, requiring another full reconcile. This is a control-plane head-of-line blocking bug, not a gate failure.\n\nImplementation scope: move standalone branch quality-gate execution and result waiting out of the orchestrator control tick into durable/independently scheduled work, or otherwise ensure the tick never awaits the external full-suite process. Preserve immutable exact-head snapshots, exact owner/generation cancellation, at-most-one gate per task/head, restart recovery, review adoption, and fail-closed result fencing. Liveness reconstruction and terminal-audit health/dispatch must continue while a multi-minute gate runs; tracker changes during the gate must not invalidate an unrelated liveness publication. Relevant code: standalone review/gate reconciliation in oompah/orchestrator.py, oompah/quality_gate.py, durable workflow scheduling/continuations, liveness reconstruction, and alert/state projection.\n\nRequired tests: deterministic barrier holding a real/fake gate beyond the restart deadline while repeated control ticks publish a complete fresh liveness snapshot, clear reconstruction_pending before deadline, scan/dispatch terminal audits, and keep HTTP/WebSocket generations advancing; concurrent tracker mutation supersedes only gate result authority, not liveness publication; restart recovers one exact gate without duplication; cancellation and task/head replacement remain fenced; active gate alert is informational and clears on completion; no request/control lock is held across the gate. Acceptance: a 3+ minute branch gate cannot make health restart_overdue or stall state generations, current divergence/action-required/exhausted stay zero, the gate outcome remains exact and durable, focused concurrency/restart tests pass, terminal mutation scan passes, and the full Makefile gate passes.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-11 09:23
---
Refined live diagnosis after a quiet-window reproduction: releasing the long exact-head quality gate from the task transition lock fixes one head-of-line blocker, but a second deterministic self-supersession remained. Read-only reconciliation/API proof paths call invalidate_read_cache() defensively; the native tracker incorrectly treated that refresh as a task mutation, advanced its publication authority, and notified server caches. An epic fact refresh therefore invalidated the same snapshot being built even when no task changed. The branch now separates read-only cache refresh from mutation invalidation, retains shared authority advancement/callbacks for every native write, and adds regression coverage proving refreshes do not advance state/publication generations while real writes do. It also closes the independent-review status-only race before any review capacity or metadata write.
---
author: oompah
created: 2026-08-11 09:28
---
Branch quality gate passed for `00c1df8fa52f409d7249b870204cebb51b350039` using `make test` in 170.3s. Review creation may proceed.
---
author: oompah
created: 2026-08-11 09:54
---
Final combined candidate is rebased onto deployed main 8496297f9 and pushed at exact head d912a999d13d4fc739f4c14580b1facd94056382. It includes the independently tracked OOMPAH-1077 deterministic heartbeat-test correction. Post-rebase focused validation: 481 workflow-worker/runtime/native-tracker/standalone tests passed; git diff check and worktree are clean. Independent exact-head review and protected matrix are running.
---
author: oompah
created: 2026-08-11 10:03
---
Queued for terminal transition to Merged. An auditor will review and apply the terminal status.
---
<!-- COMMENTS:END -->
