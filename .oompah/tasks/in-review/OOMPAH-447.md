---
id: OOMPAH-447
type: bug
status: In Review
priority: 1
title: Do not reopen merged epic siblings for a later shared-branch PR
parent: null
children: []
blocked_by: []
labels:
- focus-complete:duplicate_detector
assignee: null
created_at: '2026-07-26T04:02:02.297716Z'
updated_at: '2026-07-26T04:12:42.874125Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: a857be39-6727-4b70-953b-debcf4298e58
oompah.task_costs:
  total_input_tokens: 89
  total_output_tokens: 8729
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 89
      output_tokens: 8729
      cost_usd: 0.0
  runs:
  - profile: default
    model: unknown
    input_tokens: 38
    output_tokens: 7083
    cost_usd: 0.0
    recorded_at: '2026-07-26T04:07:16.375885+00:00'
  - profile: default
    model: unknown
    input_tokens: 51
    output_tokens: 1646
    cost_usd: 0.0
    recorded_at: '2026-07-26T04:12:41.459476+00:00'
---
## Summary

Triggered by: EXOCOMP-47

Problem
When a shared epic branch is reused for a later follow-up PR, _reconcile_terminal_open_reviews matches every Merged child and the parent epic only by work_branch. PR #17 from epic-EXOCOMP-6 was owned by EXOCOMP-47, but the reconciler demoted EXOCOMP-41, EXOCOMP-42, EXOCOMP-43, EXOCOMP-44, and EXOCOMP-6 to In Review. The merged-parent sweep then moved several siblings to Needs Human even though their recovery delivery was already verified on main.

Implementation
Add review ownership validation before demoting a terminal issue. A current review is owned when persisted review_number matches, the source branch is the standalone issue branch, or the review title identifies that exact issue. For shared epic branches, do not treat branch equality alone as ownership because multiple completed siblings share it. Preserve false-Merged repair for standalone task branches and for explicitly identified epic or child reviews. Log and skip ambiguous shared-branch reviews.

Tests
Add regression coverage with a Merged epic and multiple Merged children sharing epic-EPIC-1 while a later open PR titled for only one child is ahead of main. Only the identified owner may be repaired; unrelated siblings and the parent remain Merged. Retain existing standalone false-Merged, CI-failure, conflict, and stale-cache tests. Include exact-identifier matching so TASK-4 does not match TASK-41.

Acceptance Criteria
- A later follow-up PR on a reused shared epic branch never reopens unrelated Merged siblings or the parent.
- The task named by the review can still be repaired when its delivery is genuinely unmerged.
- Standalone false-Merged repair continues to work.
- make test passes and the live service no longer recreates these Needs Human states.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-26 04:02
---
Reproduced live with exocomp PR #17: shared branch epic-EXOCOMP-6 caused unrelated terminal siblings EXOCOMP-41/42/43/44 and parent EXOCOMP-6 to be demoted. Implementing exact review ownership checks in terminal/open-review reconciliation with focused regression tests.
---
author: oompah
created: 2026-07-26 04:04
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-26 04:04
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-26 04:04
---
Understanding: Investigating OOMPAH-447 as Duplicate Investigator. The issue reports that _reconcile_terminal_open_reviews uses work_branch equality alone to match open PRs to issues, causing unrelated Merged siblings (EXOCOMP-41/42/43/44 and parent EXOCOMP-6) to be demoted to 'In Review' when a later follow-up PR reuses the shared epic branch. Searching now for candidate duplicates before any implementation begins.
---
author: oompah
created: 2026-07-26 04:07
---
Focus handoff: duplicate_detector

**Outcome:** No duplicate found. OOMPAH-447 is a unique issue.

**Evidence reviewed:**
- Searched all `.oompah/tasks/` subdirectories (archived, merged, done, backlog, open) for: reconcile_terminal, false_merged, shared branch, work_branch, sibling, demote, In Review demotion, terminal review, EXOCOMP, _open_review_branch_for_issue
- Inspected OOMPAH-219 (Archived): 'Detect shared-worktree commits that absorb another task's changes' — covers the _reconcile_shared_absorption path for Needs Human tasks that had uncommitted changes absorbed by a later commit. Different mechanism from OOMPAH-447 (which is about _reconcile_terminal_open_reviews demoting Merged siblings via branch-equality matching of an open PR). Not a duplicate.
- Inspected OOMPAH-165 (Archived): 'shared/stacked epic state bug' — about epic landing target-awareness and preventing premature Merged rollup when all children are merged but epic branch not yet landed. Different.
- Inspected OOMPAH-235 (Done): 'Recover native tracker writes after concurrent default-branch advancement' — push race rebase logic, unrelated.
- Plans dir: no plan document for false-Merged terminal review reconciliation.

**Relevant source code:** `oompah/orchestrator.py`:
- `_reconcile_terminal_open_reviews()` (~line 9401): iterates Merged issues and calls `_open_review_branch_for_issue()` to find a matching open PR
- `_open_review_branch_for_issue()` (~line 9545): matches by work_branch, branch_name, epic_branch_name, or issue identifier — does NOT validate review_number or review title. If EXOCOMP-41/42/43/44 all share `epic-EXOCOMP-6` as work_branch, a new open PR on that branch matches all of them.

**Remaining work:**
- Add review ownership validation in `_open_review_branch_for_issue` or `_reconcile_terminal_open_reviews`: for a shared epic branch, only demote if (a) issue.review_number matches, or (b) the review title identifies this exact issue, or (c) source branch is the standalone issue branch (not a shared epic branch). Log and skip ambiguous shared-branch matches.
- Add regression tests per issue description: Merged epic + multiple Merged children sharing epic-EPIC-1; a later open PR titled for only one child; verify only the identified owner is demoted; TASK-4 does not match TASK-41.

**Recommended next focus:** feature (backend implementation in oompah/orchestrator.py + tests)
---
author: oompah
created: 2026-07-26 04:07
---
Agent completed successfully in 187s (7121 tokens)
---
author: oompah
created: 2026-07-26 04:07
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/default]
- Turns: 57, Tool calls: 43
- Tokens: 38 in / 7.1K out [7.1K total]
- Cost: $0.0000
- Exit: normal, Duration: 3m 7s
- Log: OOMPAH-447__20260726T040411Z.jsonl
---
author: oompah
created: 2026-07-26 04:07
---
Focus handoff from `duplicate_detector` is complete. Queued a fresh agent run for the next applicable focus. The next agent should begin with the preceding Focus handoff comment.
---
author: oompah
created: 2026-07-26 04:07
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-26 04:07
---
Focus: DevOps Engineer
---
author: oompah
created: 2026-07-26 04:07
---
Understanding: As DevOps Engineer, I'm picking up from the duplicate_detector handoff. Root cause confirmed: _reconcile_terminal_open_reviews() in oompah/orchestrator.py uses work_branch equality alone to match open PRs to issues, causing all Merged siblings sharing a shared epic branch (e.g., epic-EXOCOMP-6) to be incorrectly demoted when a follow-up PR reuses that branch. Plan: (1) read the relevant orchestrator code around lines 9401 and 9545, (2) implement ownership validation (review_number match, exact title identifier match, or standalone task branch), (3) add regression tests for shared-branch epic scenarios, (4) run make test. The implementation is Python backend work which I can complete in this session.
---
author: oompah
created: 2026-07-26 04:12
---
Implementation is pushed in PR #555: terminal/open-review reconciliation now requires explicit ownership on shared epic branches, with exact-identifier and persisted-review regressions. Verification passed: make test (12,329 passed, 7 skipped), make check-secrets, and git diff --check. CI is running.
---
author: oompah
created: 2026-07-26 04:12
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/default]
- Turns: 0, Tool calls: 31
- Tokens: 51 in / 1.6K out [1.7K total]
- Cost: $0.0000
- Exit: terminated, Duration: 5m 4s
- Log: OOMPAH-447__20260726T040740Z.jsonl
---
<!-- COMMENTS:END -->
