---
id: OOMPAH-1257
type: task
status: Merged
priority: null
title: Recognize noncanonical epic rebase helpers after terminal audit
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-13T18:57:41.903878Z'
updated_at: '2026-08-14T03:42:52.172855Z'
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
  creation_marker: d2d82af2-71ba-4073-8f80-0b564b096e86
  request_fingerprint: c1f4d6c1fe9df59e7d2246ebc306b734d3afe6f68b28501495e6d3f247715124
oompah.lifecycle_revision: 3
oompah.terminal_audit:
  queued_comment_posted: true
  oompah.terminal_audit_tracker_projections:
  - version: 1
    audit_id: audit-77c04096c667
    project_id: proj-14849f1b
    task_id: OOMPAH-1257
    digest: 3eb871a6638e2c13f9dd8629c0576974c33d71f13fd8ab157c187a3298c35e1a
  - version: 1
    audit_id: audit-f2d36ddb237f
    project_id: proj-14849f1b
    task_id: OOMPAH-1257
    digest: 3eb871a6638e2c13f9dd8629c0576974c33d71f13fd8ab157c187a3298c35e1a
  oompah.terminal_override_records:
  - version: 1
    override_id: override-3b3ed616d55f
    project_id: proj-14849f1b
    task_id: OOMPAH-1257
    target_state: Merged
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 3eb871a6638e2c13f9dd8629c0576974c33d71f13fd8ab157c187a3298c35e1a
    authorized_by:
      version: 1
      identity: oompah-cli
      source: api
    reason: 'Project-owner terminal closure while Oompah scheduling remains intentionally
      paused: PR 874 head 525c7a2e merged as c3e791d9; all Python 3.11, 3.12, and
      3.13 CI jobs passed; the merge is included in deployed main 948ef6f; queued
      terminal audits have zero attempts and no recorded error or unresolved review
      blocker.'
    created_at: '2026-08-14T03:42:34.390811+00:00'
    selected_ref: origin/OOMPAH-1257
    selected_sha: 525c7a2e09384a6b0b13f3020e81f70dd54c48a5
    applied: true
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-1257
    target_state: Merged
    evidence_fingerprint: 3eb871a6638e2c13f9dd8629c0576974c33d71f13fd8ab157c187a3298c35e1a
    workflow_revision: null
    selected_ref: origin/OOMPAH-1257
    selected_sha: 525c7a2e09384a6b0b13f3020e81f70dd54c48a5
    landing_revision: null
    audit_ids:
    - audit-77c04096c667
    - audit-f2d36ddb237f
    kind: override
    applied: true
    retired_at: '2026-08-14T03:42:45.838119+00:00'
  oompah.terminal_audit_result_intents: []
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-77c04096c667
    project_id: proj-14849f1b
    task_id: OOMPAH-1257
    target_state: Done
    request_state: cancelled
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 3eb871a6638e2c13f9dd8629c0576974c33d71f13fd8ab157c187a3298c35e1a
    attempts: []
    source_generation: 1
    requested_by:
      version: 1
      identity: NVShawn
      source: forge
    previous_state: Open
    created_at: '2026-08-13T22:29:25.785719+00:00'
    eligible_at: '2026-08-13T22:29:25.785719+00:00'
    selected_ref: origin/OOMPAH-1257
    selected_sha: 525c7a2e09384a6b0b13f3020e81f70dd54c48a5
    updated_at: '2026-08-14T03:42:45.838072+00:00'
  - version: 1
    audit_id: audit-f2d36ddb237f
    project_id: proj-14849f1b
    task_id: OOMPAH-1257
    target_state: Merged
    request_state: cancelled
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 3eb871a6638e2c13f9dd8629c0576974c33d71f13fd8ab157c187a3298c35e1a
    attempts: []
    source_generation: 1
    requested_by:
      version: 1
      identity: NVShawn
      source: forge
    previous_state: Open
    created_at: '2026-08-13T22:29:25.785719+00:00'
    prerequisite_audit_id: audit-77c04096c667
    selected_ref: origin/OOMPAH-1257
    selected_sha: 525c7a2e09384a6b0b13f3020e81f70dd54c48a5
    updated_at: '2026-08-14T03:42:45.838100+00:00'
  attempt_history: []
---
## Summary

Bug exposed live after OOMPAH-1255 allowed TRICKLE-141 to publish the persisted noncanonical TRICKLE-130 epic branch. The helper published candidate b4add27840872ec39ea08bcb4c68895a4ff978db and passed independent audit to Done, but integration.py:is_direct_epic_maintenance_issue still classifies only titles containing the convention-derived epic-<parent> name. Because TRICKLE-141 is titled "Rebase TRICKLE-130 onto epic-TRICKLE-127", downstream integration/rollup no longer recognizes it as direct epic maintenance, emits evidence.landing_missing, exhausts refresh retries, and leaves the parent rebase state/epic:rebasing label uncleared even though guarded publication is proven. Scope: replace convention-only downstream classification with explicit, project-scoped authoritative helper evidence (including persisted noncanonical epic branch) while retaining fail-closed rejection for ordinary title-shaped tasks and conflicting scope; ensure a successfully published/audited helper reaches the maintenance completion path instead of generic source-to-target landing. Relevant files: oompah/integration.py, integration/work-decision fact projection and epic rebase reconciliation paths. Tests must reproduce a noncanonical helper through publish -> audit Done -> parent rebase-state convergence, retain canonical helper compatibility, and reject spoofed/conflicting metadata. Acceptance: TRICKLE-141-like helpers do not emit evidence.landing_missing/retry.exhausted after audit; the parent exits rebasing based on exact guarded publication evidence; no direct Git push or manual task-ledger edit is required.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-13 21:47
---
Implementation in progress on branch OOMPAH-1257. Root cause confirmed: downstream title-only classification misses persisted noncanonical epic branches after exact publication/PASS. Fix projects project-scoped create/target/authority metadata into normalized issues, classifies fail-closed, makes audited Done maintenance terminal without an ordinary landing fact, converges the parent rebase state, and recovers pre-fix Done+ready records without a redundant audit. Focused regression suite currently passes (260 tests); wider workflow/terminal suites running.
---
author: oompah
created: 2026-08-13 21:55
---
Implementation pushed at 79c80fc2c and opened as PR #874. Focused regression suites (260 tests), wider workflow/terminal suites (904 tests), terminal-audit mutation scan, secret scan, and diff checks pass. Full make test gate is still running; merge and live recovery remain pending that gate and CI.
---
author: oompah
created: 2026-08-13 22:12
---
Independent exact-head review found two blockers before merge: incomplete GitLab project/parent/branch projection and a two-write crash window between parent REBASED state and target evidence. Both are fixed at updated head 609cec731: GitLab now canonicalizes parent identity and projects exact scope/branches; parent state+target now persist in one durable snapshot before label I/O, with existing target retained across transitions. New adapter and simulated-crash/restart regressions pass. Verification: 730 tracker tests, 638 workflow/audit tests, terminal scan 21/21. Fresh exact-head review and CI are running.
---
author: oompah
created: 2026-08-13 22:17
---
Second exact-head review found the post-persistence label-repair restart edge and ignored save failure. Fixed at 2d2d3d485: same-state recovery now reconciles stale labels, integration recovery re-enters only for proven integrated Done helpers whose parent label still needs repair, and a failed state snapshot aborts before labels/completion. Added simulated restart label repair, failed-save, direct-completion fail-closed, and integrated-checkpoint recovery tests. Combined focused suite: 1,371 passed; direct changed-path set: 386 passed; terminal scan and secret scan pass. Final exact-head review and CI are running.
---
author: oompah
created: 2026-08-13 22:29
---
Queued for terminal transition to Merged. An auditor will review and apply the terminal status.
---
author: oompah
created: 2026-08-14 03:42
---
Override by oompah-cli: terminal transition to Merged applied by project owner.

Reason: Project-owner terminal closure while Oompah scheduling remains intentionally paused: PR 874 head 525c7a2e merged as c3e791d9; all Python 3.11, 3.12, and 3.13 CI jobs passed; the merge is included in deployed main 948ef6f; queued terminal audits have zero attempts and no recorded error or unresolved review blocker.
---
author: oompah
created: 2026-08-14 03:42
---
Merged and deployed through PR 874; owner-verified terminal evidence replaces the intentionally unrun paused-project auditor.
---
<!-- COMMENTS:END -->
