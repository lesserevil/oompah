---
id: OOMPAH-1253
type: task
status: Merged
priority: null
title: Use authoritative nested epic source branch in rebase publication
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-13T17:17:20.003713Z'
updated_at: '2026-08-14T07:42:42.017710Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.create_once:
  version: 1
  project_id: proj-14849f1b
  operation_kind: api_task_create
  creation_marker: 6e9a3122-657b-49c8-9d6a-a03403fc29d7
  request_fingerprint: 9a265123bae3b1d83de177148e24c5f726c4024c399235059accbff9739687bb
oompah.terminal_audit:
  queued_comment_posted: true
  oompah.terminal_audit_tracker_projections:
  - version: 1
    audit_id: audit-1eb1b20d5792
    project_id: proj-14849f1b
    task_id: OOMPAH-1253
    digest: edf6a0d74512f0378777d1eb0f620bd838a354e7486d5ce3ece94d4555399e43
  - version: 1
    audit_id: audit-1305481d6502
    project_id: proj-14849f1b
    task_id: OOMPAH-1253
    digest: edf6a0d74512f0378777d1eb0f620bd838a354e7486d5ce3ece94d4555399e43
  oompah.terminal_override_records:
  - version: 1
    override_id: override-cdbf7053300f
    project_id: proj-14849f1b
    task_id: OOMPAH-1253
    target_state: Merged
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: edf6a0d74512f0378777d1eb0f620bd838a354e7486d5ce3ece94d4555399e43
    authorized_by:
      version: 1
      identity: oompah-cli
      source: api
    reason: 'Owner convergence: PR #872 merged as 4e457274d and that landed tree is
      contained by origin/main; this stale non-terminal projection requires no further
      implementation.'
    created_at: '2026-08-14T07:42:35.556043+00:00'
    selected_ref: origin/main
    selected_sha: 4e457274d4adedbd11def403bab6a28e8046e1bf
    applied: false
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-1eb1b20d5792
    project_id: proj-14849f1b
    task_id: OOMPAH-1253
    target_state: Done
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: edf6a0d74512f0378777d1eb0f620bd838a354e7486d5ce3ece94d4555399e43
    attempts: []
    source_generation: 1
    requested_by:
      version: 1
      identity: NVShawn
      source: forge
    previous_state: Backlog
    created_at: '2026-08-13T18:01:08.539974+00:00'
    eligible_at: '2026-08-13T18:01:08.539974+00:00'
    selected_ref: origin/main
    selected_sha: 4e457274d4adedbd11def403bab6a28e8046e1bf
  - version: 1
    audit_id: audit-1305481d6502
    project_id: proj-14849f1b
    task_id: OOMPAH-1253
    target_state: Merged
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: edf6a0d74512f0378777d1eb0f620bd838a354e7486d5ce3ece94d4555399e43
    attempts: []
    source_generation: 1
    requested_by:
      version: 1
      identity: NVShawn
      source: forge
    previous_state: Backlog
    created_at: '2026-08-13T18:01:08.539974+00:00'
    prerequisite_audit_id: audit-1eb1b20d5792
    selected_ref: origin/main
    selected_sha: 4e457274d4adedbd11def403bab6a28e8046e1bf
  attempt_history: []
oompah.lifecycle_revision: 2
---
## Summary

Bug: epic-rebase admission records authority against the parent epic's authoritative work_branch via _epic_branch_for_issue(), but publish_epic_rebase_candidate() and _epic_rebase_push_denial() recompute the source with project_store.epic_branch_name(). For nested Trickle epic TRICKLE-130, admission correctly leased remote TRICKLE-130 at 4493710568cd38feecde4778685bc93218db8117, while publication inspected epic-TRICKLE-130 at 7290eb7ac421f0f64bedd12000ac5aaa44dc18a6 and falsely returned epic_rebase_generation_stale. Scope: make all publication/push revalidation paths resolve the same authoritative epic source branch as admission, preserving exact generation/CAS checks. Add regression tests where an epic has work_branch different from canonical epic-<id>, proving publication observes and pushes the authoritative ref and rejects genuine changes. Run focused epic-rebase state tests plus terminal audit/secret scans. Acceptance: a scoped nested-epic helper with an unchanged leased work_branch can publish its exact candidate; wrong/stale refs remain fail-closed; TRICKLE-141 can publish candidate 734e24b8b2021511b01f329bc76bdb091817af89 after deployment.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-13 17:22
---
Direct operator implementation is pushed as PR #872 while the Oompah project remains paused. Root cause confirmed live: admission leased authoritative work_branch TRICKLE-130, but both server publisher and legacy push revalidation recomputed epic-TRICKLE-130. Fix uses _epic_branch_for_issue(parent) consistently. Regression coverage added for exact observed ref, force-with-lease ref, refspec, and shell-push revalidation. Focused file: 111 passed; terminal mutation scan and full secret scan passed.
---
author: oompah
created: 2026-08-13 17:36
---
Scope extended before merge after following the live path through completion: direct-maintenance completion and ProjectStore reconciliation also assumed epic-<id>. The fix now carries the validated authoritative branch through publisher, push revalidation, and post-publish worktree reconciliation. Full affected suites: 276 passed; terminal mutation and paranoid secret scans passed. PR #872 updated.
---
author: oompah
created: 2026-08-13 18:01
---
Queued for terminal transition to Merged. An auditor will review and apply the terminal status.
---
<!-- COMMENTS:END -->
