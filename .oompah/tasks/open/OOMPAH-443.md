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
updated_at: '2026-07-25T18:01:35.126489Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: 25d0d144-8484-442d-9f45-b0f4b7bd552b
oompah.task_costs:
  total_input_tokens: 811813
  total_output_tokens: 4358
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 811813
      output_tokens: 4358
      cost_usd: 0.0
  runs:
  - profile: default
    model: unknown
    input_tokens: 811813
    output_tokens: 4358
    cost_usd: 0.0
    recorded_at: '2026-07-25T17:57:26.212393+00:00'
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
<!-- COMMENTS:END -->
