---
id: OOMPAH-1264
type: feature
status: Done
priority: 1
title: Resolve external prerequisites with exact CAS and one fresh generation
parent: OOMPAH-1231
children: []
blocked_by: []
start_blocked_by: &id001
- OOMPAH-1262
labels: []
assignee: null
created_at: '2026-08-14T02:39:54.222347Z'
updated_at: '2026-08-14T07:33:42.553977Z'
work_branch: OOMPAH-1264
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.create_once:
  version: 1
  project_id: oompah
  operation_kind: api_task_create
  creation_marker: oompah-1231-resolution-cas-v1
  request_fingerprint: 1f4866dfd9890e09cbc705a0030d9bf030cc49ba6b22639e33bb93bbf52f65e5
oompah.start_blocked_by: *id001
oompah.lifecycle_revision: 3
oompah.integration:
  version: 2
  state: ready
  attempts: 0
  mode: queue
  task_branch: OOMPAH-1264
  base_branch: epic-OOMPAH-1231
  base_sha: ae57ba61bae24db3f17f390b1b5ace43f313c23d
  head_sha: 038e10c2de1f1515ea19e7a63dbc2d3745137407
  submitted_at: '2026-08-14T07:32:37.869357+00:00'
  updated_at: '2026-08-14T07:32:37.869357+00:00'
oompah.work_branch: OOMPAH-1264
oompah.terminal_audit:
  queued_comment_posted: true
  oompah.terminal_audit_tracker_projections:
  - version: 1
    audit_id: audit-30ff280f670a
    project_id: proj-14849f1b
    task_id: OOMPAH-1264
    digest: 49a50d8320e9eca5362acb0860974cf6158c97cf27e203b7f938153b0c624c74
  oompah.terminal_override_records:
  - version: 1
    override_id: override-169824cc83ad
    project_id: proj-14849f1b
    task_id: OOMPAH-1264
    target_state: Done
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 49a50d8320e9eca5362acb0860974cf6158c97cf27e203b7f938153b0c624c74
    authorized_by:
      version: 1
      identity: oompah-cli
      source: api
    reason: 'Owner convergence for paused direct work: PR #881 merged exact reviewed
      head 038e10c2 into epic-OOMPAH-1231 as 2ff3966dd; hosted CI passed Python 3.11/3.12/3.13,
      local full gate passed 20,568 tests, independent review signed off, and exact
      tree equality is proven.'
    created_at: '2026-08-14T07:33:33.542854+00:00'
    selected_ref: 038e10c2de1f1515ea19e7a63dbc2d3745137407
    selected_sha: 038e10c2de1f1515ea19e7a63dbc2d3745137407
    applied: true
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-1264
    target_state: Done
    evidence_fingerprint: 49a50d8320e9eca5362acb0860974cf6158c97cf27e203b7f938153b0c624c74
    workflow_revision: null
    selected_ref: 038e10c2de1f1515ea19e7a63dbc2d3745137407
    selected_sha: 038e10c2de1f1515ea19e7a63dbc2d3745137407
    landing_revision: null
    audit_ids:
    - audit-30ff280f670a
    kind: override
    applied: true
    retired_at: '2026-08-14T07:33:41.412578+00:00'
  oompah.terminal_audit_result_intents: []
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-30ff280f670a
    project_id: proj-14849f1b
    task_id: OOMPAH-1264
    target_state: Done
    request_state: cancelled
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 49a50d8320e9eca5362acb0860974cf6158c97cf27e203b7f938153b0c624c74
    attempts: []
    source_generation: 1
    requested_by:
      version: 1
      identity: NVShawn
      source: forge
    previous_state: Open
    created_at: '2026-08-14T07:33:08.996014+00:00'
    eligible_at: '2026-08-14T07:33:08.996014+00:00'
    selected_ref: 038e10c2de1f1515ea19e7a63dbc2d3745137407
    selected_sha: 038e10c2de1f1515ea19e7a63dbc2d3745137407
    updated_at: '2026-08-14T07:33:41.412541+00:00'
  attempt_history: []
---
## Summary

Add a project-owner authenticated prerequisite-resolution API and task CLI operation using exact blocker ID plus task authority revision/generation compare-and-swap. Resolution must be idempotent, reject stale blocker/run identities, preserve structured continuation evidence (work branch, exact head, review and pipeline identity), and create exactly one fresh workflow generation instead of rearming old exhausted rows. Support task-qualified cross-project triggers, profile-capability triggers, and named operator actions without allowing status toggles merely to wake work. Reuse existing owner-resolution authentication and transition journal patterns. Required tests: authorization, malformed/cross-scope input, exact CAS, concurrent replacement, idempotent replay, atomic owner/job/status publication, dependency/profile resolution, and TRICKLE-143-shaped continuation resuming review/CI instead of generic implementation. Acceptance: resolving the named prerequisite naturally resumes the correct phase once, while stale or duplicate resolution cannot mutate current work.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-14 03:55
---
Claimed for direct implementation in /home/shedwards/src/oompah-1264 on branch OOMPAH-1264, based on integrated prerequisite bf53cfb7a35c8c9773557712b55cbe09d5de6ef6 from epic-OOMPAH-1231. Oompah remains paused.
---
author: oompah
created: 2026-08-14 04:09
---
Implementation checkpoint: immutable project-owner resolution receipt and exact blocker/run/task-authority CAS are committed locally at 587aab590a7d352c988f35c7cbdf3a80c40c37e2. Lost-response idempotency, conflicting/stale/malformed authority, exact continuation evidence, and native/GitHub/GitLab projections pass 64 focused tests. Distinct resolution-lane workflow and authenticated API/CLI slices are in progress.
---
author: oompah
created: 2026-08-14 04:36
---
Frozen clean local stack at 342696588b65fc9640312430496147e5f2907e20 (8 task commits) after integrating the owner API/CLI. Final combined suite passes 1,137 tests with two pre-existing warnings. Final admission re-reads task/profile trigger truth and exact live review/pipeline identity under ordered locks; same-project and non-reentrant lock cases are covered. Awaiting OOMPAH-1263 epic integration before rebase/push.
---
author: oompah
created: 2026-08-14 04:55
---
Rebased exact prerequisite-resolution and fresh-continuation implementation onto landed OOMPAH-1263 parking authority at ae57ba61bae24db3f17f390b1b5ace43f313c23d. Conflict resolution preserves the distinct implementation_park and implementation-prerequisite-resolution lanes. Joint conflict-sensitive verification passes 1,796 tests; branch is clean at a1dd8c9633f747886196dc2fe63f0b79c1b02a1d and is being published for hosted CI.
---
author: oompah
created: 2026-08-14 07:00
---
Final reviewed head 038e10c2de1f1515ea19e7a63dbc2d3745137407 is frozen clean. Independent blocking review signed off after exact CAS/lifecycle/provider/integration/profile race corrections. Authoritative plain make test: 20,568 passed, 7 skipped, 2 xfailed, zero failures in 22m34s; terminal mutation scan 21/21 passed. Publishing PR 881 update for supported-Python hosted CI.
---
author: oompah
created: 2026-08-14 07:32
---
Implemented exact owner-authenticated prerequisite resolution with blocker/run/task-authority CAS, idempotent receipts, one fresh continuation generation, profile/dependency/operator triggers, and stale provider/review/integration fencing. Independent review signed off exact head 038e10c2; full local gate passed 20,568 tests plus 21/21 mutation scan, and hosted CI passed Python 3.11, 3.12, and 3.13.
---
author: oompah
created: 2026-08-14 07:33
---
Queued for terminal transition to Done. An auditor will review and apply the terminal status.
---
author: oompah
created: 2026-08-14 07:33
---
Override by oompah-cli: terminal transition to Done applied by project owner.

Reason: Owner convergence for paused direct work: PR #881 merged exact reviewed head 038e10c2 into epic-OOMPAH-1231 as 2ff3966dd; hosted CI passed Python 3.11/3.12/3.13, local full gate passed 20,568 tests, independent review signed off, and exact tree equality is proven.
---
<!-- COMMENTS:END -->
