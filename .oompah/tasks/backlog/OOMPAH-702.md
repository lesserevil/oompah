---
id: OOMPAH-702
type: bug
status: Backlog
priority: 1
title: Synchronize merged-webhook tests with background terminal staging
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-02T20:34:49.621752Z'
updated_at: '2026-08-02T20:34:49.621752Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
---
## Summary

Triggered by: OOMPAH-699

Production CI reproduction on PR #660, run 30765374167: Python 3.11 failed tests/test_server_webhooks.py::TestWebhookMergedReconciliation::test_pr_merged_stages_task_merged because request_terminal_transition had not yet been awaited when the test asserted. Python 3.13 passed, the exact test passed immediately when rerun locally, and the Python 3.12 matrix job was canceled by fail-fast. The webhook handler intentionally launches _label_task_merged_from_pr in a daemon background thread, while this test asserts immediately after TestClient.post returns and has no completion barrier. Thread scheduling therefore determines the result. This unrelated flake moved OOMPAH-699 from In Review back to a repair state despite a clean branch gate.\n\nImplementation scope:\n- Give webhook background work a deterministic test-visible completion boundary, or make this test wait on an explicit event/future rather than wall-clock sleeps.\n- Audit the adjacent merged, merge-group, In Review, and tracked-branch sync webhook tests for the same start-thread-then-assert race.\n- Preserve fast production webhook responses and do not make network-facing handlers synchronously wait for repository or tracker work.\n- Ensure background exceptions remain observable and do not silently satisfy the test barrier.\n\nRelevant code: oompah/server.py _handle_webhook_event and _label_task_merged_from_pr; tests/test_server_webhooks.py TestWebhookMergedReconciliation and adjacent background webhook cases.\n\nRequired tests:\n- Reproduce delayed thread scheduling and prove the merged webhook test waits deterministically for request_terminal_transition.\n- Prove a background exception is surfaced to the test instead of producing a false pass or timeout.\n- Exercise repeated runs under Python 3.11, 3.12, and 3.13 without sleeps or scheduler assumptions.\n- Verify the HTTP response remains prompt while production work continues asynchronously.\n\nAcceptance criteria:\n- The PR #660 failure cannot recur from thread scheduling.\n- Webhook tests have explicit synchronization for every asserted background side effect.\n- Focused webhook tests and make test pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

