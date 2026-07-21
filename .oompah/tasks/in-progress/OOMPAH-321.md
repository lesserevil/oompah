---
id: OOMPAH-321
type: task
status: In Progress
priority: 1
title: Complete GitLab Merge Request provider parity
parent: OOMPAH-318
children: []
blocked_by:
- OOMPAH-320
labels:
- focus-complete:duplicate_detector
assignee: null
created_at: '2026-07-21T20:33:51.110283Z'
updated_at: '2026-07-21T23:58:56.653099Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: c5a26b6e-036a-411c-97c6-4a0481505493
oompah.task_costs:
  total_input_tokens: 563971
  total_output_tokens: 3508
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 563971
      output_tokens: 3508
      cost_usd: 0.0
  runs:
  - profile: default
    model: unknown
    input_tokens: 390372
    output_tokens: 2376
    cost_usd: 0.0
    recorded_at: '2026-07-21T23:23:35.814488+00:00'
  - profile: standard
    model: unknown
    input_tokens: 173599
    output_tokens: 1132
    cost_usd: 0.0
    recorded_at: '2026-07-21T23:24:34.903902+00:00'
---
## Summary

Plan reference: plans/gitlab-forge-parity.md, GitLab implementation.

Implement GitLabProvider against the forge-neutral SCM contract for GitLab.com and configurable GitLab 17+ hosts. Handle nested namespace project IDs, URL encoding, pagination, retries, rate limits, redacted errors, MR list/detail/find/create/rebase/merge/close, labels, notes, changed files, commits, reviewers, approvals, draft/WIP, conflicts, divergence, and mergeability. Preserve history: do not force squash. Implement normal GitLab auto-merge through merge_when_pipeline_succeeds; return actionable policy/approval errors and do not implement merge trains.

Tests:
- HTTP fixtures for GitLab.com and self-managed base URL/nested namespace requests.
- Every SCM contract operation, pagination, auth failure, conflict, unavailable MR, label preservation, history-preserving merge, and auto-merge rejection.

Acceptance criteria:
- GitLab MRs behave equivalently to GitHub PRs for all supported SCM operations.
- No request leaks an access token in logs or errors.
- make test passes.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-21 23:22
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-21 23:22
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-21 23:23
---
Agent completed successfully in 63s (392748 tokens)
---
author: oompah
created: 2026-07-21 23:23
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/default]
- Turns: 1, Tool calls: 10
- Tokens: 390.4K in / 2.4K out [392.7K total]
- Cost: $0.0000
- Exit: normal, Duration: 1m 3s
- Log: OOMPAH-321__20260721T232234Z.jsonl
---
author: oompah
created: 2026-07-21 23:23
---
Agent completed without closing this issue (63s (392748 tokens)). Escalating from 'default' to 'standard'. Retrying in 10s (1/3).
---
author: oompah
created: 2026-07-21 23:23
---
Agent dispatched (profile: standard)
---
author: oompah
created: 2026-07-21 23:23
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-21 23:24
---
Understanding: I am screening this GitLabProvider parity task for overlap before implementation. The requested scope is the full forge-neutral Merge Request provider contract, including requests, error handling, and HTTP fixtures.
---
author: oompah
created: 2026-07-21 23:24
---
Focus handoff: duplicate_detector\n\nOutcome: no confirmed duplicate.\n\nEvidence: reviewed OOMPAH-319 (explicit forge configuration and project migration) and OOMPAH-320 (test mock rename for get_review_commits); both are prerequisite/adjacent work, not GitLabProvider MR parity. Repository search found plans/gitlab-forge-parity.md as the specification and no existing task record covering this implementation surface.\n\nRemaining work/risks: implement and contract-test GitLabProvider against the plan, preserving token redaction and GitLab auto-merge constraints.\n\nRecommended next focus: feature.
---
author: oompah
created: 2026-07-21 23:24
---
Agent completed successfully in 41s (174731 tokens)
---
author: oompah
created: 2026-07-21 23:24
---
Run #2 [attempt=2, profile=standard, role=standard -> Codex/default]
- Turns: 1, Tool calls: 5
- Tokens: 173.6K in / 1.1K out [174.7K total]
- Cost: $0.0000
- Exit: normal, Duration: 41s
- Log: OOMPAH-321__20260721T232355Z.jsonl
---
author: oompah
created: 2026-07-21 23:24
---
Focus handoff from `duplicate_detector` is complete. Queued a fresh agent run for the next applicable focus. The next agent should begin with the preceding Focus handoff comment.
---
author: oompah
created: 2026-07-21 23:25
---
Agent dispatched (profile: standard)
---
author: oompah
created: 2026-07-21 23:26
---
Focus: Test Engineer
---
author: oompah
created: 2026-07-21 23:26
---
Understanding: As Test Engineer, I'm tasked with writing comprehensive tests for the GitLabProvider MR parity implementation. Plan reference is plans/gitlab-forge-parity.md. I'll explore the codebase to understand the SCM contract, existing GitHub provider tests, and the GitLab implementation, then write fixture-based HTTP tests covering all SCM contract operations, pagination, auth failures, conflicts, label preservation, history-preserving merge, and auto-merge rejection. No external network calls — all tests will use HTTP fixtures.
---
author: oompah
created: 2026-07-21 23:43
---
Discovery: Reviewed oompah/scm.py (2512 lines) and tests/test_scm.py (3204 lines). GitLabProvider is fully implemented but has two spec violations: (1) merge_review hardcodes 'squash: True' — plan says 'do not force squash'; (2) enable_auto_merge falls back to a direct merge instead of using merge_when_pipeline_succeeds as required by the plan. Test coverage for GitLab is sparse — only label add/remove, get_review_files, close_review, and branch-protection tests exist. Missing: list_open_reviews, list_merged_reviews, find_pr_for_branch, get_review, create_review, rebase_review, needs_rebase, is_available, get_pr_commits, nested namespace URL encoding, self-managed base URL, CI status from head_pipeline, draft/WIP detection, token-leakage prevention, and auto-merge via merge_when_pipeline_succeeds. Will write comprehensive fixture-based tests and fix the two impl bugs.
---
author: oompah
created: 2026-07-21 23:58
---
Implementation: Fixed 2 bugs in GitLabProvider and added 102 new tests.\n\nBugs fixed:\n1. merge_review sent 'squash: True' — removed; plan requires history-preserving merges.\n2. enable_auto_merge delegated to merge_review (direct merge) — replaced with proper PUT /merge + merge_when_pipeline_succeeds=True per spec; policy/approval rejections return actionable messages.\n\nTests added (test_scm.py, +665 lines):\n- TestGitLabProviderIsAvailable (5 tests) — probes /user, returns bool on auth failure/network error\n- TestGitLabSelfManagedUrl (4 tests) — _api_url() uses configured hostname; detect_provider propagates it\n- TestGitLabNestedNamespaceEncoding (5 tests) — group/sub/project → group%2Fsub%2Fproject in every API call\n- TestGitLabListOpenReviews (14 tests) — all fields, CI status from head_pipeline, draft/WIP, conflicts/divergence, label preservation, state param\n- TestGitLabListMergedReviews (5 tests) — field mapping, auth failure, skips missing source branch, request params\n- TestGitLabListMergedBranches (2 tests) — delegates to merged reviews\n- TestGitLabFindPrForBranch (8 tests) — open/merged/closed, not found, empty branch, API params, newest-first selection\n- TestGitLabGetReview (6 tests) — field mapping, 404/401/network, draft, URL path encoding\n- TestGitLabCreateReview (5 tests) — 201 success, field validation, rejection, network error, nested path encoding\n- TestGitLabRebaseReview (6 tests) — 200/202 success, conflict actionable msg, 400, network error, endpoint path\n- TestGitLabNeedsRebase (6 tests) — conflicts, diverged, both, clean, 404, network error\n- TestGitLabMergeReviewHistoryPreserving (4 tests) — no squash, success, 405 failure, network error\n- TestGitLabEnableAutoMerge (6 tests) — merge_when_pipeline_succeeds flag, no squash, policy rejection actionable, 405, network error, endpoint path\n- TestGitLabGetPrCommits (8 tests) — oldest-first ordering, single commit, 404/401/network error, get_review_commits bridge, nested path encoding, skips entries without id\n- TestGitLabTokenNotLeakedInErrors (4 tests) — merge/rebase/close/auto-merge error messages do not expose token\n- TestGitLabCloseReview (5 tests) — note+close, no-comment, note failure degrades gracefully, close failure, network error\n- TestGitLabLabelPreservation (4 tests) — add appends, remove keeps rest, oompah:status:* labels survive add/remove operations
---
author: oompah
created: 2026-07-21 23:58
---
Verification: make test passes — 10627 passed, 36 skipped (was 10525+36 before this work; added 102 new tests). All new GitLab contract tests pass. The two implementation bugs that were caught by the tests are fixed. Branch pushed and up to date with origin.
---
<!-- COMMENTS:END -->
