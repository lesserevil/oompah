---
id: OOMPAH-726
type: task
status: Backlog
priority: null
title: Prune terminal nested-epic worktrees using recorded target-branch evidence
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-03T15:37:02.712106Z'
updated_at: '2026-08-03T15:37:44.861117Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
---
## Summary

Live reproduction: terminal nested epic EXOCOMP-185 merged through PR #22 into its recorded target branch epic-EXOCOMP-127 at merge commit 2c9ad37b8a482cc5541bf72b1a0cad5d4a771752. The source branch origin/epic-EXOCOMP-185 was then deleted normally. Its clean managed worktree remains at exact source head a163c8323e9b83e2360af73c9f3e972b99f9dc0d, which is the merge second parent and is reachable from origin/epic-EXOCOMP-127. Every cleanup sweep logs Refusing terminal cleanup of unpublished task worktree because it checks the deleted source/default target evidence and ignores the nested epic recorded target branch and reviewed merge evidence.

Implementation scope:
- Extend terminal managed-worktree cleanup to resolve a nested epic recorded target branch and durable review/terminal-audit landing evidence before classifying its clean head as unpublished.
- Fetch the authoritative recorded target ref, require the exact worktree head to be an ancestor or verified merge parent, and only then remove the managed worktree and exact local/source ref.
- Treat normal post-merge source-branch deletion as expected when target landing remains provable.
- Preserve fail-closed behavior for dirty worktrees, active Git operations, missing/unreachable heads, stale or unavailable target refs, shared branches, unregistered paths, and cross-task identities.
- Keep cleanup idempotent and stop repeated warning spam once the workspace is safely absent.

Relevant code: ProjectStore terminal cleanup ancestry guards in oompah/projects.py, orchestrator terminal cleanup routing, nested epic target metadata, terminal audit evidence, and repository hygiene reporting.

Required tests:
- Reproduce EXOCOMP-185 with a nested epic source branch deleted after a two-parent merge into a non-default parent epic branch; prove the clean exact managed worktree and local source ref are pruned.
- Cover fast-forward landing, merge-commit landing, deleted source, target fetch failure, head not reachable, dirty/active worktree, shared checkout, wrong target metadata, and repeated cleanup.
- Prove ordinary top-level/default-branch cleanup and OOMPAH-581 task-style epic repair cleanup remain unchanged.
- Run focused projects, cleanup/hygiene, nested-epic, and terminal lifecycle suites plus make test.

Acceptance criteria:
- EXOCOMP-185-style terminal nested epics do not accumulate clean worktrees solely because their source branch was deleted.
- Cleanup never removes unproven or task-owned recovery work.
- Repo hygiene reports the cleanup once and remains quiet/idempotent afterward.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-03 15:37
---
In-flight cleanup completed with exact guards. Verified the managed EXOCOMP-185 worktree was clean, on exact branch epic-EXOCOMP-185 at a163c8323e9b83e2360af73c9f3e972b99f9dc0d; fetched origin/epic-EXOCOMP-127; proved a163c832 is the second parent of reviewed merge 2c9ad37b and an ancestor of current target tip e826d0d5. Removed only /home/shedwards/.oompah/worktrees/exocomp/epic-EXOCOMP-185 and compare-and-deleted the exact local source ref. The remote source was already absent and the commit remains reachable from the authoritative target.
---
<!-- COMMENTS:END -->
