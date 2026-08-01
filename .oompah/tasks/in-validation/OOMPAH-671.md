---
id: OOMPAH-671
type: task
status: In Validation
priority: null
title: Recover terminal audits when historical work branches were deleted
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-07-31T23:31:12.705782Z'
updated_at: '2026-08-01T01:36:28.778367Z'
work_branch: OOMPAH-671
target_branch: main
review_url: https://github.com/lesserevil/oompah/pull/634
review_number: '634'
merged_at: null
oompah.integration:
  version: 2
  state: ready
  attempts: 0
  task_branch: OOMPAH-671
  head_sha: 6d34fc1adb6ca08a60d807b76eb2d982d5837cb4
  submitted_at: '2026-08-01T00:04:04.596518+00:00'
  updated_at: '2026-08-01T00:04:04.596518+00:00'
oompah.review_url: https://github.com/lesserevil/oompah/pull/634
oompah.review_number: '634'
oompah.work_branch: OOMPAH-671
oompah.target_branch: main
oompah.terminal_audit:
  queued_comment_posted: true
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-0be8237f0624
    project_id: proj-14849f1b
    task_id: OOMPAH-671
    target_state: Done
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: f713ab0bbbd1c702553b62fa10cb99fcc3db2bdc76bfc17fc69ef3e7e0069cb9
    attempts: []
    requested_by:
      version: 1
      identity: lesserevil
      source: forge
    previous_state: In Review
    created_at: '2026-08-01T01:36:24.558751+00:00'
  - version: 1
    audit_id: audit-9f357f4a2c68
    project_id: proj-14849f1b
    task_id: OOMPAH-671
    target_state: Merged
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: f713ab0bbbd1c702553b62fa10cb99fcc3db2bdc76bfc17fc69ef3e7e0069cb9
    attempts: []
    requested_by:
      version: 1
      identity: lesserevil
      source: forge
    previous_state: In Review
    created_at: '2026-08-01T01:36:24.558751+00:00'
  attempt_history: []
---
## Summary

Fix terminal-audit dispatch for terminal or auto-archive audits whose persisted work_branch references a branch that was deleted after merge. Live reproduction: EXOCOMP-75/76/77/88/89/90/91/92/99/100/101/102/103/104/105 were canonically Merged and queued for aged-Merged auto-archive; each auditor attempt failed during git worktree add with 'invalid reference: origin/epic-EXOCOMP-2', then exhausted attempts and was incorrectly surfaced as no_independent_candidate in Needs Human. Implementation scope: trace terminal-audit workspace selection and checkout creation in oompah/orchestrator.py and oompah/projects.py; select a safe, immutable audited revision or verified default-branch fallback when the historical work branch no longer exists; fail closed when the audited evidence is ambiguous or unreachable; classify checkout/source-reference failures separately from auditor-provider availability; and provide an idempotent retry/rearm path that does not reopen terminal tasks for implementation dispatch. Required tests: deleted merged epic branch with evidence reachable from default branch; unreachable/ambiguous evidence fails closed; aged-Merged Archived audit; correct error classification; retry idempotency across restart; project isolation; no normal implementation dispatch. Acceptance: affected audits can be retried against the intended evidence, no false no-independent_candidate alert is emitted for a deleted historical branch, Exocomp tasks remain out of implementation flow, and alert state retires after successful audit or explicit durable terminal disposition. Run focused terminal-audit tests and the full Makefile gate.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-31 23:31
---
Claimed for direct operator implementation at the project owner's request. Needs Human will be used only as a scheduler-control hold while I implement and verify the fix; do not dispatch a worker for this task.
---
author: oompah
created: 2026-07-31 23:31
---
Moved to Needs Human from the dashboard/API. Human action required: inspect OOMPAH-671 (Recover terminal audits when historical work branches were deleted), add the specific decision, missing information, or manual fix needed, then move the task back to Open when it is ready for agents again.
---
author: oompah
created: 2026-07-31 23:47
---
Implementation progress: terminal auditors now resolve a detached, attempt-scoped checkout from persisted immutable revision evidence; legacy Merged-to-Archived records may fall back to the fetched default branch only when no immutable SHA exists, while unreachable immutable evidence fails closed. Infrastructure retry exhaustion is no longer mislabeled as no-independent-candidate. Added an owner-authorized, idempotent audit-rearm path that preserves/supersedes the failed record and restores In Validation without reopening implementation. Focused workspace, coordinator, API, CLI, cleanup, and dispatch tests pass (469 passed); the broader terminal-audit suite is running.
---
author: oompah
created: 2026-08-01 00:04
---
Direct operator implementation is complete on pushed head 6d34fc1adb6ca08a60d807b76eb2d982d5837cb4. Verification: full make test before rebase passed (14,558 passed, 7 skipped, 1 xfailed); after rebasing onto current origin/main, the 849 focused terminal-audit, workspace, API/CLI, ACP, and candidate-failover tests passed. Terminal mutation scan and git diff --check passed.
---
author: oompah
created: 2026-08-01 00:04
---
Recover terminal audits after source branch cleanup with detached evidence worktrees, fail-closed revision resolution, infrastructure-aware exhaustion, and an owner-authorized audit rearm path. Pushed head 6d34fc1adb6ca08a60d807b76eb2d982d5837cb4; full and focused gates pass.
---
author: oompah
created: 2026-08-01 01:27
---
Branch quality gate passed for `6d34fc1adb6ca08a60d807b76eb2d982d5837cb4` using `make test` in 392.5s. Review creation may proceed.
---
author: oompah
created: 2026-08-01 01:36
---
Queued for terminal transition to Merged. An auditor will review and apply the terminal status.
---
author: oompah
created: 2026-08-01 01:36
---
YOLO: merged PR #634.
---
<!-- COMMENTS:END -->
