---
id: OOMPAH-1260
type: task
status: In Validation
priority: null
title: Prevent recurring scheduler churn after superseded evidence revalidation
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-14T00:43:53.961262Z'
updated_at: '2026-08-14T01:48:41.340519Z'
work_branch: OOMPAH-1260
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.create_once:
  version: 1
  project_id: oompah
  operation_kind: api_task_create
  creation_marker: dd002099-ee31-4cf1-a637-09386bf4bc3d
  request_fingerprint: 8659dfa3f103dbd0aa12b6c34378cca3b4feee5d6e7337fa88ef20a251491586
oompah.lifecycle_revision: 2
oompah.integration:
  version: 2
  state: ready
  attempts: 0
  mode: standalone
  task_branch: OOMPAH-1260
  base_branch: main
  base_sha: eb61ed2adae7447952c31b30198849642f7a7ba6
  head_sha: 2cdb4eafb999baf7c329c585a01ea3618b235191
  submitted_at: '2026-08-14T01:29:33.421530+00:00'
  updated_at: '2026-08-14T01:29:33.421530+00:00'
oompah.work_branch: OOMPAH-1260
oompah.terminal_audit:
  queued_comment_posted: true
  oompah.terminal_audit_tracker_projections:
  - version: 1
    audit_id: audit-8762e515d125
    project_id: proj-14849f1b
    task_id: OOMPAH-1260
    digest: 566bbc72ccb601f9e7f9c42c0b2f321243cafa6284022c68dd0c248c86b4631e
  - version: 1
    audit_id: audit-ce4e9b2b5984
    project_id: proj-14849f1b
    task_id: OOMPAH-1260
    digest: 566bbc72ccb601f9e7f9c42c0b2f321243cafa6284022c68dd0c248c86b4631e
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-8762e515d125
    project_id: proj-14849f1b
    task_id: OOMPAH-1260
    target_state: Done
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 566bbc72ccb601f9e7f9c42c0b2f321243cafa6284022c68dd0c248c86b4631e
    attempts: []
    source_generation: 1
    requested_by:
      version: 1
      identity: NVShawn
      source: forge
    previous_state: Open
    created_at: '2026-08-14T01:40:35.710686+00:00'
    eligible_at: '2026-08-14T01:40:35.710686+00:00'
    selected_ref: 2cdb4eafb999baf7c329c585a01ea3618b235191
    selected_sha: 2cdb4eafb999baf7c329c585a01ea3618b235191
  - version: 1
    audit_id: audit-ce4e9b2b5984
    project_id: proj-14849f1b
    task_id: OOMPAH-1260
    target_state: Merged
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 566bbc72ccb601f9e7f9c42c0b2f321243cafa6284022c68dd0c248c86b4631e
    attempts: []
    source_generation: 1
    requested_by:
      version: 1
      identity: NVShawn
      source: forge
    previous_state: Open
    created_at: '2026-08-14T01:40:35.710686+00:00'
    prerequisite_audit_id: audit-8762e515d125
    selected_ref: 2cdb4eafb999baf7c329c585a01ea3618b235191
    selected_sha: 2cdb4eafb999baf7c329c585a01ea3618b235191
  attempt_history: []
---
## Summary

Bug exposed by live acceptance of OOMPAH-1259: a recurring managed child_landing_verification decision with stable decision/evidence revision (live reproducer TRICKLE-134) is activated on every ~30-second world cut. The queued job is claimed, then worker revalidation supersedes it with 'workflow evidence changed after job enqueue'; OOMPAH-1259 correctly rotates the dead Superseded generation immediately, but because the cause persists this becomes an unbounded enqueue/claim/supersede livelock rather than waiting until next_reassessment_at. Scope: identify and correct the mismatch between scheduler job/spec revision and worker evidence revalidation for recurring child landing verification, while preserving OOMPAH-1259 restart reconstruction convergence and protected event exclusivity. The scheduler must not rearm a stable same-evidence recurrence before its stated deadline merely because worker-side derived/spec data changed between cuts; genuine authoritative evidence changes must still supersede promptly. Add a production-shaped regression that executes the recurring job across multiple snapshots/restart, proves either useful completion or one deadline-fenced recurrence (no per-scan churn), and proves reconstruction required=materialized remains converged. Relevant context: workflow scheduler/store/runtime and epic child_landing_verification revalidation. Required tests include same evidence + changing snapshot/spec revision, true evidence change, protected event race, completed/cancelled/exhausted fences, and restart recovery. Acceptance: live TRICKLE-134 stops producing a new superseded job every scan, its current recurrence respects next_reassessment_at, worker admission stays open, and focused/full CI pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-14 00:44
---
Claimed for direct implementation from live post-deployment acceptance. Oompah remains paused; only Trickle remains resumed. Reproduced stable expected_evidence_revision with per-scan spec revisions, claim-time supersession, and immediate scheduler rotation creating a ~30-second livelock.
---
author: oompah
created: 2026-08-14 01:04
---
Root cause confirmed: same-generation recurring revalidation was terminally superseding the row, while immediate terminal recovery correctly rearmed it on every scan. Implemented an exact-deadline RETRY_WAIT handoff that restores the pre-effect attempt budget and remains active restart authority; genuine generation changes and non-recurring stale jobs still supersede. Store/worker/scheduler focused suite currently passes (205 tests). Adding the cross-component restart/churn regression before full gate and deployment. All projects remain temporarily paused for containment; only Trickle will be resumed after live acceptance.
---
author: oompah
created: 2026-08-14 01:29
---
Implementation committed and pushed as 2cdb4eafb999baf7c329c585a01ea3618b235191; PR #877 opened. Full Makefile gate passed: 20,369 passed, 7 skipped, 2 xfailed. Independent race review found no blockers.
---
author: oompah
created: 2026-08-14 01:29
---
Implemented exact-deadline durable deferral for same-generation recurring revalidation, with restart and multi-scan integration coverage; PR #877.
---
author: oompah
created: 2026-08-14 01:40
---
Queued for terminal transition to Merged. An auditor will review and apply the terminal status.
---
author: oompah
created: 2026-08-14 01:48
---
Live acceptance passed on deployed main 5a0ae9f886796123d6a7a1dd095f6b823fb4cd7f. After resuming only Trickle, TRICKLE-134 created one current recurring job at sequence 18858; worker revalidation moved it to retry_wait with attempts restored to 0 and retry_at 1786672861.54279. Across successive scheduler cuts the row count and max sequence remained stable, with no additional superseded generation. Restart reconstruction is complete, liveness published, admission remains open, and every project except Trickle remains paused.
---
author: oompah
created: 2026-08-14 01:48
---
Correction to the preceding live note: a later scheduler cut at 01:48:18 UTC invalidated acceptance. TRICKLE-134 advanced from 136 rows/max sequence 18858 to 138 rows/max sequence 18865 before retry_at 1786672861.54279, and the retry_wait row disappeared. Trickle is paused again for containment. OOMPAH-1260 remains In Validation while the second deadline-bypass/authority-rotation path is fixed.
---
<!-- COMMENTS:END -->
