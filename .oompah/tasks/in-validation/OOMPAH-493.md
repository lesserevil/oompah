---
id: OOMPAH-493
type: task
status: In Validation
priority: 1
title: Remove real retry sleeps from GitHub tracker error tests
parent: OOMPAH-490
children: []
blocked_by:
- OOMPAH-491
labels:
- focus-complete:duplicate_detector
assignee: null
created_at: '2026-07-28T13:53:28.451050Z'
updated_at: '2026-08-04T17:26:11.105639Z'
work_branch: epic-OOMPAH-490
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: f748aabd-48e0-4b04-9327-f4d7bc5f403e
oompah.work_branch: epic-OOMPAH-490
oompah.task_costs:
  total_input_tokens: 825978
  total_output_tokens: 6162
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 825978
      output_tokens: 6162
      cost_usd: 0.0
  runs:
  - profile: default
    model: unknown
    input_tokens: 825922
    output_tokens: 4328
    cost_usd: 0.0
    recorded_at: '2026-07-28T15:21:18.120388+00:00'
  - profile: default
    model: unknown
    input_tokens: 56
    output_tokens: 1834
    cost_usd: 0.0
    recorded_at: '2026-07-28T15:29:39.940089+00:00'
oompah.terminal_audit:
  queued_comment_posted: true
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-a5f61ba90a42
    project_id: proj-14849f1b
    task_id: OOMPAH-493
    target_state: Archived
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 51b206b136a05b8614cb2afee3eb2942b331aebef3195d9af63e010253f2f1e9
    attempts: []
    requested_by:
      version: 1
      identity: oompah
      source: auto_archive
    previous_state: Merged
    created_at: '2026-08-04T17:26:04.993556+00:00'
  attempt_history: []
---
## Summary

Implementation scope

Make `tests/test_github_tracker.py::TestGitHubIssueTrackerMutations::test_remove_label_re_raises_non_404_errors` deterministic. The mocked raw HTTP layer returns 500 on every attempt, so the production retry wrapper currently performs real exponential-backoff sleeps before raising. Patch the GitHub client's `_sleep` boundary, preserve the 500 response for every attempt, and assert both the final `TrackerError` and the expected retry/sleep behavior. Review only the neighboring mutation error tests in the same class for the identical always-transient-response pattern and apply the same treatment where confirmed. Do not reduce production retry coverage or change retry constants.

Tests

Run the targeted test with `--durations=5`, then the complete `tests/test_github_tracker.py`. Add assertions proving retries occurred and sleep was requested without actually waiting. Run `make test` after prerequisite isolation work is complete.

Acceptance criteria

The 500-error path still proves retry exhaustion and error propagation, performs no real sleep, and completes in ordinary unit-test time while 404 no-op and successful removal behavior remain covered.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-28 15:19
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-28 15:19
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-28 15:19
---
Understanding: duplicate-detector focus will search existing tasks and project records for prior coverage of GitHub tracker mutation tests that incur real retry sleeps, inspect close candidates in full, and either archive this task as a confirmed duplicate or hand it off without code changes.
---
author: oompah
created: 2026-07-28 15:20
---
Discovery: No confirmed duplicate. Searched .oompah/tasks, docs, plans, README.md, and WORKFLOW.md for GitHub tracker retries, real sleeps, remove_label/non-404 errors, retry exhaustion, _sleep patching, and transient 500 responses. Reviewed OOMPAH-490, OOMPAH-491, OOMPAH-492, OOMPAH-499, OOMPAH-500, and OOMPAH-6 in full. OOMPAH-490 uniquely assigns this deterministic retry-exhaustion test to OOMPAH-493; OOMPAH-491 blocks network Git, OOMPAH-492 isolates unrelated live-tracker leaks, OOMPAH-499 removes exact duplicates, OOMPAH-500 is the final audit, and OOMPAH-6 concerns authentication errors. In TestGitHubIssueTrackerMutations, code search found only test_remove_label_re_raises_non_404_errors using an always-500 response; the lower-level test_500_retries_then_succeeds already patches _sleep but covers success after retry, not exhaustion/error propagation.
---
author: oompah
created: 2026-07-28 15:21
---
Focus handoff: duplicate_detector

1. Outcome: No duplicate; OOMPAH-493 should proceed as a focused test-isolation change.
2. Evidence: Relevant code is tests/test_github_tracker.py:2955-2961. The test returns the same 500 response for every raw HTTP call and does not patch tracker._client._sleep, so production retries incur real backoff. Search of the surrounding TestGitHubIssueTrackerMutations class found no other always-transient response needing the same treatment. Existing test_500_retries_then_succeeds at lines 894-902 patches _sleep but proves a different retry-success contract.
3. Remaining work/risks: Patch tracker._client._sleep in the 500 mutation test; assert TrackerError after exhaustion, raw request attempt count, and sleep call count/arguments without changing retry constants. Preserve the 404 no-op and successful DELETE tests. Run the named test with --durations=5, the full tests/test_github_tracker.py file, then make test now that OOMPAH-491 and OOMPAH-492 are Done.
4. Recommended next focus: test implementation. No code was changed and no tests were run during duplicate screening.
---
author: oompah
created: 2026-07-28 15:21
---
Agent completed successfully in 139s (830250 tokens)
---
author: oompah
created: 2026-07-28 15:21
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/default]
- Turns: 1, Tool calls: 18
- Tokens: 825.9K in / 4.3K out [830.2K total]
- Cost: $0.0000
- Exit: normal, Duration: 2m 19s
- Log: OOMPAH-493__20260728T151905Z.jsonl
---
author: oompah
created: 2026-07-28 15:21
---
Focus handoff from `duplicate_detector` is complete. Queued a fresh agent run for the next applicable focus. The next agent should begin with the preceding Focus handoff comment.
---
author: oompah
created: 2026-07-28 15:21
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-28 15:21
---
Focus: Test Engineer
---
author: oompah
created: 2026-07-28 15:21
---
Understanding: As the Test Engineer, I will patch tracker._client._sleep in test_remove_label_re_raises_non_404_errors so the 500-error retry path does not incur real sleeps. I'll assert TrackerError is raised after retry exhaustion, check that retries occurred (request attempt count), and verify sleep was called with expected arguments — all without actual waiting. I'll also scan neighboring mutation error tests in TestGitHubIssueTrackerMutations for the same always-transient-500 pattern and apply the same treatment. No production retry constants will be changed.
---
author: oompah
created: 2026-07-28 15:23
---
Discovery: Confirmed the target test is at lines 2955-2962. The test uses return_value=resp with _mock_response(500) so the same 500 is returned for every retry attempt. Since 500 is in _RETRYABLE_STATUS, the production retry loop makes _MAX_RETRIES+1 = 4 requests and calls _sleep(_backoff(n)) for 3 sleeps before raising TrackerError. No _sleep patch means real backoff occurs. Scan of TestGitHubIssueTrackerMutations confirms no other always-transient-500 pattern — test_create_issue_raises_on_bad_response uses 422 (not retryable). Fix: wrap the HTTP mock with patch.object(tracker._client, '_sleep') and assert call_count for both request (4) and sleep (3).
---
author: oompah
created: 2026-07-28 15:29
---
Implementation: Updated test_remove_label_re_raises_non_404_errors in tests/test_github_tracker.py. Added patch.object(tracker._client, '_sleep') nested inside the HTTP mock context so no real backoff sleeps occur. Added two assertions: mock_http.call_count == _MAX_RETRIES + 1 (all 4 retry attempts made) and mock_sleep.call_count == _MAX_RETRIES (3 sleep calls, one before each retry). 404 no-op and successful DELETE tests are untouched. Scan of TestGitHubIssueTrackerHierarchyAndDependencies confirmed neighboring re_raises_non_404_errors tests use 422 (not retryable) so they need no change.
---
author: oompah
created: 2026-07-28 15:29
---
Verification: Targeted test passes in 0.02s call time (was ~7.3s with real sleeps). Full tests/test_github_tracker.py: 365 passed in 2.17s. make test: 12361 passed, 7 skipped, 13 warnings in 260.82s. All green.
---
author: oompah
created: 2026-07-28 15:29
---
Completion: Delivered a single-file change to tests/test_github_tracker.py. test_remove_label_re_raises_non_404_errors now patches tracker._client._sleep, asserts all 4 retry attempts were made and 3 sleep calls occurred (matching _MAX_RETRIES), and raises TrackerError — all without real waits. Test call time dropped from ~7.3s to 0.02s. No production code changed. Full suite green (12361 passed). Pushed to epic-OOMPAH-490.
---
author: oompah
created: 2026-07-28 15:29
---
Patched _sleep in test_remove_label_re_raises_non_404_errors; test now runs in 0.02s instead of ~7.3s while asserting retry exhaustion and sleep behavior. All 12361 tests pass.
---
author: oompah
created: 2026-07-28 15:29
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/default]
- Turns: 0, Tool calls: 33
- Tokens: 56 in / 1.8K out [1.9K total]
- Cost: $0.0000
- Exit: terminated, Duration: 8m 9s
- Log: OOMPAH-493__20260728T152132Z.jsonl
---
author: oompah
created: 2026-08-04 17:26
---
Queued Archived audit: Aged Merged auto-archive (closed 7 days ago). An auditor will review before the task is retired.
---
<!-- COMMENTS:END -->
