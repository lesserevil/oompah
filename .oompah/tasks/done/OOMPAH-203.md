---
id: OOMPAH-203
type: bug
status: Done
priority: 1
title: Prevent auto-update restarts after native tracker writes
parent: null
children: []
blocked_by: []
labels: []
assignee: null
created_at: '2026-07-13T19:58:10.079940Z'
updated_at: '2026-07-13T20:02:35.060684Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

Dashboard drag/drop writes native task state and pushes a .oompah/tasks commit. The service auto-update check currently treats that self-authored tracker-only commit as a code update, restarts via os.execv while the PATCH request is active, and the dashboard reports Update failed: network error.

Fix the auto-update decision so tracker-only commits do not restart the service, while commits that change service/runtime code still do. Include regression tests for both paths.

Acceptance criteria
- A tracker-only commit ahead of the running checkout does not request a restart.
- A commit that changes a runtime-relevant file does request a restart when idle.
- Drag/drop PATCH requests are not disconnected by an auto-update caused by their own tracker write.
- make test passes.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-13 20:00
---
Implemented and pushed auto-update filtering for tracker-only commits. Added regression coverage for tracker-only and runtime-code update paths; make test passed.
---
author: oompah
created: 2026-07-13 20:02
---
Implemented auto-update filtering for tracker-only .oompah/tasks commits. Tracker writes no longer restart the service and interrupt dashboard PATCH requests; non-tracker code updates still restart. Added two regressions. Verification: make test passed.
---
<!-- COMMENTS:END -->
