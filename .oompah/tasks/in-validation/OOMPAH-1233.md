---
id: OOMPAH-1233
type: task
status: In Validation
priority: null
title: Recognize landed standalone submissions after source branch deletion
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-13T10:25:26.660518Z'
updated_at: '2026-08-13T10:47:09.861319Z'
work_branch: OOMPAH-1233
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.create_once:
  version: 1
  project_id: oompah
  operation_kind: api_task_create
  creation_marker: 6b34eecc-c88d-485e-86a2-e62b75d7493a
  request_fingerprint: aa782013cdbafb0b5c541f0295c2ecb65e5297e67b4c97a81dbdd9875bbac022
oompah.lifecycle_revision: 2
oompah.integration:
  version: 2
  state: ready
  attempts: 0
  mode: standalone
  task_branch: OOMPAH-1233
  head_sha: d93f9a2fe38c8237901b3589fca8550a63333cc8
  submitted_at: '2026-08-13T10:31:33.095227+00:00'
  updated_at: '2026-08-13T10:31:33.095227+00:00'
oompah.work_branch: OOMPAH-1233
oompah.terminal_audit:
  queued_comment_posted: true
  oompah.terminal_audit_tracker_projections:
  - version: 1
    audit_id: audit-fc08a1a3f68f
    project_id: proj-14849f1b
    task_id: OOMPAH-1233
    digest: eac24b5776ffc0a8b16c1ac77eb7b116efde8db1afc5fa39605cc3df8d59460c
  - version: 1
    audit_id: audit-1bb2efa68b22
    project_id: proj-14849f1b
    task_id: OOMPAH-1233
    digest: eac24b5776ffc0a8b16c1ac77eb7b116efde8db1afc5fa39605cc3df8d59460c
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-fc08a1a3f68f
    project_id: proj-14849f1b
    task_id: OOMPAH-1233
    target_state: Done
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: eac24b5776ffc0a8b16c1ac77eb7b116efde8db1afc5fa39605cc3df8d59460c
    attempts: []
    source_generation: 1
    requested_by:
      version: 1
      identity: NVShawn
      source: forge
    previous_state: Open
    created_at: '2026-08-13T10:46:58.431485+00:00'
    eligible_at: '2026-08-13T10:46:58.431485+00:00'
    selected_ref: d93f9a2fe38c8237901b3589fca8550a63333cc8
    selected_sha: d93f9a2fe38c8237901b3589fca8550a63333cc8
  - version: 1
    audit_id: audit-1bb2efa68b22
    project_id: proj-14849f1b
    task_id: OOMPAH-1233
    target_state: Merged
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: eac24b5776ffc0a8b16c1ac77eb7b116efde8db1afc5fa39605cc3df8d59460c
    attempts: []
    source_generation: 1
    requested_by:
      version: 1
      identity: NVShawn
      source: forge
    previous_state: Open
    created_at: '2026-08-13T10:46:58.431485+00:00'
    prerequisite_audit_id: audit-fc08a1a3f68f
    selected_ref: d93f9a2fe38c8237901b3589fca8550a63333cc8
    selected_sha: d93f9a2fe38c8237901b3589fca8550a63333cc8
  attempt_history: []
---
## Summary

Bug reproduced live on TRICKLE-140. A standalone task reached Ready to Integrate with accepted immutable head 6d089ed666372e2fe5a4c732e4da6dbfae68d3c4 already contained by the configured target branch, while the GitLab source branch had been deleted after merge. Standalone delivery checks get_branch_head_sha first, emits an actionable missing-branch alert, retries five times, and exhausts before invoking the existing immutable-head containment/no-op terminalization path. Implementation scope: when the accepted submission head is present but the source branch is absent, prove the exact accepted head against a freshly fetched configured target branch; if contained, persist canonical standalone integrated/no-op evidence and enter terminal audit without creating a review; if not contained or proof is unavailable, preserve the current fail-closed actionable missing-branch behavior. Fence every proof and tracker write with the exact standalone delivery authority/generation and do not infer containment from review state alone. Required tests: deleted source plus exact head contained terminalizes without forge review; deleted source plus head not contained alerts; target fetch/proof failure alerts; authority changes during containment cannot write; replay/restart is idempotent; unrelated missing branches retain current behavior. Acceptance: TRICKLE-140-shaped already-landed work cannot exhaust delivery solely because the forge deleted its source branch, while genuinely undelivered or ambiguous work remains blocked, and focused standalone delivery/workflow job tests plus the complete Makefile gate pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-13 10:26
---
Claimed directly by the operator agent while the Oompah project remains paused. Reproduced on TRICKLE-140: accepted head is already on target, but standalone delivery exhausts at the earlier source-branch existence check. Implementing on branch OOMPAH-1233 with exact-head containment and authority-fencing regressions.
---
author: oompah
created: 2026-08-13 10:31
---
Implemented exact accepted-head containment for forge-deleted standalone source branches. If the immutable accepted head is already contained by the freshly fetched target, Oompah persists canonical no-op integration evidence and stages the normal terminal audit without a review; negative/unavailable proofs retain the missing-branch alert. Added contained, uncontained, proof-unavailable, and authority-race regressions. Validation: 107 standalone delivery tests passed; 14 focused workflow/dispatch tests passed; terminal mutation scan and diff checks passed. Commit d93f9a2fe pushed.
---
author: oompah
created: 2026-08-13 10:47
---
Queued for terminal transition to Merged. An auditor will review and apply the terminal status.
---
<!-- COMMENTS:END -->
