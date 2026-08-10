---
id: OOMPAH-980
type: bug
status: In Validation
priority: 1
title: Reuse authoritative full branch gates in terminal audits
parent: OOMPAH-940
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-10T01:42:03.823626Z'
updated_at: '2026-08-10T02:33:53.810596Z'
work_branch: OOMPAH-980
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.integration:
  version: 2
  state: blocked
  attempts: 1
  mode: queue
  task_branch: OOMPAH-980
  base_branch: epic-OOMPAH-940
  base_sha: 2dd74be288b81265ea4a242d7467ecc1ed9f1435
  head_sha: 10f586bbcdd87287f486906840e4a5405de4bddd
  submitted_at: '2026-08-10T02:22:46.589167+00:00'
  last_error: automatic rebase could not prove that the rewritten head preserves every
    accepted submission change; rebase the private branch explicitly and submit the
    resulting exact head
oompah.work_branch: OOMPAH-980
oompah.terminal_audit:
  queued_comment_posted: true
  oompah.terminal_audit_tracker_projections:
  - version: 1
    audit_id: audit-cd3df7f6baa7
    project_id: proj-14849f1b
    task_id: OOMPAH-980
    digest: 3e8483858cb6678a11d1ad45db692f279d49ed26910557e96c6f56631b4c52a4
  - version: 1
    audit_id: audit-aca2a9199109
    project_id: proj-14849f1b
    task_id: OOMPAH-980
    digest: 3e8483858cb6678a11d1ad45db692f279d49ed26910557e96c6f56631b4c52a4
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-cd3df7f6baa7
    project_id: proj-14849f1b
    task_id: OOMPAH-980
    target_state: Done
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 3e8483858cb6678a11d1ad45db692f279d49ed26910557e96c6f56631b4c52a4
    attempts: []
    source_generation: 1
    requested_by:
      version: 1
      identity: NVShawn
      source: forge
    previous_state: Needs Rebase
    created_at: '2026-08-10T02:33:48.003361+00:00'
    selected_ref: 10f586bbcdd87287f486906840e4a5405de4bddd
    selected_sha: 10f586bbcdd87287f486906840e4a5405de4bddd
  - version: 1
    audit_id: audit-aca2a9199109
    project_id: proj-14849f1b
    task_id: OOMPAH-980
    target_state: Merged
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 3e8483858cb6678a11d1ad45db692f279d49ed26910557e96c6f56631b4c52a4
    attempts: []
    source_generation: 1
    requested_by:
      version: 1
      identity: NVShawn
      source: forge
    previous_state: Needs Rebase
    created_at: '2026-08-10T02:33:48.003361+00:00'
    selected_ref: 10f586bbcdd87287f486906840e4a5405de4bddd
    selected_sha: 10f586bbcdd87287f486906840e4a5405de4bddd
  attempt_history: []
---
## Summary

Triggered by OOMPAH-979. Its exact branch head 7fc8bc8ea4a36c952a96349406a173c6b85ec94e had an authoritative full make test result recorded before review, but terminal audit authority treated the gate as incomplete and launched another full test run. Under the outer auditor validation environment, that redundant run also classified two ordinary native test lifecycles as opaque instead of full. Scope: reproduce the OOMPAH-979 branch-gate-to-terminal-audit path end to end; identify and fix the exact-head authority propagation or compatibility gap so a current compatible full gate is reused before any auditor process launch; add a native guard regression proving ordinary make test lifecycle telemetry stays full beneath an outer auditor guard without weakening hostile or leading-assignment fail-closed classification. Relevant context includes orchestrator exact-gate authority and audit launch policy, api_agent gate enforcement, validation_resource_lease, native validation guard and ACP lifecycle plumbing. Required tests: focused unit and integration regressions for compatible gate reuse, stale or incompatible rejection, no redundant auditor launch, nested native scope classification, and preserved opaque fail-closed cases. Acceptance: an OOMPAH-979-shaped exact-head full gate is reused rather than rerun; nested ordinary lifecycle scope remains full; no broad environment sanitization is introduced; focused tests and the complete project gate pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-10 01:42
---
Claimed for direct-owner completion. Reproducing the exact OOMPAH-979 gate-authority and nested native lifecycle path on current main before changing production code.
---
author: oompah
created: 2026-08-10 01:54
---
Reproduction complete. OOMPAH-979 had durable exact-head make test evidence and review_head 7fc8bc8e, but terminal audit identity ignored review_head and therefore never queried the gate store. Separately, the Make-launched service leaked MAKEFLAGS and MFLAGS into auditor environments, making the fail-closed classifier report ordinary make test as opaque. The fix now uses canonical exact-head resolution for audit evidence and strips only inherited Make control variables at the agent boundary; the classifier remains fail closed for command-supplied controls. Focused verification: 290 affected gate, auth, API lifecycle, and native Codex tests passed.
---
author: oompah
created: 2026-08-10 02:22
---
Implementation complete at exact pushed head 10f586bbcdd87287f486906840e4a5405de4bddd. Independent review approved with no blockers. Verification: 310 affected tests passed; complete make test passed with 19,279 passed, 7 skipped, 2 expected failures, zero failures in 1246.99 seconds; terminal mutation scan, diff check, commit hooks, and secret scan passed.
---
author: oompah
created: 2026-08-10 02:23
---
Canonical review heads now reuse durable exact gate evidence, and inherited Make control channels are removed at the agent boundary while explicit hostile controls remain fail closed.
---
author: oompah
created: 2026-08-10 02:33
---
Queued for terminal transition to Merged. An auditor will review and apply the terminal status.
---
<!-- COMMENTS:END -->
