---
id: OOMPAH-443
type: task
status: Open
priority: null
title: Require child landing evidence before epic merge and rollup
parent: null
children: []
blocked_by: []
labels:
- focus-complete:duplicate_detector
assignee: null
created_at: '2026-07-25T17:52:13.750962Z'
updated_at: '2026-07-25T18:18:30.352456Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: 5e3991c0-149f-44cb-9445-d27d6397dfce
oompah.task_costs:
  total_input_tokens: 811917
  total_output_tokens: 7220
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 811917
      output_tokens: 7220
      cost_usd: 0.0
  runs:
  - profile: default
    model: unknown
    input_tokens: 811813
    output_tokens: 4358
    cost_usd: 0.0
    recorded_at: '2026-07-25T17:57:26.212393+00:00'
  - profile: standard
    model: unknown
    input_tokens: 104
    output_tokens: 2862
    cost_usd: 0.0
    recorded_at: '2026-07-25T18:05:03.188400+00:00'
---
## Summary

Fix the shared-epic lifecycle regression exposed by exocomp: epic PRs merged while child tasks were incomplete or had committed work only on separate branches, after which reconciliation blindly marked every child Merged. Before opening or merging an epic rollup PR, require every actionable child to be workflow-complete and verify available child landing/commit evidence is contained by the epic branch or target. When an epic is already merged, do not promote a child to Merged without containment evidence; surface a recoverable state with an actionable explanation instead. Cover incomplete children, stranded child branches, late child completion after parent merge, and valid shared-branch children with regression tests. Run make test and deploy.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-25 17:55
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-25 17:55
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-25 17:55
---
Understanding: Duplicate screening will determine whether an existing task already covers the shared-epic regression: gating epic rollup on child workflow completion and commit/landing containment, plus safe post-merge child reconciliation. I will search task history and relevant docs, read full candidate task state/comments, and will not implement during this focus.
---
author: oompah
created: 2026-07-25 17:56
---
Discovery: Duplicate screening found no confirmed duplicate. Closest full-history candidates: OOMPAH-165 guards the parent epic's Merged transition and validates the epic PR target, but does not validate each child's workflow state or landing evidence; OOMPAH-219 persists evidence for uncommitted shared-worktree changes later absorbed by another commit, but does not handle child commits stranded on separate branches or post-parent-merge promotion; OOMPAH-168 simplified orchestration to shared-only behavior without adding these containment gates. OOMPAH-443 is distinct follow-up regression work.
---
author: oompah
created: 2026-07-25 17:57
---
Focus handoff: duplicate_detector

1. Outcome: No duplicate confirmed; OOMPAH-443 is a distinct regression and requires implementation.
2. Evidence: Searched .oompah/tasks, docs, plans, README.md, and WORKFLOW.md for shared-epic, rollup, landing/containment, and child-Merged terms. Read full task histories for OOMPAH-165, OOMPAH-219, OOMPAH-168, and OOMPAH-28. Closest tasks are OOMPAH-165 (parent epic landing/target correctness), OOMPAH-219 (uncommitted shared-worktree absorption evidence), and OOMPAH-168 (shared-only strategy cleanup), all materially narrower/different. Relevant current code: oompah/orchestrator.py::_shared_epic_child_done, _reconcile_epic_rollup_statuses, _open_epic_main_prs, _label_merged_issues, _label_merged_epics; oompah/landing_gate.py::check_landing_gate. Relevant tests include tests/test_epic_strategy.py, tests/test_orchestrator_merged.py, tests/test_landing_gate.py, tests/test_shared_absorption.py, and tests/test_independently_merged.py.
3. Remaining work/risks: Implement pre-rollup child workflow and containment gates plus evidence-aware post-parent-merge reconciliation. Cover incomplete children, committed work stranded on separate child branches, children completing after parent merge, and valid shared-branch children. Preserve the distinct OOMPAH-165 parent landing guard and OOMPAH-219 absorption recovery. Run make test and deploy per task scope.
4. Recommended next focus: feature (backend orchestration lifecycle implementation and regression tests). No code was changed and no tests were run during duplicate screening.
---
author: oompah
created: 2026-07-25 17:57
---
Agent completed successfully in 137s (816171 tokens)
---
author: oompah
created: 2026-07-25 17:57
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/default]
- Turns: 1, Tool calls: 17
- Tokens: 811.8K in / 4.4K out [816.2K total]
- Cost: $0.0000
- Exit: normal, Duration: 2m 17s
- Log: OOMPAH-443__20260725T175511Z.jsonl
---
author: oompah
created: 2026-07-25 17:57
---
Focus handoff from `duplicate_detector` is complete. Queued a fresh agent run for the next applicable focus. The next agent should begin with the preceding Focus handoff comment.
---
author: oompah
created: 2026-07-25 17:57
---
Agent dispatched (profile: standard)
---
author: oompah
created: 2026-07-25 17:57
---
Focus: DevOps Engineer
---
author: oompah
created: 2026-07-25 18:03
---
Understanding: I've been dispatched as DevOps Engineer but the core work is backend Python implementation in oompah/orchestrator.py. The task has two parts: (1) implementation of containment gates and (2) running tests/deploy. I'll implement the feature and run tests.

Root cause identified: `_mark_epic_merged` blindly promotes all non-terminal children to Merged when an epic's PR lands, without verifying each child's committed work is actually contained in the epic branch that merged. Similarly, `_open_epic_main_prs` verifies children are workflow-complete but does NOT verify each child's work_branch commits are contained in the epic branch.

Fix plan:
1. Add `EPIC_STRANDED_CHILD_LABEL = 'epic:stranded-child'` constant to models.py
2. Add `_child_work_contained_by_branch(project, child_branch, container_branch)` helper
3. Modify `_open_epic_main_prs`: after terminal-state gate, check each child's work_branch against epic_branch using git; skip epic PR if any child has stranded commits
4. Modify `_mark_epic_merged`: before promoting child to Merged, check if child work_branch is contained in target_branch; if not, add epic:stranded-child label and skip promotion with warning log
5. Add regression tests covering all four scenarios (incomplete children, stranded branches, late completion, valid shared children)
---
author: oompah
created: 2026-07-25 18:05
---
Run #1 [attempt=1, profile=standard, role=standard -> Claude/default]
- Turns: 0, Tool calls: 62
- Tokens: 104 in / 2.9K out [3.0K total]
- Cost: $0.0000
- Exit: terminated, Duration: 7m 28s
- Log: OOMPAH-443__20260725T175737Z.jsonl
---
author: oompah
created: 2026-07-25 18:05
---
Agent dispatched (profile: standard)
---
author: oompah
created: 2026-07-25 18:05
---
Focus: DevOps Engineer
---
author: oompah
created: 2026-07-25 18:05
---
Understanding: I will implement backend lifecycle safeguards in the epic rollup/reconciliation paths. The gate must require every actionable child to be workflow-complete and must treat recorded child branch/commit evidence as satisfied only when contained by the epic branch or landed target. After a parent merge, children lacking containment will remain recoverable with an actionable explanation rather than being promoted blindly. I will preserve existing absorption and independent-merge handling, add regressions for incomplete, stranded, late, and valid shared-branch children, run make test, deploy with the project Makefile, commit, push, and close the task.
---
author: oompah
created: 2026-07-25 18:10
---
Run #2 [attempt=2, profile=standard, role=standard -> Codex/default]
- Turns: 0, Tool calls: 58
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: terminated, Duration: 4m 50s
- Log: OOMPAH-443__20260725T180519Z.jsonl
---
author: oompah
created: 2026-07-25 18:10
---
Retrying (attempt #2, agent: standard)
---
author: oompah
created: 2026-07-25 18:10
---
Focus: DevOps Engineer
---
author: oompah
created: 2026-07-25 18:10
---
Understanding (attempt #2): Previous runs terminated before completing implementation. I will now implement the full fix: (1) add child workflow-completeness gate before opening epic rollup PRs, (2) add containment evidence gate (child work_branch commits must be contained in the epic branch), (3) guard post-parent-merge child promotion in _mark_epic_merged with containment check - surface recoverable state instead of blindly promoting, (4) add regression tests for all four scenarios, (5) run make test, commit, push, and close. Starting now.
---
author: oompah
created: 2026-07-25 18:11
---
Discovery: The lifecycle has three inconsistent gates.  checks canonical child states but never checks a child's recorded branch/review evidence.  explicitly allows the legitimate epic branch without revalidating children immediately before enqueue/direct merge.  marks every non-terminal child Merged unless a separate review is visibly open;  repeats that promotion after restarts. Existing , review metadata/cache, provider merged-review data, and local git ancestry are sufficient to distinguish shared-branch/landed work from stranded child branches. The fix will centralize that decision and reopen/label stranded Done children with an actionable comment.
---
author: oompah
created: 2026-07-25 18:11
---
Discovery correction: The lifecycle has three inconsistent gates. _open_epic_main_prs checks canonical child states but never checks a child recorded branch/review evidence. _yolo_epic_strategy_block_reason allows the legitimate epic branch without revalidating children immediately before enqueue/direct merge. _mark_epic_merged marks every non-terminal child Merged unless a separate review is visibly open; _reconcile_merged_epic_children repeats that promotion after restarts. Existing work_branch, review metadata/cache, provider merged-review data, and local git ancestry are sufficient to distinguish shared-branch/landed work from stranded child branches. The fix will centralize that decision and reopen/label stranded Done children with an actionable comment.
---
<!-- COMMENTS:END -->
