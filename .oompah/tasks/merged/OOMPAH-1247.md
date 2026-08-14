---
id: OOMPAH-1247
type: task
status: Merged
priority: null
title: Capture standalone submission base identity before review adoption
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-13T15:23:30.972748Z'
updated_at: '2026-08-14T07:42:08.220081Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.create_once:
  version: 1
  project_id: oompah
  operation_kind: api_task_create
  creation_marker: 044a45d0-2dc4-49fb-bbcf-383ced769abe
  request_fingerprint: efb813c451d9d465b70814c784f63f4a5b4b3cbea5a64143614946ff8ad68acd
oompah.lifecycle_revision: 3
oompah.terminal_audit:
  queued_comment_posted: true
  oompah.terminal_audit_tracker_projections:
  - version: 1
    audit_id: audit-6e33d7755ecf
    project_id: proj-14849f1b
    task_id: OOMPAH-1247
    digest: 0dd145e05f410094fda7c36299dfefb0c85151e32c16e6f1c01aeffafadaf559
  - version: 1
    audit_id: audit-adf8b00c0ba2
    project_id: proj-14849f1b
    task_id: OOMPAH-1247
    digest: 0dd145e05f410094fda7c36299dfefb0c85151e32c16e6f1c01aeffafadaf559
  oompah.terminal_override_records:
  - version: 1
    override_id: override-2c077a20b0ae
    project_id: proj-14849f1b
    task_id: OOMPAH-1247
    target_state: Merged
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 0dd145e05f410094fda7c36299dfefb0c85151e32c16e6f1c01aeffafadaf559
    authorized_by:
      version: 1
      identity: oompah-cli
      source: api
    reason: 'Owner convergence: PR #869 merged as 254291a69 and that landed tree is
      contained by origin/main; this stale non-terminal projection requires no further
      implementation.'
    created_at: '2026-08-14T07:42:04.375947+00:00'
    selected_ref: origin/OOMPAH-1247
    selected_sha: 34d90f4efde71aa784abf068fa040d3e4c068518
    applied: false
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-6e33d7755ecf
    project_id: proj-14849f1b
    task_id: OOMPAH-1247
    target_state: Done
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 0dd145e05f410094fda7c36299dfefb0c85151e32c16e6f1c01aeffafadaf559
    attempts: []
    source_generation: 1
    requested_by:
      version: 1
      identity: NVShawn
      source: forge
    previous_state: Open
    created_at: '2026-08-13T15:55:46.142863+00:00'
    eligible_at: '2026-08-13T15:55:46.142863+00:00'
    selected_ref: origin/OOMPAH-1247
    selected_sha: 34d90f4efde71aa784abf068fa040d3e4c068518
  - version: 1
    audit_id: audit-adf8b00c0ba2
    project_id: proj-14849f1b
    task_id: OOMPAH-1247
    target_state: Merged
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 0dd145e05f410094fda7c36299dfefb0c85151e32c16e6f1c01aeffafadaf559
    attempts: []
    source_generation: 1
    requested_by:
      version: 1
      identity: NVShawn
      source: forge
    previous_state: Open
    created_at: '2026-08-13T15:55:46.142863+00:00'
    prerequisite_audit_id: audit-6e33d7755ecf
    selected_ref: origin/OOMPAH-1247
    selected_sha: 34d90f4efde71aa784abf068fa040d3e4c068518
  attempt_history: []
---
## Summary

Bug: a standalone Ready-to-Integrate submission can persist integration v2 with head_sha but no base_sha (observed TRICKLE-122 at head 00d343bf, accepted 2026-08-13T15:16:50Z). GitLab MR !9 has complete exact diff_refs, but _standalone_review_matches_submission rejects it with the misleading message that the open review lacks exact head or base identity because expected_base is empty. Scope: trace validation submission/submit persistence and guarantee the accepted target branch base SHA is recorded for standalone submissions; fail closed before Ready if it cannot be captured; distinguish missing accepted-submission base evidence from missing forge MR evidence in diagnostics. Add regression tests covering submit-created records and exact GitLab MR adoption. Acceptance: a freshly submitted standalone task persists full head/base generation identity, MR !9-shaped evidence is accepted, legacy/incomplete records receive a bounded recovery path or precise actionable diagnosis, and focused workflow/integration tests pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-13 15:37
---
Implemented on PR #869. Root cause: top-level standalone submit omitted the project default target, so exact Git verification could not capture base_sha and later blamed a healthy GitLab MR. Added default-target capture, precise diagnostics, and regression coverage. Focused suite: 550 passed; hosted CI in progress.
---
author: oompah
created: 2026-08-13 15:55
---
Queued for terminal transition to Merged. An auditor will review and apply the terminal status.
---
<!-- COMMENTS:END -->
