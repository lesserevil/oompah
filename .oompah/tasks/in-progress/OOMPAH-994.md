---
id: OOMPAH-994
type: bug
status: In Progress
priority: 1
title: Make API task creation durable, idempotent, and bounded
parent: OOMPAH-992
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-10T10:52:30.794441Z'
updated_at: '2026-08-10T11:10:35.335814Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
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
<!-- COMMENTS:END -->
