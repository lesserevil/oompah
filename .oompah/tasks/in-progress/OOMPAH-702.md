---
id: OOMPAH-702
type: bug
status: In Progress
priority: 1
title: Synchronize merged-webhook tests with background terminal staging
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-02T20:34:49.621752Z'
updated_at: '2026-08-02T21:52:47.872541Z'
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
  verdict: no_duplicate
  checked_at: '2026-08-02T21:52:02.848082+00:00'
  matched_identifiers: []
  evidence: "Focus handoff: duplicate_detector  \nDuplicate preflight verdict: no_duplicate\
    \  \nMatches: none  \n\nEvidence: The closest webhook task, OOMPAH-14, is Archived\
    \ and addresses metadata normalization, not background-thread synchronization.\
    \ Other webhook-related candidates are terminal or unrelated."
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: 4cfd9318-e160-4bfc-a292-837b59670d39
oompah.task_costs:
  total_input_tokens: 50596
  total_output_tokens: 545
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 50596
      output_tokens: 545
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 50596
    output_tokens: 545
    cost_usd: 0.0
    recorded_at: '2026-08-02T21:52:02.835725+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-702__20260802T215139Z
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: duplicate_detector
    source_branch: OOMPAH-702
    source_sha: 366129d0a5046c5ed7caed4acf26cd8cd2a3fbdd
    completed_at: '2026-08-02T21:52:02.871153+00:00'
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
author: oompah
created: 2026-08-02 21:52
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 0
- Tokens: 50.6K in / 545 out [51.1K total]
- Cost: $0.0000
- Exit: normal, Duration: 34s
- Log: OOMPAH-702__20260802T215139Z.jsonl
---
author: oompah
created: 2026-08-02 21:52
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-08-02 21:52
---
Focus: Test Engineer
---
author: oompah
created: 2026-08-02 21:52
---
Understanding: I will audit merged and adjacent webhook tests for assertions that race daemon background work, introduce an explicit test-visible completion/error boundary while preserving prompt asynchronous HTTP responses, add delayed-scheduling and exception regression coverage, run focused checks and make test, then commit, push, and submit.
---
<!-- COMMENTS:END -->
