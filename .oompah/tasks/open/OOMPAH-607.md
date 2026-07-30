---
id: OOMPAH-607
type: bug
status: Open
priority: 1
title: Canonicalize project aliases before terminal owner authorization
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-07-30T18:17:13.371379Z'
updated_at: '2026-07-30T18:18:06.415287Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

Triggered by: OOMPAH-605

Implementation scope

Fix terminal status requests made with the supported project-name alias (for example `oompah task set-status ... --project oompah`) so the server carries the canonical managed project ID into `_stage_terminal_transition` and owner authorization. Today `_get_tracker_for_issue_or_project` can resolve the tracker through the alias while returning the alias unchanged; `_project_by_id` then returns no project and a valid configured owner receives a misleading HTTP 403. Preserve fail-closed authorization for unknown projects and unauthorized actors. Relevant files include oompah/server.py project/tracker resolution, task CLI project handling, and terminal status interfaces.

Tests

Add regressions showing a configured owner can use an audit override through both project ID and project-name alias; an unauthorized actor and unknown alias still fail closed; ordinary staged terminal requests retain the canonical project ID; error messages do not leak configuration. Run focused server terminal-interface/override/CLI tests and make test.

Acceptance criteria

Project aliases accepted by normal task CLI operations behave identically for terminal owner authorization, no valid owner sees a false 403 solely because an alias was used, and authorization is not weakened.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-30 18:18
---
Owner-approved liveness follow-up discovered during OOMPAH-605 recovery. Let the oompah server claim and implement this task; direct operator work is not needed while scheduler capacity is healthy.
---
<!-- COMMENTS:END -->
