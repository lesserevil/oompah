---
id: OOMPAH-322
type: task
status: In Progress
priority: 1
title: Add GitLab pipeline and commit CI status support
parent: OOMPAH-318
children: []
blocked_by:
- OOMPAH-321
labels:
- focus-complete:duplicate_detector
assignee: null
created_at: '2026-07-21T20:33:52.275830Z'
updated_at: '2026-07-22T00:02:31.344103Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: 2abe0594-12ab-4145-84f4-c6ba45789f8d
oompah.task_costs:
  total_input_tokens: 30
  total_output_tokens: 6937
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 30
      output_tokens: 6937
      cost_usd: 0.0
  runs:
  - profile: default
    model: unknown
    input_tokens: 30
    output_tokens: 6937
    cost_usd: 0.0
    recorded_at: '2026-07-22T00:01:59.525916+00:00'
---
## Summary

Plan reference: plans/gitlab-forge-parity.md, GitLab implementation.

Implement GitLab pipeline/job lookup for branch heads, commit SHAs, and MRs using the forge-neutral CI contract. Normalize pipeline/job outcomes to passed, failed, pending, or unknown; include bounded actionable warnings and job/pipeline URLs. Support self-managed GitLab API bases.

Do not wire orchestration behavior in this task; expose provider methods and tests only.

Tests:
- Success, failure, canceled, skipped, running, pending, no-pipeline, forbidden, rate-limited, and malformed-response fixtures.
- Multiple pipeline/job aggregation and deterministic warning ordering.
- Contract parity assertions against the GitHub CI result shape.

Acceptance criteria:
- Callers can determine GitLab CI state for a MR, branch, or commit without parsing provider payloads.
- Unavailable CI permissions are visible as capability warnings, not false success.
- make test passes.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-21 23:59
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-21 23:59
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-22 00:01
---
Understanding: I am screening OOMPAH-322 (GitLab pipeline/commit CI status support) for duplicates before any implementation begins. The task requests implementing get_branch_head_sha and get_ci_status_for_sha on GitLabProvider, normalizing GitLab pipeline outcomes to the CIStatus enum (passed/failed/pending/unknown), adding bounded warnings and pipeline URLs, and full fixture-based test coverage. Closest candidate for overlap: OOMPAH-321 (GitLab MR provider parity, now Done).
---
author: oompah
created: 2026-07-22 00:01
---
Focus handoff: duplicate_detector

Outcome: No confirmed duplicate. OOMPAH-322 is NOT a duplicate of OOMPAH-321 or any other task.

Evidence:
- Closest candidate: OOMPAH-321 (Done) covered GitLabProvider MR parity — it reads CI status passively from head_pipeline when listing MRs, but does NOT implement get_branch_head_sha or get_ci_status_for_sha on GitLabProvider.
- GitLabProvider (oompah/scm.py line 1873) has no implementations of get_branch_head_sha or get_ci_status_for_sha — both fall back to base class stubs (return None / CIStatus.UNKNOWN).
- GitHubProvider does implement both (lines 1814 and 1853), confirming the gap.
- No other task in .oompah/tasks/ (archived, done, merged, backlog) covers GitLab CI pipeline/commit SHA lookup.
- tests/test_scm.py confirms: there are no TestGitLab*CI, TestGitLab*Pipeline, TestGitLab*BranchHead, or TestGitLab*CommitSha test classes.

Remaining work:
1. Implement get_branch_head_sha on GitLabProvider (call GET /projects/:id/repository/branches/:branch, extract commit.id).
2. Implement get_ci_status_for_sha on GitLabProvider (call GET /projects/:id/pipelines?sha=:sha, normalize pipeline statuses to CIStatus enum; also GET /projects/:id/pipelines/:id/jobs for job-level detail).
3. Add bounded CapabilityWarning for forbidden/rate-limited/malformed cases.
4. Expose pipeline/job web URLs in warnings.
5. Support self-managed GitLab API bases (already done via _api_url() in GitLabProvider).
6. Comprehensive fixture-based tests per acceptance criteria: success, failure, canceled, skipped, running, pending, no-pipeline, forbidden, rate-limited, malformed-response, multiple pipelines/jobs aggregation, warning ordering, and contract parity with GitHub CI result shape.

Key files: oompah/scm.py (GitLabProvider at line 1873), tests/test_scm.py.
Plan reference: plans/gitlab-forge-parity.md.
Contract shape: CIStatus enum (passed/failed/pending/unknown), CapabilityWarning TypedDict.

Recommended next focus: feature
---
author: oompah
created: 2026-07-22 00:02
---
Agent completed successfully in 151s (6967 tokens)
---
author: oompah
created: 2026-07-22 00:02
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/default]
- Turns: 53, Tool calls: 41
- Tokens: 30 in / 6.9K out [7.0K total]
- Cost: $0.0000
- Exit: normal, Duration: 2m 31s
- Log: OOMPAH-322__20260721T235931Z.jsonl
---
author: oompah
created: 2026-07-22 00:02
---
Focus handoff from `duplicate_detector` is complete. Queued a fresh agent run for the next applicable focus. The next agent should begin with the preceding Focus handoff comment.
---
author: oompah
created: 2026-07-22 00:02
---
Agent dispatched (profile: standard)
---
author: oompah
created: 2026-07-22 00:02
---
Focus: Test Engineer
---
author: oompah
created: 2026-07-22 00:02
---
Understanding: I am covering the GitLab CI provider contract with deterministic, fixture-style unit tests. I will inspect the existing SCM test patterns and GitHub CI contract, add behavior-level coverage for pipeline outcomes and capability failures, run the relevant Make target, then hand off implementation work with findings.
---
<!-- COMMENTS:END -->
