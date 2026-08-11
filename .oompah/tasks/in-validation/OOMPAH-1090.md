---
id: OOMPAH-1090
type: bug
status: In Validation
priority: 1
title: Keep standalone delivery authority alive across long gates and terminal staging
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-11T14:26:47.067526Z'
updated_at: '2026-08-11T16:08:17.972589Z'
work_branch: OOMPAH-1090
target_branch: main
review_url: https://github.com/lesserevil/oompah/pull/825
review_number: '825'
review_head: 6703b97115b0b7aff922deab2ead89119bc1d486
merged_at: null
oompah.create_once:
  version: 1
  project_id: proj-14849f1b
  operation_kind: api_task_create
  creation_marker: standalone-delivery-long-effect-authority-20260811
  request_fingerprint: b6ba9251b85b875b51c6525abdd27dc17cfb827d712b3b17797b91d5087ce666
oompah.integration:
  version: 2
  state: ready
  attempts: 0
  mode: standalone
  task_branch: OOMPAH-1090
  base_branch: main
  base_sha: 6449341d762d9c7645271b8479dfa406e648be54
  head_sha: 6703b97115b0b7aff922deab2ead89119bc1d486
  submitted_at: '2026-08-11T15:14:35.883839+00:00'
  updated_at: '2026-08-11T15:39:50.437327+00:00'
oompah.work_branch: OOMPAH-1090
oompah.review_url: https://github.com/lesserevil/oompah/pull/825
oompah.review_number: '825'
oompah.target_branch: main
oompah.review_head: 6703b97115b0b7aff922deab2ead89119bc1d486
oompah.terminal_audit:
  queued_comment_posted: true
  oompah.terminal_audit_tracker_projections:
  - version: 1
    audit_id: audit-7b88cfff3a93
    project_id: proj-14849f1b
    task_id: OOMPAH-1090
    digest: f1dcbc7148b1ce4b91fd1c48148a4476eb358ca5ba2ce69d59109a8bcfbc9555
  - version: 1
    audit_id: audit-58b6f417d9a3
    project_id: proj-14849f1b
    task_id: OOMPAH-1090
    digest: f1dcbc7148b1ce4b91fd1c48148a4476eb358ca5ba2ce69d59109a8bcfbc9555
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-7b88cfff3a93
    project_id: proj-14849f1b
    task_id: OOMPAH-1090
    target_state: Done
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: f1dcbc7148b1ce4b91fd1c48148a4476eb358ca5ba2ce69d59109a8bcfbc9555
    attempts:
    - version: 1
      attempt_id: attempt-dc7c136ed75d
      target_state: Done
      request_state: in_progress
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: f1dcbc7148b1ce4b91fd1c48148a4476eb358ca5ba2ce69d59109a8bcfbc9555
      created_at: '2026-08-11T16:08:08.056772+00:00'
      provider_id: prov-651d553c
      model: haiku
      started_at: '2026-08-11T16:08:08.056772+00:00'
      branch_key: OOMPAH-1090
      selected_ref: 6703b97115b0b7aff922deab2ead89119bc1d486
      selected_sha: 6703b97115b0b7aff922deab2ead89119bc1d486
    source_generation: 1
    requested_by:
      version: 1
      identity: lesserevil
      source: forge
    previous_state: In Review
    created_at: '2026-08-11T16:00:47.346773+00:00'
    eligible_at: '2026-08-11T16:00:47.346773+00:00'
    selected_ref: 6703b97115b0b7aff922deab2ead89119bc1d486
    selected_sha: 6703b97115b0b7aff922deab2ead89119bc1d486
    updated_at: '2026-08-11T16:08:08.056772+00:00'
  - version: 1
    audit_id: audit-58b6f417d9a3
    project_id: proj-14849f1b
    task_id: OOMPAH-1090
    target_state: Merged
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: f1dcbc7148b1ce4b91fd1c48148a4476eb358ca5ba2ce69d59109a8bcfbc9555
    attempts: []
    source_generation: 1
    requested_by:
      version: 1
      identity: lesserevil
      source: forge
    previous_state: In Review
    created_at: '2026-08-11T16:00:47.346773+00:00'
    prerequisite_audit_id: audit-7b88cfff3a93
    selected_ref: 6703b97115b0b7aff922deab2ead89119bc1d486
    selected_sha: 6703b97115b0b7aff922deab2ead89119bc1d486
  attempt_history:
  - version: 1
    attempt_id: attempt-dc7c136ed75d
    target_state: Done
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: f1dcbc7148b1ce4b91fd1c48148a4476eb358ca5ba2ce69d59109a8bcfbc9555
    created_at: '2026-08-11T16:08:08.056772+00:00'
    provider_id: prov-651d553c
    model: haiku
    started_at: '2026-08-11T16:08:08.056772+00:00'
    branch_key: OOMPAH-1090
    selected_ref: 6703b97115b0b7aff922deab2ead89119bc1d486
    selected_sha: 6703b97115b0b7aff922deab2ead89119bc1d486
---
## Summary

Triggered by: OOMPAH-1084

Live incident: OOMPAH-1084 was exactly resubmitted at accepted merged head cf3578ff00f5564a06ea31650553dca337280427 after stale audit recovery. Its durable standalone_delivery job acquired a 30-second workflow lease, then ran the canonical exact branch gate for about 190 seconds. The gate passed, but workflow authority had been revoked before publication, so the pass was discarded as a superseded delivery and the job retried. The retry reused the exact cached pass, discovered merged PR 821, and entered terminal staging, but the synchronous bridge timed out after 15 seconds while the detached operation retained task ownership; the outer delivery then recorded superseded authority and the detached operation failed its later authority CAS. Scope: give long exact gates and terminal-transition staging a dedicated lease-renewed or durable continuation whose authority remains valid for the admitted exact task, branch, head, target, review, and evidence generation; ensure an outer bridge timeout cannot revoke a detached operation that still owns the exact generation; publish one current gate result and one terminal-stage intent; cancel promptly and discard late outcomes only when exact evidence truly changes; and recover deterministically across restart. Relevant areas include integration_workflow standalone_delivery effects, workflow lease heartbeat and interruption, standalone delivery authorities, BranchQualityGate callbacks/result publication, terminal staging bridge, detached operation ownership, and transition coordinator waits. Required tests: a gate longer than the workflow lease, terminal staging longer than the bridge timeout, interruption during each phase, concurrent replacement submission, restart during the continuation, and replay after cached pass must prove one current pass/stage, no duplicate full gate, no stale mutation, and bounded cancellation. Acceptance: a normal multi-minute make test cannot self-revoke its delivery job, detached exact terminal staging is not invalidated merely because a bridge wait expires, OOMPAH-1084-style recovery reaches exact terminal audit without exhausting retries, focused workflow/gate/transition tests and terminal mutation scan pass, and protected CI is green.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-11 14:27
---
Direct owner claimed from live OOMPAH-1084 recovery. Evidence: standalone_delivery workflow-job-05cb980d332b404abbdc4b30515eced9 admitted exact cf3578ff, the roughly 190-second canonical gate passed but its outcome was discarded after the short workflow authority expired, and the cached-pass retry then exceeded the 15-second terminal-staging bridge while its detached operation still owned the task. Worktree is prepared from deployed main 6a0f7210; implementation will preserve exact cancellation while separating admitted long effects from short outer waits.
---
author: oompah
created: 2026-08-11 14:34
---
Further live diagnosis: workflow lease heartbeats did renew every 10 seconds throughout the 176.7-second gate, so lease expiry was not the first revoker. Gate result publication performs a multi-second tracker/project/SCM preflight and then rejects if the tracker-wide publication revision changed; unrelated task mutations during that window can discard an otherwise exact same-task pass. After the cached pass, the synchronous terminal bridge returns false at its fixed 10-second timeout while the shielded coroutine continues. The workflow effect then schedules a retry and its local authority becomes false, so the detached operation later fails its exact tracker CAS; each replacement attempt repeats this loop. The fix must use task-scoped evidence rather than unrelated global revision churn for publication and must keep the admitted workflow generation alive until shielded terminal staging completes or is explicitly superseded.
---
author: oompah
created: 2026-08-11 14:47
---
Implemented the exact-authority repair in the task worktree. Gate publication now uses a bounded project mutation journal to accept only journal-proven changes to other tasks; same-task, active, unscoped, overflowed, or unreadable deltas still fail closed. The synchronous terminal bridge now treats its 10-second timeout as a liveness observation interval and retains the workflow owner until shielded exact staging settles, so retries cannot revoke their own in-flight tracker CAS. Added focused project-journal, external-tracker concurrency, same-task cancellation, and long terminal-staging ownership tests. Verification so far: 558 quality-gate/standalone/integration-workflow tests passed, 73 project-lock/provenance tests passed, and terminal mutation scan passed 21/21. Preparing final branch checks and commit; not submitted.
---
author: oompah
created: 2026-08-11 14:52
---
Implementation is committed and pushed at exact head 1cede601022304b70c36201a5b2b27fe8163148b on origin/OOMPAH-1090. Final focused verification: 632 affected quality-gate, standalone-delivery, integration-workflow, project-lock, and provenance tests passed; 28 adjacent workflow/tracker publication tests passed; 32 architecture/duplicate-name checks passed; terminal mutation scan passed 21/21; commit secret hooks passed. Exact behavior: completed changes to unrelated tasks no longer discard a current standalone gate result; gated-task and finish-dependency changes, active mutations, unscoped deltas, incomplete journals, and journal overflow still reject publication. Terminal bridge timeouts now report liveness while retaining the admitted workflow owner until exact staging settles. Branch is ready for independent review; intentionally not submitted or merged.
---
author: oompah
created: 2026-08-11 14:55
---
Rebased cleanly onto current origin/main exact fe9599111d478b8221a2949c878fecb61d558760 and pushed replacement exact head fc1220a984310449df12564fb66cbb5f24b92980 with an exact force-with-lease against prior 1cede601022304b70c36201a5b2b27fe8163148b. Canonical commit attribution is intact. Rebase verification: 632 affected quality-gate, standalone-delivery, integration-workflow, project-lock, and provenance tests passed; 28 adjacent workflow/tracker-publication tests passed; terminal mutation scan passed 21/21; diff check is clean. Branch is clean and synchronized with origin/OOMPAH-1090. Ready for independent review; intentionally not submitted or merged.
---
author: oompah
created: 2026-08-11 15:03
---
Fresh independent exact-head review ACCEPTED fc1220a984310449df12564fb66cbb5f24b92980 on current main fe9599111. Reviewer verified same-task and finish-dependency mutations reject; completed unrelated-task mutation publishes; active/unscoped/unknown/overflow deltas fail closed; final late-change CAS is serialized under project_write_lock; and the 10s terminal bridge interval retains workflow ownership through success, cancellation, and loop shutdown without holding the issue lock. Evidence: 682 changed-area/integration/workflow-worker tests passed, adversarial journal probes passed, terminal mutation scan 21/21, diff check clean. Ready for canonical branch gate and integration.
---
author: oompah
created: 2026-08-11 15:04
---
Preserve exact standalone-delivery authority across long gates and terminal staging; accept only journal-proven unrelated tracker churn while retaining fail-closed task/dependency boundaries.
---
author: oompah
created: 2026-08-11 15:14
---
After OOMPAH-1087 advanced main, rebased the independently ACCEPTED implementation onto current origin/main 6449341d762d9c7645271b8479dfa406e648be54 and pushed replacement exact head 6703b97115b0b7aff922deab2ead89119bc1d486. git range-diff proves the commit patch-equivalent to accepted fc1220a984310449df12564fb66cbb5f24b92980; post-rebase 443 focused quality-gate/standalone/project-lock tests passed, terminal mutation scan 21/21, diff check clean. Re-submitting the exact current-base head after the previous authority was correctly revoked by the main advance.
---
author: oompah
created: 2026-08-11 15:14
---
Preserve exact standalone-delivery authority across long gates and terminal staging on the current main base.
---
author: oompah
created: 2026-08-11 15:26
---
Branch quality gate passed for `6703b97115b0b7aff922deab2ead89119bc1d486` using `make test` in 177.5s. Review creation may proceed.
---
author: oompah
created: 2026-08-11 15:47
---
Branch quality gate passed for `6703b97115b0b7aff922deab2ead89119bc1d486` using `make test` in 179.0s. Review creation may proceed.
---
author: oompah
created: 2026-08-11 15:57
---
Branch quality gate passed for `6703b97115b0b7aff922deab2ead89119bc1d486` using `make test` in 180.8s. Review creation may proceed.
---
author: oompah
created: 2026-08-11 16:00
---
Queued for terminal transition to Merged. An auditor will review and apply the terminal status.
---
author: oompah
created: 2026-08-11 16:04
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/haiku)
---
author: oompah
created: 2026-08-11 16:04
---
Focus: Completion Auditor
---
author: oompah
created: 2026-08-11 16:04
---
Run #1 [attempt=1, profile=auditor, role=auditor -> Claude/haiku]
- Turns: 0, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: lifecycle_drain_before_launch, Duration: 16s
- Log: OOMPAH-1090__20260811T160417Z.jsonl
---
author: oompah
created: 2026-08-11 16:08
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/haiku)
---
author: oompah
created: 2026-08-11 16:08
---
Focus: Completion Auditor
---
<!-- COMMENTS:END -->
