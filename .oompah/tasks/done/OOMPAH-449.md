---
id: OOMPAH-449
type: task
status: Done
priority: null
title: Do not merge a newly updated PR before its CI checks register
parent: null
children: []
blocked_by: []
labels:
- focus-complete:duplicate_detector
assignee: null
created_at: '2026-07-26T04:35:24.362802Z'
updated_at: '2026-07-26T18:48:45.159281Z'
work_branch: OOMPAH-449
target_branch: main
review_url: https://github.com/lesserevil/oompah/pull/556
review_number: '556'
merged_at: null
oompah.agent_run_id: 0ba8b49d-c198-488a-a9f5-0eaa9016b551
oompah.task_costs:
  total_input_tokens: 103
  total_output_tokens: 33427
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 103
      output_tokens: 33427
      cost_usd: 0.0
  runs:
  - profile: default
    model: unknown
    input_tokens: 15
    output_tokens: 3834
    cost_usd: 0.0
    recorded_at: '2026-07-26T18:17:55.482900+00:00'
  - profile: standard
    model: unknown
    input_tokens: 27
    output_tokens: 934
    cost_usd: 0.0
    recorded_at: '2026-07-26T18:20:29.009962+00:00'
  - profile: default
    model: unknown
    input_tokens: 61
    output_tokens: 28659
    cost_usd: 0.0
    recorded_at: '2026-07-26T18:35:06.772616+00:00'
oompah.review_url: https://github.com/lesserevil/oompah/pull/556
oompah.review_number: '556'
oompah.work_branch: OOMPAH-449
oompah.target_branch: main
---
## Summary

Triggered by PR #555 / OOMPAH-447.

Problem
At 2026-07-26 04:26:36-04:26:37 UTC, PR #555 received head ed815c908 and a synchronize webhook. Oompah queried combined status and check-runs at 04:26:39; both APIs returned successfully but the new workflow run had not registered yet. The workflow was created at 04:26:40 and jobs started at 04:26:42, while YOLO merged the PR at 04:26:43. GitHub logs confirm the replacement matrix did not finish until 04:32:58. GitHubProvider._fetch_ci_status_and_warnings currently returns passed when both APIs report zero checks, and the YOLO gate accepts passed/empty, creating a post-push race that bypasses CI.

Implementation
Make an empty check set fail closed for a recently created or synchronized PR head when the repository/PR is known to use CI. Preserve legitimate YOLO merging for repositories with no CI configured. Use authoritative head-SHA and review/update timing or a bounded observation state/grace period so a new SHA must either acquire checks and reach passed, or be positively classified as no-CI. Invalidate any prior-head CI verdict on synchronize. Relevant code: oompah/scm.py GitHubProvider._fetch_ci_status_and_warnings and list_open_reviews, oompah/orchestrator.py YOLO merge gate, webhook/cache refresh paths.

Tests
Add a regression sequence for old SHA failed -> synchronize to new SHA -> successful empty status/check-runs response -> checks later pending -> passed. Assert no merge/enqueue occurs during the empty registration window and merge becomes eligible only after the new SHA passes. Add a true no-CI repository case that remains mergeable and a stale prior-SHA verdict case. Run make test.

Acceptance Criteria
- A PR head update can never inherit or synthesize a passed CI verdict before checks for that exact SHA register.
- YOLO does not merge or enqueue during the post-synchronize empty-check race.
- Once required checks for the current SHA pass, normal YOLO delivery resumes.
- Repositories positively known to have no CI retain their current automatic merge behavior.
- Tests reproduce the PR #555 timestamp ordering and make test passes.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-26 18:16
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-26 18:16
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-26 18:16
---
Understanding: Investigating OOMPAH-449 as Duplicate Investigator. The issue describes a race condition where YOLO merge fires before CI checks register for a newly synchronized PR head SHA. After a synchronize webhook, oompah queries GitHub's status/check-run APIs and gets empty results (checks haven't registered yet), which currently maps to 'passed', allowing premature merge. My plan: search existing tasks for similar problems around CI check racing, empty check sets, YOLO gate, synchronize webhooks, and head SHA verdicts. Will check any candidates thoroughly before handing off to an implementation agent.
---
author: oompah
created: 2026-07-26 18:17
---
Focus handoff: duplicate_detector

**Outcome:** No duplicate found. OOMPAH-449 is a genuinely new issue.

**Evidence reviewed:**
- Searched all task states (open, backlog, archived, merged) for: synchronize, YOLO merge, empty check, CI race, head SHA, check register, fail closed, grace period, post-push race, zero checks, bypass CI, premature merge, prior-head verdict.
- Closest candidate: **OOMPAH-210** (Archived) — also touches `_fetch_ci_status_and_warnings` in `oompah/scm.py`, but covers a completely different root cause: HTTP 403 from check-runs API silently falling through, not empty check sets being treated as passed post-synchronize.
- No other task mentions: (1) empty check set returning 'passed', (2) CI checks not yet registered for a new head SHA, (3) grace period / bounded observation state, (4) invalidating prior-head verdicts on synchronize webhook, or (5) PR #555's specific race window.

**Relevant files (per description):**
- `oompah/scm.py` — `GitHubProvider._fetch_ci_status_and_warnings`, `list_open_reviews`
- `oompah/orchestrator.py` — YOLO merge gate, webhook/cache refresh paths
- `tests/` — regression tests for the race sequence (old SHA failed → synchronize → empty → pending → passed)

**Remaining work:**
1. Make empty check set fail-closed for recently synchronized PR heads when repo is known to use CI
2. Preserve legitimate YOLO merging for no-CI repos
3. Invalidate prior-head CI verdict on synchronize
4. Add regression tests per the acceptance criteria
5. Run `make test`

**Recommended next focus:** `feature` (backend CI gate fix in `oompah/scm.py` and `oompah/orchestrator.py`)
---
author: oompah
created: 2026-07-26 18:17
---
Agent completed successfully in 93s (3849 tokens)
---
author: oompah
created: 2026-07-26 18:17
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/default]
- Turns: 30, Tool calls: 21
- Tokens: 15 in / 3.8K out [3.8K total]
- Cost: $0.0000
- Exit: normal, Duration: 1m 33s
- Log: OOMPAH-449__20260726T181624Z.jsonl
---
author: oompah
created: 2026-07-26 18:17
---
Focus handoff from `duplicate_detector` is complete. Queued a fresh agent run for the next applicable focus. The next agent should begin with the preceding Focus handoff comment.
---
author: oompah
created: 2026-07-26 18:18
---
Agent dispatched (profile: standard)
---
author: oompah
created: 2026-07-26 18:18
---
Focus: DevOps Engineer
---
author: oompah
created: 2026-07-26 18:18
---
Understanding: Implementing the CI check race condition fix as DevOps Engineer. The bug: after a PR synchronize webhook, oompah queries GitHub's status/check-run APIs and gets empty results (checks not yet registered), which maps to 'passed', allowing YOLO to merge before CI runs. My plan: (1) explore oompah/scm.py and oompah/orchestrator.py to understand current CI verdict logic, (2) implement fail-closed behavior for empty check sets on recently-synchronized PRs when repo has CI history, (3) preserve no-CI repo behavior, (4) invalidate prior-head verdicts on synchronize, (5) add regression tests covering the PR #555 race sequence, (6) run make test.
---
author: oompah
created: 2026-07-26 18:20
---
Run #1 [attempt=1, profile=standard, role=standard -> Claude/default]
- Turns: 0, Tool calls: 18
- Tokens: 27 in / 934 out [961 total]
- Cost: $0.0000
- Exit: terminated, Duration: 2m 22s
- Log: OOMPAH-449__20260726T181810Z.jsonl
---
author: oompah
created: 2026-07-26 18:21
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-26 18:21
---
Focus: DevOps Engineer
---
author: oompah
created: 2026-07-26 18:21
---
Understanding: Implementing the CI check race condition fix. The bug: after a PR synchronize webhook, oompah queries GitHub's check-run/status APIs too quickly, gets empty results (checks not yet registered), which maps to 'passed', allowing YOLO to merge before CI runs.

My plan:
1. Read oompah/scm.py and oompah/orchestrator.py to understand current CI verdict logic
2. Implement fail-closed behavior: empty check set for a recently-synchronized SHA = 'pending', not 'passed', when the repo has CI history
3. Track head-SHA and synchronize timestamps to detect the race window
4. Invalidate prior-head CI verdicts on synchronize
5. Add regression tests for the PR #555 race sequence
6. Run make test and push
---
author: oompah
created: 2026-07-26 18:26
---
Discovery: Found the root cause in oompah/scm.py GitHubProvider._fetch_ci_status_and_warnings (lines ~987-1130).

Root cause:
- When both `/commits/{sha}/status` (total_count=0) and `/commits/{sha}/check-runs` (empty array) return empty results, the function returns `'passed', warnings`
- The YOLO gate at orchestrator.py:~11530 allows merge when `ci_ok = review.ci_status in ('passed', '', None)`
- After a synchronize webhook, GitHub Actions workflows typically register 3-6 seconds after the push - within this window, oompah polls and gets empty results → returns 'passed' → YOLO merges immediately

Fix approach:
- Add class-level `_ci_active_repos` set to `GitHubProvider`
- When non-empty check-runs are found for any SHA in a repo: mark that repo as 'CI-active'
- When empty check-runs are found for a CI-active repo: return 'pending' (fail-closed) instead of 'passed'
- When empty check-runs for a non-CI repo (never seen checks): return 'passed' (preserves no-CI repo behavior)
- CI status is always fetched per-SHA, so there's no stale verdict from prior heads to worry about

Files to change:
- oompah/scm.py: Add _ci_active_repos class cache, update _fetch_ci_status_and_warnings
- tests/test_scm.py: Update test_no_statuses_and_no_check_runs_are_eligible_to_merge, add new tests
- tests/test_ci_sync_race.py: Add regression sequence for PR #555 timestamp ordering
---
author: oompah
created: 2026-07-26 18:34
---
Implementation: Fixed the post-synchronize CI race condition.

Changes made:

**oompah/scm.py** (`GitHubProvider`):
- Added class-level `_ci_active_repos: set[str]` and `_ci_active_repos_lock` cache to track repos that have had non-empty CI check-runs observed during the process lifetime.
- In `_fetch_ci_status_and_warnings`: when non-empty check-runs are found, add the repo to `_ci_active_repos`. When both APIs return empty results (no checks registered yet), check if the repo is in `_ci_active_repos`: if yes, return `'pending'` (fail-closed) instead of `'passed'`.
- Repos NOT in `_ci_active_repos` (never seen with checks) still return `'passed'` for empty check sets, preserving no-CI YOLO behavior.

**tests/test_scm.py**:
- Updated `test_no_statuses_and_no_check_runs_are_eligible_to_merge` to properly isolate `_ci_active_repos` state.
- Added `test_known_ci_repo_empty_checks_returns_pending`: CI-active repo + empty checks → 'pending'.
- Added `test_non_empty_check_runs_register_repo_as_ci_active`: seeing checks marks the repo.

**tests/test_ci_sync_race.py** (new):
- Full regression sequence for PR #555 timeline (old SHA failed → synchronize → empty → pending → passed).
- No-CI repo: empty checks → 'passed' → YOLO merges (preserved behavior).
- Stale prior-SHA verdict: new SHA evaluated independently (no inheritance).
- YOLO gate: `pending` blocks merge, `passed` allows merge.
- Full sequence test: no premature merge across all 4 phases.

Why the fix works: the YOLO gate checks `ci_ok = review.ci_status in ('passed', '', None)`. 'pending' is not in this set, so YOLO cannot merge during the empty check window.
---
author: oompah
created: 2026-07-26 18:34
---
Verification: make test passed — 12113 passed, 39 skipped, 12 warnings in 250s.

All 10 new tests pass:
- TestCISyncRaceGuard (6 tests): direct unit tests for the race guard
  - No-CI repo empty checks → 'passed' (preserved behavior)
  - Known-CI repo empty checks → 'pending' (fail-closed)
  - Non-empty checks mark repo as CI-active
  - PR #555 sequence: empty window returns pending
  - Stale prior-SHA verdict not inherited
  - Legacy failure + empty checks still fails
- TestYoloGateCiSyncRace (4 tests): orchestrator-level YOLO gate
  - pending CI blocks merge
  - No-CI repo (ci_status='passed') merges immediately
  - Passed CI triggers merge
  - Full PR #555 sequence: no premature merge across 4 phases
---
author: oompah
created: 2026-07-26 18:34
---
Completion: OOMPAH-449 delivered.

Root cause: GitHubProvider._fetch_ci_status_and_warnings returned 'passed' when both /commits/{sha}/status and /commits/{sha}/check-runs returned empty results. GitHub Actions workflows typically register 3-6 seconds after a push, creating a window where a newly-synchronized PR SHA had no checks but was treated as passing CI.

Fix: Added class-level _ci_active_repos tracking to GitHubProvider. Repos that have had non-empty check-runs at any point in the process lifetime are marked CI-active. For CI-active repos, empty check sets return 'pending' (fail-closed) instead of 'passed'. No-CI repos (never seen with checks) retain the 'passed' behavior.

Files changed:
- oompah/scm.py: _ci_active_repos cache + fail-closed logic (21 lines added)
- tests/test_scm.py: 3 tests updated/added
- tests/test_ci_sync_race.py: 10-test regression suite (new file)

All 12113 tests pass. Branch pushed to origin/OOMPAH-449.
---
author: oompah
created: 2026-07-26 18:34
---
Fixed post-synchronize CI check race: GitHubProvider now tracks CI-active repos and fails closed (returns 'pending' instead of 'passed') when empty check sets are observed for repos known to use CI. All 12113 tests pass. Regression test suite added in tests/test_ci_sync_race.py.
---
author: oompah
created: 2026-07-26 18:35
---
Agent completed successfully in 841s (28720 tokens)
---
author: oompah
created: 2026-07-26 18:35
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/default]
- Turns: 104, Tool calls: 64
- Tokens: 61 in / 28.7K out [28.7K total]
- Cost: $0.0000
- Exit: normal, Duration: 14m 1s
- Log: OOMPAH-449__20260726T182107Z.jsonl
---
author: oompah
created: 2026-07-26 18:35
---
Close refused by orchestrator: branch `OOMPAH-449` has 1 commit not on `main` and no open PR targets `main` from this branch.

Diagnostic:
  Unmerged commits: 1
    bc3f6e876 OOMPAH-449: Fail-closed on empty CI checks for known-CI repos
  Open PRs from this branch: 0
  Merged PRs from this branch: 0

Required: open a PR before closing.
  gh pr create --base main --head OOMPAH-449 --title "OOMPAH-449: Do not merge a newly updated PR before its CI checks register" --body "..."

Task reopened. Re-dispatch on the next tick will see this comment in its prompt context.
---
author: oompah
created: 2026-07-26 18:35
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-26 18:35
---
Focus: DevOps Engineer
---
author: oompah
created: 2026-07-26 18:35
---
Understanding: Prior work implemented and verified the CI registration race fix, committed it as bc3f6e876, and pushed branch OOMPAH-449. Closure was refused only because no PR targets main. I will verify the branch/test evidence and remote state, create the required PR, confirm the worktree is clean and up to date, then close the task.
---
author: oompah
created: 2026-07-26 18:37
---
Discovery: The pushed implementation has a cold-start gap and does not yet meet the acceptance criteria.  only knows about check-runs observed during the current process; immediately after a service restart, a synchronized CI-enabled PR can still receive empty status/check-run responses and be classified . Conversely,  is not a positive no-CI classification. I am replacing this with a bounded per-PR head-SHA registration observation in : a newly created or changed head fails closed while its exact SHA is within a configurable grace period; a head with no checks becomes no-CI eligible only after that bounded observation. Head changes reset the observation, preventing prior-SHA reuse.
---
author: oompah
created: 2026-07-26 18:38
---
Discovery correction: The pushed implementation has a cold-start gap and does not yet meet the acceptance criteria. The ci-active repository set only knows about check-runs observed during the current process; immediately after a service restart, a synchronized CI-enabled PR can still receive empty status/check-run responses and be classified passed. Conversely, never observed is not a positive no-CI classification. I am replacing this with a bounded per-PR head-SHA registration observation in list_open_reviews: a newly created or changed head fails closed while its exact SHA is within a configurable grace period; a head with no checks becomes no-CI eligible only after that bounded observation. Head changes reset the observation, preventing prior-SHA reuse.
---
author: oompah
created: 2026-07-26 18:47
---
Implementation: Replaced the process-lifetime ci-active repository heuristic with a bounded, class-level CI observation keyed by repository and PR number, storing the exact head SHA and first successful empty-check observation. list_open_reviews now requests an internal empty-set signal, returns pending for the configurable 60-second registration window, resets the window whenever head.sha changes, and returns passed only after that exact SHA remains check-free for the full window. Closed PR observations are pruned. Added OOMPAH_CI_REGISTRATION_GRACE_SECONDS to .env.example and rewrote regression coverage around real list_open_reviews plus direct and merge-queue YOLO gates.
---
author: oompah
created: 2026-07-26 18:47
---
Verification: Focused SCM and CI-race suite passed: 294 passed in 0.67s. Full make test gate passed: 12111 passed, 39 skipped, 13 warnings in 238.97s. The host uv snap launcher could not create its systemd transient scope, so make test was run with a process-local uv-run shim targeting the existing project .venv; the repository and dependencies were not modified by the workaround. git diff --check also passes.
---
author: oompah
created: 2026-07-26 18:48
---
Completion: Delivered and pushed the head-SHA-aware bounded CI registration guard in commits bc3f6e876 and 26272e5c7. PR #556 is open against main: https://github.com/lesserevil/oompah/pull/556. Empty checks for a new/synchronized exact SHA now block both merge and enqueue; registered pending checks remain blocked; passed checks resume delivery; a truly check-free SHA becomes no-CI eligible after the configured grace. Full make test passed with 12111 passed and 39 skipped. Branch is clean and up to date with origin.
---
author: oompah
created: 2026-07-26 18:48
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/default]
- Turns: 0, Tool calls: 36
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: terminated, Duration: 13m 25s
- Log: OOMPAH-449__20260726T183522Z.jsonl
---
author: oompah
created: 2026-07-26 18:48
---
Implemented a head-SHA-aware bounded CI registration guard, added regression coverage for PR #555 and no-CI behavior, passed the full 12111-test suite, pushed the branch, and opened PR #556.
---
<!-- COMMENTS:END -->
