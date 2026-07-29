---
id: OOMPAH-549
type: feature
status: Backlog
priority: 0
title: Expose finish-order lifecycle in UI, prompts, and operator documentation
parent: OOMPAH-545
children: []
blocked_by: []
labels:
- human-only
assignee: null
created_at: '2026-07-29T16:23:11.842687Z'
updated_at: '2026-07-29T16:23:56.761276Z'
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
<!-- COMMENTS:END -->
