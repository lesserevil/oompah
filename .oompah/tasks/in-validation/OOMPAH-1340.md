---
id: OOMPAH-1340
type: bug
status: In Validation
priority: null
title: Task submit rejects generated helper paths that were deleted from the submitted
  head
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-25T18:29:09.896071Z'
updated_at: '2026-08-25T18:45:20.533935Z'
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
  creation_marker: 76403418-a933-4a65-a346-6e8e21f133c9
  request_fingerprint: 9cd737f3213b89d8a30fdb8825ab80b5f1344d939508805d2bb80cfd00b3a109
oompah.terminal_audit:
  queued_comment_posted: true
  oompah.terminal_audit_tracker_projections:
  - version: 1
    audit_id: audit-a08fa7910e1a
    project_id: proj-14849f1b
    task_id: OOMPAH-1340
    digest: c38b91cc5f8b575cda68843348eb959d4c9a249545034b5e0e78d6e31a64576e
  - version: 1
    audit_id: audit-a9d23f4f58f2
    project_id: proj-14849f1b
    task_id: OOMPAH-1340
    digest: c38b91cc5f8b575cda68843348eb959d4c9a249545034b5e0e78d6e31a64576e
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-a08fa7910e1a
    project_id: proj-14849f1b
    task_id: OOMPAH-1340
    target_state: Done
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: c38b91cc5f8b575cda68843348eb959d4c9a249545034b5e0e78d6e31a64576e
    attempts: []
    source_generation: 1
    requested_by:
      version: 1
      identity: NVShawn
      source: forge
    previous_state: Backlog
    created_at: '2026-08-25T18:45:13.020693+00:00'
    eligible_at: '2026-08-25T18:45:13.020693+00:00'
    selected_ref: origin/OOMPAH-1340
    selected_sha: c4d9c48eba5a2dfc282596debb2b5843ab50919b
  - version: 1
    audit_id: audit-a9d23f4f58f2
    project_id: proj-14849f1b
    task_id: OOMPAH-1340
    target_state: Merged
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: c38b91cc5f8b575cda68843348eb959d4c9a249545034b5e0e78d6e31a64576e
    attempts: []
    source_generation: 1
    requested_by:
      version: 1
      identity: NVShawn
      source: forge
    previous_state: Backlog
    created_at: '2026-08-25T18:45:13.020693+00:00'
    prerequisite_audit_id: audit-a08fa7910e1a
    selected_ref: origin/OOMPAH-1340
    selected_sha: c4d9c48eba5a2dfc282596debb2b5843ab50919b
  attempt_history: []
oompah.lifecycle_revision: 1
---
## Summary

### Problem
`oompah task submit` rejects a repaired task branch when an Oompah-generated helper was removed in the repair commit. Reproduced on TRICKLE-142: `.oompah-no-hooks/prepare-commit-msg` is absent from HEAD and the remote head, but submission still says it is present.

### Root cause
`task_cli._git_submission_evidence()` computes `changed_paths` with `git diff --name-only <merge-base>..HEAD`, which includes deleted paths. `server._submission_record()` rejects any changed path matching `is_generated_worktree_helper`, without distinguishing a file present in the submitted tree from a deletion. Therefore the required repair (`git rm`, commit, push) can never satisfy submission: the deletion itself remains in changed_paths and is rejected.

### Scope
Change submission evidence or server validation so only generated helper paths present in the submitted HEAD are rejected. Prefer emitting changed paths with a diff filter excluding deletions, while preserving all added/modified/renamed/copied paths used by submission fencing. Add defense-in-depth server validation if needed.

### Tests
- A branch adding/tracking `.oompah-no-hooks/prepare-commit-msg` is rejected.
- A branch deleting the helper from its base is accepted.
- Ordinary deleted source files do not corrupt changed-path evidence.

### Acceptance Criteria
- TRICKLE-142 clean head 2ee10c54b (helper absent from HEAD) can be submitted.
- Generated helpers present in HEAD remain rejected.
- Submission authority tests pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-25 18:45
---
Queued for terminal transition to Merged. An auditor will review and apply the terminal status.
---
<!-- COMMENTS:END -->
