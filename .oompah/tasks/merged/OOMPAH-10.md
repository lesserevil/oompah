---
id: OOMPAH-10
type: bug
status: Merged
priority: 1
title: Fix native markdown tracker default-branch sync failures
parent: null
children: []
blocked_by: []
labels:
- bug
- native-tracker
- dispatch
- git-sync
assignee: null
created_at: '2026-06-20T02:43:17.381453Z'
updated_at: '2026-06-20T03:08:21.427507Z'
work_branch: OOMPAH-10
target_branch: main
review_url: https://github.com/lesserevil/oompah/pull/336
review_number: '336'
merged_at: null
oompah.agent_run_id: e11e3b9d-d625-45d0-b56e-65b58d4f37d0
oompah.task_costs:
  total_input_tokens: 79
  total_output_tokens: 2622
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 79
      output_tokens: 2622
      cost_usd: 0.0
  runs:
  - profile: default
    model: unknown
    input_tokens: 79
    output_tokens: 2622
    cost_usd: 0.0
    recorded_at: '2026-06-20T02:54:31.080814+00:00'
oompah.review_url: https://github.com/lesserevil/oompah/pull/336
oompah.review_number: '336'
oompah.work_branch: OOMPAH-10
oompah.target_branch: main
---
## Summary

The native markdown tracker dispatch path can fail before launching an agent when it tries to update task state with `git pull --rebase origin main`. In the managed trickle repo this reproduced on a clean default branch with:

```
git pull --rebase origin main
fatal: Cannot rebase onto multiple branches
```

This prevented TRICKLE-2 from being marked In Progress and aborted dispatch, leaving no agents running until a later retry happened to get past the sync step.

Expected behavior:
- Syncing native `.oompah/tasks` on the managed default branch should be robust for clean fast-forward cases.
- Use an explicit fetch plus safe fast-forward/update strategy instead of a brittle `git pull --rebase origin main` for tracker metadata commits.
- If sync cannot proceed, oompah should surface a clear alert with the project, task, command, and remediation path instead of silently starving dispatch.

Acceptance criteria:
- Reproduce the failure with a unit or integration test around the native markdown tracker/project sync path.
- Replace the failing rebase pull path with deterministic fetch/fast-forward behavior for clean managed default branches.
- Preserve protection for dirty/conflicted worktrees; do not overwrite user work.
- Dispatch no longer aborts for a clean up-to-date managed repo due to `Cannot rebase onto multiple branches`.
- A failed sync creates a visible actionable alert.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-06-20 02:46
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-06-20 02:47
---
Understanding: OOMPAH-10 is NOT a duplicate — no prior task covers the git pull --rebase sync failure in the native markdown tracker dispatch path. This is a fresh bug. My plan: (1) Find the dispatch/sync code that runs 'git pull --rebase origin main', (2) Search for any related git sync helpers, (3) Implement fetch+fast-forward replacement, (4) Add a failing test that reproduces the bug, (5) Verify tests pass.
---
author: oompah
created: 2026-06-20 02:50
---
Discovery: Root cause found in oompah/oompah_md_tracker.py. Two locations call 'git pull --rebase origin <branch>': (1) _prepare_default_branch_for_write() at line ~715 — fetches first then re-fetches+rebases with the pull, which can fail with 'Cannot rebase onto multiple branches'. (2) _commit_and_push() at line ~735 — retry path on push conflict also uses the same brittle pull --rebase. Fix: Replace both with deterministic 'git fetch origin <branch>' + 'git merge --ff-only origin/<branch>'. This avoids the rebase ambiguity while preserving protection for dirty worktrees. Will also add a visible alert via TrackerError with actionable remediation. No duplicate task found — proceeding with implementation.
---
author: oompah
created: 2026-06-20 02:54
---
Implementation: Replaced both 'git pull --rebase origin <branch>' calls in oompah/oompah_md_tracker.py with a new _sync_from_remote() helper that runs 'git fetch origin <branch>' followed by 'git merge --ff-only origin/<branch>'. The fetch+ff-only approach is fully deterministic for clean managed repos and cannot produce the 'Cannot rebase onto multiple branches' error. Both fetch failures and ff-only failures now raise TrackerError with project/command/remediation context so callers can surface a visible alert. The _commit_and_push() retry path was also fixed.
---
author: oompah
created: 2026-06-20 02:54
---
Verification: All 6907 tests pass (28 skipped). The 5 new TestOompahMarkdownTrackerGitSync tests all pass: (1) fetch+ff-only called, pull --rebase never called; (2) fetch failure raises TrackerError with remediation; (3) ff-only failure raises TrackerError with remediation (OOMPAH-10 regression path); (4) clean repo never calls git pull; (5) commit+push retry also uses fetch+ff-only.
---
author: oompah
created: 2026-06-20 02:54
---
Completion: OOMPAH-10 is not a duplicate (no existing task covered this bug). Fixed in oompah/oompah_md_tracker.py: replaced both 'git pull --rebase origin main' calls with deterministic fetch+ff-only via new _sync_from_remote() helper. Tests added in tests/test_oompah_md_tracker.py. Branch OOMPAH-10 pushed and all tests passing.
---
author: oompah
created: 2026-06-20 02:54
---
Fixed: replaced 'git pull --rebase origin main' with fetch+ff-only in _prepare_default_branch_for_write() and _commit_and_push(). New _sync_from_remote() helper raises TrackerError with actionable remediation on failure. 5 regression tests added. All 6907 tests pass.
---
author: oompah
created: 2026-06-20 02:54
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/default]
- Turns: 0, Tool calls: 54
- Tokens: 79 in / 2.6K out [2.7K total]
- Cost: $0.0000
- Exit: terminated, Duration: 8m 18s
- Log: OOMPAH-10__20260620T024616Z.jsonl
---
<!-- COMMENTS:END -->
