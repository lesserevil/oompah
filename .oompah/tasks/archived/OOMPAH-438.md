---
id: OOMPAH-438
type: task
status: Archived
priority: null
title: Wake dispatch after a task becomes dispatchable
parent: null
children: []
blocked_by: []
labels: []
assignee: null
created_at: '2026-07-24T15:53:33.753602Z'
updated_at: '2026-08-02T01:26:43.799969Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.terminal_audit:
  queued_comment_posted: true
  applied_result_attempts:
    attempt-cd33eeb154ba: '2026-08-02T01:26:37.829157+00:00'
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-438
    target_state: Archived
    evidence_fingerprint: 9654dd2fb4c062d451bc916c2cea21fd200c285209ee453dcbfd7dc5d1d045ab
    audit_ids:
    - audit-d9afc59181c0
    kind: result
    applied: true
    retired_at: '2026-08-02T01:26:37.829168+00:00'
  oompah.terminal_audit_result_intents:
  - project_id: proj-14849f1b
    task_id: OOMPAH-438
    audit_id: audit-d9afc59181c0
    attempt_id: attempt-cd33eeb154ba
    target_state: Archived
    evidence_fingerprint: 9654dd2fb4c062d451bc916c2cea21fd200c285209ee453dcbfd7dc5d1d045ab
    status: Archived
    audit_ids:
    - audit-d9afc59181c0
    applied: true
    created_at: '2026-08-02T01:26:37.829185+00:00'
    applied_at: '2026-08-02T01:26:42.870203+00:00'
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-d9afc59181c0
    project_id: proj-14849f1b
    task_id: OOMPAH-438
    target_state: Archived
    request_state: completed
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 9654dd2fb4c062d451bc916c2cea21fd200c285209ee453dcbfd7dc5d1d045ab
    attempts:
    - version: 1
      attempt_id: attempt-cd33eeb154ba
      target_state: Archived
      request_state: completed
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: 9654dd2fb4c062d451bc916c2cea21fd200c285209ee453dcbfd7dc5d1d045ab
      created_at: '2026-08-02T01:16:31.759948+00:00'
      provider_id: prov-651d553c
      model: opus
      started_at: '2026-08-02T01:16:31.759948+00:00'
      branch_key: OOMPAH-438
      verdict: pass
      completed_at: '2026-08-02T01:26:37.828968+00:00'
      ended_at: '2026-08-02T01:26:37.828968+00:00'
    requested_by:
      version: 1
      identity: oompah
      source: auto_archive
    previous_state: Merged
    created_at: '2026-08-02T01:14:06.743932+00:00'
    updated_at: '2026-08-02T01:26:37.828968+00:00'
  attempt_history:
  - version: 1
    attempt_id: attempt-cd33eeb154ba
    target_state: Archived
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 9654dd2fb4c062d451bc916c2cea21fd200c285209ee453dcbfd7dc5d1d045ab
    created_at: '2026-08-02T01:16:31.759948+00:00'
    provider_id: prov-651d553c
    model: opus
    started_at: '2026-08-02T01:16:31.759948+00:00'
    branch_key: OOMPAH-438
---
## Summary

PATCH /api/v1/issues currently updates a task to Open but does not call orchestrator.request_refresh(), leaving newly dispatchable work idle until the long safety-net poll. Trigger a refresh after a successful transition into a dispatchable status, without waking for non-dispatchable metadata-only changes. Add API regression coverage proving an Open transition requests refresh and a non-dispatchable transition does not. Run make test and deploy.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-24 15:55
---
Fixed and deployed immediate scheduler wake-up after a task transitions into Open. Added API regression coverage for dispatchable and non-dispatchable transitions; make test passed (12,312 tests). Commit 609e0ea26 pushed to main.
---
author: oompah
created: 2026-07-26 00:29
---
Delivery reconciled: immediate scheduler wake-up on dispatchable transitions is present on origin/main in commit 609e0ea26. This task was Done rather than waiting for an agent; it is now being aligned with the delivered repository state.
---
author: oompah
created: 2026-07-26 00:29
---
Verified delivered on origin/main in 609e0ea26 and reconciled stale Done state.
---
author: oompah
created: 2026-08-02 01:14
---
Queued Archived audit: Aged Merged auto-archive (closed 7 days ago). An auditor will review before the task is retired.
---
author: oompah
created: 2026-08-02 01:16
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/opus)
---
author: oompah
created: 2026-08-02 01:16
---
Focus: Completion Auditor
---
author: oompah
created: 2026-08-02 01:26
---
Audit PASS — Archived

[REDACTED]

Safe evidence:
- delivery_commit: 609e0ea269f7b8bfd53fc8ff755ce26a482d11aa
- commit_subject: Wake scheduler when tasks become dispatchable
- commit_on_main: yes (git branch --contains lists main)
- server_change_location: oompah/server.py:10357-10377 (api_update_issue post-status-update guard)
- server_change_predicate: new_status is not None AND is_dispatchable_status(new_status) AND (existing_issue is None OR not is_dispatchable_status(existing_issue.state)) -> orch.request_refresh()
- dispatchable_test: tests/test_server_epic_state.py:264 test_open_transition_requests_immediate_dispatch_refresh (Backlog->Open, request_refresh.assert_called_once())
- non_dispatchable_test: tests/test_server_epic_state.py:282 test_non_dispatchable_transition_does_not_request_refresh (Open->Backlog, request_refresh.assert_not_called())
- previous_state: Merged
- archive_reason: Aged Merged auto-archive (closed 7 days ago)
---
<!-- COMMENTS:END -->
