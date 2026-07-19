---
id: OOMPAH-248
type: task
status: In Progress
priority: null
title: Fix Release Delivery discovery when merged task branches were deleted
parent: null
children: []
blocked_by:
- OOMPAH-237
labels:
- focus-complete:duplicate_detector
assignee: null
created_at: '2026-07-19T18:24:37.584983Z'
updated_at: '2026-07-19T18:32:22.121473Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: 26f4d2be-e7ed-43aa-9e4e-fd50540bc755
oompah.task_costs:
  total_input_tokens: 17
  total_output_tokens: 4480
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 17
      output_tokens: 4480
      cost_usd: 0.0
  runs:
  - profile: default
    model: unknown
    input_tokens: 17
    output_tokens: 4480
    cost_usd: 0.0
    recorded_at: '2026-07-19T18:27:43.525511+00:00'
---
## Summary

Problem

The Release Delivery backlog for Trickle release/0.11 currently returns zero primary items while reporting 7,513 unassociated commits, despite main being ahead and containing substantive task work. OOMPAH-237/OOMPAH-238 added tracker-sourced discovery, but it resolves a Merged issue only by running git rev-list against refs/remotes/origin/<work_branch>. Oompah normally deletes the task branch after its PR merges, so that ref is absent and the candidate is silently excluded.

Required implementation

- Replace work-branch existence as the primary proof with durable native tracker merge evidence: merged PR number/head+merge SHA, recorded merge commit SHA, or another persisted merge-to-default-branch field available after branch deletion.
- Resolve every resulting source commit set against origin/<default_branch>; include only commits that are reachable there.
- Retain work-branch history only as an optional enrichment/fallback when the ref still exists; missing/deleted branch must not exclude a genuinely merged task or epic.
- Keep release-delivery ledger and selected-release ancestry solely for delivery state, not candidate eligibility.
- Ensure the endpoint can return primary candidates before (or independently of) unassociated diagnostics.

Tests

- Unit regression: a Merged task with no ledger entry, a deleted/missing work_branch ref, and a persisted merge commit reachable from main appears once as Not selected.
- Unit regression: same task with a merge SHA not reachable from main is excluded.
- Unit regression: optional live work branch can add associated commits without being required.
- API/fixture regression representing Trickle release/0.11 demonstrates a selectable primary candidate after the task branch has been deleted.

Acceptance criteria

- Release Delivery for Trickle release/0.11 shows eligible merged task/epic changes that have never been queued, even if their original work branches no longer exist.
- An empty primary list is not returned merely because merged task branches were cleaned up.
- make test passes.
## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-19 18:25
---
Implementation clarification for dispatch: native Markdown task records persist / even when  has been deleted. For a Merged item with no usable remote work branch, use that recorded PR reference through the existing SCM/PR integration to obtain the merged PR's merge commit and/or commit list; verify the resulting SHA(s) are reachable from origin/<default_branch>. Do not invent a new metadata schema unless inspection proves the existing review reference cannot supply durable evidence. The work-branch scan remains optional enrichment only.
---
author: oompah
created: 2026-07-19 18:25
---
Correction to the prior comment: native Markdown task records persist the review_number and review_url fields even when the work_branch has been deleted. For a Merged item with no usable remote work branch, use that recorded PR reference through the existing SCM/PR integration to obtain the merged PR merge commit and/or commit list; verify the resulting SHAs are reachable from origin/default branch. Do not invent a new metadata schema unless inspection proves the existing review reference cannot supply durable evidence. The work-branch scan remains optional enrichment only.
---
author: oompah
created: 2026-07-19 18:25
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-19 18:25
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-19 18:27
---
Understanding: Investigating whether OOMPAH-248 is a duplicate of OOMPAH-237 or OOMPAH-238 (or other related tasks). Reviewing the full history of the release delivery backlog work (OOMPAH-237 epic and all children OOMPAH-238 through OOMPAH-247).
---
author: oompah
created: 2026-07-19 18:27
---
Focus handoff: duplicate_detector

1. Outcome: OOMPAH-248 is NOT a duplicate. Duplicate screening complete.

Candidates reviewed:
- OOMPAH-237 (Merged, parent epic): 'Fix Release Delivery backlog candidate discovery and timeout' — merged via PR #445. OOMPAH-237's last comment explicitly states: 'Regression found after merge: the live Trickle release/0.11 backlog returns items=0 and unassociated=7513. Candidate discovery still requires refs/remotes/origin/<work_branch>; merged task branches are normally deleted, so no commits are resolved and eligible Merged tasks are excluded. Filed OOMPAH-248 with durable merge-evidence and deleted-branch regression requirements.' OOMPAH-248 is the successor bug, not a duplicate.
- OOMPAH-238 (Merged, child): Implemented _find_branch_commits_in_main() using refs/remotes/origin/<work_branch> — this is exactly the mechanism OOMPAH-248 must replace. Not a duplicate; OOMPAH-248 fixes OOMPAH-238's residual hole.
- OOMPAH-239–247 (Merged): Timeout fix, dashboard/Trickle regression tests, and rebase tasks. None cover durable merge evidence from deleted branches.

2. Relevant files and evidence:
- oompah/release_delivery_backlog.py — ItemBacklogService.get_backlog(); current tracker-sourced discovery path using _find_branch_commits_in_main() which requires a live remote work_branch ref
- oompah/release_delivery_inventory.py — _find_branch_commits_in_main() added by OOMPAH-238; must be replaced or supplemented with PR-based durable evidence
- oompah/models.py — Issue fields: review_number, review_url (persist after branch deletion), work_branch (may be missing/deleted)
- oompah/oompah_md_tracker.py — existing SCM/PR integration (fetch_pull_request() or equivalent) for resolving merge commit from review_number
- tests/test_release_delivery_backlog.py — existing test patterns to extend

3. Remaining work:
- Replace work-branch ref dependency with durable PR merge evidence (review_number/review_url → merge commit SHA via SCM API) when branch ref is absent
- Verify resulting SHAs are reachable from origin/<default_branch>
- Keep work-branch history as optional enrichment only
- Add unit regression tests per spec: Merged task with deleted branch + persisted merge commit reachable from main → Not selected; same task with merge SHA not reachable → excluded; optional live branch can add commits; API/fixture for Trickle release/0.11

4. Recommended next focus: feature (backend fix to release_delivery_inventory.py + release_delivery_backlog.py + new unit tests)
---
author: oompah
created: 2026-07-19 18:27
---
Agent completed successfully in 110s (4497 tokens)
---
author: oompah
created: 2026-07-19 18:27
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/default]
- Turns: 30, Tool calls: 24
- Tokens: 17 in / 4.5K out [4.5K total]
- Cost: $0.0000
- Exit: normal, Duration: 1m 50s
- Log: OOMPAH-248__20260719T182600Z.jsonl
---
author: oompah
created: 2026-07-19 18:27
---
Focus handoff from `duplicate_detector` is complete. Queued a fresh agent run for the next applicable focus. The next agent should begin with the preceding Focus handoff comment.
---
author: oompah
created: 2026-07-19 18:28
---
Agent dispatched (profile: standard)
---
author: oompah
created: 2026-07-19 18:28
---
Focus: Test Engineer
---
author: oompah
created: 2026-07-19 18:28
---
Understanding: As Test Engineer for OOMPAH-248, I need to write regression tests for the Release Delivery discovery fix when merged task branches are deleted. Required tests per spec:
1. Merged task with deleted/missing work_branch ref + persisted merge commit reachable from main → appears as Not selected (not excluded)
2. Same task with merge SHA NOT reachable from main → excluded
3. Optional live work branch can add associated commits without being required
4. API/fixture regression for Trickle release/0.11 demonstrates selectable primary candidate after branch deletion

Starting with codebase exploration to understand existing patterns and the current state of implementation.
---
author: oompah
created: 2026-07-19 18:32
---
Discovery: The feature for OOMPAH-248 has NOT been implemented yet on this branch (only task metadata commits exist). 

Root cause confirmed: In release_delivery_backlog.py, the tracker-sourced discovery loop (step 3b) calls _find_branch_commits_in_main() which requires refs/remotes/origin/<work_branch> to exist. When oompah deletes the task branch after merge, this ref is gone and the function returns [], causing the item to be silently excluded.

Fix requires:
1. ItemBacklogService to accept optional scm (SCMProvider) param
2. When _find_branch_commits_in_main returns empty AND issue has review_number AND issue has managed_repo, fall back to scm.get_pr_commits(managed_repo, review_number) and intersect with main_shas
3. New _find_pr_commits_in_main() function in release_delivery_inventory.py

Writing regression tests now (TDD style - tests will fail until feature is implemented). Tests cover all 4 required scenarios from spec.
---
<!-- COMMENTS:END -->
