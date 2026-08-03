---
id: OOMPAH-733
type: task
status: Open
priority: null
title: Fail closed when a nested epic rebase target cannot be resolved
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-03T18:23:48.756544Z'
updated_at: '2026-08-03T18:24:05.759204Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
---
## Summary

Live reproduction: EXOCOMP-245 was auto-filed as Rebase epic-EXOCOMP-135 onto main even though EXOCOMP-135 is a nested epic whose authoritative synchronization target is epic-EXOCOMP-127. The worker successfully force-pushed a main-based rebase, but the parent branch contains required exact prerequisite ancestry that main does not, so the Ready queue remains unclaimable. OOMPAH-633 allows nested-parent queue repair only when the target is the resolved authoritative parent; however, _resolve_epic_target_branch treats a transient _resolve_parent_epic lookup failure as proof that the epic is top-level and silently falls back to project.default_branch. Implementation scope: distinguish confirmed top-level epics from failed or incomplete parent resolution; when parent_id is present, resolve the parent from a canonical project snapshot or fail closed with a retryable diagnostic, never substitute main. Carry the resolved target branch as durable evidence into rebase-task creation, dispatch, prompt/workspace routing, completion, restart recovery, and dashboard diagnostics. Reject or supersede an existing active helper whose recorded target no longer matches the authoritative parent, without racing a worker or deleting recovery refs. Preserve the OOMPAH-633 parent-only policy, cooldown and duplicate fencing, exact force-with-lease behavior, and direct-maintenance completion from OOMPAH-731. Relevant code: _resolve_parent_epic, _resolve_epic_target_branch, nested integration-queue staleness repair, proactive rebase filing, helper task classification/prompting, and epic rebase state persistence. Required tests: reproduce a nested epic with parent_id where fetch_issue_detail transiently fails and assert no main-target helper is filed or dispatched; recover the parent lookup and assert exactly one helper targets origin/epic-parent; cover restart between failed lookup and recovery, stale wrong-target helper replacement, parent deletion or malformed metadata, true top-level epic main target, and unrelated epic denial. Run focused parallel-epic, epic-strategy, rebase maintenance, restart, and queue tests plus make test. Acceptance criteria: nested epic synchronization never mutates against main solely because parent lookup failed; EXOCOMP-245-style repairs converge on the authoritative parent target; ambiguous hierarchy remains retryable and visible without stranding Ready rows.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

