---
id: OOMPAH-549
type: feature
status: Merged
priority: 0
title: Expose finish-order lifecycle in UI, prompts, and operator documentation
parent: OOMPAH-545
children: []
blocked_by:
- OOMPAH-546
- OOMPAH-547
- OOMPAH-548
labels:
- human-only
assignee: null
created_at: '2026-07-29T16:23:11.842687Z'
updated_at: '2026-07-29T18:29:16.785798Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

Update task/epic workflow documentation, bootstrap/AGENTS command references, prompts, dashboard terminology, and API descriptions so blocked_by is presented as Must finish after and start_blocked_by as Cannot start until. Document Ready to Integrate, task submission, cycle recovery, and the distinction between agent completion and task completion. Ensure the UI shows exact dependency and integration wait reasons without normal-operation alerts.

Tests must cover generated bootstrap instructions, prompt contracts, dashboard rendering, OpenAPI descriptions, and status-label catalogs.

Acceptance criteria: agents and operators receive unambiguous instructions, existing command documentation is updated, actionable blocked reasons are visible, and focused tests plus make test pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-29 16:23
---
Claimed by the interactive Codex session for the owner-requested parallel-epic execution implementation. Keep human-only; do not dispatch another worker. Work will be completed, tested, pushed, and handed off through the parent epic.
---
author: oompah
created: 2026-07-29 17:57
---
Implementation is complete on epic-OOMPAH-545. Full project gate passed: 13,213 tests passed, 7 skipped. Final rebase, merge, and deployment are in progress; this task remains human-owned and must not be dispatched.
---
author: oompah
created: 2026-07-29 18:15
---
The parent epic OOMPAH-545 merged from epic-OOMPAH-545, but this task was Backlog with work branch unset. Its work is not proven to be in the merged epic. Inspect the task's agent history and remote branches, recover any missing commits through a new recovery epic or approved follow-up PR, then move this task to Done only after the recovered work is verified on the target branch.
---
author: oompah
created: 2026-07-29 18:17
---
The parent epic OOMPAH-545 merged from epic-OOMPAH-545, but this task was Needs Human with work branch unset. Its work is not proven to be in the merged epic. Inspect the task's agent history and remote branches, recover any missing commits through a new recovery epic or approved follow-up PR, then move this task to Done only after the recovered work is verified on the target branch.
---
author: oompah
created: 2026-07-29 18:27
---
Implemented in PR #579 and merged to main at 31f8938b8f669a316a830690aaedcc1e0d3834bf. Full GitHub CI passed on Python 3.11, 3.12, and 3.13; focused post-rebase compatibility tests passed.
---
<!-- COMMENTS:END -->
