---
id: OOMPAH-726
type: task
status: In Progress
priority: null
title: Prune terminal nested-epic worktrees using recorded target-branch evidence
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-03T15:37:02.712106Z'
updated_at: '2026-08-03T16:36:35.794899Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 169accb34643e266577eaefccfc7cdd71eac4bd85c64eb7b1bbe53ee9ae6e54e
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-08-03T16:03:38.237304+00:00'
  matched_identifiers: []
  evidence: "Focus handoff: duplicate_detector\nDuplicate preflight verdict: no_duplicate\n\
    Matches: none\nEvidence: Closest tasks OOMPAH-162, OOMPAH-165, and OOMPAH-168\
    \ are all Archived and address epic landing/state behavior, not terminal nested-epic\
    \ worktree cleanup.\nFocus handoff: duplicate_detector  \nDuplicate preflight\
    \ verdict: no_duplicate  \nMatches: none\n\nEvidence: Closest tasks OOMPAH-162,\
    \ OOMPAH-165, and OOMPAH-168 are all Archived and address epic landing/state behavior,\
    \ not terminal nested-epic worktree cleanup."
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: 9a220120-44e7-4d6a-93d6-e5b5cbb7b608
oompah.task_costs:
  total_input_tokens: 51649
  total_output_tokens: 351
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 51649
      output_tokens: 351
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 51649
    output_tokens: 351
    cost_usd: 0.0
    recorded_at: '2026-08-03T16:03:38.235728+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-726__20260803T160311Z
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: duplicate_detector
    source_branch: OOMPAH-726
    source_sha: d510748342777dd4748070d83391ffb0eae40091
    completed_at: '2026-08-03T16:03:38.254173+00:00'
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
author: oompah
created: 2026-08-03 15:40
---
Second live workaround completed for EXOCOMP-128. Verified clean managed source worktree at f34b7d15612196d3963bcaa9378278ba2e142e50, exact second parent of PR #21 merge 2476a39252e92b4690337d7fe706d1b28781bd60 and ancestor of current origin/epic-EXOCOMP-127. Removed only the managed worktree and compare-and-deleted local source ref; the commit remains target-reachable.
---
author: oompah
created: 2026-08-03 16:03
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-03 16:03
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-03 16:03
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 0
- Tokens: 51.6K in / 351 out [52.0K total]
- Cost: $0.0000
- Exit: normal, Duration: 36s
- Log: OOMPAH-726__20260803T160311Z.jsonl
---
author: oompah
created: 2026-08-03 16:04
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-08-03 16:04
---
Focus: Refactoring Specialist
---
author: oompah
created: 2026-08-03 16:05
---
Understanding: I will trace terminal managed-worktree cleanup and its nested-epic/review-audit metadata paths, then add narrowly scoped target-branch landing evidence guards. I will preserve default-branch and task-style cleanup behavior, add regression coverage for fast-forward/merge/deletion/failure/idempotence cases, run focused tests and the configured gate, then commit, push, and submit.
---
author: oompah
created: 2026-08-03 16:06
---
Discovery: ProjectStore._assert_terminal_worktree_safe_locked currently accepts only source-branch publication or origin/default ancestry; deleted nested-epic sources therefore fail closed even after a reviewed merge into the parent epic. Orchestrator cleanup routes terminal issues through cleanup_terminal_issue without target/evidence context, while Issue and terminal metadata already persist target_branch/review_number/review_head and merge audit data. I am tracing those exact contracts before changing the API.
---
author: oompah
created: 2026-08-03 16:22
---
Implementation: ProjectStore now has an opt-in nested-target landing verifier that exact-checks registered worktrees, refreshes/prunes the authoritative target ref, compares the exact reviewed head, accepts ancestry or an explicitly verified merge parent, and protects branch-only cleanup. Orchestrator cleanup resolves canonical parent-epic targets, rejects wrong/missing metadata, and supplies review-head or current-fingerprint passing terminal-Merged audit evidence. Added real bare-remote regression coverage for merge/fast-forward/deleted-source/failure/unreachable/dirty-active/unregistered/idempotent paths and routing tests.
---
author: oompah
created: 2026-08-03 16:36
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 0, Tool calls: 104
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: terminated, Duration: 31m 42s
- Log: OOMPAH-726__20260803T160459Z.jsonl
---
<!-- COMMENTS:END -->
