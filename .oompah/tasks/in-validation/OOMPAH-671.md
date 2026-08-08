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
updated_at: '2026-08-08T02:00:07.855192Z'
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
  applied_result_attempts:
    attempt-31bcf8c69258: '2026-08-01T01:42:06.310957+00:00'
    attempt-825f51c8a8f3: '2026-08-01T01:50:56.767619+00:00'
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-671
    target_state: Done
    evidence_fingerprint: f713ab0bbbd1c702553b62fa10cb99fcc3db2bdc76bfc17fc69ef3e7e0069cb9
    audit_ids:
    - audit-0be8237f0624
    kind: result
    applied: true
    retired_at: '2026-08-01T01:42:06.310964+00:00'
  - project_id: proj-14849f1b
    task_id: OOMPAH-671
    target_state: Merged
    evidence_fingerprint: f713ab0bbbd1c702553b62fa10cb99fcc3db2bdc76bfc17fc69ef3e7e0069cb9
    audit_ids:
    - audit-9f357f4a2c68
    kind: result
    applied: true
    retired_at: '2026-08-01T01:50:56.767637+00:00'
  oompah.terminal_audit_result_intents:
  - project_id: proj-14849f1b
    task_id: OOMPAH-671
    audit_id: audit-0be8237f0624
    attempt_id: attempt-31bcf8c69258
    target_state: Done
    evidence_fingerprint: f713ab0bbbd1c702553b62fa10cb99fcc3db2bdc76bfc17fc69ef3e7e0069cb9
    status: In Validation
    audit_ids:
    - audit-0be8237f0624
    applied: true
    created_at: '2026-08-01T01:42:06.310974+00:00'
    applied_at: '2026-08-01T01:42:09.790127+00:00'
  - project_id: proj-14849f1b
    task_id: OOMPAH-671
    audit_id: audit-9f357f4a2c68
    attempt_id: attempt-825f51c8a8f3
    target_state: Merged
    evidence_fingerprint: f713ab0bbbd1c702553b62fa10cb99fcc3db2bdc76bfc17fc69ef3e7e0069cb9
    status: Merged
    audit_ids:
    - audit-9f357f4a2c68
    applied: true
    created_at: '2026-08-01T01:50:56.767659+00:00'
    applied_at: '2026-08-01T01:51:01.185880+00:00'
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-0be8237f0624
    project_id: proj-14849f1b
    task_id: OOMPAH-671
    target_state: Done
    request_state: completed
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: f713ab0bbbd1c702553b62fa10cb99fcc3db2bdc76bfc17fc69ef3e7e0069cb9
    attempts:
    - version: 1
      attempt_id: attempt-31bcf8c69258
      target_state: Done
      request_state: completed
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: f713ab0bbbd1c702553b62fa10cb99fcc3db2bdc76bfc17fc69ef3e7e0069cb9
      created_at: '2026-08-01T01:36:37.428513+00:00'
      provider_id: prov-651d553c
      model: opus
      started_at: '2026-08-01T01:36:37.428513+00:00'
      branch_key: OOMPAH-671
      verdict: pass
      completed_at: '2026-08-01T01:42:06.310853+00:00'
      ended_at: '2026-08-01T01:42:06.310853+00:00'
    requested_by:
      version: 1
      identity: lesserevil
      source: forge
    previous_state: In Review
    created_at: '2026-08-01T01:36:24.558751+00:00'
    updated_at: '2026-08-01T01:42:06.310853+00:00'
  - version: 1
    audit_id: audit-9f357f4a2c68
    project_id: proj-14849f1b
    task_id: OOMPAH-671
    target_state: Merged
    request_state: completed
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: f713ab0bbbd1c702553b62fa10cb99fcc3db2bdc76bfc17fc69ef3e7e0069cb9
    attempts:
    - version: 1
      attempt_id: attempt-825f51c8a8f3
      target_state: Merged
      request_state: completed
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: f713ab0bbbd1c702553b62fa10cb99fcc3db2bdc76bfc17fc69ef3e7e0069cb9
      created_at: '2026-08-01T01:43:30.886891+00:00'
      provider_id: prov-651d553c
      model: opus
      started_at: '2026-08-01T01:43:30.886891+00:00'
      branch_key: OOMPAH-671
      verdict: pass
      completed_at: '2026-08-01T01:50:56.767439+00:00'
      ended_at: '2026-08-01T01:50:56.767439+00:00'
    requested_by:
      version: 1
      identity: lesserevil
      source: forge
    previous_state: In Review
    created_at: '2026-08-01T01:36:24.558751+00:00'
    updated_at: '2026-08-01T01:50:56.767439+00:00'
  - version: 1
    audit_id: audit-855b52b3974f
    project_id: proj-14849f1b
    task_id: OOMPAH-671
    target_state: Archived
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: a432d5fc26f27a027cfc764208411878fbd9cbb106addeac61b545359b551900
    attempts:
    - version: 1
      attempt_id: attempt-8213b5093b10
      target_state: Archived
      request_state: in_progress
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: a432d5fc26f27a027cfc764208411878fbd9cbb106addeac61b545359b551900
      created_at: '2026-08-08T01:59:56.891389+00:00'
      provider_id: prov-651d553c
      model: haiku
      started_at: '2026-08-08T01:59:56.891389+00:00'
      branch_key: OOMPAH-671
      selected_ref: 6d34fc1adb6ca08a60d807b76eb2d982d5837cb4
      selected_sha: 6d34fc1adb6ca08a60d807b76eb2d982d5837cb4
    requested_by:
      version: 1
      identity: oompah
      source: auto_archive
    previous_state: Merged
    created_at: '2026-08-08T01:59:17.900742+00:00'
    selected_ref: 6d34fc1adb6ca08a60d807b76eb2d982d5837cb4
    selected_sha: 6d34fc1adb6ca08a60d807b76eb2d982d5837cb4
    updated_at: '2026-08-08T01:59:56.891389+00:00'
  attempt_history:
  - version: 1
    attempt_id: attempt-31bcf8c69258
    target_state: Done
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: f713ab0bbbd1c702553b62fa10cb99fcc3db2bdc76bfc17fc69ef3e7e0069cb9
    created_at: '2026-08-01T01:36:37.428513+00:00'
    provider_id: prov-651d553c
    model: opus
    started_at: '2026-08-01T01:36:37.428513+00:00'
    branch_key: OOMPAH-671
  - version: 1
    attempt_id: attempt-825f51c8a8f3
    target_state: Merged
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: f713ab0bbbd1c702553b62fa10cb99fcc3db2bdc76bfc17fc69ef3e7e0069cb9
    created_at: '2026-08-01T01:43:30.886891+00:00'
    provider_id: prov-651d553c
    model: opus
    started_at: '2026-08-01T01:43:30.886891+00:00'
    branch_key: OOMPAH-671
  - version: 1
    attempt_id: attempt-8213b5093b10
    target_state: Archived
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: a432d5fc26f27a027cfc764208411878fbd9cbb106addeac61b545359b551900
    created_at: '2026-08-08T01:59:56.891389+00:00'
    provider_id: prov-651d553c
    model: haiku
    started_at: '2026-08-08T01:59:56.891389+00:00'
    branch_key: OOMPAH-671
    selected_ref: 6d34fc1adb6ca08a60d807b76eb2d982d5837cb4
    selected_sha: 6d34fc1adb6ca08a60d807b76eb2d982d5837cb4
oompah.task_costs:
  total_input_tokens: 120
  total_output_tokens: 13077
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 120
      output_tokens: 13077
      cost_usd: 0.0
  runs:
  - profile: auditor
    model: unknown
    input_tokens: 51
    output_tokens: 10290
    cost_usd: 0.0
    recorded_at: '2026-08-01T01:42:19.318700+00:00'
  - profile: auditor
    model: unknown
    input_tokens: 69
    output_tokens: 2787
    cost_usd: 0.0
    recorded_at: '2026-08-01T01:51:19.968360+00:00'
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
author: oompah
created: 2026-08-01 01:36
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/opus)
---
author: oompah
created: 2026-08-01 01:36
---
Focus: Completion Auditor
---
author: oompah
created: 2026-08-01 01:42
---
Audit PASS — Done

[REDACTED]

Safe evidence:
- head_sha: 6d34fc1adb6ca08a60d807b76eb2d982d5837cb4
- merged_pr: 634
- merge_commit: 45f746f26ead32a352aafd26c4dda73030f4f8a5
- files_changed: 13
- insertions: 1184
- deletions: 29
- recovery_tests: 3 passed
- epic_children_tests: 31 passed
- detached_worktree_tests: 2 passed
- coordinator_tests: 119 passed
- interfaces_tests: 58 passed
- terminal_audit_broad: 166 passed
- auditor_broad: 162 passed
---
author: oompah
created: 2026-08-01 01:42
---
Run #1 [attempt=1, profile=auditor, role=auditor -> Claude/opus]
- Turns: 55, Tool calls: 45
- Tokens: 51 in / 10.3K out [10.3K total]
- Cost: $0.0000
- Exit: normal, Duration: 5m 41s
- Log: OOMPAH-671__20260801T013642Z.jsonl
---
author: oompah
created: 2026-08-01 01:43
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/opus)
---
author: oompah
created: 2026-08-01 01:43
---
Focus: Completion Auditor
---
author: oompah
created: 2026-08-01 01:50
---
Audit PASS — Merged

[REDACTED]

Safe evidence:
- head_sha: 6d34fc1adb6ca08a60d807b76eb2d982d5837cb4
- merge_commit: 45f746f26ead32a352aafd26c4dda73030f4f8a5
- merged_pr: 634
- base_branch: main
- files_changed: 13
- insertions: 1184
- deletions: 29
- commit_trailer_ok: true
- focus_terminal_audit_workspace_recovery: 3 passed
- focus_terminal_transition_coordinator: 119 passed
- focus_terminal_status_interfaces: 58 passed
- focus_parallel_epic_children: 31 passed
- focus_projects: 102 passed
- focus_task_cli: 139 passed
- focus_terminal_audit_broad: 132 passed
- focus_auditor_broad: 162 passed
---
author: oompah
created: 2026-08-01 01:51
---
Run #1 [attempt=1, profile=auditor, role=auditor -> Claude/opus]
- Turns: 0, Tool calls: 50
- Tokens: 69 in / 2.8K out [2.9K total]
- Cost: $0.0000
- Exit: terminated, Duration: 7m 48s
- Log: OOMPAH-671__20260801T014339Z.jsonl
---
author: oompah
created: 2026-08-08 02:00
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/haiku)
---
author: oompah
created: 2026-08-08 02:00
---
Focus: Completion Auditor
---
<!-- COMMENTS:END -->
