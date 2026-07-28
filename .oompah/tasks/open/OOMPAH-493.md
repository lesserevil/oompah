---
id: OOMPAH-493
type: task
status: Open
priority: 1
title: Remove real retry sleeps from GitHub tracker error tests
parent: OOMPAH-490
children: []
blocked_by:
- OOMPAH-491
labels: []
assignee: null
created_at: '2026-07-28T13:53:28.451050Z'
updated_at: '2026-07-28T14:35:25.255013Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
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

