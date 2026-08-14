---
id: OOMPAH-1255
type: task
status: In Validation
priority: null
title: Stamp native sibling scope before noncanonical rebase authority selection
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-13T18:13:35.579127Z'
updated_at: '2026-08-14T03:42:14.351322Z'
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
  creation_marker: cbca0849-a742-4e96-9196-41c398ed2525
  request_fingerprint: 9787e58516647b17cd2bb7f697947ea7aa802671f8dc89dd12f0f358a4da8aef
oompah.terminal_audit:
  queued_comment_posted: true
  oompah.terminal_audit_tracker_projections:
  - version: 1
    audit_id: audit-8f9db42cad50
    project_id: proj-14849f1b
    task_id: OOMPAH-1255
    digest: 009f4916dbca6a26974577789d55909c6de11318f1bb23a8ce6d300feddf19f4
  - version: 1
    audit_id: audit-0002fec1d997
    project_id: proj-14849f1b
    task_id: OOMPAH-1255
    digest: 009f4916dbca6a26974577789d55909c6de11318f1bb23a8ce6d300feddf19f4
  oompah.terminal_override_records:
  - version: 1
    override_id: override-90d4fe0a20ba
    project_id: proj-14849f1b
    task_id: OOMPAH-1255
    target_state: Merged
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 009f4916dbca6a26974577789d55909c6de11318f1bb23a8ce6d300feddf19f4
    authorized_by:
      version: 1
      identity: oompah-cli
      source: api
    reason: 'Project-owner terminal closure while Oompah scheduling remains intentionally
      paused: PR 873 head 24ae869d merged as 535bccdc; all Python 3.11, 3.12, and
      3.13 CI jobs passed; the merge is included in deployed main 948ef6f; queued
      terminal audits have zero attempts and no recorded error or unresolved review
      blocker.'
    created_at: '2026-08-14T03:42:11.309375+00:00'
    selected_ref: origin/OOMPAH-1255
    selected_sha: 24ae869d94a828afa9c13b5d9b15f86d8d995847
    applied: false
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-8f9db42cad50
    project_id: proj-14849f1b
    task_id: OOMPAH-1255
    target_state: Done
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 009f4916dbca6a26974577789d55909c6de11318f1bb23a8ce6d300feddf19f4
    attempts: []
    source_generation: 1
    requested_by:
      version: 1
      identity: NVShawn
      source: forge
    previous_state: Backlog
    created_at: '2026-08-13T18:30:28.101348+00:00'
    eligible_at: '2026-08-13T18:30:28.101348+00:00'
    selected_ref: origin/OOMPAH-1255
    selected_sha: 24ae869d94a828afa9c13b5d9b15f86d8d995847
  - version: 1
    audit_id: audit-0002fec1d997
    project_id: proj-14849f1b
    task_id: OOMPAH-1255
    target_state: Merged
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 009f4916dbca6a26974577789d55909c6de11318f1bb23a8ce6d300feddf19f4
    attempts: []
    source_generation: 1
    requested_by:
      version: 1
      identity: NVShawn
      source: forge
    previous_state: Backlog
    created_at: '2026-08-13T18:30:28.101348+00:00'
    prerequisite_audit_id: audit-8f9db42cad50
    selected_ref: origin/OOMPAH-1255
    selected_sha: 24ae869d94a828afa9c13b5d9b15f86d8d995847
  attempt_history: []
oompah.lifecycle_revision: 1
---
## Summary

Bug exposed live by TRICKLE-141 after OOMPAH-1253 deployed. publish_epic_rebase_candidate correctly resolves durable authority task_id=TRICKLE-141 and authoritative source branch TRICKLE-130, but _active_epic_rebase_siblings reloads native Markdown tasks whose Issue.project_id is unset. _is_epic_rebase_task therefore cannot consult the project-scoped durable authority, falls back to the canonical epic-TRICKLE-130 title convention, excludes the actual noncanonical helper, and publication falsely returns epic_rebase_duplicate_authority with an empty winner set. Scope: stamp the known epic/project identity on tracker-backed child and active-pool candidates before project-scoped classification/ownership checks, without accepting conflicting non-empty scope; cover native unscoped helper discovery, conflicting scope rejection, noncanonical source authority selection, and publisher success regression. Acceptance: the sole live helper named by durable authority remains the winner after native reload and TRICKLE-141 can publish its exact candidate through the server.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-13 18:22
---
Implementation is pushed in PR #873 (commit 24ae869d9). The fix restores tracker-known project scope on unstamped native sibling rows before authority classification and rejects conflicting scope. Verification: all 114 tests in tests/test_epic_rebase_state.py passed; make terminal-audit-scan passed; make check-secrets passed. Awaiting branch-gate CI.
---
author: oompah
created: 2026-08-13 18:30
---
Queued for terminal transition to Merged. An auditor will review and apply the terminal status.
---
author: oompah
created: 2026-08-13 18:52
---
Live acceptance passed after deployment at revision 535bccdcf: TRICKLE-141 published candidate b4add27840872ec39ea08bcb4c68895a4ff978db through the guarded server CAS path (published=true, recovered=false); origin/TRICKLE-130 now names that exact SHA; an independent Opus audit passed and advanced TRICKLE-141 to Done. The false duplicate-authority rejection is resolved.
---
<!-- COMMENTS:END -->
