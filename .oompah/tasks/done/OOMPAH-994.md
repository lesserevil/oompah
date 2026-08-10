---
id: OOMPAH-994
type: bug
status: Done
priority: 1
title: Make API task creation durable, idempotent, and bounded
parent: OOMPAH-992
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-10T10:52:30.794441Z'
updated_at: '2026-08-10T15:40:41.654882Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.terminal_audit:
  oompah.terminal_override_records:
  - version: 1
    override_id: override-82c1785cd257
    project_id: proj-14849f1b
    task_id: OOMPAH-994
    target_state: Done
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: e08269f0228e329a40c19efb50000eee1cf784f00ab6e3dfb7c3b5d2654e8868
    authorized_by:
      version: 1
      identity: oompah-cli
      source: api
    reason: 'PR #798 merged as 2ab880be5; parent OOMPAH-992 is authoritatively terminal;
      contained 5daf54016 is stable-patch-identical to reviewed OOMPAH-994 head 3d5716069.
      Recording shared-child completion as Done because no separate parent review
      record exists.'
    created_at: '2026-08-10T15:40:27.721463+00:00'
    selected_ref: origin/OOMPAH-994
    selected_sha: 3d5716069ebb80fe3bad5121c44912cc76d4ccda
    applied: true
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-994
    target_state: Done
    evidence_fingerprint: e08269f0228e329a40c19efb50000eee1cf784f00ab6e3dfb7c3b5d2654e8868
    audit_ids: []
    kind: override
    applied: true
    retired_at: '2026-08-10T15:40:39.734916+00:00'
  oompah.terminal_audit_result_intents: []
  version: 1
  pending_chain: []
  attempt_history: []
---
## Summary

Add request idempotency for API task creation and its CLI/UI callers. Reuse NativeTaskTracker create_issue_once with a durable operation marker and payload fingerprint; replaying the same key must return the same task, conflicting payloads must return 409, and cancellation or restart after acceptance must not create duplicates. Bound admission so callers receive a bounded 503 before acceptance or a durable operation response after acceptance. Add tests for cancel/replay, restart recovery, conflict, and API pool responsiveness.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-10 11:10
---
Implementation is complete and pushed at exact head 3d5716069ebb80fe3bad5121c44912cc76d4ccda on branch OOMPAH-994, based on integration head c4ad83e47b1492e7526098dcf5816b3dfd3eb50b. Keyed native API creates now use the existing durable create_issue_once marker/fingerprint boundary; exact replay returns the same task with HTTP 201, changed payload returns typed HTTP 409 idempotency_conflict, and keyed adapters without atomic support fail closed with HTTP 501 while unkeyed legacy creation remains compatible. A dedicated two-worker/no-queue create lane keeps the general API pool responsive; project-lock admission is cancellation-aware and bounded by OOMPAH_TASK_CREATE_ADMISSION_TIMEOUT_SECONDS, returning retryable HTTP 503 before mutation. Cancellation after admission leaves the shielded durable operation running so the same key recovers it; detached exceptions are consumed. CLI create/child-create generate or accept --idempotency-key, retry transport loss once with the same key, and surface it for later recovery; the dashboard reuses a key for identical-payload retries and rotates it when the payload changes. Validation: /home/shedwards/src/oompah/.venv/bin/python -m pytest -q tests/test_server_create_issue.py tests/test_server_create_issue_idempotency.py tests/test_server_json_validation.py tests/test_task_cli.py tests/test_dashboard_create_native.py tests/test_dashboard_create_github.py tests/test_oompah_md_tracker.py tests/test_oompah_md_tracker_state_branch.py => 439 passed. The 8-case cancel/replay/restart/conflict/admission/responsiveness file passed 10/10 repeated runs. Generated-key transport retry exact selector passed 2/2. compileall, git diff --check, Makefile terminal-audit-scan, secret hooks, and push passed. Full suite intentionally not run for this child.
---
author: oompah
created: 2026-08-10 11:11
---
Independent integration review accepted exact child commit 3d5716069ebb80fe3bad5121c44912cc76d4ccda. The patch is cherry-picked into the shared PR #798 integration branch as 5daf540165b336040a93f0738eb6e2f197807ac0. The clean child worktree has been pruned immediately; origin/OOMPAH-994 remains as recoverable provenance until the shared PR lands. Task remains In Progress for shared landing disposition.
---
author: oompah
created: 2026-08-10 15:40
---
Override by oompah-cli: terminal transition to Done applied by project owner.

Reason: PR #798 merged as 2ab880be5; parent OOMPAH-992 is authoritatively terminal; contained 5daf54016 is stable-patch-identical to reviewed OOMPAH-994 head 3d5716069. Recording shared-child completion as Done because no separate parent review record exists.
---
<!-- COMMENTS:END -->
