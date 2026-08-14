---
id: OOMPAH-1260
type: task
status: Open
priority: null
title: Prevent recurring scheduler churn after superseded evidence revalidation
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-14T00:43:53.961262Z'
updated_at: '2026-08-14T01:29:42.793873Z'
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
oompah.lifecycle_revision: 1
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
<!-- COMMENTS:END -->
