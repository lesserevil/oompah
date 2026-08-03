---
id: OOMPAH-725
type: task
status: Open
priority: null
title: Reject lifecycle-incompatible Merged overrides for shared-epic children
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-03T15:33:53.224136Z'
updated_at: '2026-08-03T15:40:50.698619Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
---
## Summary

Live reproduction: EXOCOMP-240 is an auto-filed rebase maintenance task parented by shared epic EXOCOMP-130. Its completion auditor passed the required Done transition. A later project-owner terminal override changed the child to Merged even though its work landed only on epic-EXOCOMP-130, not the project default branch. The epic rollup correctly rejects that evidence and now logs EXOCOMP-240=Merged (requires Done), so a superficially more terminal state indefinitely blocks the parent.

Implementation scope:
- Enforce shared-epic child lifecycle compatibility at every terminal transition boundary, including project-owner audit override, ACP override, API/CLI set-status, recovery, and maintenance/rebase completion.
- A child whose accepted work is contained only in its parent epic branch may reach audited Done but may not reach Merged until the parent review lands on the configured target branch.
- Auto-filed epic rebase/maintenance tasks must use Done as their successful terminal target and must not enqueue or invite a second Merged transition merely because they mutate the epic branch directly.
- Preserve legitimate owner override authority for evidence-backed emergency recovery, but reject structurally impossible Merged evidence with a precise conflict explaining the required parent landing.
- Add reconciliation for existing incompatible Merged children: when Done audit evidence exists and the parent has not landed, safely restore Done without rerunning implementation or losing audit history.

Relevant code: terminal_transition_coordinator owner overrides, API/ACP terminal boundaries, shared-epic strategy validation, auto-filed rebase completion, epic rollup reconciliation, and terminal-audit enforcement recovery.

Required tests:
- Reproduce EXOCOMP-240: maintenance child passes Done, owner requests Merged before parent landing, request is rejected and parent completion still accepts the child as Done.
- Cover ordinary shared-epic children, nested epics, default-branch landing followed by legitimate Merged, API and ACP owner overrides, restart recovery, and legacy incompatible records.
- Prove the repair preserves the completed Done audit and cancels no unrelated audit.
- Run focused terminal-override, transition-coordinator, epic-strategy, maintenance/rebase, lifecycle, and terminal-audit-enforcement suites plus make test.

Acceptance criteria:
- A shared-epic child cannot enter Merged solely because its commit is on the epic branch.
- Existing EXOCOMP-240-style records converge to audited Done and no longer block rollup.
- Legitimately target-landed children and top-level tasks can still reach Merged through normal audited or owner-override paths.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

