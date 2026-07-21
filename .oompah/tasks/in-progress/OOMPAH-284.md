---
id: OOMPAH-284
type: task
status: In Progress
priority: null
title: Fix Release Delivery task associations and metadata-only filtering
parent: null
children: []
blocked_by: []
labels:
- focus-complete:duplicate_detector
assignee: null
created_at: '2026-07-21T03:38:39.097123Z'
updated_at: '2026-07-21T03:47:51.272086Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: c4697c39-b6e1-4671-85b2-9474f3630ff4
oompah.task_costs:
  total_input_tokens: 31
  total_output_tokens: 16648
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 31
      output_tokens: 16648
      cost_usd: 0.0
  runs:
  - profile: default
    model: unknown
    input_tokens: 31
    output_tokens: 16648
    cost_usd: 0.0
    recorded_at: '2026-07-21T03:47:42.064464+00:00'
---
## Summary

Bug: Trickle release/0.11 Release Delivery shows no needs-delivery task rows despite 44 substantive commits reachable from main and absent from release/0.11. The current association path assigns broad branch history to a merged task (for example TRICKLE-12 receives 3,012 commits), including commits already ancestral to release/0.11. The aggregate then marks every task row delivered by ancestry and the default needs-delivery filter hides all 23 rows.\n\nImplement: (1) associate a merged task/epic only with commits introduced by its PR/merge, excluding inherited/base-branch history; (2) exclude commits whose changed paths are exclusively .oompah/ from Release Delivery candidate, association, ancestry, and unassociated diagnostics results; (3) keep mixed code-plus-.oompah commits eligible; (4) invalidate/rebuild cached backlogs after the fix.\n\nTests: construct a repo where a task branch contains inherited release-branch history plus one new code commit and metadata-only commits; verify only the new code commit appears as needs delivery. Add a regression fixture matching the Trickle pattern and assert default backlog exposes pending task rows for a release branch behind main.\n\nAcceptance criteria: a task with inherited commits already on the target release branch is not falsely delivered when its introduced code commit is absent; metadata-only commits never appear as deliverable rows; mixed commits remain visible.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-21 03:41
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-21 03:41
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-21 03:42
---
Understanding: Investigating OOMPAH-284 as Duplicate Investigator. This issue reports a bug in Release Delivery where: (1) merged tasks receive too many commits due to broad branch history rather than PR-introduced commits, (2) metadata-only .oompah/ commits pollute delivery candidate lists, (3) these issues combine to falsely mark all tasks as delivered. My role is to determine if this is a duplicate of an existing issue before any implementation begins. Searching for related tasks now.
---
author: oompah
created: 2026-07-21 03:47
---
Focus handoff: duplicate_detector

**Outcome:** No duplicate found. OOMPAH-284 is NOT a duplicate of any existing task.

**Evidence reviewed:**
- Searched all .oompah/tasks/ directories (merged, archived, backlog, needs-rebase, needs-ci-fix, done) for: 'release delivery', 'task association', 'metadata only', 'needs-delivery', 'ancestor', 'falsely delivered', 'branch history', 'introduced commit', 'PR commit', 'oompah filter'
- Reviewed all related release-delivery tasks: OOMPAH-237, OOMPAH-238, OOMPAH-239, OOMPAH-248, OOMPAH-241 (and children OOMPAH-240, 243, 244, 245, 246, 247)
- Read plans/release-delivery-commit-inventory.md for context on current implementation
- Read current code: oompah/release_delivery_backlog.py (association path), oompah/release_delivery_inventory.py (_find_branch_commits_in_main)

**Root cause identified (confirmed NOT covered by existing tasks):**

Bug 1 — Association over-assignment: `_find_branch_commits_in_main()` in oompah/release_delivery_inventory.py (L655-721) runs `git rev-list --no-merges refs/remotes/origin/<work_branch>` which walks the ENTIRE commit history reachable from the work branch tip — including inherited base-branch history. When TRICKLE-12's branch was created from a base that includes all of release/0.11's commits, the intersection with `main_shas` returns 3,012 commits (all of release/0.11's history). Then the ancestry check marks all 3,012 as 'delivered by ancestry' (since they ARE on release/0.11), and the aggregate status for TRICKLE-12 becomes 'delivered', hiding it from needs-delivery.

Bug 2 — Metadata-only commit pollution: commits whose ONLY changed files are under `.oompah/` appear as delivery candidates, unassociated rows, and ancestry-check inputs. They are not substantive code changes and should be excluded from all Release Delivery views.

**Closest reviewed tasks (all confirmed DISTINCT):**
- OOMPAH-237 (Merged): switched from ledger-based to tracker-based candidate discovery — tasks not appearing AT ALL vs appearing but falsely marked delivered (different bug)
- OOMPAH-238 (Merged): child of 237, same scope as 237 — different bug
- OOMPAH-239 (Merged): bounded unassociated-commit subprocess calls — performance fix, different scope
- OOMPAH-248 (Merged): added SCM PR-commit fallback for deleted work branches — correct PR commits for Strategy 2, but Strategy 1 (_find_branch_commits_in_main) still has the over-assignment bug
- OOMPAH-241 (Merged): regression tests for 237/238 — distinct scope (tests for different bugs)

**Key files for implementing agent:**
- oompah/release_delivery_inventory.py: `_find_branch_commits_in_main()` (L655) — needs to restrict to PR-introduced commits, not full branch history. Also `_is_tracker_only_commit()` for metadata filtering.
- oompah/release_delivery_backlog.py: `ItemBacklogService.get_backlog()` — association loop (L426-553), ancestry check (L561+), unassociated rows (L665+). All three paths need .oompah/-only exclusion.
- tests/test_release_delivery_backlog.py — regression tests for both bugs
- tests/test_release_delivery_inventory.py (or new file) — unit tests for _find_branch_commits_in_main fix

**Remaining work:**
1. Fix `_find_branch_commits_in_main` to return only commits INTRODUCED by the PR/merge (not inherited from base branch). Correct git idiom: use merge-base to find the fork point, then `git rev-list --no-merges <fork-point>..<work_branch>`. For merged branches where the fork-point approach may be tricky, Strategy 2 (SCM PR commit list) already does this correctly — consider making Strategy 1 also fork-point aware, or preferring Strategy 2 when available.
2. Implement metadata-only commit exclusion: in all four paths (candidate discovery, association, ancestry inputs, unassociated diagnostics), skip commits whose ONLY changed files are under `.oompah/`. The `_is_tracker_only_commit()` function already checks this — ensure it's applied as a filter in all relevant loops.
3. Mixed commits (code + .oompah/) must remain eligible.
4. Add regression tests: (a) a task branch with inherited release-branch history plus one new code commit — only the new commit appears as needs-delivery; (b) metadata-only commits never appear as rows; (c) mixed commits remain visible.
5. Invalidate/rebuild cached backlogs after the fix.

**Recommended next focus:** feature (backend implementation in oompah/release_delivery_inventory.py + oompah/release_delivery_backlog.py, plus tests)
---
author: oompah
created: 2026-07-21 03:47
---
Agent completed successfully in 351s (16679 tokens)
---
author: oompah
created: 2026-07-21 03:47
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/default]
- Turns: 72, Tool calls: 45
- Tokens: 31 in / 16.6K out [16.7K total]
- Cost: $0.0000
- Exit: normal, Duration: 5m 51s
- Log: OOMPAH-284__20260721T034154Z.jsonl
---
author: oompah
created: 2026-07-21 03:47
---
Focus handoff from `duplicate_detector` is complete. Queued a fresh agent run for the next applicable focus. The next agent should begin with the preceding Focus handoff comment.
---
<!-- COMMENTS:END -->
