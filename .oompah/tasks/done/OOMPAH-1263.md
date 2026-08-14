---
id: OOMPAH-1263
type: bug
status: Done
priority: 1
title: Park external blockers and retire every stale durable lane
parent: OOMPAH-1231
children: []
blocked_by: []
start_blocked_by: &id001
- OOMPAH-1262
labels: []
assignee: null
created_at: '2026-08-14T02:39:37.692542Z'
updated_at: '2026-08-14T04:53:40.457800Z'
work_branch: OOMPAH-1263
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.create_once:
  version: 1
  project_id: oompah
  operation_kind: api_task_create
  creation_marker: oompah-1231-park-retirement-v1
  request_fingerprint: 98432ed9fc5b6f6b2f2c9c65ea49a82baf69aba3719cebb46325f1817bfe1024
oompah.start_blocked_by: *id001
oompah.lifecycle_revision: 3
oompah.terminal_audit:
  queued_comment_posted: true
  oompah.terminal_audit_tracker_projections:
  - version: 1
    audit_id: audit-2e91e427a457
    project_id: proj-14849f1b
    task_id: OOMPAH-1263
    digest: ec9ccef497f001bd8aee3f8893969a73d67c26899de61e5f59e875c48ecd3884
  - version: 1
    audit_id: audit-93416b9e3515
    project_id: proj-14849f1b
    task_id: OOMPAH-1263
    digest: 6a2a797a5eb2d6a4eb9f9ce6b729d1c2c1f73357d271bb5e212e6c70357d5d33
  oompah.terminal_override_records:
  - version: 1
    override_id: override-a1405a25a540
    project_id: proj-14849f1b
    task_id: OOMPAH-1263
    target_state: Done
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 6a2a797a5eb2d6a4eb9f9ce6b729d1c2c1f73357d271bb5e212e6c70357d5d33
    authorized_by:
      version: 1
      identity: oompah-cli
      source: api
    reason: Project-owner recovery after a post-merge submission changed the auditable
      integration projection; PR 880 is merged into epic-OOMPAH-1231, the landed tree
      equals reviewed head 987c46cb8075073aac18a09c140eafe9526190fd, and GitHub Actions
      run 31770033759 passed all supported Python versions.
    created_at: '2026-08-14T04:53:31.814697+00:00'
    selected_ref: 987c46cb8075073aac18a09c140eafe9526190fd
    selected_sha: 987c46cb8075073aac18a09c140eafe9526190fd
    applied: true
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-1263
    target_state: Done
    evidence_fingerprint: 6a2a797a5eb2d6a4eb9f9ce6b729d1c2c1f73357d271bb5e212e6c70357d5d33
    workflow_revision: null
    selected_ref: 987c46cb8075073aac18a09c140eafe9526190fd
    selected_sha: 987c46cb8075073aac18a09c140eafe9526190fd
    landing_revision: null
    audit_ids:
    - audit-2e91e427a457
    - audit-93416b9e3515
    kind: override
    applied: true
    retired_at: '2026-08-14T04:53:39.269113+00:00'
  oompah.terminal_audit_result_intents: []
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-2e91e427a457
    project_id: proj-14849f1b
    task_id: OOMPAH-1263
    target_state: Done
    request_state: superseded
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: ec9ccef497f001bd8aee3f8893969a73d67c26899de61e5f59e875c48ecd3884
    attempts: []
    source_generation: 1
    requested_by:
      version: 1
      identity: NVShawn
      source: forge
    previous_state: Open
    created_at: '2026-08-14T04:46:48.047549+00:00'
    eligible_at: '2026-08-14T04:46:48.047549+00:00'
    selected_ref: origin/OOMPAH-1263
    selected_sha: 987c46cb8075073aac18a09c140eafe9526190fd
  - version: 1
    audit_id: audit-93416b9e3515
    project_id: proj-14849f1b
    task_id: OOMPAH-1263
    target_state: Done
    request_state: cancelled
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 6a2a797a5eb2d6a4eb9f9ce6b729d1c2c1f73357d271bb5e212e6c70357d5d33
    attempts: []
    source_generation: 2
    requested_by:
      version: 1
      identity: oompah-cli
      source: api
    previous_state: In Validation
    created_at: '2026-08-14T04:53:24.952732+00:00'
    eligible_at: '2026-08-14T04:53:24.952732+00:00'
    selected_ref: 987c46cb8075073aac18a09c140eafe9526190fd
    selected_sha: 987c46cb8075073aac18a09c140eafe9526190fd
    updated_at: '2026-08-14T04:53:39.269076+00:00'
  attempt_history: []
oompah.integration:
  version: 2
  state: ready
  attempts: 0
  mode: queue
  task_branch: OOMPAH-1263
  base_branch: epic-OOMPAH-1231
  base_sha: bf53cfb7a35c8c9773557712b55cbe09d5de6ef6
  head_sha: 987c46cb8075073aac18a09c140eafe9526190fd
  submitted_at: '2026-08-14T04:47:44.958735+00:00'
  updated_at: '2026-08-14T04:47:44.958735+00:00'
oompah.work_branch: OOMPAH-1263
---
## Summary

Consume exact structured prerequisite authority to publish a stable jobless work decision and an accepted managed zero-job authority cut. Atomically retire the outgoing owner/run and supersede or cancel every task-scoped durable lane that must not outlive the park, including current exhausted implementation or standalone delivery and overdue nested-dispatch topology repair. Project unresolved task dependencies as non-alerting Blocked decisions with named prerequisites; reserve Action Required warnings for genuine operator-only or unavailable-platform triggers. Preserve accepted-submission precedence and fail closed across crash/restart. Relevant areas: workflow decisions/controllers/scheduler store, implementation worker-exit adapter, authority revocation, nested topology recovery, liveness projection. Required regressions: TRICKLE-132 current exhausted standalone row retires, TRICKLE-139 retry-wait auxiliary row cannot run after park, repeated ticks/restart remain zero-job, current replacement authority wins races, and ordinary focus handoffs still progress. Acceptance: a parked task has no live owner, claimable/retryable/exhausted current job, false global warning, or restart redispatch.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-14 03:17
---
Live regression reproduced during the 948ef6f restart: TRICKLE-138 and TRICKLE-139 had current jobless Needs Human decisions, but unmanaged nested_dispatch_topology_repair rows survived and TRICKLE-138 advanced from attempt 3 to 5. Exact rows 18391/18392 were safely cancelled by generation CAS while Trickle was paused, then verified terminal with retry_at cleared. Scope must explicitly retire stale auxiliary/unmanaged lanes such as nested-dispatch-topology when current structured prerequisite or zero-job authority parks the task; authority_revocation currently covers implementation ownership only and is insufficient. Add restart/reclaim regressions for this exact shape.
---
author: oompah
created: 2026-08-14 03:55
---
Claimed for direct implementation in /home/shedwards/src/oompah-1263 on branch OOMPAH-1263, based on integrated prerequisite bf53cfb7a35c8c9773557712b55cbe09d5de6ef6 from epic-OOMPAH-1231. Oompah remains paused.
---
author: oompah
created: 2026-08-14 04:09
---
Implementation checkpoint: exact managed zero-job lane retirement and publication rollback/restart fencing are implemented; six focused store regressions pass. Decision classification now keeps dependency waits quiet, retains real operator/platform warnings, gives accepted submissions precedence, and schedules exact outgoing-source revocation before parking. Nested topology final-lease fencing and runtime race coverage are in progress in parallel.
---
author: oompah
created: 2026-08-14 04:26
---
Implemented stable structured prerequisite parking: exact blocked prerequisites now classify dependency waits as non-alerting Blocked and capability/operator failures as Action Required warnings; accepted submissions and current replacement generations retain precedence. Zero-job park cuts durably retire managed implementation work plus exact fact, imperative, and nested-repair event lanes while preserving the prerequisite-resolution lane. Added outgoing-run revocation and nested-repair mutation fencing, fail-closed publication rollback, restart/current-replacement behavior, and same-task tracker-drift retry protection. Focused consolidated verification: 789 passed across workflow runtime, store, scheduler/controller, decision, adapter, duplicate-preflight, implementation workflow, and nested topology suites. Branch remains local and unsubmitted for parent integration.
---
author: oompah
created: 2026-08-14 04:28
---
Frozen branch pushed at exact head 987c46cb8075073aac18a09c140eafe9526190fd in PR 880 targeting epic-OOMPAH-1231. Focused verification passes 789 tests and diff check is clean. Auto-merge is intentionally disabled until GitHub CI completes.
---
author: oompah
created: 2026-08-14 04:46
---
Queued for terminal transition to Done. An auditor will review and apply the terminal status.
---
author: oompah
created: 2026-08-14 04:47
---
Terminal evidence: PR 880 merged into epic-OOMPAH-1231 as ae57ba61bae24db3f17f390b1b5ace43f313c23d. Its tree exactly equals reviewed head 987c46cb8075073aac18a09c140eafe9526190fd. GitHub Actions run 31770033759 passed on Python 3.11, 3.12, and 3.13; 789 focused tests passed locally.
---
author: oompah
created: 2026-08-14 04:48
---
Completed durable prerequisite parking and exact stale-lane retirement in PR 880; all focused and three-version CI gates passed.
---
author: oompah
created: 2026-08-14 04:53
---
Override by oompah-cli: terminal transition to Done applied by project owner.

Reason: Project-owner recovery after a post-merge submission changed the auditable integration projection; PR 880 is merged into epic-OOMPAH-1231, the landed tree equals reviewed head 987c46cb8075073aac18a09c140eafe9526190fd, and GitHub Actions run 31770033759 passed all supported Python versions.
---
<!-- COMMENTS:END -->
