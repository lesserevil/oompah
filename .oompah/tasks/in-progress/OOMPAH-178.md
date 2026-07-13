---
id: OOMPAH-178
type: task
status: In Progress
priority: 1
title: Execute queued addendums with worktrees and pull requests
parent: OOMPAH-172
children: []
blocked_by:
- OOMPAH-177
labels: []
assignee: null
created_at: '2026-07-13T02:35:53.454708Z'
updated_at: '2026-07-13T05:18:39.513781Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: a9fd5959-10de-4f7d-ade2-62da4bd1fe39
---
## Summary

Read section 8 of plans/release-branch-addendums.md. Extract reusable cherry-pick/push/PR operations from the release-pick child-task code so they operate on a ReleaseAddendum. Create/reuse a deterministic release worktree rooted at origin/<target_branch>, apply only the persisted commit snapshot, push the persisted oompah/release work branch, and create or reuse exactly one target-branch PR. Persist in_review, result_commits, and pr_url on success; persist blocked plus diagnostics on conflict or execution failure and preserve the conflicted worktree. Tests: correct target base and commit order; existing worktree/PR reuse; successful state/evidence updates; conflict preservation; non-conflict failure; and proof no tracker task is created. Acceptance: an open queue item can become an in_review addendum with a PR, while its source remains untouched.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-13 05:07
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-13 05:07
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-13 05:10
---
Understanding: OOMPAH-178 is not a duplicate. Searched all tasks in the OOMPAH-172 epic (OOMPAH-173 through OOMPAH-185). The done tasks cover schema (173), project config (174), catalog API (175), approval+snapshot (176), and queue claiming+recovery (177). OOMPAH-178 uniquely covers the execution step: cherry-pick commits into a release worktree, push the work branch, and create/reuse a target-branch PR. No other task covers this. Proceeding with implementation by reading section 8 of plans/release-branch-addendums.md and then extracting/implementing the execution logic.
---
author: oompah
created: 2026-07-13 05:12
---
Discovery: The key files are oompah/cherry_pick_pr_creator.py (existing cherry-pick/push/PR logic for BackportEntry+child Issue) and oompah/release_addendum_schema.py+queue.py (already implemented by OOMPAH-177). OOMPAH-178 requires a new oompah/release_addendum_executor.py that: (1) creates/reuses the worktree via worktree_key+work_branch based at origin/<target_branch>, (2) reuses an existing PR if present (idempotency), (3) applies cherry-pick from addendum.commits, (4) pushes the work_branch, (5) opens a PR targeting target_branch, (6) persists in_review+pr_url+result_commits via AddendumRepository.transition(), (7) on conflict: persists blocked+diagnostic+preserves worktree, posts comment on source task (not a child task), (8) never touches tracker.create_issue or update_issue on source. Tests will cover: target base/commit order, worktree+PR reuse, success state updates, conflict preservation, non-conflict failure (blocked), and proof no tracker task is created.
---
author: oompah
created: 2026-07-13 05:17
---
Implementation: Created oompah/release_addendum_executor.py with:\n- cherry_pick_addendum(): main entry point that takes ReleaseAddendum (no child Issue)\n- _find_existing_pr(): queries SCM for existing open PR on work_branch before opening new one\n- _open_release_pr(): opens PR targeting target_branch using work_branch as source\n- _get_result_commits(): fetches cherry-picked SHAs ahead of origin/<target_branch>\n- _persist_blocked(): transitions addendum to BLOCKED via AddendumRepository.transition()\n- _post_source_comment(): posts diagnostic comment on source task with author oompah\n\nKey behaviors:\n- Worktree created with worktree_key as path, base_branch=target_branch, branch_name=work_branch\n- Existing open PR reused (idempotent re-run) without re-cherry-picking or pushing\n- Commits already applied are skipped (idempotency via _has_new_commits check)\n- On conflict: worktree preserved, blocked+error persisted, comment posted on source (not child)\n- On non-conflict failure: blocked+error persisted, comment posted on source\n- NEVER calls tracker.create_issue() or tracker.update_issue() on source\n\nTests: 72 tests in tests/test_release_addendum_executor.py covering all required scenarios.
---
author: oompah
created: 2026-07-13 05:18
---
Verification: All 72 new tests in test_release_addendum_executor.py pass. Full test suite: 7732 passed, 28 skipped (no regressions). Branch epic-OOMPAH-172 pushed and up to date with origin.
---
author: oompah
created: 2026-07-13 05:18
---
Completion: Delivered oompah/release_addendum_executor.py implementing section 8 of plans/release-branch-addendums.md:\n\n1. cherry_pick_addendum() - main execution function for a claimed ReleaseAddendum\n2. Deterministic worktree via worktree_key+work_branch rooted at origin/<target_branch>\n3. Existing open PR reuse (idempotent re-run skips cherry-pick+push)\n4. Commits already applied are skipped (explicit _has_new_commits check before apply_cherry_pick)\n5. On success: persists in_review + pr_url + result_commits via AddendumRepository.transition()\n6. On conflict: BLOCKED + diagnostic + preserved worktree + source task comment (oompah author)\n7. On non-conflict failure: BLOCKED + diagnostic + source task comment\n8. ZERO tracker.create_issue() calls; ZERO tracker.update_issue() calls on source\n\n72 tests verify all required behaviors. Committed to epic-OOMPAH-172 (f78e3df6) and pushed.
---
<!-- COMMENTS:END -->
