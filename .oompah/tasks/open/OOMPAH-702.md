---
id: OOMPAH-702
type: bug
status: Open
priority: 1
title: Synchronize merged-webhook tests with background terminal staging
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-02T20:34:49.621752Z'
updated_at: '2026-08-02T21:51:31.316990Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 031f38c6c40dcf1b0bd78f2318d6a4ac10df34ecdd776a048fd70f5a39cdebbd
  detector_version: duplicate-detector-v1
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: ''
  claim_id: 1c77241c-a4c6-4c8e-b18b-ac97fca83556
  claim_owner: 0b22eab2-a2d1-4082-a6c8-404ec37650a4
  claimed_at: '2026-08-02T21:51:24.556912+00:00'
  claim_expires_at: '2026-08-02T22:21:24.556912+00:00'
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: fafa039e-a50e-4082-ba7f-7fd92918c9fe
---
## Summary

Triggered by: OOMPAH-699

Production CI reproduction on PR #660, run 30765374167: Python 3.11 failed tests/test_server_webhooks.py::TestWebhookMergedReconciliation::test_pr_merged_stages_task_merged because request_terminal_transition had not yet been awaited when the test asserted. Python 3.13 passed, the exact test passed immediately when rerun locally, and the Python 3.12 matrix job was canceled by fail-fast. The webhook handler intentionally launches _label_task_merged_from_pr in a daemon background thread, while this test asserts immediately after TestClient.post returns and has no completion barrier. Thread scheduling therefore determines the result. This unrelated flake moved OOMPAH-699 from In Review back to a repair state despite a clean branch gate.\n\nImplementation scope:\n- Give webhook background work a deterministic test-visible completion boundary, or make this test wait on an explicit event/future rather than wall-clock sleeps.\n- Audit the adjacent merged, merge-group, In Review, and tracked-branch sync webhook tests for the same start-thread-then-assert race.\n- Preserve fast production webhook responses and do not make network-facing handlers synchronously wait for repository or tracker work.\n- Ensure background exceptions remain observable and do not silently satisfy the test barrier.\n\nRelevant code: oompah/server.py _handle_webhook_event and _label_task_merged_from_pr; tests/test_server_webhooks.py TestWebhookMergedReconciliation and adjacent background webhook cases.\n\nRequired tests:\n- Reproduce delayed thread scheduling and prove the merged webhook test waits deterministically for request_terminal_transition.\n- Prove a background exception is surfaced to the test instead of producing a false pass or timeout.\n- Exercise repeated runs under Python 3.11, 3.12, and 3.13 without sleeps or scheduler assumptions.\n- Verify the HTTP response remains prompt while production work continues asynchronously.\n\nAcceptance criteria:\n- The PR #660 failure cannot recur from thread scheduling.\n- Webhook tests have explicit synchronization for every asserted background side effect.\n- Focused webhook tests and make test pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-02 21:51
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-02 21:51
---
Focus: Duplicate Investigator
---
<!-- COMMENTS:END -->
