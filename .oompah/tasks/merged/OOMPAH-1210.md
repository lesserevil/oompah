---
id: OOMPAH-1210
type: bug
status: Merged
priority: 1
title: Retire exhausted fact authority when imperative recovery takes over
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-13T03:23:09.049536Z'
updated_at: '2026-08-14T03:41:55.319459Z'
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
  creation_marker: implementation-cross-lane-exhaustion-retirement-v1
  request_fingerprint: 4d7141f1c88a1aeda0fb22cd95b74276f1ebabc5d622fc0c9f0286cb4e779208
oompah.terminal_audit:
  queued_comment_posted: true
  oompah.terminal_audit_tracker_projections:
  - version: 1
    audit_id: audit-d4c565ae09b1
    project_id: proj-14849f1b
    task_id: OOMPAH-1210
    digest: c2ad1fbb3e241350b571c7f5d5bbe7bd3675b600b50038e9210cdd3e6086a338
  - version: 1
    audit_id: audit-0bf822b502f2
    project_id: proj-14849f1b
    task_id: OOMPAH-1210
    digest: c2ad1fbb3e241350b571c7f5d5bbe7bd3675b600b50038e9210cdd3e6086a338
  oompah.terminal_override_records:
  - version: 1
    override_id: override-686839f046ff
    project_id: proj-14849f1b
    task_id: OOMPAH-1210
    target_state: Merged
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: c2ad1fbb3e241350b571c7f5d5bbe7bd3675b600b50038e9210cdd3e6086a338
    authorized_by:
      version: 1
      identity: oompah-cli
      source: api
    reason: 'Project-owner terminal closure while Oompah scheduling remains intentionally
      paused: PR 848 head b9db3a83 merged as 9401a3f7; all Python 3.11, 3.12, and
      3.13 CI jobs passed; the merge is included in deployed main 948ef6f; queued
      terminal audits have zero attempts and no recorded error or unresolved review
      blocker.'
    created_at: '2026-08-14T03:41:51.369525+00:00'
    selected_ref: origin/OOMPAH-1210
    selected_sha: b9db3a83a25ab9bdd9f58fca85e46128ae6734fe
    applied: false
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-d4c565ae09b1
    project_id: proj-14849f1b
    task_id: OOMPAH-1210
    target_state: Done
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: c2ad1fbb3e241350b571c7f5d5bbe7bd3675b600b50038e9210cdd3e6086a338
    attempts: []
    source_generation: 1
    requested_by:
      version: 1
      identity: NVShawn
      source: forge
    previous_state: Backlog
    created_at: '2026-08-13T03:42:20.595269+00:00'
    eligible_at: '2026-08-13T03:42:20.595269+00:00'
    selected_ref: origin/OOMPAH-1210
    selected_sha: b9db3a83a25ab9bdd9f58fca85e46128ae6734fe
  - version: 1
    audit_id: audit-0bf822b502f2
    project_id: proj-14849f1b
    task_id: OOMPAH-1210
    target_state: Merged
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: c2ad1fbb3e241350b571c7f5d5bbe7bd3675b600b50038e9210cdd3e6086a338
    attempts: []
    source_generation: 1
    requested_by:
      version: 1
      identity: NVShawn
      source: forge
    previous_state: Backlog
    created_at: '2026-08-13T03:42:20.595269+00:00'
    prerequisite_audit_id: audit-d4c565ae09b1
    selected_ref: origin/OOMPAH-1210
    selected_sha: b9db3a83a25ab9bdd9f58fca85e46128ae6734fe
  attempt_history: []
oompah.lifecycle_revision: 2
---
## Summary

Fix cross-lane exhaustion authority in the implementation workflow. An active event:implementation:imperative retry can supersede an exhausted event:implementation:fact generation under the shared implementation ordering namespace, but current_exhausted_jobs still treats the older fact row as authoritative because retirement only recognizes same-lane successors. The universal projection then reports retry.exhausted and blocks restart worker admission even though an exact queued imperative retry owns recovery (observed live on TRICKLE-118). Scope: record a durable event-handoff retirement when materialize_event atomically enqueues a successor that explicitly supersedes sibling lanes, and teach current-exhaustion proof to honor only that exact replacement authority; avoid retiring unrelated lanes. Relevant files: oompah/workflow_jobs.py, oompah/implementation_workflow.py if needed, and focused workflow store/controller/runtime tests. Acceptance: a queued imperative retry retires prior fact-lane exhaustion; if the retry itself exhausts it remains actionable; unrelated/different lanes cannot suppress exhaustion; restart liveness no longer projects stale retry.exhausted; focused tests and the project gate pass. After deployment, rearm or replay the exact live TRICKLE-118 retry through supported workflow authority so the in-flight task resumes.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-13 03:42
---
Queued for terminal transition to Merged. An auditor will review and apply the terminal status.
---
<!-- COMMENTS:END -->
