---
id: OOMPAH-452
type: bug
status: In Progress
priority: 1
title: Recover the GitLab Issues tracker implementation onto main
parent: OOMPAH-451
children: []
blocked_by: []
labels:
- focus-complete:duplicate_detector
assignee: null
created_at: '2026-07-28T12:34:50.818103Z'
updated_at: '2026-07-28T12:45:05.716124Z'
work_branch: epic-OOMPAH-451
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: 2b8c3788-ac6e-48d8-b1cd-87c008057920
oompah.work_branch: epic-OOMPAH-451
oompah.task_costs:
  total_input_tokens: 20
  total_output_tokens: 7139
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 20
      output_tokens: 7139
      cost_usd: 0.0
  runs:
  - profile: default
    model: unknown
    input_tokens: 20
    output_tokens: 7139
    cost_usd: 0.0
    recorded_at: '2026-07-28T12:44:39.059331+00:00'
---
## Summary

Problem: OOMPAH-337 through OOMPAH-339 are marked Merged, but current main has no oompah/gitlab_tracker.py and no reachable GitLab Issues tracker registration. Their implementation survives only on origin/epic-OOMPAH-318 after the parent epic merged early.

Implementation scope: selectively reconcile the GitLabIssueTracker adapter, protocol registration, metadata persistence, pagination, relationships, comments, labels, status governance, authorized-actor audit and revert behavior from the stranded commits onto current tracker interfaces. Preserve current GitHub and native Markdown behavior. Relevant files include oompah/gitlab_tracker.py, oompah/tracker.py, oompah/server.py, and tests/test_gitlab_tracker.py.

Tests: restore and update the GitLab tracker contract/lifecycle tests, status authorization tests, pagination and API failure fixtures, plus existing tracker protocol tests; run make test.

Acceptance criteria: tracker_kind=gitlab_issues resolves to a complete TrackerProtocol implementation on main; task and epic lifecycle operations round-trip through GitLab Issues; secrets remain redacted; GitHub and native tracker regressions remain green.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-28 12:41
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-28 12:42
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-28 12:42
---
Understanding: I am the Duplicate Investigator for OOMPAH-452. The issue claims that OOMPAH-337 through OOMPAH-339 (GitLab Issues tracker implementation) were marked Merged but the code never landed on main — it survives only on origin/epic-OOMPAH-318. This task asks to recover gitlab_tracker.py, tracker.py registration, server.py wiring, and tests onto main. My plan: search .oompah/tasks for any overlapping task (especially OOMPAH-337, OOMPAH-338, OOMPAH-339, OOMPAH-318, and any other gitlab-tracker recovery tasks), read their full descriptions/comments, and determine if OOMPAH-452 duplicates any of them or is a genuinely new recovery task.
---
author: oompah
created: 2026-07-28 12:44
---
Focus handoff: duplicate_detector

1. **Outcome**: OOMPAH-452 is NOT a duplicate. No existing open task covers the same ground.

2. **Evidence and key findings**:
   - Searched .oompah/tasks/ (all states), docs/, plans/, README.md, WORKFLOW.md for: gitlab, GitLabIssueTracker, gitlab_issues, recover, recovery, stranded, reconcile — no matching open/backlog tasks cover recovering gitlab_tracker.py onto main.
   - Confirmed the gap: `oompah/gitlab_tracker.py` does NOT exist on current HEAD (git log tip: 6657f40c6, OOMPAH-450 merge). `tests/test_gitlab_tracker.py` also absent. `gitlab_issues`/`gitlab-issues` not registered in `oompah/tracker.py`.
   - The original implementation (OOMPAH-337, 338, 339 — children of OOMPAH-323) IS marked Merged, and those agents confirmed all 11000+ tests passed and pushed to `origin/epic-OOMPAH-323`.
   - Root cause of the gap: PR #533 merged `epic-OOMPAH-318` → `main` at 2026-07-22 08:21. PR #534 (OOMPAH-323's branch into epic-OOMPAH-318) merged at 2026-07-22 22:27 — AFTER main had already moved on. The GitLab tracker commits (oompah/gitlab_tracker.py, tests/test_gitlab_tracker.py, oompah/tracker.py registry, oompah/server.py, oompah/webhooks.py governance) are stranded on origin/epic-OOMPAH-318 and were never rebased/cherry-picked onto main.
   - OOMPAH-452 is a legitimate recovery task under OOMPAH-451 (recovery epic), not a duplicate of the original implementation tasks.

3. **Relevant commits to recover** (from OOMPAH-323 history on origin/epic-OOMPAH-318):
   - The description of OOMPAH-451 identifies commits: 24ae25693, 696d5bfaa, 2b3312672, 4302b74e8, 62cde900b
   - Files: oompah/gitlab_tracker.py (792 lines, GitLabIssueTracker full TrackerProtocol + status governance), oompah/tracker.py (registry for 'gitlab_issues'/'gitlab-issues'), oompah/server.py (status-label guard extensions), oompah/webhooks.py (parse_gitlab_webhook Issue Hook + label governance), tests/test_gitlab_tracker.py (1463+ lines, 115+ tests)

4. **Remaining work**: Selectively cherry-pick or reconstruct the GitLabIssueTracker adapter (oompah/gitlab_tracker.py), protocol registration (oompah/tracker.py), status governance wiring (oompah/server.py, oompah/webhooks.py), and tests (tests/test_gitlab_tracker.py) onto current main. Run `make test` to verify no regressions. Push and close.

5. **Recommended next focus**: feature (backend implementation — cherry-pick or re-implement the stranded code onto current tracker interfaces).
---
author: oompah
created: 2026-07-28 12:44
---
Agent completed successfully in 163s (7159 tokens)
---
author: oompah
created: 2026-07-28 12:44
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/default]
- Turns: 45, Tool calls: 31
- Tokens: 20 in / 7.1K out [7.2K total]
- Cost: $0.0000
- Exit: normal, Duration: 2m 43s
- Log: OOMPAH-452__20260728T124200Z.jsonl
---
author: oompah
created: 2026-07-28 12:44
---
Focus handoff from `duplicate_detector` is complete. Queued a fresh agent run for the next applicable focus. The next agent should begin with the preceding Focus handoff comment.
---
author: oompah
created: 2026-07-28 12:44
---
Agent dispatched (profile: deep)
---
author: oompah
created: 2026-07-28 12:44
---
Focus: Maintenance Engineer
---
author: oompah
created: 2026-07-28 12:45
---
Understanding: I am the Maintenance Engineer for OOMPAH-452. The previous duplicate-detector confirmed this is a legitimate recovery task — the GitLab Issues tracker implementation (oompah/gitlab_tracker.py, tests/test_gitlab_tracker.py, tracker.py registry, server.py wiring, webhooks.py governance) was implemented in OOMPAH-337-339 but got stranded on origin/epic-OOMPAH-318 and never landed on main.

Plan:
1. Fetch origin/epic-OOMPAH-318 and examine the stranded commits (24ae25693, 696d5bfaa, 2b3312672, 4302b74e8, 62cde900b)
2. Cherry-pick or selectively apply the relevant files onto current branch
3. Resolve any conflicts with current interfaces (tracker.py, server.py, webhooks.py have evolved)
4. Run make test to verify no regressions
5. Commit and push
---
<!-- COMMENTS:END -->
