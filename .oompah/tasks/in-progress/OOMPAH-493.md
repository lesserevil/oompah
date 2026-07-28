---
id: OOMPAH-493
type: task
status: In Progress
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
updated_at: '2026-07-28T15:21:12.956331Z'
work_branch: epic-OOMPAH-490
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: f75e1b31-5fdd-47e1-a383-1fa4b1843e47
oompah.work_branch: epic-OOMPAH-490
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
<!-- COMMENTS:END -->
