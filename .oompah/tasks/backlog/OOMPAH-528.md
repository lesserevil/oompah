---
id: OOMPAH-528
type: epic
status: Backlog
priority: 2
title: Pre-dispatch duplicate screening for Open tasks
parent: null
children:
- OOMPAH-529
- OOMPAH-530
- OOMPAH-531
blocked_by: []
labels:
- needs:feature
assignee: null
created_at: '2026-07-28T21:18:12.111324Z'
updated_at: '2026-07-28T21:19:12.290998Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

Implement model-backed duplicate screening as a qualification stage that can prepare Open tasks before an implementation agent claims them.

Current behavior:
- The inexpensive similarity filter already scans non-terminal candidates before dispatch.
- The model-backed duplicate_detector is a normal focus run: it moves a task to In Progress and records focus-complete:duplicate_detector after handoff.
- That label is not tied to the task revision, so a material edit can leave stale screening evidence.

Target behavior:
- Open tasks without a current duplicate-screening result may use otherwise-available agent capacity for a model-backed preflight run.
- A preflight run uses a separate atomic claim and does not represent implementation work; the task remains Open and exposes screening state separately.
- A real implementation agent cannot claim the task while screening is running or while the result is missing/stale.
- A no-duplicate verdict persists revision-aware evidence and returns the task to implementation eligibility.
- A supported duplicate verdict moves the task to Duplicate Candidate and posts evidence linking the match.
- Screening compares only against non-terminal tasks.
- Task edits or detector-version changes invalidate old evidence automatically.
- Preflight work is capacity-capped so it cannot monopolize all configured agents.

Non-goals:
- Do not replace the existing inexpensive similarity filter.
- Do not change terminal-state definitions or include terminal tasks in duplicate comparisons.
- Do not treat a heuristic similarity miss as equivalent to a model-backed pass.

Acceptance criteria:
1. The complete child-task dependency graph is implemented and covered by tests.
2. Open tasks visibly progress through unchecked, running, checked, or stale duplicate-screening states without entering In Progress for screening alone.
3. Claims prevent preflight and implementation agents from running concurrently on the same task.
4. Screening evidence is portable across supported trackers and invalidates after relevant task changes.
5. Capacity behavior uses only allowed slots and preserves an implementation lane.
6. make test passes, documentation describes configuration and operator-visible behavior, and all work is committed and pushed on the epic branch.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

